#!/usr/bin/env python

import sys
import requests
import os.path
from termcolor import colored
import argparse
import xml.etree.ElementTree
import time
from subprocess import Popen
import urllib3
from subprocess import Popen, PIPE
from pprint import pprint
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEBUG_NAME_LEN = 20

# Newark
mpd_base = 'https://newark-tc-clients.winkcdn.com/public/dash/{}_cvp.mpd'
ns = {'mpd' : 'urn:mpeg:dash:schema:mpd:2011'}
chunk_base = 'https://newark-tc-clients.winkcdn.com/public/dash/{}_cvp-{}.m4v'


def _debug(name, msg):
    sys.stdout.write("[{}] [{}] {}\n".format(colored('debg', 'blue'), name, msg)) 
    sys.stdout.flush()
def _error(name, msg):
    sys.stderr.write("[{}] [{}] {}\n".format(colored('erro', 'red'), name, msg))
    sys.exit(1)
def _warn(name, msg):
    sys.stderr.write("[{}] [{}] {}\n".format(colored('warn', 'yellow'), name, msg))
    sys.stdout.flush()
def _info(name, msg):
    sys.stdout.write("[{}] [{}] {}\n".format(colored('info', 'green'), name, msg)) 
    sys.stdout.flush()

class Chunk(object):
    def __init__(self, start, duration):
        self.start = start
        self.duration = duration
        self.num = -1

    def __eq__(self, other):
        if not isinstance(other, Chunk):
            return False
        else:
            return self.start == other.start and self.duration == other.duration

    def __str__(self):
        return "chunk#{}(s={},d={})".format(self.num, self.start, self.duration)

    def __repr__(self):
        return self.__str__()

class Stream(object):
    def __init__(self, args):
        self.sid = args.sid
        self.name = args.name
        self.debug_name = self.name[:DEBUG_NAME_LEN].ljust(DEBUG_NAME_LEN)
        self.duration = args.duration
        self.root = args.root
        self.verbose = args.verbose
        self.subdir = os.path.join(self.root, self.name)
        self.prepare_subdirectory()

    def debug(self, msg):
        if self.verbose:
            _debug(self.debug_name, msg)
    def info(self, msg):
        _info(self.debug_name, msg)
    def warn(self, msg):
        _warn(self.debug_name, msg)
    def error(self, msg):
        _error(self.debug_name, msg)

    def prepare_subdirectory(self):
        if not os.path.exists(self.subdir):
            self.info('Creating subdirectory {}'.format(self.subdir))
            os.makedirs(self.subdir)

class ParkStream(Stream):
    CAMERAS = {
        'left'   : '40.132.190.147',
        'center' : '40.132.190.148',
        'right'  : '40.132.190.149',
    }
    def __init__(self, args):
        super().__init__(args)

        start = time.strftime("%m%d%Y-%H%M")
        self.filename = '{}+{}'.format(start, self.duration)
        self.outfile = os.path.join(self.subdir, self.filename + '.mp4')

        if not self.sid in ParkStream.CAMERAS:
            self.ip = self.sid
        else:
            self.ip = ParkStream.CAMERAS[self.sid]
            #super().error("Unknown SID for Bryant Park video stream: {}".format(self.sid))

    def follow(self):
        self.info("starting stream...")
        ffmpeg = Popen("ffmpeg -i http://{}/axis-cgi/mjpg/video.cgi -map 0:v:0 -loglevel {} {}".format(
            self.ip,
            'info' if self.verbose else 'error',
            self.outfile
        ), shell=True, stdin=PIPE)

        duration_sec = self.duration * 60
        self.info("waiting...")
        time.sleep(duration_sec)
        self.info("done")

        ffmpeg.communicate('q'.encode('utf-8'))
        ffmpeg.wait()
        

