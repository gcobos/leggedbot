#!/usr/bin/env python3

from robot import Robot
from tracker import Tracker
from time import time
from gevent import sleep

#tetra = Robot('tetra')
tracker = Tracker(training = True)

# TODO: Every loop, evaluates all the programs, makes modifications and evaluates again

cache = {}
while tracker.running:
    
    #print("One second range for X", tracker.get_position('axis', time_from = time() - 1))
    #print("3 last positions of circles", tracker.get_position('circle', limit = 3))
    #print("Triangle AVG speed:", tracker.get_path_speed('triangle', time_from = time()-5)[0:])
    #print("Triangle instant speed:", tracker.get_speed('triangle')[0:])
    #print("Arrow angle", tracker.get_angle('arrow'))
    
    # Check movements (events)
    for shape in ( 'arrow', ): # 'triangle', 'circle', 'square', 'axis',
        #t = time()
        distances = tracker.get_distance(shape, time_from = time() - 2)
        #print("Distance takes", time()-t)
        moved = [ (int(distance*100)/100, i) for i, distance in enumerate(distances) if distance > 2]
        #print(moved)
        if not moved:
            continue
        
        if cache.get("%s-%d" % (shape, moved[0][1])) > time()-2:
            continue

        if len(moved) == 1:
            print("%s-%d" % (shape, moved[0][1]), "moved by", moved[0][0], "units")
            positions = tracker.get_position(shape, time_from = time() - 2)
            if len(positions) and positions[moved[0][1]]:
                print("From", positions[moved[0][1]][0],"to",positions[moved[0][1]][-1])
        else:
            print(len(moved), (shape + 's' if shape !='axis' else shape), "were moved by", " and ".join(["%s-%d" % (shape, i[1]) for i in moved]), "units")
        cache["%s-%d" % (shape, moved[0][1])] = time()

    
    sleep(0.1)
