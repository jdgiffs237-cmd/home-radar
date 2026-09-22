// radar_joystick_stepper -- Home Radar 2.0, hand-steered.
//
// The stepper edition of 1.0's radar_joystick v3: you aim the beam with the
// joystick, the sensor pings wherever you point, the board remembers the
// latest range at each bearing and streams the whole picture in the same
// S/R/E protocol -- so run_radar.py / the scope work unchanged.
//
// Keeps v3's search/track split:
//   * Parked (still for SETTLE_MS): median of 3 pings ("track mode").
//   * Slow pan: one quick ping per step, picture paints as you sweep
//     ("search mode"); too-close readings while moving are mount ringing.
//   * Fast pan: no pings -- a hard-driven mount vibrates and the
//     transducer hears its own ringing as phantom close targets.
// New for the stepper: coils release when parked (saves the USB budget,
// quiets the rails), and the centering ritual replaces the servo's
// known-angle luxury.
//
// Wiring (docs/stepper-wiring.html -- everything on Arduino 5V/USB):
//   D2->IN1  D3->IN2  D4->IN3  D5->IN4      HC-SR04: TRIG->D10 ECHO->D11
//   Joystick: VRx->A0                        power: 5V/GND rails + capacitor
//
// Startup: point the sensor STRAIGHT AHEAD by hand within 5 seconds,
// hands OFF the stick (it self-calibrates its center at boot).

#include <Stepper.h>

// ---------------------------------------------------------------- config ---
const int STEPS_PER_REV = 2048;
Stepper motor(STEPS_PER_REV, 2, 4, 3, 5);   // library wants 1-3-2-4 order
const int COIL_PIN_FIRST = 2;
const int COIL_PIN_LAST  = 5;

const int PIN_TRIG  = 10;
const int PIN_ECHO  = 11;
const int PIN_JOY_X = A0;

const int   JOY_DIRECTION = 1;    // set to -1 if push-right steers left
const int   DEADZONE      = 60;   // stick wiggle that counts as "centered"
const float MAX_SPEED     = 2.0;  // degrees per loop at full push
const int   MOTOR_RPM     = 14;

const int   STEP_DEG = 5;         // bearing resolution of the stored picture
const int   N_CELLS  = 37;        // 0..180 in 5 degree cells

const float SPEED_OF_SOUND = 343.0;   // m/s at 20 C (68 F)
const float MAX_RANGE_M    = 4.0;
const unsigned long ECHO_TIMEOUT_US = 25000UL;

const unsigned long SETTLE_MS   = 60;   // still this long -> parked: median-of-3
const float PAN_PING_MAX_STEP   = 1.5;  // deg/loop; panning slower still pings
const float PAN_MIN_RANGE_M     = 0.15; // closer than this while panning = ringing
const unsigned long PING_GAP_MS = 30;   // between the 3 pings of one median
const unsigned long EMIT_MS     = 300;  // how often to send the picture

// ------------------------------------------------------------------ state ---
float angle = 90.0;               // where the beam points (0=right, 180=left)
long  positionSteps = 0;          // shaft position in steps; 0 = 0 deg
float cells[N_CELLS];
unsigned long frame = 0;
unsigned long lastEmit = 0;
unsigned long lastMove = 0;
int  joyCenter = 512;
bool coilsOn = true;

long angleToSteps(float deg) {
  return JOY_DIRECTION * (long)(deg * (STEPS_PER_REV / 2) / 180.0 + 0.5);
}

// Point the beam. Computes the target from the ANGLE every time, so
// rounding never accumulates lap after lap.
void aim(float bearing) {
  long target = angleToSteps(bearing);
  if (target != positionSteps) {
    motor.step((int)(target - positionSteps));
    positionSteps = target;
    coilsOn = true;
  }
}

