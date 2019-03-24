Marathon
========

This repository provides a simple script to download live streams from a DASH video server.

At the moment it is specific to the API for Newark's [Citizen Virtual Patrol](https://cvp.newarkpublicsafety.org/):
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

### Example

The following command will download the next 60 seconds from the first camera in the CVP list (12th Ave & S 8th St):

```bash
python marathon.py WF05-AD81-B326-50EA-8110 --name 12th_s8th --duration 60 --root .
```
