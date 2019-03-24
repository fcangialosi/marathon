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
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

mpd_base = 'https://newark-tc-clients.winkcdn.com/public/dash/{}_cvp.mpd'
ns = {'mpd' : 'urn:mpeg:dash:schema:mpd:2011'}

chunk_base = 'https://newark-tc-clients.winkcdn.com/public/dash/{}_cvp-{}.m4v'

def debug(msg):
    sys.stdout.write("[{}] {}\n".format(colored('debg', 'blue'), msg)) 
def error(msg):
    sys.stderr.write("[{}] {}\n".format(colored('erro', 'red'), msg))
    sys.exit(1)
def warn(msg):
    sys.stderr.write("[{}] {}\n".format(colored('warn', 'yellow'), msg))
def info(msg):
    sys.stdout.write("[{}] {}\n".format(colored('info', 'green'), msg)) 

class Stream(object):
    def __init__(self, args):
        self.sid = args.sid
        self.name = args.name
        self.duration = args.duration
        self.root = args.root
        self.verbose = args.verbose
        self.subdir = os.path.join(self.root, self.name)

        self.init_file = None
        self.chunk_queue = []

        self.prepare_subdirectory()
        self.get_manifest()

    def follow(self):

        if not self.get('init'):
            error('Cannot progress without init.')
 
        num_got = 0
        for chunk in self.chunk_queue[:4]:
            if self.get(chunk):
                num_got += 1

        self.chunk_queue = self.chunk_queue[4:]

        missing_chunks = []
        for chunk in self.chunk_queue:
            time.sleep(self.chunk_duration / 1000.0)
            tries = 0
            got = False
            while not got:
                tries += 1
                got = self.get(chunk)
                if not got:
                    if tries >= 3:
                        warn('Failed to get chunk 3 times, skipping...')
                        missing_chunks.append(chunk)
                        break
                    time.sleep(1)
                    info('Retrying...')
            if got:
                num_got += 1

        info('Finished downloading {} {}-ms chunks.'.format(num_got, self.chunk_duration))
        if len(missing_chunks) > 0:
            info('Failed to get the following chunks: {}'.format(missing_chunks))

        info('Creating MP4...')
        Popen("MP4Box -add {} -new {}".format(self.outfile, self.mp4file), shell=True)


    def prepare_subdirectory(self):
        if not os.path.exists(self.subdir):
            info('Creating subdirectory {}'.format(self.subdir))
            os.makedirs(self.subdir)

    def get(self, chunk):
        url = chunk_base.format(self.sid, chunk)
        if self.verbose:
            debug('GET {}'.format(url))
        r = requests.get(url, verify=False)
        if r.status_code >= 200 and r.status_code < 300:
            with open(self.outfile, 'ab') as f:
                f.write(r.content)
            return True
        else:
            warn('Failed to download {}. Server returned {}'.format(url, r.status_code))
            return False

    def get_manifest(self):
        mpd_url = mpd_base.format(self.sid)
        info('Requesting initial manifest...')
        r = requests.get(mpd_url, verify=False)
        if r.status_code < 200 or r.status_code >= 300:
            warn('Cannot GET MPD. Server returned {}'.format(r.status))
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
            error('No initialization file found!')
        timescale = segment_template.attrib.get('timescale', 0)

        segment_timelines = segment_template.findall('mpd:SegmentTimeline', ns)
        assert(len(segment_timelines) == 1)
        segment_timeline = segment_timelines[0]

        segments = segment_timeline.findall('mpd:S', ns)
        segment = segments[0]
        segment_duration = int( segment.attrib.get('d', '0') )
        if segment_duration == 0:
            error('Initial segment missing duration')
        first_segment = int( segment.attrib.get('t', '-1') )
        if first_segment == -1:
            warn('Segment missing start time')
        self.chunk_duration = segment_duration

        info('Found stream. frame_rate={} band={} mime={} timescale={} start={} chunk_duration={}'.format(
            frame_rate, bandwidth, mime, timescale, first_segment, segment_duration
        ))
        
        duration_ms = self.duration * 1000
        for i in range(0, duration_ms, segment_duration):
            self.chunk_queue.append(first_segment + i)

        self.filename = '{}-{}'.format(first_segment, self.duration)
        self.outfile = os.path.join(self.subdir, self.filename + '.m4v')
        self.mp4file = os.path.join(self.subdir, self.filename + '.mp4')
        self.mpdfile = os.path.join(self.subdir, self.filename + '.mpd')

        with open(self.mpdfile, 'wb') as f:
            f.write(xml.etree.ElementTree.tostring(mpd))

def run(args):
    s = Stream(args)
    
    s.follow()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sid", type=str, help="Stream ID")
    parser.add_argument("--name", type=str, help="Nickname for this stream", required=True)
    parser.add_argument("--duration", type=int, help="Length of time to record in minutes", required=True)
    parser.add_argument('--root', type=str, help="Root directory", required=True)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    run(args)

if __name__ == '__main__':
    main()
