# Marathon

This repository provides a simple script to download live streams

It currently supports 4 live camera systems:
1. Newark's [Citizen Virtual Patrol](https://cvp.newarkpublicsafety.org/) (DASH Video Server)
2. NYC DOT's Traffic Cameras (MJPEG, i.e. frames encoded as individual jpegs)
3. Bryant Park (NYC) Camera (MJPEG, distributed via CGI)
4. Any M3U8 video stream, e.g. those found on [Skyline Webcams](https://www.skylinewebcams.com/) (MPEG)

Run `python marathon.py --help` for a list of available parameters. It also lists the SID format 
for each camera system. As far as I know, there does not exist a publicly available list of stream
IDs and thus they must be looked up manually. They can be found easily by opening up a stream of interest
and checking the corresponding request in the network tab of your browser's dev tools.


## API Details

Below I've included some notes on how each system/API works and how Marathon uses it to download the stream.


### Newark's Citizen Virtual Patrol API

* Each camera has a unique identifier which can be found by monitoring network requests when viewing the feed from that camera
* Each live stream is made up of 5-second chunks of 640x360 8fps videos. 
* The MPD (manifest) file for each camera ID provides a list of the most recent four 5-second chunks at the time of the request as well as an initial chunk that specifies the stream metadata.
* However, the chunks are named according to the beginning timestamp of each chunk (see `chunk_base` at the top of `marathon.py`), 
so it's easy to calculate any number of subsequent chunk names once you've seen the first one. 
* The chunks are m4v files without any DRM copy protection and thus can be easily concatenated and converted to mp4

The script operates as follows given a camera ID and duration of time to download:
1. Download the manifest for the camera and find the first chunk time
2. Download the init m4v which provides all of the stream meta data
3. Download the first chunk and append it to the initial m4v
4. Repeat for the remaining chunks, calculating the next chunk name by just adding 5000 (ms) to the timestamp
5. USe MP4Box to convert the concatenated m4v files into a single mp4 file. 

This script can easily be run using cron to download the stream at specific times, and can be run in parallel to download many streams at once. 

### NYC DOT Traffic Cameras

* Streams are provided as a single JPEG per cctv that is updated roughly every 1-2 seconds
* Issuing a GET request to http://IP/cctv{ID}.jpg grabs the latest frame
* Stream created by polling this URL for each cctv and then using ffmpeg to stitch frames together

### Bryant Park Cameras

* There are three AXIS Q3709-PVE Network Cameras positioned next to each other to capture a continuous wide angle view of the park
* Each camera is streamed on it's own ip address: 40.132.190.14{7,8,9}
* Streams are MJPEG distributed via CGI (common gateway interface)
* No parameters are necessary in the request, it provides the highest resolution by default

### M3U8 Streams

* Each camera will have a unique url specific to the streaming site that can be queried to get a list of the most recent chunks, e.g. https://hddn01.skylinewebcams.com/live.m3u8?a=ID
* This URL can be found by viewing the webcam in Chrome and monitoring the network tab of the debug tools.  
* Sending a GET request to this URL returns a text file with a list of chunks and their length in seconds. 
* These chunks can be downloaded sequentially and simply appended together to form a single video file
* The extension is usually listed as ".ts" but these can be safely renamed to ".mpeg"

## Manager

The marathon script manages the download of a single video stream. The manager script is provided
as a utility to download a list of streams in parallel by internally calling marathon.

It expects a space-separated file in the local directory called cameras.txt where each line represents
a single stream and contains 3 columns:
{stream nickname} {location} {sid}

Manager will skip any lines beginning with #.

For example, to monitor camera #50 from the NYC DOT system and the center camera from bryant park:
```
stream1 nyc 50
stream2 park center
```

Manager takes a single command-line argument: the length of time to download the streams in minutes.
