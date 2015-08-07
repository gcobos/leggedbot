#!/usr/bin/python2.7

import sys, glob
import cv2
import itertools as it
from contextlib import contextmanager
import numpy as np
from math import fabs

CONFIG_DEFAULT_ERODE=0
CONFIG_DEFAULT_MINAREA=130
CONFIG_DEFAULT_LEVEL1=500
CONFIG_DEFAULT_LEVEL2=150
CONFIG_DEFAULT_THRESHOLD=600

def clock():
    return cv2.getTickCount() / cv2.getTickFrequency()

@contextmanager
def Timer(msg):
    start = clock()
    try:
        yield
    finally:
        pass #print msg, " %.2f ms" % ((clock()-start)*1000)

def angle_cos(p0, p1, p2):
    d1, d2 = (p0-p1).astype('float'), (p2-p1).astype('float')
    return abs( np.dot(d1, d2) / np.sqrt( np.dot(d1, d1)*np.dot(d2, d2) ) )


# Adjusts the number of levels (tones) in the image using the most accurate tone
def quantize (image, num, score_tone = 100, score_hist = 1000, score_diff = 100):

    if 0>=num>=256: return
    
    score_tone *= image.size
    score_hist *= image.size
    score_diff *= image.size
    
    pixels = image.data
    class _Cls:
        color=0
        hist=0
        score=0
        next=0
    cls=[_Cls() for i in range(256)]
    
    # Get histogram
    i = 0
    while i < image.size:
        cls[ord(pixels[i])].hist+=1
        i+=1

    # Initialize all classes
    colors=0
    last=-1
    first=-1
    for i in range(256):
        cls[i].color = i
        if cls[i].hist:
            if last==-1:
                last=i
                first=i
            else:
                cls[last].score = (fabs(cls[last].color-cls[i].color)*score_tone) \
                                + (cls[last].hist+cls[i].hist)*score_hist   \
                                - (abs(cls[last].hist-cls[i].hist)*score_diff)
                cls[last].next=i
                colors+=1
                last=i
        else:
            cls[i].color=-1
            cls[i].score=0
            cls[i].next=-1
	
	# Register the last one
    cls[last].color=last
    cls[last].score = (1 * score_tone)  \
                + (cls[last].hist+cls[last].hist)*score_hist   \
                - (abs(cls[last].hist-cls[last].hist)*score_diff)

    cls[last].next=-1
    colors+=1

    # Remove a color everytime, until I have the number of colors required
    while (colors>num):
        i=first
        ant=-1
        last=i
        min=i
        while (i!=-1):
            if (cls[i].score<cls[min].score):
                last=ant
                min=i
            ant=i
            i=cls[i].next

        if (min==first):				# First one
            i=min
            j=cls[min].next

            n=((cls[i].color*cls[i].hist)+(cls[j].color*cls[j].hist))/float(cls[i].hist+cls[j].hist)

            # Match colors
            c1=cls[i].color
            c2=cls[j].color
            for k in range(256):
                if (cls[k].color==c1):
                    cls[k].color=n
                if (cls[k].color==c2):
                    cls[k].color=n

            cls[j].hist+=cls[i].hist
            cls[j].score=  (fabs(cls[j].color-cls[cls[j].next].color)*score_tone)  \
                        + (cls[j].hist+cls[cls[j].next].hist)*score_hist          \
                        - (abs(cls[j].hist-cls[cls[j].next].hist)*score_diff)

            # Remove the least one
            first=cls[i].next

        else:
            if (min==ant):				# last one
                i=cls[last].next
                j=last

                n=((cls[i].color*cls[i].hist)+(cls[j].color*cls[j].hist))/float(cls[i].hist+cls[j].hist)

                # Matching colors
                ant=-1
                c1=cls[i].color
                c2=cls[j].color
                for k in range(256):
                    if (cls[k].color==c1):
                        cls[k].color=n

                    if (cls[k].color==c2):
                        cls[k].color=n

                    # Get the previous to the last one
                    if (cls[k].next==last):
                        ant=k

                cls[j].hist+=cls[i].hist
                if (ant!=-1):
                    cls[ant].score= (fabs(cls[ant].color-cls[j].color)*score_tone) \
                                    + (cls[ant].hist+cls[j].hist)*score_hist \
                                    - (abs(cls[ant].hist-cls[j].hist)*score_diff)

                # Remove the least
                cls[j].next=-1

            else:					# Enmedio
                i=min
                j=cls[min].next

                n=((cls[i].color*cls[i].hist)+(cls[j].color*cls[j].hist))/float(cls[i].hist+cls[j].hist)
				
                # Matching colors
                c1=cls[i].color
                c2=cls[j].color
                for k in range(256):
                    if (cls[k].color==c1):
                        cls[k].color=n
                    if (cls[k].color==c2):
                        cls[k].color=n

                cls[j].hist+=cls[i].hist
                cls[last].score=  (fabs(cls[last].color-cls[j].color)*score_tone)   \
                            + (cls[last].hist+cls[j].hist)*score_hist   \
                            - (abs(cls[last].hist-cls[j].hist)*score_diff)
                cls[j].score=  (fabs(cls[cls[j].next].color-cls[j].color)*score_tone)   \
                            + (cls[cls[j].next].hist+cls[j].hist)*score_hist   \
                            - (abs(cls[cls[j].next].hist-cls[j].hist)*score_diff)

                # Remove the least
                cls[last].next=j;

        colors-=1

    # Rellena la tabla de colores (quedan los primeros sin arreglar. Da igual)
    c1=-1
    for i in range(256):
        if (cls[i].color!=-1):
            c1=cls[i].color
        else:
            cls[i].color=c1

    # Modify tones in the original image
    i = 0
    while i < image.size:
        j=ord(pixels[i])
        pixels[i]=chr(int(cls[j].color+0.5))
        i+=1

