#!/usr/bin/env python

import kivy
kivy.require('1.0.6')
import sys
from time import sleep
from struct import pack
from jnius import autoclass, JavaException
from kivy.app import App
from kivy.animation import Animation
from kivy.uix.floatlayout import FloatLayout
from kivy.logger import Logger
from kivy.network.urlrequest import UrlRequest

def get_socket_stream(name):

    try: 
        BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
        BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
        BluetoothSocket = autoclass('android.bluetooth.BluetoothSocket')
        UUID = autoclass('java.util.UUID')
    except JavaException as e:
        Logger.error("Couldn't load some android classes %s" % str(e))
        return None, None, None

    paired_devices = BluetoothAdapter.getDefaultAdapter().getBondedDevices().toArray()
    socket = None
    if not paired_devices:
        return None, None, None
    for device in paired_devices:
        if device.getName() == name:
            socket = device.createRfcommSocketToServiceRecord(
                UUID.fromString("00001101-0000-1000-8000-00805F9B34FB"))
            socket.connect()
            sleep(0.1)
            recv_stream = socket.getInputStream()
            send_stream = socket.getOutputStream()
            break

    return socket, recv_stream, send_stream

def upload_programs (out, code = None):
    code = code or [255, 255, 138, 1, 10, 83, 152, 194, 66, 212, 186, 222, 72, 220, 11, 0, 20, 0, 112, 0, 139, 0, 214, 0, 241, 0, 3, 1, 34, 1, 52, 1, 79, 1, 97, 1, 48, 170, 33, 106, 34, 106, 3, 0, 255, 48, 227, 33, 142, 34, 142, 35, 35, 255, 0, 227, 33, 177, 34, 177, 35, 71, 255, 48, 170, 33, 213, 34, 213, 35, 106, 255, 48, 113, 33, 248, 34, 248, 35, 142, 255, 48, 57, 241, 0, 242, 0, 35, 177, 255, 48, 0, 1, 0, 2, 0, 35, 213, 255, 0, 0, 1, 0, 2, 0, 35, 248, 255, 48, 57, 33, 35, 34, 35, 243, 0, 255, 48, 113, 33, 71, 34, 71, 3, 0, 254, 1, 255, 240, 0, 242, 255, 255, 255, 241, 255, 243, 0, 255, 255, 240, 255, 242, 0, 255, 255, 241, 0, 243, 255, 255, 255, 254, 2, 255, 48, 80, 49, 239, 34, 0, 51, 40, 255, 48, 120, 241, 31, 2, 0, 51, 80, 255, 48, 159, 33, 0, 50, 40, 51, 120, 255, 48, 199, 1, 0, 50, 80, 51, 159, 255, 48, 239, 49, 40, 50, 120, 51, 199, 255, 240, 31, 49, 80, 50, 159, 51, 239, 255, 32, 0, 49, 120, 50, 199, 243, 31, 255, 0, 0, 49, 159, 50, 239, 35, 0, 255, 254, 3, 255, 240, 255, 242, 0, 255, 255, 241, 255, 243, 0, 255, 255, 240, 255, 242, 255, 255, 255, 241, 0, 243, 255, 255, 255, 254, 4, 255, 0, 128, 1, 128, 2, 128, 3, 128, 255, 255, 255, 255, 255, 255, 255, 254, 0, 255, 0, 0, 1, 255, 2, 255, 3, 0, 255, 255, 241, 255, 243, 0, 255, 255, 240, 0, 242, 0, 255, 255, 241, 0, 243, 255, 255, 255, 254, 6, 255, 112, 255, 1, 80, 2, 255, 255, 255, 113, 240, 255, 0, 0, 255, 255, 254, 7, 255, 240, 0, 242, 255, 255, 255, 241, 0, 243, 255, 255, 255, 240, 255, 242, 0, 255, 255, 241, 255, 243, 0, 255, 255, 254, 8, 255, 112, 0, 1, 80, 2, 0, 255, 255, 113, 240, 255, 0, 255, 255, 255, 254, 9, 255, 112, 113, 114, 113, 255, 112, 140, 113, 64, 114, 140, 115, 172, 255, 112, 113, 114, 113, 255, 112, 140, 114, 140, 255, 112, 113, 113, 172, 114, 113, 115, 64, 255, 112, 140, 114, 140, 255, 254, 10, 255]    
    out.flush()
    for i in code:
        out.write(i)
        sleep(0.02)
    out.flush()
    return True

