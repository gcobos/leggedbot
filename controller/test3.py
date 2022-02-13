#!/usr/bin/env python3

from robot import Robot
from gevent import sleep

tetra = Robot('sandbox')
tetra.ticks_per_step = 6
#tetra.setup_channel('E', active = False)
#tetra.setup_channel('S', active = False)
#tetra.setup_channel('D', active = False)
print("Move leg...")
for channel in range(1, 2): #9):
	tetra.set_position(0, 1, channel, 0, 0, 0); sleep(1)
	tetra.set_position (0, 1, channel, 0, 0, 255); sleep(1)
