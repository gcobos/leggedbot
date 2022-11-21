#!/usr/bin/env python3

from robot import Robot
from gevent import sleep

tetra = Robot('tetra3')
for i in range(1000):
	res = tetra.get_sensors()
	print(f"{res[0]}, {res[1]}")
	#print("Range:",abs(res[0]-res[1]))
	#print("Corrected", abs(int((4+res[0]*1.15)-res[1])))
	#if 3+res[0]*1.15 > res[1]:
	#    print("Derecha")
	#else:
	#    print("Izquierda")
	sleep(0.25)