class M3U8Stream(Stream):

    def __init__(self, args):
        super().__init__(args)
        self.url = self.sid
        start = time.strftime("%m%d%Y-%H%M")
        self.filename = '{}+{}'.format(start, self.duration)
        self.outfile = os.path.join(self.subdir, self.filename + '.mpeg')
        self.chunk_queue = []
        super().prepare_subdirectory()

    def follow(self):
        elapsed = 0
        num_got = 0
        wait_time = 1
        self.done = []
        missing_chunks = []
        while elapsed < self.duration * 60:
            if self.chunk_queue:
                chunk = self.chunk_queue.pop(0)
                chunk_len, chunk_url = chunk
                got = self.get(chunk_url)
                if not got:
                    missing_chunks.append(chunk_url)
                else:
                    num_got += 1
                    self.done.append(chunk)
                    elapsed += chunk_len
                    wait_time = chunk_len
            else:
                time.sleep(wait_time)
                self.get_manifest()
        self.info("Finished downloading {} chunks, totaling {} minutes of video.".format(num_got, int(elapsed / 60.0)))
        if len(missing_chunks) > 0:
            self.warn("Failed to get the following chunks: {}".format(missing_chunks))

    def get_manifest(self):
        new_chunks = 0
        r = requests.get(self.url, verify=False)
        if r.status_code >= 200 and r.status_code < 300:
            manifest = r.text
            if not 'EXTM3U' in manifest:
                sys.exit("ERROR: got M3U8 Manifest with unsupported extension!")
            manifest = manifest.split("\n")
            i = 0
            while i < len(manifest):
                l = manifest[i].strip()
                if 'EXTINF:' in l:
                    chunk_len = float(l.split(":")[1].replace(",",""))
                else:
                    i+=1
                    continue
                chunk_url = manifest[i+1]
                i+=2
                chunk = (chunk_len, chunk_url)
                if not chunk in self.chunk_queue and not chunk in self.done[-10:]:
                    self.chunk_queue.append(chunk)
                    new_chunks += 1
        self.info("Found {} new chunks".format(new_chunks))

    def get(self, chunk):
        self.debug('GET {}'.format(chunk))
        r = requests.get(chunk, verify=False)
        if r.status_code >= 200 and r.status_code < 300:
            with open(self.outfile, 'ab') as f:
                f.write(r.content)
            return True
        else:
            self.warn('Failed to download {}. Server returned {}'.format(url, r.status_code))
            return False


class NYCDOTStream(Stream):
    URL = 'http://207.251.86.238/cctv{}.jpg'

    def __init__(self, args):
        super().__init__(args)

        if int(args.sid) > 999:
            super().error("Bad SID format for NYCDOT traffic stream: {}".format(self.sid))
        self.url = NYCDOTStream.URL.format(self.sid)

        start = time.strftime("%m%d%Y-%H%M")
        self.subdir = os.path.join(self.subdir, '{}+{}'.format(start, self.duration))
        super().prepare_subdirectory()

    def follow(self):

        elapsed = 0
        duration_sec = self.duration * 60

        while elapsed < duration_sec:
            self.get(elapsed)
            time.sleep(1)
            elapsed += 1
            
    def get(self, frame):
        outfile = os.path.join(self.subdir, '{:04d}.jpg'.format(frame))
        self.debug('GET {}'.format(self.url))
        r = requests.get(self.url, verify=False)
        if r.status_code >= 200 and r.status_code < 300:
            with open(outfile, 'ab') as f:
                f.write(r.content)
            return True
        else:
            self.warn('Failed to download {}. Server returned {}'.format(url, r.status_code))
            return False

