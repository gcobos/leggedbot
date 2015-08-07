leggedbot
========

Instructions, code and tests to build a legged robot


Abstract: 
Construction of an legged robot controller, using arduino.

Interface:
It uses up to 12 channels (pins 2-13), and pins 1 and 2 to control the movements using serial communication.

Serial protocol:

1) Number of leg (4 bits)
Chooses the pin to move an actuator

2) Speed or number of steps for the transition 0-15 (4 bits)
Define how many partitions there must be to reach the desired new position for every leg. For now, transitions
are linear only.

4) Position 0-255 (8 bits)
Second byte sets position to reach by the selected leg.


Special commands: 

There are two special commands, by specifying actuator (beyond 11). So there are a few values that are going to be special:

- 254 for program control: 254 + 0 = stop, 254 + 1 = run program #1, ...
- 255 for meta commands: 255 + 255 = upload, 255 + 0 = read actuator positions, 255 + 1 = read analogic sensors...

Remote controller:

Programs that would be good to have:

    idle, forward, backward, turn_left_30, turn_right_30, turn_left_60, turn_right_60, turn_left_90, turn_right_90


