import sys
from time import sleep
from subprocess import Popen

cameras = []

with open('cameras.txt') as f:
    for l in f:
        name, loc, sid = l.strip().split(" ")
        if name[0] == '#':
            continue
        cameras.append((name, loc, sid))

duration = int(sys.argv[1])

procs= []
for (name,sid) in cameras:
    procs.append(
        Popen("python marathon.py {} --name {} --location {} --duration {} --root /streams".format(sid, name, loc, duration), shell=True)
    )
    sleep(0.5)

