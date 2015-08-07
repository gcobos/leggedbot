__author__ = 'Gonzalo Cobos'

from scipy import array
import numpy as np
from math import sin
from time import time
from pybrain.rl.agents.learning import LearningAgent
from pybrain.rl.agents import OptimizationAgent

class TetrapodAgent (LearningAgent):
    """
       Controller for the simulations
       Generates a program and executes it, generating actions for every step
    """
    def __init__(self, module, learner = None):
        LearningAgent.__init__(self, module, learner)
        self.module = module
        self.learner = learner
        self.data = None
        self.step = 0
        self.lastobs = None
        self.lastaction = None
        self.lastreward = None
        self.max_reward = 0.0

    def integrateObservation(self, obs):
        self.lastobs = obs
        
    def giveReward (self, r):
        """
            Give a reward for every action... Not used
        """
        self.lastreward = r
        
    def newEpisode (self):        
        self.data = self.module.get_raw_data()
        #print "Testing", self.module
        self.step = 0
    
    def getAction(self):
        """
            Gives a step in the program
            Front axis, front left leg, front right leg, rear axis, rear left leg, rear right leg
        """
        if not self.data:
            return array([0,0,0,0,0,0])

        # Ordered as Q   W   A   S
        if self.step < len(self.data[0])-1:
            self.step += 1
        else:
            self.step = 0
        
        channels = []
        for i in range(len(self.data)):
            channels.append(self.data[i][self.step])

        actions = array([
            (channels[1]/128.0)-1.0, 
            (channels[0]/128.0)-1.0,
            -1.0+channels[0]/128.0, 
            (channels[3]/128.0)-1.0,
            channels[2]/128.0-1.0, 
            -1.0+channels[2]/128.0
        ])
        
        """
        for k, v in enumerate(actions):
            if self.mins[k] is None or v < self.mins[k]:
                self.mins[k] = v
            if self.maxs[k] is None or v > self.maxs[k]:
                self.maxs[k] = v
        """
        self.lastaction = actions

        return actions 

    def learn(self, episodes = 1, total_reward = None):
        #print "Learn called!"
        
        if not self.learning:
            #print "not learning..."
            return
        
        if not self.learner.batchMode:
            print('Learning is done online, and already finished.')
            return

        if total_reward > self.max_reward * 0.7:
            self.module.mutate()
        else:
            self.module.randomize()

        if total_reward > self.max_reward:
            self.max_reward = total_reward
            #print "Max", total_reward
            print "Best reward",total_reward, self.module


        """
        for seq in self.history:
            for obs, action, reward in seq:
                if self.laststate is not None:
                    self.learner._updateWeights(self.lastobs, self.lastaction, self.lastreward, obs)
                self.lastobs = obs
                self.lastaction = action[0]
                self.lastreward = reward
            self.learner.newEpisode()
        """