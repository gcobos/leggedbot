/**********************************************************
 author: Gonzalo Cobos Bergillos
 email: gcobos@gmail.com
**********************************************************/

#include <TimerOne.h>

//#define DEBUG_PULSE 1

#define MEM_FOR_PROGRAMS  1100
#define TOTAL_CHANNELS    12    // Max is 12
#ifndef DEBUG_PULSE
  #define PERIOD_IN_USECS   20000
  #define MIN_PULSE_WIDTH   600
  #define MAX_PULSE_WIDTH   2400
#else
  #define PERIOD_IN_USECS   50000
  #define MIN_PULSE_WIDTH   5000
  #define MAX_PULSE_WIDTH   15000
#endif
#define SAFE_PULSE_WIDTH  (MAX_PULSE_WIDTH + MIN_PULSE_WIDTH) / 2

unsigned char programs[MEM_FOR_PROGRAMS] = {255};  // Enough size for all the programs (beware of the 2Kb total limit)
unsigned int total_programs = 0;
unsigned int program_offset = 0;
unsigned int ticks_per_step = 6;
unsigned int total_outputs = TOTAL_CHANNELS;
boolean uploading = false;
volatile unsigned int step_tick = 0;
volatile unsigned int activity[TOTAL_CHANNELS];
int delta[TOTAL_CHANNELS] = {0};                // Keeps delta to add to current_pos until it reaches desired_pos (speed)
unsigned int desired_pos[TOTAL_CHANNELS];       // Keeps the desired position for every actuator
unsigned int min_range[TOTAL_CHANNELS] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};       // Keeps the min range for every channel
unsigned int max_range[TOTAL_CHANNELS] = {255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255};     // Keeps the max range for every channel
unsigned int inverted_channels = 0;             // Each bit keeps if channel must be inverted (bit 0 being channel 0, ...)
volatile int current_pos[TOTAL_CHANNELS];       // Keeps the current value for every actuator
volatile int order[TOTAL_CHANNELS];             // Keeps the order of every channel
volatile long elapsed;                          // Keeps the time lapsed in a pulse

/// --------------------------------------
/// Control for program execution
/// --------------------------------------
void stopProgram ()
{
  program_offset = 0;  // Stop
}

void runProgram (unsigned char num)
{  
  if (num<=total_programs) { // Last program is empty
    program_offset = ((int*)programs)[num-1];  // Pointer of execution for the program
  }
}

void runProgramStep ()
{
  int cmd = 0;        // Keeps latest command read
  int pos = 0;        // Keeps latest position read
  
  while (program_offset) {
    cmd = programs[program_offset];
    if (cmd==255) { // Tick (wait to the next step)
      program_offset++;
      break;
    }
    pos = programs[program_offset+1];
    program_offset+=2;
    processCommand(cmd, pos);
  }
}

