#!/usr/bin/env python3

from robot import Robot
from gevent import sleep

tetra = Robot('sandbox')

for channel in ('Q', 'W', 'E', 'A', ):
	tetra.set_position(0, 1, channel, 0, 0, 50); sleep(1)
	tetra.set_position (0, 1, channel, 0, 0, 224); sleep(1)