void releaseCoils() {
  // ~240 mA even at rest, and electrical noise on the rails while the
  // sensor listens. Off while parked; next step re-energizes them.
  if (coilsOn) {
    for (int p = COIL_PIN_FIRST; p <= COIL_PIN_LAST; p++) digitalWrite(p, LOW);
    coilsOn = false;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  digitalWrite(PIN_TRIG, LOW);
  motor.setSpeed(MOTOR_RPM);

  // centering ritual: the human sets the reference, the firmware keeps it
  Serial.println(F("# CENTERING: point the sensor STRAIGHT AHEAD by hand."));
  Serial.println(F("# Hands off the joystick. 5 seconds..."));
  delay(5000);
  positionSteps = angleToSteps(90.0);   // "here" is 90 deg by definition
  lastMove = millis();

  // Measure the stick's true resting value instead of assuming 512 (the
  // centered reading is half the rail voltage, and rails vary). A held
  // stick or loose wire at boot gives nonsense: fall back to 512.
  long sum = 0;
  for (int i = 0; i < 16; i++) { sum += analogRead(PIN_JOY_X); delay(5); }
  int measured = sum / 16;
  joyCenter = (measured > 400 && measured < 624) ? measured : 512;

  for (int i = 0; i < N_CELLS; i++) cells[i] = -1.0;   // nothing seen yet

  Serial.print(F("# radar_joystick_stepper v1 fov=180 step="));
  Serial.print(STEP_DEG);
  Serial.print(F(" c="));
  Serial.print(SPEED_OF_SOUND, 1);
  Serial.print(F(" joyCenter="));
  Serial.println(joyCenter);
}

// One ping. Range in metres, or -1.0 for no echo.
float pingOnce() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(4);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  unsigned long dt = pulseIn(PIN_ECHO, HIGH, ECHO_TIMEOUT_US);
  if (dt == 0) return -1.0;
  float range = (dt * 1e-6 * SPEED_OF_SOUND) / 2.0;
  if (range > MAX_RANGE_M || range < 0.02) return -1.0;
  return range;
}

// Median of 3: one bad reading gets outvoted; 2 of 3 misses is a miss.
float pingMedian3() {
  float a = pingOnce();
  delay(PING_GAP_MS);
  float b = pingOnce();
  delay(PING_GAP_MS);
  float c = pingOnce();

  if (a > b) { float t = a; a = b; b = t; }
  if (b > c) { float t = b; b = c; c = t; }
  if (a > b) { float t = a; a = b; b = t; }
  return b;
}

// The whole remembered picture as one S/R.../E frame -- radar_sweep's
// protocol exactly, so the Python side needs no changes.
void emitFrame() {
  Serial.print(F("S "));
  Serial.println(frame);
  for (int i = 0; i < N_CELLS; i++) {
    Serial.print(F("R "));
    Serial.print(i);
    Serial.print(' ');
    Serial.print(i * STEP_DEG);
    Serial.print(' ');
    Serial.println(cells[i], 3);
  }
  Serial.print(F("E "));
  Serial.print(frame);
  Serial.print(' ');
  Serial.println(N_CELLS);
  frame++;
}

void loop() {
  // 1. steer: stick deflection sets pan speed, like a drone stick
  int push = analogRead(PIN_JOY_X) - joyCenter;
  float step = 0.0;
  if (abs(push) > DEADZONE) {
    step = -(push / 512.0) * MAX_SPEED;   // stick left = beam toward 180
    angle = constrain(angle + step, 0.0, 180.0);
    aim(angle);
    lastMove = millis();
  }
  delay(20);

  // 2. ping. Parked -> careful (track mode), coils off for a quiet rail.
  //    Slow pan -> quick ping (search mode). Fast pan -> nothing.
  int cell = constrain((int)(angle / STEP_DEG + 0.5), 0, N_CELLS - 1);
  if (millis() - lastMove >= SETTLE_MS) {
    releaseCoils();
    cells[cell] = pingMedian3();
  } else if (fabs(step) <= PAN_PING_MAX_STEP) {
    float r = pingOnce();
    if (r >= 0.0 && r < PAN_MIN_RANGE_M) r = -1.0;   // ringing, not a target
    cells[cell] = r;
  }

  // 3. send the full picture to the scope
  if (millis() - lastEmit >= EMIT_MS) {
    emitFrame();
    lastEmit = millis();
  }
}
