#!/usr/bin/env python3

import re
from math import fabs
from pprint import pprint
import unittest
import numpy as np
from scipy import dot
import itertools
import yaml
from copy import copy
from random import random, choice
from pybrain.structure.modules.module import Module
from pybrain.structure.parametercontainer import ParameterContainer

"""
TODO:
 - Ensure the x is in order when loading expanded data
 - Simplify programs when the slope doesn't change in consecutive steps

"""

_signal_types_table = []

def load_signal_types (config = 'signal_types'):
    global _signal_types_table
    try:
        with open('%s.conf' % config, 'r') as f:
            _signal_types_table = yaml.safe_load(f) or []
    except IOError:
        pass

def save_signal_types (config = 'signal_types'):
    global _signal_types_table
    with open('%s.conf' % config, 'w') as f:
        f.write(yaml.safe_dump(_signal_types_table, default_flow_style=False, canonical=False))


class Signal(object):
    """
        Holds a signal given its type and offset, or data as a list containing tuples of (time, value)
        Also keeps a general table with all the signal types, so if they can be created and modified
        The offset is valid for types or data constructions, and if the signal is saved, the offset is dropped, so
        only the set of values resulting with that offset applied are saved
        Values in the data sets should be in the range [0.0 1.0)
        @param type (optional) must be positive integer from 0 to N
        @param offset (optional) must be in the range [0.0 1.0)
    """

    def __init__ (self, data = None, type = None, offset = 0.0, steps = None):
        self._steps = steps or 12
        self._in_min = 0.0
        self._in_max = 1.0
        self.set_data(data = data, type = type, offset = offset)

    def set_data (self, data = None, type = None, offset = 0.0):
        if isinstance(data, (tuple, list)):
            if data and isinstance(data[0], (tuple, list)):
                self.data = data
            elif len(data):
                if len(data) == 2:
                    self.data = self._expand(data[0])
                    self._set_offset(data[1])
                else:
                    raise ValueError
            else:
                self.data = []
        elif type is not None:
            self.data = self._expand(type)
        else:
            raise ValueError
        self.data = self._set_offset(self._interpolate(self.data), offset)

    def _set_offset (self, data, offset = 0.0):
        if not data:
            return []
        if 0 < offset < 1:
            x, y = zip(*data)
            offset_idx = int(offset*len(y))
            y = y[offset_idx:] + y[:offset_idx]
            data = zip(x, y)
        return data

    def _expand (self, type):
        global _signal_types_table
        if not _signal_types_table:
            load_signal_types()
        data = _signal_types_table[type]
        if len(data) < self._steps:
            data = self._interpolate(data)
        return data

    def _interpolate (self, data):
        if not data:
            return []
        result = []
        x, y = zip(*data)
        dx = max(x)/float(self._steps-1)
        return zip(
            range(self._steps),
            [float(i) for i in np.interp([i*dx for i in range(self._steps)], x, y, left=(y[0]+y[-1])/2.0, right=(y[0]+y[-1])/2.0)],
        )

    def save_type (self, type):
        global _signal_types_table
        if not _signal_types_table:
            load_signal_types()
        idx = int(type)
        if len(_signal_types_table) <= idx:
            _signal_types_table += [[] for i in range(1 + idx - len(_signal_types_table))]
            
        _signal_types_table[idx] = list(self.data)
        save_signal_types()

    def remap (self, out_min, out_max):
        result = []
        for t, y in self.data:
            result.append((t, ((y - self._in_min) * (out_max - out_min) / float(self._in_max - self._in_min)) + out_min))
        self._in_min = float(out_min)
        self._in_max = float(out_max)
        self.data = result


