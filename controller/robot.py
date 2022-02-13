
import sys
import serial
import struct
from gevent import sleep, spawn, Timeout
import copy
import yaml
from program import RobotProgram

"""
   Robot interface
"""

class Robot(object):

    DEFAULT_PORTS = ["/dev/rfcomm1", "/dev/rfcomm0", "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2"]
    BAUD_RATE = 57600
    CHANNELS = ['Q', 'W', 'E', 'A', 'S', 'D', 'R', 'T', 'Y', 'F', 'G', 'H']
    CONTROL_COMMAND = 254
    META_COMMAND = 255

    def __init__ (self, prefix=''):

        self._conn = None
        self.read_lock = False
        self.send_commands_flag = True
        self.ticks_per_step = 6
        self.channels_setup = [(1, 1, (0, 255), 0) for i in Robot.CHANNELS]  # Keeps (active, is_servo, ranges, is_inverted) for every channel num
        self.running = False
        self.prefix = prefix
        self.program = RobotProgram(self.prefix, Robot.CHANNELS)
        self._positions = []
        self._sensors = []
        self._connect()

    def load_config (self, suffix = ''):
        custom = {}
        try:
            with open('%s%s.conf' % (self.prefix, suffix), 'r') as f:
                config = yaml.load(f, Loader=yaml.FullLoader)
                self.send_commands_flag = config['send_commands_flag']
                self.ticks_per_step = config['ticks_per_step']
                self.channels_setup = config['channels_setup']
                custom = config.get('custom') or {}
        except IOError as e:
            pass
        return custom
            
    def save_config (self, suffix = '', custom = {}):
        with open('%s%s.conf' % (self.prefix, suffix), 'w') as f:
            config = {
                'send_commands_flag': self.send_commands_flag,
                'ticks_per_step': self.ticks_per_step,
                'channels_setup': self.channels_setup,
                'custom': custom,
            }
            f.write(yaml.dump(config))

    def load (self, program):
        self.program.load(program)                

    def save (self, program):
        self.program.save(program)                
        
    def run (self, program):
        """
            Program 0 is stop, otherwise, starts the execution of the program number given (1-255)
        """
        self.channel_commands[len(Robot.CHANNELS)].append((Robot.CONTROL_COMMAND, program))
    
    def stop (self):
        self.run(0)

    def set_code (self, program, code=''):
        self.program.set_program_source_code(program, code)
        
    def get_code (self, program):
        return self.program.get_program_source_code(program)

    def generate_code (self, program, seed = None, steps = 12, types_subset = None):
        self.program.generate_code(program, channels_setup = self.channels_setup, seed = seed, steps = steps, types_subset = types_subset)

    def upload_programs (self):
        """
            Upload all the programs to the robot
        """
        raw, length = self.program.get_all_raw_code(self.ticks_per_step, self.channels_setup)
        # Saves the raw programs in an accesible location
        print("About to upload", length,"bytes...")
        print(raw)
        with open('/home/drone/public_html/robot/programs.json', 'w') as f:
            f.write(str([255] + raw))
        
        self.channel_commands[len(Robot.CHANNELS)].append((Robot.META_COMMAND, raw))
    
    def set_position (self, program, step, channel, speed, mode, pos):
        """
            Set the position for a channel
        """
        if not isinstance(channel, int):
            channel = Robot.CHANNELS.index(channel.upper())

        channels_in_use = [i for i, v in enumerate(self.channels_setup) if v[0] ]
        channels_lut = {k: channels_in_use.index(k) for k, _ in enumerate(Robot.CHANNELS) if k in channels_in_use}
        if channel in channels_lut:
            cmd = self.program.pack_command(channel, speed, mode)
            cmd_alt = self.program.pack_command(channels_lut[channel] if channel in channels_lut else channel, speed, mode)
            self.channel_commands[channel].append((cmd_alt, pos))
            self.program.set_command(program, step, cmd, pos)

    def setup_channel (self, channel, active = None, is_servo = None, min_range = None, max_range = None, inverted = None):
        """
           Configure a channel as being active or disabled, and also defines the type of pwm for 
           the channel (servo or pure pwm)
        """
        if not isinstance(channel, int):
            channel = Robot.CHANNELS.index(channel.upper())
        
        self.channels_setup[channel] = (
            active if active is not None else self.channels_setup[channel][0],
            is_servo if is_servo is not None else self.channels_setup[channel][1],
            (
                min_range if min_range is not None else self.channels_setup[channel][2][0],
                max_range if max_range is not None else self.channels_setup[channel][2][1]
            ),
            inverted if inverted is not None else self.channels_setup[channel][3],
        )
        #print("Channels setup", self.channels_setup)

    def get_positions (self):
        self.channel_commands[len(Robot.CHANNELS)].append((Robot.META_COMMAND, 0))
        while self._positions == []:
            sleep(0.1)
        if self._sensors is None:
            print("Error reading positions")
        return self._positions

    def get_sensors (self):
        self.channel_commands[len(Robot.CHANNELS)].append((Robot.META_COMMAND, 1))
        while self._sensors == []:
            sleep(0.1)
        if self._sensors is None:
            print("Error reading sensors")
        return self._sensors

    def _connect (self):
        
        if self._conn and self._conn.isOpen():
            return

        for device in Robot.DEFAULT_PORTS:
            try:
                self._conn = serial.Serial()
                self._conn.port = device
                self._conn.timeout = 2
                self._conn.baudrate = Robot.BAUD_RATE
                self._conn.open()
                self._conn.flush()
                sleep(4)    # Give it time to establish the connection
                break
            except:
                self._conn = None
                continue

        if self._conn:
            sys.stderr.write("Connected by %s\n" % str(device))
        self.channel_commands = [[] for i in range(len(Robot.CHANNELS)+1)]    # channels + one special for control & meta commands

        self.running = True
        self._send_loop = spawn(self._send_commands_loop)
        sleep(0) # yields

    def _send_commands_loop (self):
        """
            Sends every last command given to a channel and drops the previous ones
        """
        while self.running:
            if self.read_lock:
                sleep(0.01)
                continue
            for i, commands in enumerate(self.channel_commands):
                if commands:
                    cmd, pos = commands[-1]
                    #if self.channel_commands[i][:-1]:
                    #    print("Skipping ", self.channel_commands[i][:-1])
                    self.channel_commands[i] = []    # Deletes all pending commands from the channel
                    # Send commands optionally for legs and trunk, but allow control commands always
                    if self.send_commands_flag or i >= len(Robot.CHANNELS):
                        if i >= len(Robot.CHANNELS):        # Control commands and upload
                            if cmd == Robot.CONTROL_COMMAND:
                                self._send(struct.pack('B', cmd) + struct.pack('B', pos))
                            elif cmd == Robot.META_COMMAND:
                                self._send(struct.pack('B', cmd))
                                if isinstance(pos, list):
                                    subcmd = pos[0]
                                else:
                                    subcmd = pos
                                if subcmd == 0:           # READ POSITIONS
                                    self._send(struct.pack('B', subcmd))
                                    # Wait here for a response 
                                    self._positions = []
                                    self._positions = self._recv()
                                elif subcmd == 1:         # READ SENSORS
                                    self._send(struct.pack('B', subcmd))
                                    # Wait here for a response
                                    self._sensors = []
                                    self._sensors = self._recv()
                                elif subcmd == 255:       # UPLOAD
                                    # Writes all the programs at once
                                    #print("Writing programs into robot's memory")
                                    #print(pos)
                                    for i in pos:
                                        self._send(struct.pack('B', i))
                        else:
                            #print("Send", cmd, pos)
                            #print("Channel",cmd & 15, "Speed", (cmd >> 4))
                            self._send(struct.pack('B', cmd) + struct.pack('B', pos))
                    sleep(0.01)

            sleep(0.01)
            
    def _recv (self, length = None, timeout = 2.0):
        result = []
        try:
            print("Receiving...")
            with Timeout(timeout):
                self.read_lock = True
                # Get response if any
                if length is None:
                    while not self._conn.inWaiting(): sleep(0.01)
                    num = self._conn.inWaiting()-1
                    length = ord(self._conn.read(1))
                i = 0
                while num or i < length:
                    while not self._conn.inWaiting(): sleep(0.01)
                    num = self._conn.inWaiting()
                    result.extend((ord(i) for i in self._conn.read(num)))
                    i+=num
                    num=0
        except Timeout as e:
            print("Receiving timeout...")
            self._conn.flush()
            sleep(1)
            result = None
        finally:
            self.read_lock = False
        return result
 
    def _send (self, data, max_retries = 3, flush = True):
        retries = 1
        while True:
            try:
                #print("Writing", len(data))
                self._conn.write(data)
                if flush:
                    self._conn.flush()
                sleep(0.02)
                break
            except (serial.SerialException, ValueError, IOError) as e:
                print("Error?", e)
                sleep(1)
                #print("Reconnecting...", retries)
                try:
                    if self._conn:
                        self._conn.close()
                except:
                    pass
                self._conn = None
                self._connect()
            if retries > max_retries:
                raise IOError("Unable to send %d bytes to robot" % len(data))
            retries += 1

        return True

    def __del__ (self):
        try:
            if self._conn:
                self._conn.close()
        except:
            raise
            