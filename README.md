# Marathon

This repository provides a simple script to download live streams

It currently supports 3 live camera systems:
1. Newark's [Citizen Virtual Patrol](https://cvp.newarkpublicsafety.org/) (DASH Video Server)
2. NYC DOT's Traffic Cameras (MJPEG, i.e. frames encoded as individual jpegs)
3. Bryant Park (NYC) Camera (MJPEG, distributed via CGI)

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
