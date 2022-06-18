#!/usr/bin/env python3

from robot import Robot
from gevent import sleep

tetra = Robot('tetra3')
tetra.ticks_per_step = 10
tetra.setup_channel('E', active = False)
tetra.setup_channel('S', active = False)
tetra.setup_channel('D', active = False)
for i in range(3):  # Load programs
    tetra.load(i+1)
tetra.upload_programs()
sleep(10)
tetra.run(5)
print("Move leg...")
tetra.set_position(0, 1, 0, 0, 0, 240); sleep(2)
tetra.set_position (0, 1, 0, 0, 0, 16); sleep(2)
print("Test walking...")
tetra.run(2); sleep(3)
print("Standing position...")
tetra.run(5); sleep(3)
print("Turn right...")
tetra.run(9); sleep(6)
print("Stop")
tetra.run(5); sleep(3)
print("Walk backwards...")
tetra.run(8); sleep(4)
print("Turn right again...")
tetra.run(9); sleep(6)
print("Standing position...")
tetra.run(5); sleep(3)
print("Walk again...")
tetra.run(2); sleep(3)
print("Standing position.")
tetra.run(5); sleep(3)
print("The end.")
