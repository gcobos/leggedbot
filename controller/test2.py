#!/usr/bin/env python

from robot import Robot
from gevent import sleep

tetra = Robot('tetra')
sleep(0)

tetra.load_config()

# Load programs
for i in range(9):
    tetra.load(i+1)
tetra.upload_programs()
sleep(3)

print "Searching for light..."
threshold = 2
try:
    while True:
        eyes = tetra.get_sensors()
        sleep(0.3)
        diff = eyes[0] - eyes[1]*0.9
        print diff
        #continue
        if diff > threshold:
            print "Move right"
            tetra.run(6)
            sleep(3)
        elif diff < -threshold:
            print "Move left"
            tetra.run(4)
            sleep(3)
        elif abs(diff) < threshold*0.3:
            tetra.run(2)
            sleep(2)
        else:
            tetra.run(5)
            sleep(3)
        
except:
    print "Stopping..."
    tetra.run(5)
    sleep(2)