void uploadPrograms ()
{
  unsigned int length, i;
  uploading = true;
  
  while (Serial.available()<1);
  // Get code length (lower byte)
  length = Serial.read();
  // Get code length (high byte)
  while (Serial.available()<1);
  length |= Serial.read()<<8;

  if (length>MEM_FOR_PROGRAMS) {
    length=MEM_FOR_PROGRAMS;
  }

  // Get total_programs
  while (Serial.available()<1);
  total_programs = Serial.read();
  
  // Get ticks_per_step and total_outputs
  while (Serial.available()<1);
  ticks_per_step = Serial.read();
  total_outputs = (ticks_per_step & 15)+1;
  ticks_per_step = (ticks_per_step >> 4)+1;
  
  // Get ranges for every active channel
  for (i=0;i<total_outputs;i++) {
    while (Serial.available()<1);
#ifndef DEBUG_PULSE
    min_range[i] = map((long)Serial.read(), 0, 255, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
#else
    min_range[i] = MIN_PULSE_WIDTH; Serial.read();
#endif
    while (Serial.available()<1);
#ifndef DEBUG_PULSE
    max_range[i] = map((long)Serial.read(), 0, 255, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
#else
    max_range[i] = MAX_PULSE_WIDTH; Serial.read();
#endif

  }
  
  // Get array of bits representing which of the channels are inverted (2-byte array of bits)
  while (Serial.available()<1);
  // Get inverted_channels array (lower byte)
  inverted_channels = Serial.read();
  // Get inverted_channels array (high byte)
  while (Serial.available()<1);
  inverted_channels |= Serial.read()<<8;

  // Get program offsets and code
  for (i=0;i<length;i++) {
    while (Serial.available()<1);
    programs[i] = Serial.read();
  }
  uploading = false;
}

/// -----------------------------------------------------
/// Process a command and sets the new position to reach
/// -----------------------------------------------------
void processCommand (unsigned int cmd, unsigned int pos)
{
  if (uploading) return;
  // Look if the command is control or meta
  if (cmd == 254) {  // Control command
    if (pos==0) {
      stopProgram();
      return;
    } else {
      runProgram(pos);
      return;
    }
  } else if (cmd == 255) {  // Meta commands
    if (pos==0) {
      // Get channels' current positions
      Serial.write(total_outputs);
      for (int i=0;i<total_outputs;i++) {
        Serial.write(current_pos[i]);
      }
      Serial.flush();
    } else if (pos==1) {
      // Get sensors values
      Serial.write(6);
      for (int i=0;i<6;i++) {
        Serial.write(map(analogRead(i),0,1023,0,255));
        delay(15);
      }
      Serial.flush();
    } else if (pos==255) {
      uploadPrograms();
    }
    return;
  }
  
  /* 
  The structure of a command (byte) is: 
  
  - speed (4 bits 7-4)  Sets the number of transitions to the new position
  - pin (4 bits 3-0)    Selects the actuator to move to a new position
  */
  int speed = 1+(cmd >> 4);
  int channel = cmd & 15;
  activity[channel] = ticks_per_step << 3;                   // Set the robot into active mode

  if (inverted_channels & (1 << channel)) {
    pos = 255 - pos;
  }
  // Ranges are always given from 0-255, independently of the range configured for the channel
  desired_pos[channel] = (int)map(pos, 0, 255, min_range[channel], max_range[channel]);
  
  // Set the speed for the transition
  delta[channel] = ((long)(desired_pos[channel] - (long)current_pos[channel]) * speed) / 16;
}

/// --------------------------
/// Custom ISR Timer Routine
/// --------------------------
void setPositionIsr()
{
  register int i, x, y;
  int z, total_active;

  // Decreases the tick for program execution
  if (step_tick>0 && !uploading && total_programs>0) {
    step_tick--;
  }

  total_active = 0;
  for (i=0; i<total_outputs; i++) {
    if (activity[i]) {
#ifndef DEBUG_PULSE      
      activity[i]--;
#endif
      order[total_active] = i;
      total_active++;      
    }
  }
  if (!total_active) return;             // Nothing to do here

  // Update every active channel towards their desired positions and adjusts deltas
  for (x=0;x<total_active; x++) {
    i = order[x];
    z = desired_pos[i];
    y = delta[i];
    current_pos[i] += y;
    if (y < 0) {
      if (current_pos[i] <= z) {
        delta[i] = 0;
        current_pos[i] = z;
      }
    } else if (y > 0) {
      if (current_pos[i] >= z) {
        delta[i] = 0;
        current_pos[i] = z;
      }
    } else {
      current_pos[i] = z;
    }
  }

  // Order channels by their current_pos
  for (x = 0; x < total_active - 1; x++) {
    for (y = x + 1; y < total_active; y++) {
      if (current_pos[order[x]] > current_pos[order[y]]) {
        i = order[x];
        order[x] = order[y];
        order[y] = i;
      }
    }
  }  

  // Turn on all the active channels
  x = 0;  // PortD
  y = 0;  // PortB
  for (z = 0; z < total_active; z++) {
    i = order[z];
    if (i < 6) {
      x |= 1 << (i+2);
    } else {
      y |= 1 << (i-6);
    }
  }
  PORTD |= x;              // all outputs except serial pins 0 & 1
  PORTB |= y;              // turn on all pins of ports D & B

  // Go through the pulse turning off the channels when its duty has ended
  x = 0; elapsed = 0;
  while (true) {
    if (x >= total_active) break;
    i = order[x];
    y = current_pos[i];
    if (y > elapsed) {
      delayMicroseconds(y - elapsed);
      elapsed = y + 8;
    }
    if (i < 6) {
      PORTD &= ~(1 << (i+2));             // corresponds to PORTD
    } else {
      PORTB &= ~(1 << (i-6));             // corresponds to PORTB
    }
    x++;
  }
}


/// --------------------------------------------
/// Setup serial, pins IO and service interrupt
/// --------------------------------------------
void setup() 
{
  DDRD=0xFC;                // direction variable for port D - make em all outputs except serial pins 0 & 1
  DDRB=0xFF;                // direction variable for port B - all outputs

  for (int i=0; i<total_outputs; i++) {
    min_range[i] = map((long)min_range[i], 0, 255, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
    max_range[i] = map((long)max_range[i], 0, 255, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
  }
  Serial.begin(57600);       // opens serial port, sets data rate 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 28800, 38400, 57600, or 115200
  Timer1.initialize(PERIOD_IN_USECS);  // set a timer of length in microseconds
  Timer1.attachInterrupt( setPositionIsr ); // attach the service to control positions  
}

/// --------------------------------------
/// Main loop. Just waiting for commands
/// --------------------------------------

void loop() {
  unsigned int cmd = 0;        // Keeps latest command received
  unsigned int pos = 0;        // Keeps latest position received

  if (uploading) return;

  // Wait for two bytes to process the command
  if (Serial.available() >= 2) {
    // read the incoming byte:
    cmd = Serial.read();
    pos = Serial.read();
        
    // Process it
    processCommand(cmd, pos);
  } else if (total_programs && program_offset && !step_tick) {
    step_tick = ticks_per_step;
    runProgramStep();
  }
}