def reduceColors (img, colors = 4, iterations = 8):
    Z = img.reshape((-1,3))

    # convert to np.float32
    Z = np.float32(Z)

    # define criteria, number of clusters(K) and apply kmeans()
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, iterations, 1.0)
    K = colors
    ret,label,center=cv2.kmeans(Z,K,None,criteria, iterations,cv2.KMEANS_RANDOM_CENTERS)
    # Now convert back into uint8, and make original image
    center = np.uint8(center)
    res = center[label.flatten()]
    res2 = res.reshape(img.shape)
    return res2


class Processor:

    def __init__ (self, source = 0, training = False):

        self.source = 0    
        self.training = training
        self.squares = []
        self.patterns = {}
        self.original = None
        self.processed = None
        self.last_update = clock() - 5

        #self.camera = cv2.VideoCapture(self.source)

        for i in glob.glob('patterns/tag-[a-z]*.pgm'):
            print "Load", i
            pattern = cv2.cvtColor(cv2.imread(i), cv2.COLOR_BGR2GRAY)
            self.patterns[i] = pattern
            for transposed in range(1,4):
                if transposed % 2 == 0:
                    pattern = cv2.flip(pattern, -1)
                pattern = cv2.transpose(pattern)
                #cv2.imwrite("%s-t%d.pgm" % (i, transposed), pattern)
                self.patterns["%s-t%d" % (i, transposed)] = pattern

        if self.training:
            cv2.namedWindow('processed')
            cv2.createTrackbar('erosion', 'processed', CONFIG_DEFAULT_ERODE, 8, self._update)
            cv2.createTrackbar('minarea', 'processed', CONFIG_DEFAULT_MINAREA, 10000, self._update)
            cv2.createTrackbar('level1', 'processed', CONFIG_DEFAULT_LEVEL1, 1000, self._update)
            cv2.createTrackbar('level2', 'processed', CONFIG_DEFAULT_LEVEL2, 500, self._update)
            cv2.createTrackbar('threshold', 'processed', CONFIG_DEFAULT_THRESHOLD, 1000, self._update)

    def _update (self, _):
        pass

    def find_squares (self, image, min_area = 200):
        self.original = image
        level1=cv2.getTrackbarPos('level1', 'processed') if self.training else CONFIG_DEFAULT_LEVEL1
        level2=cv2.getTrackbarPos('level2', 'processed') if self.training else CONFIG_DEFAULT_LEVEL2
        gray = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY, 
            level1*2+3, 
            level2-250
        )
        erosion = cv2.getTrackbarPos('erosion', 'processed') if self.training else CONFIG_DEFAULT_ERODE
        if erosion:
            gray = cv2.morphologyEx(gray, cv2.MORPH_OPEN, None) #kernel[, dst[, anchor[, iterations[, borderType[, borderValue]]]]]) 
            #gray = cv2.open(gray, None, iterations = erosion)

        self.processed = np.copy(gray)
        self.squares = []
        if self.training:
            cv2.imshow('processed', self.processed)

        bin, contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            #cnt = cv2.convexHull(cnt)
            perimeter = cv2.arcLength(cnt, True)
            pre_area = pow(int(perimeter) >> 2,2)
            if pre_area < min_area:
                continue
            cnt = cv2.approxPolyDP(cnt, 0.1*perimeter, True)
            area = cv2.contourArea(cnt)
            if len(cnt) > 3 and area > min_area: # and cv2.isContourConvex(cnt)
                cnt = cnt.reshape(-1, 2)
                max_cos = np.max([angle_cos( cnt[i], cnt[(i+1) % 4], cnt[(i+2) % 4] ) for i in xrange(4)])
                if max_cos < 0.2:
                    self.squares.append(cnt)
        # OLD CODE
        #gray = reduceColors(image)
        ##gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        ##gray = cv2.medianBlur(gray, 3)
        ##quantize(gray,
        ##    cv2.getTrackbarPos('levels', 'processed'),
        ##    cv2.getTrackbarPos('score_tone', 'processed'),
        ##    cv2.getTrackbarPos('score_hist', 'processed'),
        ##    cv2.getTrackbarPos('score_diff', 'processed')
        ##)
        ##gray = cv2.equalizeHist(gray)
        ##ret, gray = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        ##quantize(gray, 4, 0, 95, 104)
        ##bin = cv2.erode(processed, None, iterations = 3)
        ##gray = cv2.medianBlur(gray, 3)
        ##gray = cv2.equalizeHist(gray)
        ##ret, bin = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

        return self.squares

    def detect (self, image, threshold = 0.7):
        match_method = cv2.TM_CCOEFF_NORMED
        detected = {}
        num_objects = 0
            
        with Timer('detection'):
            # Compare squares against patterns, and if not recognized, take the sample as new pattern
            for i, cnt in enumerate(self.squares):
                max_found = threshold
                max_item = None
                max_location = (-1,-1)
                max_angle = -1
                bounds = cv2.boundingRect(cnt)
                location_abs, size, phi = cv2.minAreaRect(cnt)
                cropped = cv2.getRectSubPix(self.processed, bounds[2:], location_abs)
                location = (location_abs[0]-bounds[0], location_abs[1]-bounds[1])
                w, h = tuple(int(c) for c in size)
                rot = cv2.getRotationMatrix2D(location, phi, 1)
                rotated = cv2.warpAffine(cropped, rot, dsize = cropped.shape[:2], flags=cv2.INTER_CUBIC)                
                sample = cv2.getRectSubPix(rotated, (w-4, h-4), location)
                #sample = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
                sample = cv2.resize(sample, (90, 90))
                #ret, sample = cv2.threshold(sample, 230, 255, cv2.THRESH_BINARY)
                #sample = cv2.equalizeHist(sample)
            
                #cv2.circle(self.original, tuple(int(l) for l in location_abs), 20, (0,0,255))
                #cv2.imshow('crop'+str(i),self.processed)
            
                for tag, pattern in self.patterns.items():
                    match = cv2.matchTemplate(sample, pattern, match_method)
                    result, _, _, _  = cv2.minMaxLoc(match)
                    if result > max_found:
                        #print "Best candidate for %s is %s with %s" % (str(i),tag, str(result))
                        max_found = result
                        max_item = tag
                        max_location = (int(location_abs[0]), int(location_abs[1]))
                        max_angle = phi
                        if result > threshold * 1.5:
                            break
                else:
                    #print "Discarted", str(i)
                    if self.training: 
                        #print "Store new pattern",i
                        cv2.imwrite('patterns/tag-%s.pgm' % str(i), sample)

                if max_item:
                    cv2.drawContours(self.original, self.squares, i, (0, 255, 0), 5)
                    tag_id = max_item.replace("patterns/tag-", "").replace(".pgm", "")
                    max_angle = (360 - max_angle) % 360
                    try:
                        name, angle = tag_id.split("-", 1)
                        #if name=='arrow':
                        #    print "Orig angle", max_angle, "using", angle
                        if angle=='t1':
                            max_angle += 90
                        elif angle=='t2':
                            max_angle += 180
                        elif angle=='t3':
                            max_angle += 270
                    except:
                        name = tag_id
                    cv2.putText(self.original, "%s" % name,
                        (max_location[0]-20, max_location[1]-20), cv2.FONT_HERSHEY_PLAIN, 1, (0,0,255), 1)
                    #vmod = 10
                    #p2 = (int(max_location[0] + vmod * np.cos(max_angle + np.pi/4)),
                    #     int(max_location[1] + vmod * np.sin(max_angle + np.pi/4)))
                    #cv2.line(self.original, max_location, p2, (0,255,255), 3)
                    #print "Chosen %s to be %s" % (str(i), max_item)
                    if not name in detected:
                        detected[name] = []
                    detected[name].append({'angle': int(100 * max_angle)/100.0, 'pos': max_location})
                    num_objects +=1
        return num_objects, detected
    
                
if __name__=='__main__':
    last_update = clock() - 5
    win = 'original.pgm'
    img = cv2.imread(win, cv2.IMREAD_GRAYSCALE)
    #img = cv2.equalizeHist(img)
    cv2.imshow('orig', img)
    def update (_):
        global img, win, last_update
        if clock() - last_update < 0.5:
            return
        img = cv2.imread(win, cv2.IMREAD_GRAYSCALE)
        quantize(img,
            cv2.getTrackbarPos('levels', win),
            cv2.getTrackbarPos('score_tone', win),
            cv2.getTrackbarPos('score_hist', win),
            cv2.getTrackbarPos('score_diff', win)
        )

    cv2.namedWindow(win)
    cv2.createTrackbar('levels', win, 3, 255, update)
    cv2.createTrackbar('score_tone', win, 1, 5000, update)
    cv2.createTrackbar('score_hist', win, 100, 5000, update)
    cv2.createTrackbar('score_diff', win, 100, 5000, update)
    update(None)

    while True:
        cv2.imshow(win, img)
        ch = 0xFF & cv2.waitKey(1)
        if ch == 27:
            break    
    
    