class Programmer (Module, ParameterContainer):
    """
        This class provides a way to generate programs automatically
        Given a seed (a list of tuples) containing tuples of (type_of_signal, offset)
        generates program code.
    """
    def __init__ (self, indim = 27, outdim = 6, seed = None, channels_setup = None, steps = None, types_subset = None):
        self._seed = seed or []
        self._steps = steps or 10
        self._channels_setup = channels_setup

        self._types_subset = types_subset or []
        if isinstance(self._seed, str):
            self.parse_seed(self._seed)
        if not self._seed:
            self.generate_seed()

        #print("Init module ", self.get_num_channels())
        Module.__init__(self, indim, outdim, None)
        ParameterContainer.__init__(self, indim)

    def _forwardImplementation(self, inbuf, outbuf):
        print("Forward implementation called in Programmer instance", outbuf)
        outbuf[:] = [random() for i in outbuf]

    def generate_seed (self, types_subset = None):
        global _signal_types_table
        if not _signal_types_table:
            load_signal_types()
        if not types_subset:
            types_subset = self._types_subset or range(len(_signal_types_table))
        channels = len([True for v in self._channels_setup if v[0]])
        if channels < 1:
            raise ValueError("No active channels")
        result = []
        for i in range(channels):
            result.append([choice(types_subset), random()])
        self._seed = result

    def parse_seed (self, seed, channels_setup = None):
        if not seed:
            return
        self._channels_setup = self._channels_setup or channels_setup
        if self._channels_setup is None:
            self._channels_setup = self._channels_setup or [(1,1, (0,255), 0) for i in range(12)]
        try:
            signals = seed.replace("--", "").replace("SEED:", "").strip().split(",")
            channels = len([True for v in self._channels_setup if v[0]])
            if channels < 1:
                raise ValueError("No active channels")
            if channels != len(signals):
                raise ValueError("Bad seed for the current channels setup")
            result = []
            for signal in signals:
                result.append([float(x) if i else int(x) for i, x in enumerate(signal.split(":", 1))])
            self._seed = result
        except:
            raise


    def get_num_channels (self):
        """
            Returns the number of channels in use
        """
        return len([True for v in self._channels_setup if v[0]])
                
    def get_raw_code (self):
        data = self.get_raw_data()
        previous_commands = []
        max_slope = 0.0
        for step, commands in enumerate(zip(*data)):
            if previous_commands:
                for p, c in zip(previous_commands, commands):
                    if p is None and c is None:
                        continue
                    elif p is None:
                        p = c
                    elif c is None:
                        c = p
                    slope = fabs(p-c)
                    if slope > max_slope:
                        max_slope = slope
            previous_commands = copy(commands)

        channels_in_use = [i for i, v in enumerate(self._channels_setup) if v[0]]
        channels_types = [v[1] for i, v in enumerate(self._channels_setup) if v[0]]
        channels_ranges = [v[2] for i, v in enumerate(self._channels_setup) if v[0]]
        channels_inverted = [v[3] for i, v in enumerate(self._channels_setup) if v[0]]

        code = []
        previous_commands = []
        slope_delta = 16/float(max_slope+1)     # Normalize speed depending on the slope
        for step, commands in enumerate(zip(*data)):
            if True: #previous_commands:
                step_code = {}
                for channel, pos in enumerate(commands):
                    if not previous_commands:
                        previous_commands = zip(*data)[-1]
                    previous_pos = previous_commands[channel]
                    if previous_pos is None and pos is None:
                        continue
                    elif previous_pos is None:
                        previous_pos = pos
                    elif pos is None:
                        pos = previous_pos
                    speed = int(abs(previous_pos-pos)*slope_delta)
                    step_code[channels_in_use[channel]] = {'s': speed, 'v': int(0.5+pos)}
                if not step_code:
                    return None             # Empty program
                code.append(step_code)
                
            previous_commands = copy(commands)
        return code

    def get_raw_data (self):
        data = []
        for type, offset in self._seed:
            signal = Signal(type = type, offset = offset, steps = self._steps)
            signal.remap(0, 255)
            data.append([y for t, y in (signal.data or [(None,None)]*self._steps)])
        return data

    def mutate(self):
        """
            Just change the offsets a bit
        """
        for i in range(len(self._seed)):
            self._seed[i][1] += (random() * 0.1)-0.05
            self._seed[i][1] %= 1.0
        

    def copy(self):
        return Programmer(
            seed = self._seed, 
            channels_setup = self._channels_setup,
            steps = self._steps,
            types_subset = self._types_subset
        )

    def randomize(self):   
        self.generate_seed()

    def __repr__(self):
        return '--SEED: %s--' % ", ".join(["%d:%f" % (i[0], i[1]) for i in self._seed])


