
import sys
import struct
from gevent import sleep, spawn, Timeout
import copy
import yaml
from program import RobotProgram
from connection import RobotConnection

"""
   Robot interface
"""

class Robot(object):

	CHANNELS = ['Q', 'W', 'E', 'A', 'S', 'D', 'R', 'T', 'Y', 'F', 'G', 'H']

	def __init__ (self, prefix=''):

		self.read_lock = False
		self.send_commands_flag = True
		self.ticks_per_step = 6
		self.prefix = prefix
		# Keeps (active, is_servo, ranges, is_inverted) for every channel num
		self._channels_setup = [(1, 1, (0, 255), 0) for i in Robot.CHANNELS]
		# Queue of channels + one special for control, misc and other commands
		self._channel_commands = [[] for i in range(len(Robot.CHANNELS)+1)]
		self._positions = []
		self._sensors = []
		self.program = RobotProgram(self.prefix, Robot.CHANNELS)
		self._conn = RobotConnection()
		self._running = True
		self._process_commands = spawn(self._process_commands_loop)
		sleep(0) # yields

	def load_config (self, suffix = ''):
		custom = {}
		try:
			with open('%s%s.conf' % (self.prefix, suffix), 'r') as f:
				config = yaml.load(f, Loader=yaml.FullLoader)
				self.send_commands_flag = config['send_commands_flag']
				self.ticks_per_step = config['ticks_per_step']
				self._channels_setup = config['channels_setup']
				custom = config.get('custom') or {}
		except IOError as e:
			pass
		return custom
			
	def save_config (self, suffix = '', custom = {}):
		with open('%s%s.conf' % (self.prefix, suffix), 'w') as f:
			config = {
				'send_commands_flag': self.send_commands_flag,
				'ticks_per_step': self.ticks_per_step,
				'channels_setup': self._channels_setup,
				'custom': custom,
			}
			f.write(yaml.dump(config))

	def load (self, program):
		self.program.load(program)                

	def save (self, program):
		self.program.save(program)                
		
	def run (self, program):
		"""
			Run program 0 means stop, otherwise, starts the execution of the program number given (1-255)
		"""
		self._request(-1, RobotProgram.CONTROL_COMMAND, program)
	
	def stop (self):
		self.run(0)

	def set_code (self, program, code=''):
		self.program.set_program_source_code(program, code)
		
	def get_code (self, program):
		return self.program.get_program_source_code(program)

	def generate_code (self, program, seed = None, steps = 12, types_subset = None):
		self.program.generate_code(program, channels_setup = self._channels_setup, seed = seed, steps = steps, types_subset = types_subset)

	def upload_programs (self, upload_mode = 0):
		"""
			Upload all the programs to the robot
			upload_mode selects if programs will be stored in RAM (0), or in EEPROM (1) 
		"""
		raw, length = self.program.get_all_raw_code(self.ticks_per_step, self._channels_setup)
		# If upload mode is EEPROM, change the first byte from 255 to 253
		if upload_mode:
			raw[0] = 253
		print("About to upload", length,"bytes", "to EEPROM" if upload_mode else "to RAM")
		print(raw)
		# Saves the raw programs in an accesible location
		#with open('/home/drone/public_html/robot/programs.json', 'w') as f:
		#	f.write(str([255] + raw))
		self._request(-1, RobotProgram.MISC_COMMAND, raw)
	
	def set_position (self, program, step, channel, speed, mode, pos):
		"""
			Set the position for a channel
		"""
		if not isinstance(channel, int):
			channel = Robot.CHANNELS.index(channel.upper())

		channels_in_use = [i for i, v in enumerate(self._channels_setup) if v[0] ]
		channels_lut = {k: channels_in_use.index(k) for k, _ in enumerate(Robot.CHANNELS) if k in channels_in_use}
		if channel in channels_lut:
			cmd = self.program.pack_command(channel, speed, mode)
			cmd_alt = self.program.pack_command(channels_lut[channel] if channel in channels_lut else channel, speed, mode)
			self._request(channel, cmd_alt, pos)
			self.program.set_command(program, step, cmd, pos)

	def setup_channel (self, channel, active = None, is_servo = None, min_range = None, max_range = None, inverted = None):
		"""
		   Configure a channel as being active or disabled, and also defines the type of pwm for 
		   the channel (servo or pure pwm)
		"""
		if not isinstance(channel, int):
			channel = Robot.CHANNELS.index(channel.upper())
		
		self._channels_setup[channel] = (
			active if active is not None else self._channels_setup[channel][0],
			is_servo if is_servo is not None else self._channels_setup[channel][1],
			(
				min_range if min_range is not None else self._channels_setup[channel][2][0],
				max_range if max_range is not None else self._channels_setup[channel][2][1]
			),
			inverted if inverted is not None else self._channels_setup[channel][3],
		)
		#print("Channels setup", self._channels_setup)

	def get_positions (self):
		self._request(-1, RobotProgram.MISC_COMMAND, 0)
		while self._positions == []:
			sleep(0.1)
		if self._positions is None:
			print("Error reading positions")
		return self._positions

	def get_sensors (self):
		self._request(-1, RobotProgram.MISC_COMMAND, 1)
		while self._sensors == []:
			sleep(0.1)
		if self._sensors is None:
			print("Error reading sensors")
		return self._sensors

	def _request (self, channel, cmd, params):
		self._channel_commands[channel].append((cmd, params))

	def _process_commands_loop (self):
		"""
			Sends every last command given to a channel and drops the previous ones
		"""
		while self._running:
			if self._conn._read_lock:
				sleep(0.01)
				continue
			for i, commands in enumerate(self._channel_commands):
				if commands:
					cmd, params = commands[-1]
					#if self._channel_commands[i][:-1]:
					#    print("Skipping ", self._channel_commands[i][:-1])
					self._channel_commands[i] = []    # Deletes all pending commands from the channel
					# Send commands optionally for legs and trunk, but allow control commands always
					if self.send_commands_flag or i >= len(self.CHANNELS):
						if i >= len(self.CHANNELS) or i == -1:        # Handles control commands and misc commands
							if cmd in (RobotProgram.CONTROL_COMMAND, RobotProgram.OTHER_COMMAND):
								self._conn.send(cmd, params)
							elif cmd == RobotProgram.MISC_COMMAND:
								if isinstance(params, (tuple, list)):
									subcmd = params[0]
								else:
									subcmd = params
								if subcmd == 0:           # READ POSITIONS	
									self._conn.send(cmd, subcmd)
									self._positions = self._conn.recv()
								elif subcmd == 1:         # READ SENSORS
									self._conn.send(cmd, subcmd)
									#print('Sent', cmd, subcmd)
									self._sensors = self._conn.recv()
								elif subcmd in (253, 254, 255):       # UPLOAD CONFIGURATION
									# Writes all the programs and configuration at once
									#print("Writing programs to the robot")
									#print(pos)
									self._conn.send(cmd, params, flush=1)
									print("Done")
						else:
							print("Send", cmd, params)
							#print("Channel",cmd & 15, "Speed", (cmd >> 4))
							self._conn.send(cmd, params)
					sleep(0.01)

			sleep(0.01)
