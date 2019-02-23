__author__ = 'Frank Sehnke, sehnke@in.tum.de'

from pybrain.rl.environments.ode import ODEEnvironment, sensors, actuators
import imp
from scipy import array

class Tetra2Environment(ODEEnvironment):
    def __init__(self, renderer=True, realtime=False, ip="127.0.0.1", port="21590", buf='16384'):
        ODEEnvironment.__init__(self, renderer, realtime, ip, port, buf)
        # load model file
        self.loadXODE("models/tetra2.xode")

        # standard sensors and actuators
        self.addSensor(sensors.JointSensor())
        self.addSensor(sensors.JointVelocitySensor())
        self.addActuator(actuators.JointActuator())

        #set act- and obsLength, the min/max angles and the relative max touques of the joints
        self.actLen = self.indim
        self.obsLen = len(self.getSensors())
        # frontAxis, frontLeftLeg, frontRightLeg, rearAxis, rearLeftLeg, rearRightLeg
        self.tourqueList = array([6.0, 1.0, 1.0, 6.0, 1.0, 1.0])
        self.cHighList = array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        self.cLowList = array([-1.0, -1.0, -1.0, -1.0, -1.0, -1.0])

        self.stepsPerAction = 1

if __name__ == '__main__' :
    w = Tetra2Environment()
    while True:
        w.step()
        if w.stepCounter == 1000: w.reset()

