/**********************************************************
  author: Gonzalo Cobos Bergillos
  email: gcobos@gmail.com
**********************************************************/

#include <TimerOne.h>
#include <EEPROM.h>

//#define DEBUG                   // Makes easier to debug servo pulses with an oscilloscope. Do NOT connect servos when debugging

//#define USE_I2C_COMMUNICATION           // Uncomment this to use NUNCHUCK, SNES WIRELESS PAD, etc. Do not enable it unless you have the receiver installed

#ifdef USE_I2C_COMMUNICATION
#include <Wire.h>

#define NUNCHUCK_DEVICE_ADDRESS 0x52
#define NUNCHUCK_READ_LENGTH 6
#endif

#define MEM_FOR_PROGRAMS  1024
#define MAX_CHANNELS    12    // Max is 12

#ifdef DEBUG
  #define PERIOD_IN_USECS   50000
  #define MIN_PULSE_WIDTH   5000
  #define MAX_PULSE_WIDTH   15000
#else
  #define PERIOD_IN_USECS   20000
  #define MIN_PULSE_WIDTH   600
  #define MAX_PULSE_WIDTH   2400
#endif

unsigned char programs[MEM_FOR_PROGRAMS] = {255};  // Enough size for all the programs (beware of the 2Kb total limit on the ATMega328p)
unsigned int total_programs = 0;
unsigned int program_offset = 0;
unsigned int ticks_per_step = 6;
unsigned int total_outputs = MAX_CHANNELS;
boolean uploading = false;
volatile unsigned int step_tick = 0;
volatile unsigned int activity[MAX_CHANNELS];
int delta[MAX_CHANNELS] = {0};                    // Keeps delta to add to current_pos until it reaches desired_pos (speed)
unsigned int desired_pos[MAX_CHANNELS];   // Keeps the desired position for every actuator
unsigned int min_range[MAX_CHANNELS] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};       // Keeps the min range for every channel
unsigned int max_range[MAX_CHANNELS] = {255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255};     // Keeps the max range for every channel
unsigned int inverted_channels = 0;               // Each bit keeps if channel must be inverted (bit 0 being channel 0, ...)
volatile int current_pos[MAX_CHANNELS];           // Keeps the current value for every actuator
volatile int order[MAX_CHANNELS];                 // Keeps the order of every channel
volatile long elapsed;                            // Keeps the time elapsed in a pulse

/// --------------------------------------
/// Control for program execution
/// --------------------------------------
void stopProgram ()
{
  program_offset = 0;  // Stop
}

void runProgram (unsigned char num)
{
  if (num <= total_programs) { // Last program is empty
    program_offset = ((int*)programs)[num - 1]; // Pointer of execution for the program
    //Serial.print("PC: ");
    //Serial.println(program_offset, DEC);
  }
}

void runProgramStep ()
{
  int cmd = 0;        // Keeps latest command read
  int pos = 0;        // Keeps latest position read
  int extra = 0;      // Extra parameters for some commands

  while (program_offset) {
    cmd = programs[program_offset];
    if (cmd == 255) { // Tick (wait to the next step)
      program_offset++;
      break;
    }
    pos = programs[program_offset + 1];
    extra = programs[program_offset + 2];
    program_offset += 2; // Commands using 'extra' parameter will increment program_offset if needed
    processCommand(cmd, pos, extra);
  }
}