class TestProgrammer (unittest.TestCase):

    #@unittest.skip('')
    def _test_interpolation (self):
        import matplotlib.pyplot as plt
        # Sine
        dots = 20
        dx = 2.0*np.pi/float(dots)
        signal_3 = [(float(i), float(0.5+np.sin(i*dx)/2.0)) for i in range(dots)]
        s3 = Signal(signal_3, steps = 24)

        plt.plot(*zip(*signal_3), marker = 'o')
        plt.plot(*zip(*s3.data), marker = '+')
        plt.title('Signal interpolation')
        plt.show()

    #@unittest.skip('')
    def test_remap (self):
        import matplotlib.pyplot as plt
        # Sine
        dots = 30
        dx = 2.0*np.pi/float(dots)
        signal_3 = [(float(i), float(0.5+np.sin(i*dx)/2.0)) for i in range(dots)]
        s3 = Signal(signal_3, steps = 30)
        s3.remap(0,2)

        plt.plot(*zip(*signal_3), marker = 'o')
        plt.plot(*zip(*s3.data), marker = '+')
        plt.title('Signal remapping')
        plt.show()

    #@unittest.skip('')
    def test_signal_generation (self):
        import matplotlib.pyplot as plt

        # Null
        signal_0 = []
        s0 = Signal(signal_0, steps = 30)
    
        # Mount
        signal_1 = [
            (0, 0.0),
            (1, 1.0),
            (2, 0.0),
        ]
        s1 = Signal(signal_1, steps = 30)        
    
        # Climb (slow) and fall (fast)
        signal_2 = [
            (0, 0.0),
            (4, 1.0),
            (4.1, 0.0),
            (5, 0.0)
        ]
        s2 = Signal(signal_2, steps = 30)

        # Up (fast) and walk-down (slow)
        signal_3 = [
            (0, 1.0),
            (1, 1.0),
            (5, 0.0)
        ]
        s3 = Signal(signal_3, steps = 30)

        # Sine
        dots = 30
        dx = 2.0*np.pi/float(dots)
        signal_4 = [(float(i), float(0.5+np.sin(i*dx)/2.0)) for i in range(dots)]
        s4 = Signal(signal_4, steps = 30)

        plt.plot(*zip(*s0.data))
        plt.plot(*zip(*s1.data), marker = 'o')
        plt.plot(*zip(*s2.data), marker = '+')
        plt.plot(*zip(*s3.data), marker = '.')
        plt.plot(*zip(*s4.data), marker = '*')
        plt.title('Basic signal generation')
        s0.save_type(0)
        s1.save_type(1)
        s2.save_type(2)
        s3.save_type(3)
        s3.save_type(4)
        plt.show()

    #@unittest.skip('')
    def test_loaded_signals (self):
        global _signal_types_table
        import matplotlib.pyplot as plt

        plt.title('Check current loaded signals')
        for i in _signal_types_table:
          plt.plot(*zip(*i))
        plt.show()

    #@unittest.skip(None)
    def test_signal_offset (self):
        import matplotlib.pyplot as plt
        from time import sleep

        dots = 20
        dx = 2.0*np.pi/float(dots)
        signal_0 = [(float(i), float(0.5+np.sin(i*dx)/2.0)) for i in range(dots)]
        s0 = Signal(signal_0, steps = 20)
        s1 = Signal(type = 3, steps=20)
        
        plt.ion()
        for i in range(20):
            s2 = Signal(type = 3, offset = (i%10)/10.0, steps=20)
            plt.plot(*zip(*s0.data), marker = '^')
            plt.plot(*zip(*s1.data), marker = 's')
            plt.plot(*zip(*s2.data), marker = 'p')
            plt.title('Signal offset')
            plt.draw()
            sleep(0.1)
            plt.clf()

    #@unittest.skip(None)
    def test_generate_seed (self):
        
        channels_setup = [(1 if i!=2 else 0,1, (0,255), 0) for i in range(5)]
        i = 0
        while i < 2:
            ap = Programmer(steps = 4, channels_setup = channels_setup, types_subset = [1, 2])
            pprint(ap._seed)
            pprint(ap.get_raw_code()); print('')
            i+=1

    #@unittest.skip(None)
    def test_parse_seed (self):
        
        channels_setup = [(1 if i!=2 else 0,1, (0,255), 0) for i in range(5)]
        ap = Programmer(steps = 5, channels_setup = channels_setup, types_subset = [1, 2])
        to_parse = "--SEED: 3:0.536607, 2:0.554794, 2:0.287840, 1:0.213163--"
        print("To be parsed", to_parse)
        ap.parse_seed(to_parse)
        print("Parsed", ap)

    #@unittest.skip(None)
    def test_generate_code (self):

        channels_setup = [(1 if i!=2 else 0,1, (0,255), 0) for i in range(4)]
        ap = Programmer(steps = 30, channels_setup = channels_setup, types_subset = [1])
        to_parse = "--SEED: 1:0.0, 1:0.5, 1:1.0--"
        print("From seed", to_parse)
        ap.parse_seed(to_parse)
        #print("data", [int(i + 0.5) for i in ap.get_raw_data()[0]])
        while True:
            code = ap.get_raw_code()
            if code or seed:
                break
        for i, v in enumerate(code):
            print("Step:", i, v)
        

if __name__ == '__main__':
    unittest.main()

