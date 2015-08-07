#!/usr/bin/python2.7

import io
import socket
import struct
import time
import picamera
import cv2
import numpy as np

WIDTH=640
HEIGHT=480

# Connect a client socket to my_server:8000 (change my_server to the
# hostname of your server)
client_socket = socket.socket()
client_socket.connect(('asus', 8000))

# Make a file-like object out of the connection
connection = client_socket.makefile('wb')
try:
    with picamera.PiCamera() as camera:
        camera.resolution = (WIDTH, HEIGHT)
        camera.framerate = 20
        #camera.awb_mode = 'auto'
        #camera.exposure_mode = 'auto'

        # Start a preview and let the camera warm up for 2 seconds
        camera.start_preview()
        time.sleep(2)

        # Note the start time and construct a stream to hold image data
        # temporarily (we could write it directly to connection but in this
        # case we want to find out the size of each capture first to keep
        # our protocol simple)
        start = time.time()
        stream = io.BytesIO()
        t0 = time.time()
        i = 0
        for foo in camera.capture_continuous(stream, 'bgr', use_video_port = True):
            t1 = time.time()
            print "FPS:", i / (t1-t0)
            i+=1
            image = np.fromstring(stream.getvalue(), dtype=np.uint8, count = WIDTH*HEIGHT*3)
            image.shape=(HEIGHT,WIDTH,3)
            image = cv2.cvtColor(image[120:-120,0:-200], cv2.COLOR_BGR2GRAY)
            #print image.shape, image.size
            ret, image = cv2.imencode('.pgm', image)
            #print "File size", image.size
            connection.write(struct.pack('<L', image.size))
            # Rewind the stream and send the image data over the wire
            #stream.seek(0)
            connection.write(image.data)
            # Reset the stream for the next capture
            stream.seek(0)
            stream.truncate()
            #time.sleep(0.001)
finally:
    # Write a length of zero to the stream to signal we're done
    connection.write(struct.pack('<L', 0))
    connection.close()
    client_socket.close()