/*
   Load configuration from EEPROM or Serial, to RAM or EEPROM
   If `fromSource` = 0, load configuration from EEPROM to RAM
   If `fromSource` = 1, load configuration from Serial to RAM
   If `fromSource` = 2, load configuration from Serial to EEPROM
*/
void loadConfiguration (int fromSource = 0)
{
  unsigned int length, i;
  uploading = true;
  digitalWrite(13, 1);

  // Get configuration length
  if (fromSource) {
    while (Serial.available() < 1);
    // Get code length (lower byte)
    length = Serial.read();
    // Get code length (high byte)
    while (Serial.available() < 1);
    length |= Serial.read() << 8;
  } else {
    // Get code length (lower byte)
    length = EEPROM[0];
    // Get code length (high byte)
    length |= EEPROM[1] << 8;
  }

  length = min(length, (fromSource == 2) ? EEPROM.length() : MEM_FOR_PROGRAMS);
  //Serial.print("Length of the code: ");
  //Serial.println(length);
  // Get total_programs
  if (fromSource) {
    while (Serial.available() < 1);
    total_programs = Serial.read();
  } else {
    total_programs = EEPROM[2];
  }

  // Get ticks_per_step and total_outputs
  if (fromSource) {
    while (Serial.available() < 1);
    ticks_per_step = Serial.read();
  } else {
    ticks_per_step = EEPROM[3];
  }

  if (fromSource == 2) {
    EEPROM.update(0, (unsigned char)(length & 0xff));
    EEPROM.update(1, (unsigned char)(length >> 8));
    EEPROM.update(2, (unsigned int)total_programs);
    EEPROM.update(3, (unsigned int)ticks_per_step);
  }
  
  total_outputs = (ticks_per_step & 15) + 1;
  ticks_per_step = (ticks_per_step >> 4) + 1;

  if (fromSource == 2) {
    for (i = 0; i < 2 + length + (total_outputs << 1); i++) {
      while (Serial.available() < 1);
      EEPROM.update(4 + i, (unsigned char)Serial.read());
      
      // Check if value written is the same as expected
      /*if (i >= (6 + (total_outputs << 1)) && EEPROM[4+i] != programs[i-(6 + (total_outputs << 1))]) {
        for (int j=0; j< i; j++) {
          digitalWrite(13, 0);
          delay(200);
          digitalWrite(13, 1);
          delay(200);
        }
        return;
      }
      */
    }
    uploading = false;
    digitalWrite(13, 0);
    return;
  }

  // Get ranges for every active channel
  for (i = 0; i < total_outputs; i++) {
    if (fromSource) {
      while (Serial.available() < 2);
#ifndef DEBUG
      min_range[i] = map((long)Serial.read(), 0, 255, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
      max_range[i] = map((long)Serial.read(), 0, 255, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
#else
      min_range[i] = MIN_PULSE_WIDTH; Serial.read();
      max_range[i] = MAX_PULSE_WIDTH; Serial.read();
#endif
    } else {
#ifndef DEBUG
      min_range[i] = map((long)EEPROM[(i << 1) + 4], 0, 255, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
      max_range[i] = map((long)EEPROM[(i << 1) + 5], 0, 255, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH);
#else
      min_range[i] = MIN_PULSE_WIDTH;
      max_range[i] = MAX_PULSE_WIDTH;
#endif
    }
  }

  // Get array of bits representing which of the channels are inverted (2-byte array of bits)
  if (fromSource) {
    while (Serial.available() < 1);
    // Get inverted_channels array (lower byte)
    inverted_channels = Serial.read();
    // Get inverted_channels array (high byte)
    while (Serial.available() < 1);
    inverted_channels |= Serial.read() << 8;
  } else {
    // Get inverted_channels array (lower byte)
    inverted_channels = EEPROM[(total_outputs << 1) + 4];
    // Get inverted_channels array (high byte)
    inverted_channels |= EEPROM[(total_outputs << 1) + 5] << 8;
  }
  // Get program offsets and code
  for (i = 0; i < length; i++) {
    if (fromSource) {
      while (Serial.available() < 1);
      programs[i] = Serial.read();
    } else {
      programs[i] = EEPROM[i + (total_outputs << 1) + 6];
    }
  }
  digitalWrite(13, 0);
  uploading = false;
}

/// -----------------------------------------------------
/// Process a command and sets the new position to reach
/// -----------------------------------------------------
void processCommand (unsigned int cmd, unsigned int pos, int extra)
{
  if (uploading) {
    return;
  }

  // Look if the command is control or misc or other
  if (cmd == 253) {         // Jump, branching and delay commands
    if (pos == 1) {             // Sleep for a number of seconds (sleep N)
      program_offset++;
      delay(1000 * extra);
    } else if (pos == 2) {      // Jump by offset (jump N)
      program_offset++;
      program_offset += (extra - 128);
    } else if (pos == 3) {      // Jump if A0 has bigger value than A1 (jleft N)
      program_offset++;
      int tmp = analogRead(0);
      delay(15);
      if (tmp > analogRead(1)) {
        program_offset += (extra - 128);
      }
    } else if (pos == 4) {      // Jump if A1 has bigger value than A0 (jright N)
      program_offset++;
      int tmp = analogRead(1);
      delay(15);
      if (tmp > analogRead(0)) {
        program_offset += (extra - 128);
      }
    } else if (pos == 5) {      // Jump randomly in a 50% probability (jrand N)
      program_offset++;
      if (random(100) >= 50) {
        program_offset += (extra - 128);
      }
    }
    return;
  } else if (cmd == 254) {  // Program control command
    if (pos == 0) {
      stopProgram();
    } else {
      runProgram(pos);
    }
    return;
  } else if (cmd == 255) {  // Misc commands (cannot be included in programs)
    if (pos == 0) {             // Get channels' current positions to the Serial
      Serial.write(total_outputs);
      for (int i = 0; i < total_outputs; i++) {
        Serial.write(current_pos[i]);
      }
    } else if (pos == 1) {      // Get sensors values to Serial
      Serial.write(6);
      for (int i = 0; i < 6; i++) {
        Serial.write(map(analogRead(i), 0, 1023, 0, 255));
        delay(15);
      }
    } else if (pos == 253) {    // Load configuration from Serial to EEPROM
      loadConfiguration(2);
    } else if (pos == 254) {    // Load configuration from EEPROM to RAM
      loadConfiguration(0);
    } else if (pos == 255) {    // Load configuration from Serial to RAM
      loadConfiguration(1);
    }
    Serial.flush();
    return;
  }

  /*
    The structure of a command (byte) is:

    - speed (4 bits 7-4)  Sets the number of transitions to the new position
    - pin (4 bits 3-0)    Selects the actuator to move to a new position
  */
  int speed = 1 + (cmd >> 4);
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
  if (step_tick > 0 && !uploading && total_programs > 0) {
    step_tick--;
  }

  total_active = 0;
  for (i = 0; i < total_outputs; i++) {
    if (activity[i]) {
#ifndef DEBUG
      activity[i]--;
#endif
      order[total_active] = i;
      total_active++;
    }
  }
  if (!total_active) return;             // Nothing to do here

  // Update every active channel towards their desired positions and adjusts deltas
  for (x = 0; x < total_active; x++) {
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
      x |= 1 << (i + 2);
    } else {
      y |= 1 << (i - 6);
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
      PORTD &= ~(1 << (i + 2));           // corresponds to PORTD
    } else {
      PORTB &= ~(1 << (i - 6));           // corresponds to PORTB
    }
    x++;
  }
}


/// --------------------------------------------
/// Setup serial, pins IO and service interrupt
/// --------------------------------------------
void setup()
{
  Serial.begin(57600);       // opens serial port, sets data rate 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 28800, 38400, 57600, or 115200

  DDRD = 0xFC;              // direction variable for port D - make em all outputs except serial pins 0 & 1
  DDRB = 0xFF;              // direction variable for port B - all outputs

#ifdef DEBUG
  for (int it = 0+14; it < 320+14; it++) {
    Serial.print(EEPROM[it], DEC);
    Serial.print(",");
  }
  Serial.println("");
  for (int it = 0; it < 320; it++) {
    Serial.print(programs[it], DEC);
    Serial.print(",");
  }
  Serial.println("");
  for (int it = 0; it < MAX_CHANNELS; it++) {
    Serial.print(min_range[it], DEC);
    Serial.print("-");
    Serial.print(max_range[it], DEC);
    Serial.print(",");
  }
  Serial.println("");
  Serial.print("Total programs: ");
  Serial.println(total_programs, DEC);
  Serial.print("Program offset: ");
  Serial.println(program_offset, DEC);
  Serial.print("Total outputs: ");
  Serial.println(total_outputs, DEC);
  Serial.print("Inverted channels: ");
  Serial.println(inverted_channels, DEC);
  Serial.print("Uploading: ");
  Serial.println(uploading, DEC);
  //while (Serial.available()) Serial.read();

  unsigned int chksum = 0;
  for (int i=0; i < 360; i++) {
    chksum+=(unsigned char)programs[i];
  }
  Serial.print("First: ");
  Serial.println(chksum, DEC);

#endif

  // Load configuration from EEPROM
  loadConfiguration(0);

  for (int i=0; i< MAX_CHANNELS; i++) {
    desired_pos[i] = (min_range[i] + max_range[i]) >> 1;
    current_pos[i] = desired_pos[i];
  }

#ifdef DEBUG
  for (int it = 0+14; it < 320 + 14; it++) {
    Serial.print(EEPROM[it], DEC);
    Serial.print(",");
  }
  Serial.println("");
  for (int it = 0; it < 320; it++) {
    Serial.print(programs[it], DEC);
    Serial.print(",");
  }
  Serial.println("");
  for (int it = 0; it < MAX_CHANNELS; it++) {
    Serial.print(min_range[it], DEC);
    Serial.print("-");
    Serial.print(max_range[it], DEC);
    Serial.print(",");
  }
  Serial.println("");
  Serial.print("Total programs: ");
  Serial.println(total_programs, DEC);
  Serial.print("Program offset: ");
  Serial.println(program_offset, DEC);
  Serial.print("Total outputs: ");
  Serial.println(total_outputs, DEC);
  Serial.print("Inverted channels: ");
  Serial.println(inverted_channels, DEC);
  Serial.print("Uploading: ");
  Serial.println(uploading, DEC);
  //while (Serial.available()) Serial.read();
  chksum = 0;
  for (int i=0; i < 360; i++) {
    chksum+=(unsigned char)programs[i];
  }
  Serial.print("Second: ");
  Serial.print(chksum, DEC);
#endif

  Timer1.initialize(PERIOD_IN_USECS);  // set a timer of length in microseconds
  Timer1.attachInterrupt( setPositionIsr ); // attach the service to control positions

#ifdef USE_I2C_COMMUNICATION
  Wire.begin();    // join i2c bus
#endif  

}

/// --------------------------------------
/// Main loop. Just waiting for commands
/// --------------------------------------

void loop() {
  unsigned int cmd = 0;        // Keeps latest command received
  unsigned int pos = 0;        // Keeps latest position received

  if (uploading) return;
#ifdef USE_I2C_COMMUNICATION
  processNunchuckKeys();
#endif

  // Wait for two bytes to process the command
  if (Serial.available() >= 2) {
    // read the incoming byte:
    cmd = Serial.read();
    pos = Serial.read();
    // Process it
    processCommand(cmd, pos, 0);
  } else if (total_programs && program_offset && !step_tick) {
    step_tick = ticks_per_step;
    runProgramStep();
  }
}

#ifdef USE_I2C_COMMUNICATION
bool KEY_UP, KEY_RIGHT, KEY_LEFT, KEY_DOWN, KEY_SELECT, KEY_START, KEY_A, KEY_B;
int cnt = 0;
uint8_t outbuf[NUNCHUCK_READ_LENGTH];    // array to store arduino output

void processNunchuckKeys()
{
  if (cnt == 0) {
    Wire.requestFrom(NUNCHUCK_DEVICE_ADDRESS, NUNCHUCK_READ_LENGTH, true); // request data from nunchuck
    while (Wire.available())
    {
      outbuf[cnt] = nunchuk_decode_byte(Wire.read());  // receive byte as an integer
      cnt++;
    }

    // If we received the NUNCHUCK_READ_LENGTH bytes, check for key presses
    if (cnt == NUNCHUCK_READ_LENGTH && outbuf[0] == 160 && outbuf[1] == 32 && outbuf[2] == 16 && outbuf[3] == 0 && outbuf[4] + outbuf[5] > 255)
    {
      // Get key presses
      KEY_UP = ~outbuf[5] & 1;
      KEY_RIGHT = ~outbuf[4] & 128;
      KEY_LEFT = ~outbuf[5] & 2;
      KEY_DOWN = ~outbuf[4] & 64;
      KEY_SELECT = ~outbuf[4] & 16;
      KEY_START = ~outbuf[4] & 4;
      KEY_A = ~outbuf[5] & 16;
      KEY_B = ~outbuf[5] & 64;

      digitalWrite (13, KEY_UP || KEY_RIGHT || KEY_LEFT || KEY_DOWN || KEY_SELECT || KEY_START || KEY_A || KEY_B);  // sets the LED on
      if (KEY_UP) processCommand(254, 2, 0);
      if (KEY_DOWN) processCommand(254, 8, 0);
      if (KEY_LEFT) processCommand(254, 4, 0);
      if (KEY_RIGHT) processCommand(254, 6, 0);
      if (KEY_SELECT) processCommand(254, 10, 0);
      if (KEY_START) processCommand(254, 5, 0);
      if (KEY_B) processCommand(254, 7, 0);
      if (KEY_A) processCommand(254, 3, 0);
    }
  }
  cnt = ++cnt % 1000;
}

// Encode data to format that most wiimote drivers except
// only needed if you use one of the regular wiimote drivers
char
nunchuk_decode_byte (char x)
{
  x = (x ^ 0x17) + 0x17;
  return x;
}
#endif    // USE_I2C_COMMUNICATION
