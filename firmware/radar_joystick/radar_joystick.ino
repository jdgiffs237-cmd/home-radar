// radar_joystick -- the hand-steered radar: joystick + servo + HC-SR04.
//
// You aim the beam with the joystick; the sensor pings wherever you point;
// the board remembers the latest range at each bearing and streams the whole
// picture to the PC in the same protocol as radar_sweep, so the scope
// (run_live.py / run_web.py) works unchanged.
//
// Wiring (power rails on the breadboard, since three modules share 5V/GND):
//   Uno 5V  -> breadboard red rail       Uno GND -> breadboard blue rail
//   Servo:    orange -> D9,  red -> red rail,  brown -> blue rail
//   HC-SR04:  TRIG -> D10, ECHO -> D11, VCC -> red rail, GND -> blue rail
//   Joystick: VRx -> A0,  +5V -> red rail,  GND -> blue rail

#include <Servo.h>

// ---------------------------------------------------------------- config ---
const int PIN_SERVO = 9;
const int PIN_TRIG  = 10;
const int PIN_ECHO  = 11;
const int PIN_JOY_X = A0;

const int   JOY_DIRECTION = 1;    // set to -1 if push-right steers left
const int   DEADZONE      = 60;   // stick wiggle that counts as "centered"
const float MAX_SPEED     = 2.0;  // degrees per loop at full push

const int   STEP_DEG = 5;         // bearing resolution of the stored picture
const int   N_CELLS  = 37;        // 0..180 in 5 degree cells

const float SPEED_OF_SOUND = 343.0;   // m/s at 20 C (68 F)
const float MAX_RANGE_M    = 4.0;
const unsigned long ECHO_TIMEOUT_US = 25000UL;

const unsigned long EMIT_MS = 500;    // how often to send the picture to the PC

// ------------------------------------------------------------------ state ---
Servo head;
float angle = 90.0;               // where the beam points right now
float cells[N_CELLS];             // latest range seen at each bearing
unsigned long frame = 0;
unsigned long lastEmit = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  digitalWrite(PIN_TRIG, LOW);

  head.attach(PIN_SERVO);
  head.write((int)angle);

  for (int i = 0; i < N_CELLS; i++) cells[i] = -1.0;   // nothing seen yet

  Serial.print(F("# radar_joystick v1 fov=180 step="));
  Serial.print(STEP_DEG);
  Serial.print(F(" c="));
  Serial.println(SPEED_OF_SOUND, 1);
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
  int push = analogRead(PIN_JOY_X) - 512;
  if (abs(push) > DEADZONE) {
    angle += JOY_DIRECTION * (push / 512.0) * MAX_SPEED;
    angle = constrain(angle, 0.0, 180.0);
    head.write((int)angle);
  }
  delay(20);            // let the servo take the step

  // 2. ping wherever we're pointing, remember it at that bearing
  float range = pingOnce();
  int cell = constrain((int)(angle / STEP_DEG + 0.5), 0, N_CELLS - 1);
  cells[cell] = range;
  delay(40);            // space the pings so old echoes die out

  // 3. twice a second, send the full picture to the scope
  if (millis() - lastEmit >= EMIT_MS) {
    emitFrame();
    lastEmit = millis();
  }
}
