__author__ = 'Frank Sehnke, sehnke@in.tum.de'

from pybrain.rl.environments import EpisodicTask
from pybrain.rl.environments.ode.sensors import * #@UnusedWildImport
from scipy import  ones, tanh, clip
from math import hypot
from time import time
from random import shuffle

#Basic class for all Tetra2 tasks
class Tetra2Task(EpisodicTask):
    def __init__(self, env):
        EpisodicTask.__init__(self, env)
        self.maxPower = 2000.0 #Overall maximal tourque - is multiplied with relative max tourque for individual joint to get individual max tourque
        self.reward_history = []
        self.count = 0 #timestep counter
        self.epiLen = 5000 #suggestet episodic length for normal Tetra2 tasks
        self.incLearn = 0 #counts the task resets for incrementall learning
        self.env.FricMu = 500.0 #We need higher friction for Tetra2
        self.env.dt = 0.006 #We also need more timly resolution

        # normalize standard sensors to (-1, 1)
        self.sensor_limits = []
        #Angle sensors
        for i in range(self.env.actLen):
            self.sensor_limits.append((self.env.cLowList[i], self.env.cHighList[i]))
        # Joint velocity sensors
        for i in range(self.env.actLen):
            self.sensor_limits.append((-1, 1))
        #Norm all actor dimensions to (-1, 1)
        self.actor_limits = [(-1, 1)] * env.actLen
        self.actor_limits = None

    def performAction(self, action):
        #Filtered mapping towards performAction of the underlying environment
        #The standard Tetra2 task uses a PID controller to control directly angles instead of forces
        #This makes most tasks much simpler to learn
        isJoints=self.env.getSensorByName('JointSensor') #The joint angles
        #print "Pos:", [int(i*10) for i in isJoints]
        isSpeeds=self.env.getSensorByName('JointVelocitySensor') #The joint angular velocitys
        #print "Speeds:", [int(i*10) for i in isSpeeds]
        #print "Action", action, "cHighList",self.env.cHighList , self.env.cLowList
        #act=(action+1.0)/2.0*(self.env.cHighList-self.env.cLowList)+self.env.cLowList #norm output to action intervall
        #action=tanh(act-isJoints-isSpeeds)*self.maxPower*self.env.tourqueList #simple PID
        #print "Action", act[:5]
        EpisodicTask.performAction(self, action *self.maxPower*self.env.tourqueList)
        #self.env.performAction(action)

    def isFinished(self):
        #returns true if episode timesteps has reached episode length and resets the task
        if self.count > self.epiLen:
            self.res()
            return True
        else:
            self.count += 1
            return False

    def getReward(self):
        """
            We are interested only in the total reward at the end of the episode
        """
        return 0.0

    def res (self):
        #sets counter and history back, increases incremental counter
        self.count = 0
        self.incLearn += 1
        self.reward_history.append(self.getTotalReward())


# Walking forward task. Tries to maximiza the walking distance
class WalkForwardTask(Tetra2Task):
    def __init__(self, env):
        Tetra2Task.__init__(self, env)
        #add task specific sensors, TODO build attitude sensors
        self.env.addSensor(SpecificBodyPositionSensor(['frontLLeg'], "frontLPos"))
        self.env.addSensor(SpecificBodyPositionSensor(['rearLLeg'], "rearLPos"))
        self.env.addSensor(SpecificBodyPositionSensor(['frontRLeg'], "frontRPos"))
        self.env.addSensor(SpecificBodyPositionSensor(['rearRLeg'], "rearRPos"))
        self.env.addSensor(SpecificBodyPositionSensor(['body'], "bodyPos"))

        #we changed sensors so we need to update environments sensorLength variable
        self.env.obsLen = len(self.env.getSensors())

        #normalization for the task specific sensors
        for _ in range(self.env.obsLen - 2 * self.env.actLen):
            self.sensor_limits.append((-1.0, 1.0))
        self.epiLen = 2000 #suggested episode length for this task

    def getTotalReward (self):
        v = self.env.getSensorByName('bodyPos') #[1] / float(self.epiLen)
        reward = hypot(v[0], v[2])
        
        #print "Total reward", reward, 
        #if reward > max(self.reward_history or [0]):
        #    print "(best so far)"
        #else:
        #    print ""
        return reward