class NewarkStream(Stream):
    def __init__(self, args):
        super().__init__(args)

        self.init_file = None
        self.chunk_queue = []
        self.done = []
        self.num_chunks = 0

        mpd = self.get_manifest()

        start = time.strftime("%m%d%Y-%H%M")
        self.filename = '{}+{}'.format(start, self.duration)
        self.outfile = os.path.join(self.subdir, self.filename + '.m4v')
        self.mp4file = os.path.join(self.subdir, self.filename + '.mp4')
        self.mpdfile = os.path.join(self.subdir, self.filename + '.mpd')
        
        with open(self.mpdfile, 'wb') as f:
            f.write(xml.etree.ElementTree.tostring(mpd))



    def follow(self):

        if not self.get(Chunk('init', 0)):
            self.error('Cannot progress without init.')

        missing_chunks = []
        num_got = 0

        total_recorded = 0
        duration_ms = self.duration * 1000 * 60
        wait_time_ms = self.chunk_queue[0].duration

        while total_recorded < duration_ms:
            if self.chunk_queue:
                chunk = self.chunk_queue.pop(0)
                got = self.get(chunk)
                if not got:
                    missing_chunks.append(chunk)
                else:
                    self.done.append(chunk)
                    total_recorded += chunk.duration
                    wait_time_ms = chunk.duration
                    num_got += 1
            else:
                time.sleep(wait_time_ms / 1000.0)
                self.get_manifest()
 
        self.info('Finished downloading {} chunks, totaling {} minutes of video.'.format(num_got, int(total_recorded / 1000.0)))
        if len(missing_chunks) > 0:
            self.warn('Failed to get the following chunks: {}'.format(missing_chunks))

        self.info('Creating MP4...')
        Popen("MP4Box -add {} -new {}".format(self.outfile, self.mp4file), shell=True)


    def get(self, chunk):
        url = chunk_base.format(self.sid, chunk.start)
        self.debug('GET {}'.format(url))
        r = requests.get(url, verify=False)
        if r.status_code >= 200 and r.status_code < 300:
            with open(self.outfile, 'ab') as f:
                f.write(r.content)
            return True
        else:
            self.warn('Failed to download {}. Server returned {}'.format(url, r.status_code))
            return False

    def get_manifest(self):
        mpd_url = mpd_base.format(self.sid)
        r = requests.get(mpd_url, verify=False)
        if r.status_code < 200 or r.status_code >= 300:
            self.error('Cannot GET MPD. Server returned {}'.format(r.status_code))
            return None
        xml.etree.ElementTree.register_namespace('', ns['mpd'])
        mpd = xml.etree.ElementTree.fromstring(r.text)

        periods = mpd.findall('mpd:Period', ns)
        assert(len(periods) == 1)
        period = periods[0]

        ad_sets = period.findall('mpd:AdaptationSet', ns)
        assert(len(ad_sets) == 1)
        ad_set = ad_sets[0]

        reps = ad_set.findall('mpd:Representation', ns)
        assert(len(reps) == 1)
        rep = reps[0]
        frame_rate = rep.attrib.get('frameRate', '-1')
        bandwidth = rep.attrib.get('bandwidth', '-1')
        mime = rep.attrib.get('mimeType', '')

        stmps = rep.findall('mpd:SegmentTemplate', ns)
        assert(len(stmps) == 1)
        segment_template = stmps[0]
        init_file = segment_template.attrib.get('initialization', None)
        if not init_file:
            self.error('No initialization file found!')
        timescale = segment_template.attrib.get('timescale', 0)

        segment_timelines = segment_template.findall('mpd:SegmentTimeline', ns)
        assert(len(segment_timelines) == 1)
        segment_timeline = segment_timelines[0]

        new_chunks = []
        recent = self.done[-10:]
        for segment in segment_timeline.findall('mpd:S', ns):
            segment_start = int( segment.attrib.get('t', '-1') )
            if segment_start == -1:
                self.warn('Segment missing start time')
                continue
            segment_duration = int( segment.attrib.get('d', '0') )
            if segment_duration == 0:
                self.warn('Initial segment missing duration')
                continue
            chunk = Chunk(segment_start, segment_duration)
            if not chunk in self.chunk_queue and not chunk in recent:
                self.num_chunks += 1
                chunk.num = self.num_chunks
                self.chunk_queue.append(chunk)
                new_chunks.append(chunk)

        if new_chunks:
            self.info('{} new chunks: {}'.format(len(new_chunks), new_chunks))

        if not self.done:
            self.info('Got manifest: frame_rate={} band={} mime={} timescale={} new={}'.format(
                frame_rate, bandwidth, mime, timescale, new_chunks
            ))

        return mpd

def run(args):
    loc = args.location.lower()
    if 'newark' in loc:
        s = NewarkStream(args)
    elif 'nyc' in loc:
        s = NYCDOTStream(args)
    elif 'park' in loc:
        s = ParkStream(args)
    elif 'm3u8' in loc:
        s = M3U8Stream(args)
    else:
        __error('parse', 'unknown location {}'.format(loc))
    
    s.follow()

import textwrap
def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("sid", type=str, help="Stream ID")
    parser.add_argument("--name", type=str, help="Nickname for this stream", required=True)
    parser.add_argument("--location", type=str, help=textwrap.dedent("""Currently supported:
    > 'Newark'
    sid format: WF00-XXXX-XXXX-XXXX-XXXX
    > 'NYC' (Traffic Cameras)
    sid format: 999
    > 'Park' (NYC's Bryant Park)
    sid format: left, center, or right
    > 'm3u8' (Any M3U8 stream)
    sid format: [url]
    """), required=True)
    parser.add_argument("--duration", type=int, help="Length of time to record in minutes", required=True)
    parser.add_argument('--root', type=str, help="Root directory", required=True)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    run(args)

if __name__ == '__main__':
    main()
