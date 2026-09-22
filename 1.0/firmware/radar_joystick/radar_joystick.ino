// radar_joystick -- the hand-steered radar: joystick + servo + HC-SR04.
//
// You aim the beam with the joystick; the sensor pings wherever you point;
// the board remembers the latest range at each bearing and streams the whole
// picture to the PC in the same protocol as radar_sweep, so the scope
// (run_live.py / run_web.py) works unchanged.
//
// v3: two ping modes, the same search/track split real radars make.
//   * Parked (head still for SETTLE_MS): median of 3 pings. Slow, but one
//     corrupted reading gets outvoted. This is "track mode".
//   * Slow pan: one quick ping per step, so the picture paints as you sweep.
//     This is "search mode". Readings under PAN_MIN_RANGE_M while moving are
//     discarded -- that's the mount ringing, not a target.
//   * Fast pan (stick near full): no pings. A hard-driven head vibrates and
//     the transducer hears its own ringing as a phantom echo centimetres away.
// Power the hungry parts (servo/sensor/joystick) from the kit's power supply
// module + 9V battery feeding the breadboard rails, NOT from the Uno's 5V pin --
// the servo's current spikes brown out the USB rail and fake close targets.
//
// Wiring:
//   Power module -> breadboard rails (both jumpers on 5V), 9V battery in jack
//   Uno GND  -> blue rail           (common ground -- required)
//   Uno 5V   -> nothing             (the module powers the rails now)
//   Servo:    orange -> D9,  red -> red rail,  brown -> blue rail
//   HC-SR04:  TRIG -> D10, ECHO -> D11, VCC -> red rail, GND -> blue rail
//   Joystick: VRx -> A0,  +5V -> red rail,  GND -> blue rail  (VRy, SW unused)

#include <Servo.h>

// ---------------------------------------------------------------- config ---
const int PIN_SERVO = 9;
const int PIN_TRIG  = 10;
const int PIN_ECHO  = 11;
const int PIN_JOY_X = A0;

const int   JOY_DIRECTION = 1;    // set to -1 if push-right steers left
const int   DEADZONE      = 60;   // stick wiggle that counts as "centered"
const float MAX_SPEED     = 2.0;  // degrees per loop at full push

// true if the servo's 0-degree end points to your LEFT (the mount got turned
// around). Mirrors the servo so the scope still reads 0=right / 180=left, and
// flips the stick to match, so stick-right still means beam-right.
const bool  MOUNT_FLIPPED = true;

const int   STEP_DEG = 5;         // bearing resolution of the stored picture
const int   N_CELLS  = 37;        // 0..180 in 5 degree cells

const float SPEED_OF_SOUND = 343.0;   // m/s at 20 C (68 F)
const float MAX_RANGE_M    = 4.0;
const unsigned long ECHO_TIMEOUT_US = 25000UL;

const unsigned long SETTLE_MS   = 30;   // head still this long -> parked: median-of-3 pings
const float PAN_PING_MAX_STEP   = 1.5;  // deg/loop; panning slower than this still pings
const float PAN_MIN_RANGE_M     = 0.15; // while panning, closer than this is ringing, not target
const unsigned long PING_GAP_MS = 30;   // between the 3 pings of one median
const unsigned long EMIT_MS     = 300;  // how often to send the picture to the PC

// ------------------------------------------------------------------ state ---
Servo head;
float angle = 90.0;               // where the beam points right now
float cells[N_CELLS];             // latest range seen at each bearing
unsigned long frame = 0;
unsigned long lastEmit = 0;
unsigned long lastMove = 0;       // when the head last changed position
int joyCenter = 512;              // stick's resting reading, measured at boot

// Point the beam at a bearing. `angle` is always the bearing the scope shows
// (0 = right, 180 = left); this is the one place that knows how the servo is
// physically mounted.
void aim(float bearing) {
  int cmd = (int)bearing;
  head.write(MOUNT_FLIPPED ? 180 - cmd : cmd);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  digitalWrite(PIN_TRIG, LOW);

  head.attach(PIN_SERVO);
  aim(angle);
  lastMove = millis();

  // Measure the stick's true resting value instead of assuming 512. The
  // "centered" reading is half the stick's supply voltage, which depends on
  // whatever rail feeds it -- so hard-coding 512 breaks the moment the supply
  // changes. Keep hands OFF the stick during the first second after power-up.
  long sum = 0;
  for (int i = 0; i < 16; i++) { sum += analogRead(PIN_JOY_X); delay(5); }
  int measured = sum / 16;
  // Only trust a plausibly-centered reading. If the stick was held (or a wire
  // is loose) at boot, the value is nonsense -- fall back to the nominal 512 so
  // a bad calibration can never brick steering.
  joyCenter = (measured > 400 && measured < 624) ? measured : 512;

  for (int i = 0; i < N_CELLS; i++) cells[i] = -1.0;   // nothing seen yet

  Serial.print(F("# radar_joystick v3 fov=180 step="));
  Serial.print(STEP_DEG);
  Serial.print(F(" c="));
  Serial.print(SPEED_OF_SOUND, 1);
  Serial.print(F(" joyCenter="));
  Serial.print(joyCenter);
  Serial.print(F(" (measured "));
  Serial.print(measured);
  Serial.println(F(")"));
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

// Median of 3 pings. One bad reading (sag, ringing, a passing echo) gets
// outvoted; two misses out of three count as a miss, which is what you want.
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

// Send the whole remembered picture as one sweep frame (S / R... / E),
// exactly the protocol radar_sweep speaks, so the Python side needs no changes.
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
  // 1. steer: joystick nudges the beam, rate-controlled like a drone stick
  int push = analogRead(PIN_JOY_X) - joyCenter;
  float step = 0.0;
  if (abs(push) > DEADZONE) {
    int dir = JOY_DIRECTION * (MOUNT_FLIPPED ? -1 : 1);
    step = dir * (push / 512.0) * MAX_SPEED;
    angle = constrain(angle + step, 0.0, 180.0);
    aim(angle);
    lastMove = millis();
  }
  delay(20);            // let the servo take the step

  // 2. ping. Parked -> careful (track mode). Slow pan -> quick (search mode).
  //    Fast pan -> nothing; a hard-driven head vibrates and hears ghosts.
  int cell = constrain((int)(angle / STEP_DEG + 0.5), 0, N_CELLS - 1);
  if (millis() - lastMove >= SETTLE_MS) {
    cells[cell] = pingMedian3();
  } else if (fabs(step) <= PAN_PING_MAX_STEP) {
    float r = pingOnce();
    if (r >= 0.0 && r < PAN_MIN_RANGE_M) r = -1.0;   // mount ringing, not a target
    cells[cell] = r;
  }

  // 3. send the full picture to the scope
  if (millis() - lastEmit >= EMIT_MS) {
    emitFrame();
    lastEmit = millis();
  }
}
