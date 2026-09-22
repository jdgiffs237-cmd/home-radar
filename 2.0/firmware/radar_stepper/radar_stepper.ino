/*
 * radar_stepper — Home Radar 2.0: stepper-scanned ultrasonic radar
 *
 * Same job as 1.0's radar_sweep.ino, new scan axis: the 28BYJ-48 stepper
 * sweeps the HC-SR04 across 180 degrees and streams the SAME serial
 * protocol — so every bit of the 1.0 Python (run_live.py, run_web.py,
 * detect, track) works against this unchanged.
 *
 * Wiring (see docs/stepper-wiring.html; everything on Arduino 5V/USB):
 *   D2 -> IN1     D4 -> IN3       HC-SR04 TRIG -> D10
 *   D3 -> IN2     D5 -> IN4       HC-SR04 ECHO -> D11
 *   ULN2003 «+»/«−» and HC-SR04 VCC/GND -> 5V / GND rails
 *   capacitor across the rails · motor cable in the white socket
 *   Mount: tape the sensor to the stepper shaft, eyes facing out,
 *   with enough cable slack for a half-turn.
 *
 * Startup (steppers can't sense position):
 *   You get 5 seconds to point the sensor STRAIGHT AHEAD (90 deg) by
 *   hand. The firmware takes it from there.
 *
 * Protocol (115200 baud — identical to 1.0):
 *   # <free text>                    banner / comments, ignore
 *   S <frame>                        start of sweep
 *   R <index> <angle_deg> <range_m>  one return; range -1.0 means no echo
 *   E <frame> <count>                end of sweep
 */

#include <Stepper.h>

// ---------------------------------------------------------------- config ---
const int STEPS_PER_REV = 2048;     // 28BYJ-48 with its gearbox
// Stepper library wants coil order 1-3-2-4: pin list D2, D4, D3, D5.
Stepper motor(STEPS_PER_REV, 2, 4, 3, 5);
const int COIL_PIN_FIRST = 2;
const int COIL_PIN_LAST  = 5;

const int PIN_TRIG = 10;
const int PIN_ECHO = 11;

const int FOV_MIN_DEG = 0;          // sweep range, inclusive
const int FOV_MAX_DEG = 180;
const int STEP_DEG    = 5;          // 5 deg -> 37 returns per sweep
const int DIRECTION   = +1;         // flip to -1 if your scope sweeps mirrored

const int MOTOR_RPM     = 12;
const int SETTLE_MS     = 20;       // steppers barely ring, but let it rest
const int PING_GAP_MS   = 60;       // min spacing so old echoes die out
const int PINGS_PER_STEP = 3;       // median-of-N rejects flyers
                                    // (drop to 1 for faster, noisier frames)

const float SPEED_OF_SOUND = 343.0; // m/s at 20 C (68 F)
const float MAX_RANGE_M    = 4.0;
const unsigned long ECHO_TIMEOUT_US = 25000UL;  // ~4.3 m round trip

// ------------------------------------------------------------------ state ---
long positionSteps = 0;   // where the shaft is, in steps; 0 steps = 0 deg
unsigned long frame = 0;
int direction = +1;       // sweep back and forth rather than snapping home

// 180 deg = half a revolution = 1024 steps. Always compute the target from
// the ANGLE, never accumulate "steps per 5 deg" -- 1024/36 isn't a whole
// number and the rounding error would build up lap after lap.
long angleToSteps(int deg) {
  return DIRECTION * (((long)deg * (STEPS_PER_REV / 2) + 90) / 180);
}

void moveToAngle(int deg) {
  long target = angleToSteps(deg);
  motor.step((int)(target - positionSteps));
  positionSteps = target;
}

void releaseCoils() {
  // The driver holds ~240 mA even at rest. Cut the coils while pinging:
  // saves the USB budget AND quiets the rails during the measurement.
  // The next motor.step() re-energizes automatically; the gearbox holds.
  for (int p = COIL_PIN_FIRST; p <= COIL_PIN_LAST; p++) digitalWrite(p, LOW);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  digitalWrite(PIN_TRIG, LOW);
  motor.setSpeed(MOTOR_RPM);

  // centering ritual: the human sets the reference, the firmware keeps it
  Serial.println(F("# CENTERING: point the sensor STRAIGHT AHEAD by hand."));
  Serial.println(F("# You have 5 seconds..."));
  delay(5000);
  positionSteps = angleToSteps(90);   // "here" is 90 deg by definition
  moveToAngle(FOV_MIN_DEG);           // drive to the start of the sweep

  Serial.print(F("# radar_stepper v1 fov="));
  Serial.print(FOV_MAX_DEG - FOV_MIN_DEG);
  Serial.print(F(" step="));
  Serial.print(STEP_DEG);
  Serial.print(F(" c="));
  Serial.println(SPEED_OF_SOUND, 1);
}

/*
 * One ping. Returns range in metres, or -1.0 on timeout / out of range.
 * (Same logic as 1.0 -- the sensor didn't change, only the motor did.)
 */
float pingOnce() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(4);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);          // HC-SR04 wants a 10 us trigger
  digitalWrite(PIN_TRIG, LOW);

  unsigned long dt = pulseIn(PIN_ECHO, HIGH, ECHO_TIMEOUT_US);
  if (dt == 0) return -1.0;       // no echo before the timeout

  float range = (dt * 1e-6 * SPEED_OF_SOUND) / 2.0;
  if (range > MAX_RANGE_M || range < 0.02) return -1.0;
  return range;
}

/*
 * Median of PINGS_PER_STEP pings; misses vote too. Same as 1.0.
 */
float pingMedian() {
  float v[PINGS_PER_STEP];
  int misses = 0;

  for (int i = 0; i < PINGS_PER_STEP; i++) {
    v[i] = pingOnce();
    if (v[i] < 0) misses++;
    if (i < PINGS_PER_STEP - 1) delay(PING_GAP_MS);
  }
  if (misses * 2 > PINGS_PER_STEP) return -1.0;

  for (int i = 1; i < PINGS_PER_STEP; i++) {  // insertion sort
    float key = v[i];
    int j = i - 1;
    while (j >= 0 && v[j] > key) { v[j + 1] = v[j]; j--; }
    v[j + 1] = key;
  }
  int first = 0;
  while (first < PINGS_PER_STEP && v[first] < 0) first++;
  int nValid = PINGS_PER_STEP - first;
  return v[first + nValid / 2];
}

void loop() {
  Serial.print(F("S "));
  Serial.println(frame);

  int index = 0;
  int count = 0;

  int start = (direction > 0) ? FOV_MIN_DEG : FOV_MAX_DEG;
  int stop  = (direction > 0) ? FOV_MAX_DEG : FOV_MIN_DEG;

  for (int angle = start;
       (direction > 0) ? (angle <= stop) : (angle >= stop);
       angle += direction * STEP_DEG) {

    moveToAngle(angle);
    releaseCoils();               // quiet + thrifty while measuring
    delay(SETTLE_MS);

    float range = pingMedian();

    Serial.print(F("R "));
    Serial.print(index);
    Serial.print(' ');
    Serial.print(angle);
    Serial.print(' ');
    Serial.println(range, 3);

    index++;
    count++;
    delay(PING_GAP_MS);
  }

  Serial.print(F("E "));
  Serial.print(frame);
  Serial.print(' ');
  Serial.println(count);

  frame++;
  direction = -direction;         // reverse for the next sweep
}
