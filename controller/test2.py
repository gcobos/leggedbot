#!/usr/bin/env python3

from robot import Robot
from gevent import sleep

tetra = Robot('tetra3')
sleep(0)

tetra.load_config()

# Load programs
for i in range(12):
    tetra.load(i+1)
tetra.upload_programs()
sleep(3)

GO_FORWARD = 2
TURN_LEFT = 4
STANDING = 5 
TURN_RIGHT = 6

print("Searching for light...")
threshold = 1
program = STANDING
try:
    while True:
        eyes = tetra.get_sensors()
        sleep(0.3)
        diff = eyes[0] - eyes[1]
        print(diff)

        if diff > threshold:
            print("Turn right")
            program = TURN_RIGHT
        elif diff < -threshold:
            print("Turn left")
            program = TURN_LEFT
        elif abs(diff) < threshold:
            print("Go forward")
            program = GO_FORWARD
        else:		# When abs(diff) == threshold
            print("Rest a bit")
            if program == STANDING:
                sleep(2)
                continue
            program = STANDING

        tetra.run(program)
        sleep(2)
except Exception as e:
    print("Stopping...", e)
    tetra.run(5)
    sleep(2)
