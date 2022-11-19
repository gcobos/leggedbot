# This module handles the serial connection with a robot

import sys
import serial
import struct
from gevent import sleep, spawn, Timeout

USE_AUTODETECT = 0
USE_PYSERIAL = 1
USE_PYBLUEZ = 2
USE_ANDROID = 3

class RobotConnection(object):

	DEFAULT_PORTS = ["/dev/rfcomm1", "/dev/rfcomm0", "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB4", "/dev/ttyUSB5"]
	BAUD_RATE = 57600
	
	def __init__ (self, use_library=USE_AUTODETECT):
		self._conn = None
		self._read_lock = False
		self.connect()

	def connect (self):
		if self.is_connected():
			return

		for device in self.DEFAULT_PORTS:
			try:
				self._conn = serial.Serial()
				self._conn.port = device
				self._conn.timeout = 10
				self._conn.baudrate = self.BAUD_RATE
				self._conn.open()
				self._conn.flush()
				sleep(3)	# Allow the connection to stablish
				break
			except:
				self._conn = None
				continue

		if self._conn:
			print("Connected by ",device)

	def is_connected (self):
		return self._conn and self._conn.isOpen()

	def recv (self, length = None, timeout = 2.0):
		result = []
		try:
			print("Receiving...")
			with Timeout(timeout):
				self.read_lock = True
				# Get response if any
				if length is None:
					while not self._conn.inWaiting(): sleep(0.01)
					num = self._conn.inWaiting()-1
					length = struct.unpack('B', self._conn.read(1))[0]
				i = 0
				while num > 0 or i < length:
					while not self._conn.inWaiting(): sleep(0.01)
					num = self._conn.inWaiting()
					result.extend((i for i in self._conn.read(num)))
					i+=num
					num=0
		except Timeout as e:
			print("Receiving timeout...")
			self._conn.flush()
			sleep(1)
			result = None
		finally:
			self._read_lock = False
		return result

	def send (self, cmd, params, max_retries = 3, flush = False):
		retries = 1
		data = struct.pack('B', cmd)
		try:
			data += struct.pack('B', params)
		except struct.error:
			for i in params:
				data += struct.pack('B', i)
		while True:
			try:
				#print("Writing", len(data), "bytes\n", cmd, "\n",  params)
				# Serial read buffer in arduino is normally 64 bytes
				for start in range(0, len(data), 32):
					chunk = data[start:start + 32]
					#print("sending chunk:", chunk)
					self._conn.write(chunk)
					sleep(0.2)
				if flush:
					self._conn.flush()
				sleep(0.01)
				break
			except (serial.SerialException, ValueError, IOError) as e:
				print("Error?", e)
				sleep(1)
				print("Reconnecting...", retries)
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

if __name__ == '__main__':
	conn = RobotConnection()
	sleep(1)

