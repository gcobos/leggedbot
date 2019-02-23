
# This handles a serial connection with the robot


USE_AUTODETECT = 0
USE_PYSERIAL = 1
USE_PYBLUEZ = 2
USE_ANDROID = 3

class Connection(object):

    DEFAULT_PORTS = ["/dev/rfcomm1", "/dev/rfcomm0", "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2"]
    BAUD_RATE = 57600
    
    def __init__ (self, use_library=USE_AUTODETECT):
        

    def connect (self):
        if self._conn and self.isConnected():
            return

        for device in Robot.DEFAULT_PORTS:
            try:
                self._conn = serial.Serial()
                self._conn.port = device
                self._conn.timeout = 2
                self._conn.baudrate = Robot.BAUD_RATE
                self._conn.open()
                self._conn.flush()
                sleep(3)
                break
            except:
                self._conn = None
                continue

        if self._conn:
            print "Connected by ",device
        self.channel_commands = [[] for i in range(len(Robot.CHANNELS)+1)]    # channels + one special for control & meta commands

        self.running = True
        self._send_loop = spawn(self._send_commands_loop)
        sleep(0) # yields
 
    def _send (self, data, max_retries = 3, flush = False):
        retries = 1
        while True:
            try:
                #print "Writing", len(data)
                self._conn.write(data)
                if flush:
                    self._conn.flush()
                sleep(0.01)
                break
            except (serial.SerialException, ValueError, IOError) as e:
                print "Error?",e
                sleep(1)
                #print "Reconnecting...", retries
                try:
                    if self._conn:
                        self._conn.close()
                except:
                    pass
                self._connect()
            if retries > max_retries:
                raise IOError("Unable to send %d bytes to robot" % len(data))
            retries += 1

        return True

    def recv (self):
            try:
                if self._conn and self._conn.isOpen() and self._conn.inWaiting()>0: 
                    print "Received: ",
                    while self._conn.inWaiting()>0: 
                        print ord(self._conn.read(1)),
            except:          
                sleep(0.1)
                raise


    def __del__ (self):
        try:
            if self._conn:
                self._conn.close()
        except:
            raise



