#!/usr/bin/env python
#########################################################################
# Reinforcement Learning with PGPE on the Tetra2 environment
#
# Tetra2 is a body structure with 4 DoF .
# Complex balancing tasks can be learned with this environment.
#
# Control/Actions:
# The agent can control all 4 DOF of the robot. 
#
# A wide variety of sensors are available for observation and reward:
# - 256 angles of joints
# - 16 velocities of joints
# - Number of foot parts that have contact to floor
#
# Task available are:
# - WalkFordward, agent has to maximize the straight distance ran during the episode
# 
# Requirements: pylab (for plotting only). If not available, comment the
# last 3 lines out
# Author: Gonzalo Cobos
#########################################################################
__author__ = "Gonzalo Cobos"
__version__ = '$Id$' 

from pybrain.tools.example_tools import ExTools
from tetra_env import Tetra2Environment
from tetra_tasks import WalkForwardTask
from pybrain.rl.learners.valuebased.valuebased import ValueBasedLearner
from pybrain.rl.agents.optimization import OptimizationAgent
from tetra_agent import TetrapodAgent
from pybrain.rl.experiments import EpisodicExperiment

from programmer import Programmer

if __name__ == '__main__':
    
    batch=1 #number of samples per learning step
    epis=10000/batch #number of roleouts
    
    numbExp=1 #number of experiments

    env = None
    for runs in range(numbExp):
        # create environment
        #Options: Bool(OpenGL), Bool(Realtime simu. while client is connected), ServerIP(default:localhost), Port(default:21560)
        if env != None: env.closeSocket()
        env = Tetra2Environment() 
        # create task
        task = WalkForwardTask(env)

        # create automatic programmer module for the robot (it will be received already created from the robot)
        channels_setup = [(1 if i!=2 else 0,1, (0,255), 0) for i in range(5)]
        
        programmer = Programmer(steps = 1000, channels_setup = channels_setup, types_subset = [1]) #, 2, 3])

        learner = ValueBasedLearner()
        agent = TetrapodAgent(programmer, learner)

        # create the experiment
        experiment = EpisodicExperiment(task, agent)

        for _ in range(epis):
            experiment.doEpisodes(batch)
            agent.learn(total_reward = task.getTotalReward())
        
        

