#!/usr/bin/env python

from gevent import monkey
monkey.patch_all()

from gevent import socket, spawn, sleep
from time import time
from math import hypot, fabs
import io
import struct
import cv2
import numpy as np
from processor import Processor, CONFIG_DEFAULT_THRESHOLD, CONFIG_DEFAULT_MINAREA

class Tracker(object):

    def __init__ (self, max_length = 60, training = True):
        self.training = training
        self.running = True
        self._connect()
        self.tracking_length = max_length
        self.tracked = {}
        self._ready_to_track = True
        self._image = None
        self._time = time()
        self._frames = 0
        spawn(self._capture_images)
        self.processor = Processor(training = self.training)

    def get_path_distance (self, name, time_from = None, time_to = None, limit = 0):
        """
            Get the sum of distances along the positions visited
        """
        footprints = self.get(name, time_from = time_from, time_to = time_to, limit = limit)
        distances = [0.0 for i in footprints]
        for i, footprint in enumerate(footprints):
            if len(footprint) > 1:
                for j, k in zip(footprint[:-1], footprint[1:]):
                    distances[i] += self._distance(j, k)
        return distances

    def get_distance (self, name, time_from = None, time_to = None, limit = 0):
        """
            Only takes the first and last position to calculate distance
        """
        footprints = self.get(name, time_from = time_from, time_to = time_to, limit = limit)
        distances = [0.0 for i in footprints]
        for i, footprint in enumerate(footprints):
            if len(footprint) > 1:
                distances[i] =  self._distance(footprint[0], footprint[-1])
        return distances

    def get_path_speed (self, name, time_from = None, time_to = None, limit = 0):
        footprints = self.get(name, time_from = time_from, time_to = time_to, limit = limit)
        speeds = [0.0 for i in footprints]
        for i, footprint in enumerate(footprints):
            if len(footprint) > 1:
                for j, k in zip(footprint[:-1], footprint[1:]):
                    speeds[i] += self._distance(j, k) / fabs(k['ts'] - j['ts'])
            speeds = [ i / len(footprint) for i in speeds]
        return speeds

    def get_speed (self, name, time_from = None, time_to = None, limit = 0):
        footprints = self.get(name, time_from = time_from, time_to = time_to, limit = limit)
        speeds = [0.0 for i in footprints]
        for i, footprint in enumerate(footprints):
            if len(footprint) > 1:
                j = footprint[0]
                k = footprint[-1]
                speeds[i] = self._distance(j, k) / fabs(k['ts'] - j['ts'])
        return speeds

    def get_position (self, name, time_from = None, time_to = None, limit = 0):
        footprints = self.get(name, time_from = time_from, time_to = time_to, limit = limit)
        return tuple(tuple(i['pos'] for i in j) for j in footprints)

    def get_angle (self, name):
        footprints = self.get(name, limit = 1)      # Only the last one
        angles = [0.0 for i in footprints]
        for i, footprint in enumerate(footprints):
            if footprint:
                angles[i] = int(footprint[-1]['angle'])
        return angles

    def get (self, name, time_from = None, time_to = None, limit = 0):
        """
            Gets the tracking vector of an object class by its name.
            @param name: object class name (i.e: "circle")
            @param time_from: In seconds, sets the time from which the object tracked will be fetched
            @param time_to : In seconds, sets the time until which the object tracked will be fetched
            @param max: Maximun of items to return (removing the older ones)
            @return: A list of vectors per each object tracked
        """
        if name not in self.tracked:
            return []
        time_from = time_from or 0
        time_to = time_to or time()
        history = []
        for ts, footprints in self.tracked[name]:
            if not time_from < ts < time_to:
                continue
            # Modifies the "history" list of vectors with a new set of footprints
            self.append_footprints(history, footprints, ts, limit = limit)
        return history
    
    def append_footprints (self, history, footprints, ts, limit = 0):
        if not len(footprints):
            return False
        
        if len(history):
            matching = []
            for i, fp in enumerate(footprints):
                min_distance = -1
                best_fit = None
                for j, obj in enumerate(history):
                    if j in matching:
                        continue
                    distance = self._distance(fp, obj[-1])
                    if min_distance == -1 or distance < min_distance:
                        min_distance = distance
                        best_fit = j
                if not best_fit is None:
                    matching.append(best_fit)
            
            for i in matching:
                if len(history) < len(matching):
                    history.insert(i, [])
                break
            
            for i, j in enumerate(matching):
                data = {'ts': ts}
                data.update(footprints[i])
                history[j].append(data)
                if limit > 1 and len(history[j]) > limit:
                    history[j].pop(0)
        else:
            for footprint in footprints:
                data = {'ts': ts}
                data.update(footprint)
                history.append([data])

        return True
     
    def _distance (self, p1, p2):
        return hypot(p2['pos'][0]-p1['pos'][0], p2['pos'][1]-p1['pos'][1])

    def _connect (self): 
        self.server_socket = socket.socket()
        self.server_socket.bind(('0.0.0.0', 8000))
        self.server_socket.listen(0)
        self.connection = self.server_socket.accept()[0].makefile('rb')

    def _capture_images (self):
        try:
            while self.running:
                # Read the length of the image as a 32-bit unsigned int. If the
                # length is zero, quit the loop
                image_len = struct.unpack('<L', self.connection.read(struct.calcsize('<L')))[0]
                if not image_len:
                    print "No image!"
                    self.running = False
                    break
                # Construct a stream to hold the image data and read the image
                # data from the connection
                image = cv2.imdecode(np.fromstring(self.connection.read(image_len), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
                #cv2.circle(image, (55,0),14, 4)
                #cv2.circle(image, (740,0),14, 4)
                #cv2.circle(image, (0,295),14, 4)
                #cv2.circle(image, (760,295),14, 4)

                pts1 = np.float32([[55,0],[740,0],[0,295],[760,295]])
                pts2 = np.float32([[0,0],[780,0],[0,300],[780,300]])
                M = cv2.getPerspectiveTransform(pts1,pts2)
                self._image = cv2.warpPerspective(image,M,(780,300))
                #
                self._image = cv2.resize(self._image, (int(0.7*image.shape[1]), int(0.7*image.shape[0])))
                while not self._ready_to_track:
                    sleep(0.01)
                spawn(self._track_objects)
        finally:
            self.running = False
            cv2.destroyAllWindows()
            self.connection.close()
            self.server_socket.close()

    def _track_objects (self):

        try:
            self._ready_to_track = False
            #image = np.copy(self._image)
            
            squares = self.processor.find_squares(self._image,
                min_area = cv2.getTrackbarPos('minarea', 'processed') if self.training else CONFIG_DEFAULT_MINAREA
            )
            
            if squares:
                # Returns a list of matches with the structure: [..., {"name": "x", "angle": 90.0, "center": (230, 212)}, ...]
                threshold = (cv2.getTrackbarPos('threshold', 'processed') if self.training else CONFIG_DEFAULT_THRESHOLD) / 1000.0
                num, detected = self.processor.detect(self._image, threshold)
                #detected = {}
                # Keeps the last N detections in a vector
                #print "Detected", detected
                if detected:
                    self._frames+=1

                    for i in detected:
                        if i not in self.tracked:
                            self.tracked[i] = []
                        self.tracked[i].append((time(),detected[i]))
                        if len(self.tracked[i]) > self.tracking_length:
                            self.tracked[i].pop(0)
    
            if self.training:
                cv2.drawContours(self._image, squares, -1, (0, 0, 255), 1)
                cv2.putText(self._image, 
                    "FPS: %s" % str(int(1000*self._frames/(time()-self._time))/1000.0),
                    (30, 30), cv2.FONT_HERSHEY_PLAIN, 2, (0,0,255), 2)
                cv2.imshow('squares', self._image)
                    
                ch = 0xFF & cv2.waitKey(1)
                if ch == 27:
                    self.running = False
            else:
                print "FPS: %s" % str(int(1000*self._frames/(time()-self._time))/1000.0)
        finally:
            self._ready_to_track = True        

if __name__=='__main__':
    tr = Tracker(training = False)
    while tr.running:
        try:
            sleep(1)
        except:
            break
    
    
