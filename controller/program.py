
import re
from struct import pack, unpack
from programmer import Programmer

class RobotProgram(object):
	"""        
		- A program is a secuence of commands that is sent in blocks called frames. Every frame represents an
		amount of time.
		- In a frame, only one command is allowed to be sent to every actuator.
		- Time of every frame is the time that the slowest possible movement takes in a single actuator.
		- Control commands are allowed inside a program, so it's possible to jump to another program or loop
		into the same program forever.
	"""

	OTHER_COMMAND = 253
	CONTROL_COMMAND = 254
	MISC_COMMAND = 255
	
	def __init__ (self, prefix = '', channels = []):
		self.prefix = prefix or 'program'
		self._code = []             # Stores the binary code for every program
		self.all_channels = channels or []

	def get_command (self, program, step, channel):
		"""
			Gets a command inside a program, step and channel if any, else returns None
		"""
		if len(self._code) > program and len(self._code[program]) > step:
			if channel in self._code[program][step]:
				return self._code[program][step][channel]
			
		return None
		
	def set_command (self, program, step, cmd, pos, extra = None):
		"""
			Inserts or edits a single command for a program and step
		"""
		self._ensure_program(program)
		self._ensure_step(program, step)
		
		# Overwrite the channel with the new command
		channel, speed, mode = self.unpack_command(cmd)
		self._code[program][step][channel] = {'s': speed, 'm': mode, 'v': pos, 'e': extra}

	def set_comment (self, program, step, comment = ''):
		"""
			Inserts or edits a comment for a step in the program
		"""
		self._ensure_program(program)
		self._ensure_step(program, step)
		
		# Overwrite the channel with the new command
		self._code[program][step]['comment'] = comment
	
	def load (self, program):
		"""
			Returns the code of the program loaded
		"""
		with open(self.prefix+'_'+str(program)+".rc", 'r') as f:
			data=f.read()
		self.set_program_source_code(program, data)
		
	def save (self, program):
		"""
			Save a program given into the memory
		"""
		data = self.get_program_source_code(program)
		with open(self.prefix+'_'+str(program)+".rc", 'w') as f:
			f.write(data)

	def get_program_source_code (self, program):
		"""
			Returns a printable version of the code for a program number
		"""
		self._ensure_program(program)

		source_code = ''
		for step, channels in enumerate(self._code[program]):
			commands = []
			comment = ''
			for channel, command in channels.items():
				if channel == 'comment':
					comment = self.get_command(program, step, channel)
					continue
				command = self.get_command(program, step, channel)
				if command:
					commands.append(self.get_command_source_code(program, channel, command))
			if comment:
				comment = '\t\t# %s' % comment if commands else '# %s' % comment
			source_code += "%s%s\n" % (" ".join(commands), comment)
		return source_code

	def generate_code (self, program, channels_setup = None, seed = None, steps = None, types_subset = None, loop = True):
		while True:
			ap = Programmer(seed = seed, channels_setup = channels_setup, steps = steps+1, types_subset = types_subset)
			code = ap.get_raw_code()
			if code or seed:
				self._ensure_program(program)
				self._code[program] = code
				break
		if loop:
			self.set_command(program, steps, RobotProgram.CONTROL_COMMAND, program)
		else:
			self.set_command(program, steps, RobotProgram.CONTROL_COMMAND, 0)
					   
	def set_program_source_code (self, program, program_code=''):
		self._ensure_program(program)
		self._code[program] = []
		for i, line_raw in enumerate(program_code.split("\n")):
			if '#' in line_raw:
				line, comment = line_raw.split('#', 1)
				line = line.strip()
				comment = comment.strip()
			else:
				line = line_raw.strip()
				comment = ''
			if line or comment:
				step = i
				self._ensure_step(program, step)
			if line:
				channels_str = line
				for j in channels_str.split():
					if j.startswith('sleep'):
						pr = int(j[5:])
						self.set_command(program, step, RobotProgram.OTHER_COMMAND, 0, pr-1)
					elif j.startswith('jump'):
						pr = int(j[4:])
						self.set_command(program, step, RobotProgram.OTHER_COMMAND, 1, pr)
					elif j.startswith('jleft'):
						pr = int(j[5:])
						self.set_command(program, step, RobotProgram.OTHER_COMMAND, 2, pr)
					elif j.startswith('jright'):
						pr = int(j[6:])
						self.set_command(program, step, RobotProgram.OTHER_COMMAND, 3, pr)
					elif j.startswith('jrand'):
						pr = int(j[5:])
						self.set_command(program, step, RobotProgram.OTHER_COMMAND, 4, pr)
					elif j.startswith('ticks'):
						pr = int(j[5:])
						self.set_command(program, step, RobotProgram.OTHER_COMMAND, 5, pr-1)
					elif j.startswith('stop'):
						self.set_command(program, step, RobotProgram.CONTROL_COMMAND, 0)
					elif j.startswith('run'):
						pr = int(j[3:])
						self.set_command(program, step, RobotProgram.CONTROL_COMMAND, pr)
					elif j.startswith('restart'):
						pr = program
						self.set_command(program, step, RobotProgram.CONTROL_COMMAND, pr)
					elif j[:1].upper() in self.all_channels:
						channel = self.all_channels.index(j[:1].upper())
						m = re.split("(\d{0,3})(:?s\d{1,2})?(:?m\d)?", j[1:], 0, re.IGNORECASE)
						if m and len(m) > 1:
							pos = int(m[1])
							speed = 0
							mode = 0
							for k in m[2:]:
								if not k:
									continue
								if k[:1]=='m':
									mode = int(k[1:])-1
									if not (0 <= mode <= 3):
										raise ValueError("Invalid mode in "+str(j))
								elif k[:1]=='s':
									speed = int(k[1:])-1
									if not (0 <= speed <= 15):
										raise ValueError("Invalid speed in "+str(j))
							cmd = self.pack_command(channel, speed, mode)
							self.set_command(program, step, cmd, pos)
						else:
							raise ValueError("Invalid format in "+str(j))
					else:
						raise ValueError("Unknown command "+str(j))
			if comment:
				self.set_comment(program, step, comment)
			
	def get_command_source_code (self, program, channel, command):
		if not command:
			raise ValueError("Invalid command")
		if channel < len(self.all_channels):
			src = "{}{:d}".format(self.all_channels[channel], command.get('v', 0))
			if int(command.get('m', 0)):
				src += 'm'+str(1+command.get('m', 0))
			if int(command.get('s', 0)):
				src += 's'+str(1+command.get('s', 0))
		else:
			cmdnum = 240 + channel
			# print("Channel?", channel, "Command?", command, "Command num?", cmdnum)
			if cmdnum == RobotProgram.OTHER_COMMAND:
				if command.get('v', 0)==0:
					src = 'sleep{:d}'.format(command.get('e', 0))	
				elif command.get('v', 0)==1:
					src = 'jump{:d}'.format(command.get('e', 0))	
				elif command.get('v', 0)==2:
					src = 'jleft{:d}'.format(command.get('e', 0))	
				elif command.get('v', 0)==3:
					src = 'jright{:d}'.format(command.get('e', 0))	
				elif command.get('v', 0)==4:
					src = 'jrand{:d}'.format(command.get('e', 0))
				elif command.get('v', 0)==5:
					src = 'ticks{:d}'.format(command.get('e', 0))
				else:
					raise ValueError("Unknown command "+str(
						(cmdnum, command.get('v', 0), command.get('e', 0))
					))
			elif cmdnum == RobotProgram.CONTROL_COMMAND:
				if command.get('v', 0)==program:
					src = 'restart'
				elif command.get('v', 0):
					src = 'run{:d}'.format(command.get('v', 0))
				else:
					src = 'stop'
			else:
				raise ValueError("Unknown command "+str(
					(cmdnum, command.get('v', 0), command.get('e', 0))	
				))
		return src

	def clear_program (self, program):
		self.set_program_source_code(program, '')

	def get_program_raw_code (self, program, channels_lut):
		raw_code = []

		for step, channels in enumerate(self._code[program]):
			commands = []
			for channel, command in channels.items():
				if channel=='comment':
					continue
				command = self.get_command(program, step, channel)
				if command and (channel in channels_lut or channel >= len(self.all_channels)):
					cmd = self.pack_command(
						channels_lut[channel] if channel in channels_lut else channel,
						command['s'],
						command.get('m', 0))
					if cmd == RobotProgram.OTHER_COMMAND:
						v = command.get('e', 0) & 0b11111
						if command['v'] in (1, 2, 3, 4):	 # convert parameter to unsigned
							v += 16
						v += command['v'] << 5
					else:
						v = command['v']
					commands.extend((cmd, v))
			if commands:
				raw_code.extend(commands)
			#if channel < len(self.all_channels):
			raw_code.append(255)    # Next step mark
		return raw_code

	def get_all_raw_code (self, ticks_per_step = 4, channels_setup = None):
		"""
			param ticks_per_step: Amount of time between steps
			param channels_setup: List of channels in use, their types and ranges. If None, defaults to all_channels, type = servo, full range
			Returns raw code for all the programs, just prepared to be uploaded
			Format is:
			1-byte for 255 (misc command for upload)
			2-bytes for total length of the offsets pointing to every program + all programs code
			1-byte for number of programs
			1-byte for ticks_per_step (7-4), number of channels in use (3-0)
			2-bytes array for ranges for every active channel
			2-bytes for inverted channel's mask
			2-bytes array for the offsets pointing to every program
			1-byte array for code of all programs
		"""
		# Process channels in use
		if channels_setup is None:
			channels_setup = [(1,1, (0, 255), 0) for i in self.all_channels]
		num_channels = len([True for v in channels_setup if v[0]])
		if num_channels < 1:
			raise ValueError("No active channels")
		#print("Channels in use", channels_in_use)
		# TODO: Simplify this
		channels_in_use = [i for i, v in enumerate(channels_setup) if v[0]]
		channels_types = [v[1] for i, v in enumerate(channels_setup) if v[0]]
		channels_ranges = [v[2] for i, v in enumerate(channels_setup) if v[0]]
		channels_inverted = [v[3] for i, v in enumerate(channels_setup) if v[0]]
		channels_lut = {k: channels_in_use.index(k) for k, _ in enumerate(self.all_channels) if k in channels_in_use}
		
		# Iterate over the programs, and get everything packed, with a header for the beginning of every program
		# Fill gaps loading the source code from files
		lengths = []
		programs_code = []
		for program, _ in enumerate(self._code):
			program_raw = self.get_program_raw_code(program, channels_lut)
			if program_raw:
				lengths.append(len(program_raw))
				programs_code.extend(program_raw)

		raw_code = [RobotProgram.MISC_COMMAND]    # Upload misc command (255)
		
		# Put first total length as 2-bytes (headers out, only offsets and code)
		body_length=(2*len(lengths))+len(programs_code)
		raw_code.extend([i for i in tuple(pack('<h', body_length))])

		# Number of programs as 1-byte (part of the header)
		raw_code.append(len(lengths))

		# Ticks per step (4 bits) and channels used (4 bits) as 1-byte (part of the header too)
		raw_code.append((ticks_per_step-1)*16+(num_channels-1))

		# Ranges for every active channel (also part of the header)
		for min_range, max_range in channels_ranges:
			raw_code.extend((min_range, max_range))

		# Masks for inverted channels (2 bytes)
		inverted_mask = 0
		for n, i in enumerate(channels_inverted):
			inverted_mask += int(i) << n
		raw_code.extend([i for i in tuple(pack('<h', inverted_mask))])
		
		header_length = len(raw_code)
		
		# This is the body (offsets + code)
		# Then the list of offsets as a 2-bytes array
		offset = len(lengths)*2     # Offset of the first program
		for length in lengths:
			raw_code.extend([i for i in tuple(pack('<h', offset))])
			offset += length
		raw_code.extend(programs_code)
		return raw_code, body_length + header_length   # Including the length of the header here

	def pack_command (self, channel, speed = 0, mode = 0):
		cmd = 0
		#cmd |= mode << 6
		cmd |= speed << 4
		cmd |= channel
		return cmd

	def unpack_command (self, cmd):
		#mode = cmd >> 6
		mode = 0
		speed = (cmd >> 4) & 0b1111
		channel = cmd & 0b1111
		return channel, speed, mode

	def _ensure_program (self, program):
		if len(self._code) <= program:
			for i in range(program+1):
				if len(self._code) <= i:
					self._code.insert(i, [])
					try:
						self.load(program)
					except:
						pass

	def _ensure_step (self, program, step):
		if len(self._code[program]) <= step:
			for i in range(step+1):
				if len(self._code[program]) <= i:
					self._code[program].insert(i, {})
