leggedbot
========

Construction of a legged robot controller, using arduino (16Mhz needed).

This repository contains the software and firmware to control up to 12 servo motors (channels) from the arduino nano or mini, in a way that its movement is reproducible and accurate. On top of that, it allows to write programs using a simple language so that it fits in the Arduino's EEPROM and RAM memory. In order to do that, this repository includes a controller with an graphical interface in gtk3, to write and test programs, while having the robot connected.

## Control ##
The robot can be controlled from Bluetooth, as far as it shows to the arduino as a serial port. Also, for ease of use, it can be also controlled from a wireless SNES remote gamepad (its protocol is similar to the one on a nunchuck).

## Protocol ##
Arduino digital pins from 2 to 13 can be used to drive servo motors. Each of those channels can be enabled or disabled, and also be configured to limit their movement range, and set as inverted or not if needed, so that commands to move them will always go from 0 to 255, without breaking the range limits. Each of the 12 channels has a name (letter), organized in a way that it reminds of a keyboard, so that servo positions in the robot make sense.

```CHANNELS = [
  'Q', 'W', 'E', 
  'A', 'S', 'D', 
  'R', 'T', 'Y', 
  'F', 'G', 'H'
]```

In order to move a channnel, for example, channel Q, we would write the command "Q255", and the servo will go to the 100% of the defined range. There is also the option to set the speed at which the servo should move (from 1 to 16). This can be specified in the command with "Q255s16". Internally, those commands will be packed to use only two bytes each.

All commands given in a same line in a program, will start at the same time. Each command has to be separated by a espace. A typical program will lok like this:

```
Q255s16 A0s16

W0 S255

Q0s16 A255s16

W255 S0

restart
```

## Language keywords ##

### CHANNEL MOVEMENT ###
Internally, a command to move a channel (servo), consists of two bytes, one for speed (bits 7:4) and the number of channel (bits 3:0), and the second byte is entirely to define the channels desired position (0-255).

_speed_ can go from 1 to 16, (or number of steps for the transition) define how many partitions there must be to reach the desired new position for every leg. For now, transitions are linear only.

_channel_ can go from 1 to 12, so even specifying the maximum speed and highest channel, the biggest value in the first byte would be 251. This means that there is room for adding new types of commands.

Inside a program, internally, a single byte 255 is used to delimit each line (that should be executed at the same time).

### MISC COMMANDS TYPE ###
There are several types of commands that can be used in a program, and others that cannot be included in programs. I call them **MISC_COMMANDS**:

- 255 to start a MISC command, followed by:
	* 0   = Get current position of each active channel (servo motor last known position)
	* 1   = Get all sensor values, which reads and returns all analog inputs from the Arduino
	* 253 = Upload configuration and programs from Serial connection to Arduino's EEPROM
	* 254 = Upload configuration and programs from Arduino's EEPROM to RAM
	* 255 = Upload configuration and programs from Serial connection to Arduino's RAM

### CONTROL COMMANDS TYPE ###
These commands control the execution in programs. It's as simple as program `0` means stop, other program number (1-255) means, run the program #. Additionally, `restart` can be used in a program to run itself again.

- 254 for program control, followed by:
	* 0 = **stop** execution
	* 1 = **run** program #1 (or **restart**, if I'm in program #1)
	* 2 = ...

### OTHER COMMNADS TYPE ###

- 253 for branching and delay commands
	* 253 + 1 + delay	= sleep for `delay` seconds (sleep N)
	* 253 + 2 + offset	= jump by `offset` (jump offset)
	* 253 + 3 + offset	= jump by `offset` if A0 > A1 (jleft offset)
	* 253 + 4 + offset	= jump by `offset` if A1 > A0 (jright offset)
	* 253 + 5 + offset	= jump by `offset` if random(100) >= 50 (jrand offset)


> **NOTE**: Commands starting by 252 are yet unused.