class RobotRemote (FloatLayout):
    '''
       Create a controller that receives a custom widget from the kv lang file.
       Add an action to be called from the kv lang file.
    '''

    def __init__ (self):
        FloatLayout.__init__(self)
        self.connected = False
        self.socket = None
        self.send_stream = None
        self.recv_stream = None
    
    def do_action (self, param=None):
        if self.connected:
            Logger.debug('write %s = %s' % (str(254),str(self.send_stream.write(254))))
            Logger.debug('Flush %s' % str(self.send_stream.flush()))
            Logger.debug('write %s = %s' % (str(param), str(self.send_stream.write(param))))
            Logger.debug('Flush %s' % str(self.send_stream.flush()))
        else:
            Logger.info('Not connected')

    def send_single (self, param=None):
        """
            It sends as a byte, the decimal value given as a string
        """
        if self.connected:
            Logger.debug('Write %s = %s' % (str(param),str(self.send_stream.write(int(param)))))
            Logger.debug('Flush %s' % str(self.send_stream.flush()))
        else:
            Logger.info('Not connected')
    def do_release (self):
        if self.connected:
            Logger.debug('Send %s = %s' % (str(254),str(self.send_stream.write(254))))
            Logger.debug('Flush %s' % str(self.send_stream.flush()))
            Logger.debug('Send %s = %s' % (str(0),str(self.send_stream.write(0))))
            Logger.debug('Flush %s' % str(self.send_stream.flush()))
        else:
            Logger.info('Not connected')

    def do_connect (self, instance):
        try:
            if self.connected:
                self.socket.close()
                self.connected = False
            self.socket, self.recv_stream, self.send_stream = get_socket_stream('tetra1')
            if self.send_stream:
                self.connected = self.socket.isConnected()
                instance.text = 'Connected'
                Logger.debug('Is BT socket connected? %s' % str(self.connected))
                Logger.debug('Uploading programs...')
                upload_programs(self.send_stream)
        except Exception as e:
            Logger.error('Error, %s' % str(e))
            instance.text = 'Failed to connect'

    def do_upload (self, instance):
        try:
            if self.connected:
                def update_programs (req, raw):
                    Logger.debug('Uploading new programs')
                    upload_programs(self.send_stream, raw)
                    instance.text = 'Updated programs'
                Logger.debug('About to start downloading new programs')
                req = UrlRequest('http://192.168.1.35/~drone/robot/programs.json', update_programs)
                Logger.debug('Request was made. Now waiting')
                req.wait()
            else:
                instance.text = 'Connect first'
        except Exception as e:
            Logger.error('Error, %s' % str(e))
            if self.connected:
                instance.text = 'Failed to upload'
                raw = [255, 255, 138, 1, 10, 83, 152, 194, 66, 212, 186, 222, 72, 220, 11, 0, 20, 0, 112, 0, 139, 0, 214, 0, 241, 0, 3, 1, 34, 1, 52, 1, 79, 1, 97, 1, 48, 170, 33, 106, 34, 106, 3, 0, 255, 48, 227, 33, 142, 34, 142, 35, 35, 255, 0, 227, 33, 177, 34, 177, 35, 71, 255, 48, 170, 33, 213, 34, 213, 35, 106, 255, 48, 113, 33, 248, 34, 248, 35, 142, 255, 48, 57, 241, 0, 242, 0, 35, 177, 255, 48, 0, 1, 0, 2, 0, 35, 213, 255, 0, 0, 1, 0, 2, 0, 35, 248, 255, 48, 57, 33, 35, 34, 35, 243, 0, 255, 48, 113, 33, 71, 34, 71, 3, 0, 254, 1, 255, 240, 0, 242, 255, 255, 255, 241, 255, 243, 0, 255, 255, 240, 255, 242, 0, 255, 255, 241, 0, 243, 255, 255, 255, 254, 2, 255, 48, 80, 49, 239, 34, 0, 51, 40, 255, 48, 120, 241, 31, 2, 0, 51, 80, 255, 48, 159, 33, 0, 50, 40, 51, 120, 255, 48, 199, 1, 0, 50, 80, 51, 159, 255, 48, 239, 49, 40, 50, 120, 51, 199, 255, 240, 31, 49, 80, 50, 159, 51, 239, 255, 32, 0, 49, 120, 50, 199, 243, 31, 255, 0, 0, 49, 159, 50, 239, 35, 0, 255, 254, 3, 255, 240, 255, 242, 0, 255, 255, 241, 255, 243, 0, 255, 255, 240, 255, 242, 255, 255, 255, 241, 0, 243, 255, 255, 255, 254, 4, 255, 0, 128, 1, 128, 2, 128, 3, 128, 255, 255, 255, 255, 255, 255, 255, 254, 0, 255, 0, 0, 1, 255, 2, 255, 3, 0, 255, 255, 241, 255, 243, 0, 255, 255, 240, 0, 242, 0, 255, 255, 241, 0, 243, 255, 255, 255, 254, 6, 255, 112, 255, 1, 80, 2, 255, 255, 255, 113, 240, 255, 0, 0, 255, 255, 254, 7, 255, 240, 0, 242, 255, 255, 255, 241, 0, 243, 255, 255, 255, 240, 255, 242, 0, 255, 255, 241, 255, 243, 0, 255, 255, 254, 8, 255, 112, 0, 1, 80, 2, 0, 255, 255, 113, 240, 255, 0, 255, 255, 255, 254, 9, 255, 112, 113, 114, 113, 255, 112, 140, 113, 64, 114, 140, 115, 172, 255, 112, 113, 114, 113, 255, 112, 140, 114, 140, 255, 112, 113, 113, 172, 114, 113, 115, 64, 255, 112, 140, 114, 140, 255, 254, 10, 255]
                upload_programs(self.send_stream, raw)
            else:
                instance.text = 'Connect to upload'

    
class RobotRemoteApp(App):
    title = 'Robot Remote Control'
    icon = 'icon.png'
        
    def build(self):
        return RobotRemote()
                    
    def on_pause(self):
        return True

if __name__ == '__main__':
    RobotRemoteApp().run()

