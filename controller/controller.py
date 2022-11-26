#!/usr/bin/env python3

import serial
import struct
import gevent
from gevent import sleep, spawn
from robot import Robot
import sys

from gevent import monkey
monkey.patch_all()

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

def idle():
	try:
		sleep(0.01)
	except:
		Gtk.main_quit()
	return True
GLib.idle_add(idle)

class RobotController (object):
	"""Robot controller"""

	def __init__(self, robotname):

		#Set the Glade file
		self._robotname = robotname
		self.gladefile = "controller.glade"
		self.wtree = Gtk.Builder()
		self.mode = 0
		self.upload_mode = 0
		self.speed = 0
		self.step = 0
		self.wtree.add_from_file(self.gladefile)
		self.robot = Robot(self._robotname)
		self.program = 1    # 0 means stop (not a program)
		self.chained_trunk_flag = True
		self.modify_code_flag = True

		#Create our dictionay and connect it
		dic = { 
			"on_leg_value_change" : self.leg_value_changed,
			"on_trunk_value_change" : self.trunk_value_changed,
			"on_program_value_changed" : self.program_value_changed,
			"on_code_changed" : self.code_changed,
			"on_code_move_cursor" : self.code_cursor_moved,
			"on_load_clicked" : self.load_clicked,
			"on_save_clicked" : self.save_clicked,
			"on_upload_clicked" : self.upload_clicked,
			"on_execute_clicked" : self.execute_clicked,
			"on_stop_clicked" : self.stop_clicked,
			"on_send_commands_toggled" : self.send_commands_toggled,
			"on_modify_code_toggled" : self.modify_code_toggled,
			"on_chained_trunk_toggled" : self.chained_trunk_toggled,
			"on_clear_clicked" : self.clear_clicked,
			"on_generate_program_clicked" : self.generate_program_clicked,
			"on_use_q_toggled" : self.use_channel_toggled,
			"on_use_w_toggled" : self.use_channel_toggled,
			"on_use_e_toggled" : self.use_channel_toggled,
			"on_use_a_toggled" : self.use_channel_toggled,
			"on_use_s_toggled" : self.use_channel_toggled,
			"on_use_d_toggled" : self.use_channel_toggled,
			"on_use_r_toggled" : self.use_channel_toggled,
			"on_use_t_toggled" : self.use_channel_toggled,
			"on_use_y_toggled" : self.use_channel_toggled,
			"on_use_f_toggled" : self.use_channel_toggled,
			"on_use_g_toggled" : self.use_channel_toggled,
			"on_use_h_toggled" : self.use_channel_toggled,
			"on_min_range_change": self.min_range_changed,
			"on_max_range_change": self.max_range_changed,
			"on_inverted_toggled" : self.inverted_toggled,
			"on_step_changed" : self.step_changed,
			"on_ticks_per_step_changed" : self.ticks_per_step_changed,
			"on_speed_change" : self.speed_changed,
			"on_mode_change" : self.mode_changed,
			"on_upload_mode_change": self.upload_mode_changed,
			"on_MainWindow_destroy" : self.destroy,
		}

		# Get the Main Window, and connect the "destroy" event
		self.window = self.wtree.get_object("MainWindow")
		combo=self.wtree.get_object("mode")
		combo.set_active(0)
		combo=self.wtree.get_object("upload_mode")
		combo.set_active(0)
		codeview=self.wtree.get_object("code")
		self.code_buffer = codeview.get_buffer()

		self.wtree.connect_signals(dic)        
		if (self.window):   
			self.window.connect("destroy", Gtk.main_quit)
		self.window.show()

		# Load config
		self.load_configuration()

		# Load the program
		self.robot.load(self.program)
		self.refresh_code()
		self.set_step(0)

		self.running = True
		sleep(0) # yields

	def destroy (self, widget):
		self.save_configuration()
		self.running = False
		Gtk.main_quit()

	def program_value_changed (self, widget):
		self.program = int(widget.get_value())
		self.refresh_code()
		self.set_step(0)

	def _get_code_text(self):
		return self.code_buffer.get_text(*self.code_buffer.get_bounds(), include_hidden_chars = True)

	def code_changed (self, widget = None, other = None):
		self.robot.set_code(self.program, self._get_code_text())
		self.refresh_code()

	def code_cursor_moved (self, widget, event=None):
		step = self._get_code_text()[0:self.code_buffer.props.cursor_position].count('\n')
		self.set_step(step)

	def load_clicked (self, widget):
		#print("Load from file program #", self.program)
		self.robot.load(self.program)
		self.refresh_code()
		self.set_step(0)

	def save_clicked (self, widget):
		#print("Save to file program #", self.program)
		self.robot.save(self.program)

	def upload_clicked (self, widget):
		self.save_configuration()
		self.robot.upload_programs(self.upload_mode)

	def execute_clicked (self, widget):
		#print("Execute code from program #", self.program)
		self.robot.run(self.program)

	def stop_clicked (self, widget):
		#print("Stop execution")
		self.robot.stop()

	def send_commands_toggled (self, widget):
		self.robot.send_commands_flag = widget.get_active()

	def modify_code_toggled (self, widget):
		self.modify_code_flag = widget.get_active()

	def chained_trunk_toggled (self, widget):
		self.chained_trunk_flag = widget.get_active()

	def clear_clicked (self, widget):
		code=self.wtree.get_object("code")
		self.robot.set_code(self.program, "")
		self.code_buffer.set_text("")

	def refresh_code (self):
		previous_step = self.step
		self.code_buffer.set_text(self.robot.get_code(self.program))
		self.set_step(previous_step);

	def generate_program_clicked (self, widget):
		seed=self.wtree.get_object("program_seed").get_text()
		total_steps=int(self.wtree.get_object("total_steps").get_value())
		signals=self.wtree.get_object("signal_types")
		#print(signals.get_active()) 
		self.robot.generate_code(self.program, steps = total_steps, seed = seed, types_subset = [1,2])
		self.refresh_code()
		self.set_step(0)

	def use_channel_toggled (self, widget):
		channel_name = self._get_name(widget, prefix='use')
		self.robot.setup_channel(channel_name, active = widget.get_active())
		#self.robot.upload_programs()

	def pwm_servo_channel_toggled (self, widget):
		channel_name = self._get_name(widget, prefix='pwm_servo')
		self.robot.setup_channel(channel_name, is_servo = widget.get_active())
		#self.robot.upload_programs()

	def leg_value_changed (self, widget):
		channel_name = self._get_name(widget, prefix='channel')
		pos = int(widget.get_value())
		self.robot.set_position(self.program, self.step, channel_name, self.speed, self.mode, pos)
		channels_setup_notebook = self.wtree.get_object('channels_setup')
		channels_setup_notebook.set_current_page(self.robot.CHANNELS.index(channel_name))
		if self.modify_code_flag:
			self.refresh_code()

	def min_range_changed (self, widget):
		channel_name = self._get_name(widget, prefix='min_range')
		self.robot.setup_channel(channel_name, min_range = int(widget.get_value()))

	def max_range_changed (self, widget):
		channel_name = self._get_name(widget, prefix='max_range')
		self.robot.setup_channel(channel_name, max_range = int(widget.get_value()))

	def inverted_toggled (self, widget):
		channel_name = self._get_name(widget, prefix='inverted')
		self.robot.setup_channel(channel_name, inverted = int(widget.get_active()))

	def trunk_value_changed (self, widget):
		channel_name = self._get_name(widget, prefix='channel')
		pos = int(widget.get_value())
		if self.chained_trunk_flag:
			if channel_name=="W":
				other_channel="S"
				other=self.wtree.get_object("channel_s")
			elif channel_name=="S":
				other_channel="W"
				other=self.wtree.get_object("channel_w")
			other_pos = 255 - pos
			other.set_value(other_pos)
		self.robot.set_position(self.program, self.step, channel_name, self.speed, self.mode, pos)

		channels_setup_notebook = self.wtree.get_object('channels_setup')
		channels_setup_notebook.set_current_page(self.robot.CHANNELS.index(channel_name))

		if self.chained_trunk_flag:
			self.robot.set_position(self.program, self.step, other_channel, self.speed, self.mode, other_pos)
		if self.modify_code_flag:
			self.refresh_code()

	def speed_changed (self, widget):
		self.speed = int(widget.get_value())-1
		#print("Speed set to", self.speed+1)

	def ticks_per_step_changed (self, widget):
		self.robot.ticks_per_step = int(widget.get_value())

	def step_changed (self, widget):
		step = int(widget.get_value())
		self.set_step(step)

	def set_step (self, step):
		step_combo=self.wtree.get_object("step")
		step_combo.set_value(step)
		code=self.wtree.get_object("code")
		iter1 = self.code_buffer.get_iter_at_line(step)
		if step != self.step:
			#self.code_buffer.place_cursor(iter1)
			self.step = step

	def mode_changed (self, widget):
		self.mode = int(widget.get_active())
		#print("Mode set to", self.mode + 1)

	def upload_mode_changed (self, widget):
		self.upload_mode = int(widget.get_active())
		print("Upload mode set to", self.upload_mode + 1)

	def load_config (self, suffix = ''):
		with open('%s%s.conf' % (prefix, suffix), 'r') as f:
			config = yaml.load(f)

	def load_configuration (self):
		custom = self.robot.load_config()
		# Populate the widges with the config loaded
		self.wtree.get_object("ticks_per_step").set_value(self.robot.ticks_per_step)
		self.wtree.get_object("send_commands").set_active(self.robot.send_commands_flag)
		self.wtree.get_object("modify_code").set_active(self.modify_code_flag)
		for channel_index, setup in enumerate(self.robot._channels_setup):
			active, is_servo, ranges, inverted = setup
			channel = self.robot.CHANNELS[channel_index].lower()
			self.wtree.get_object("use_%s" % channel).set_active(active)
			#self.wtree.get_object("pwm_servo_%s" % channel).set_active(is_servo)
			self.wtree.get_object("min_range_%s" % channel).set_value(int(ranges[0]))
			self.wtree.get_object("max_range_%s" % channel).set_value(int(ranges[1]))
			self.wtree.get_object("inverted_%s" % channel).set_active(inverted)

		# Custom variables
		self.chained_trunk_flag = custom.get('chained_trunk')
		self.wtree.get_object("chained_trunk").set_active(self.chained_trunk_flag if self.chained_trunk_flag is not None else True)

	def save_configuration (self):
		self.robot.save_config(custom = {'chained_trunk': self.chained_trunk_flag})

	def _get_name(self, obj, prefix=''):
		return Gtk.Buildable.get_name(obj).replace(prefix + "_", "").upper()

if __name__ == "__main__":

	if len(sys.argv) < 2:
		print("Show the controller interface for a robot with the name given as the first parameter")
		print(f"Use: {sys.argv[0]} robotname")
	else:
		RobotController(sys.argv[1])
		Gtk.main()
