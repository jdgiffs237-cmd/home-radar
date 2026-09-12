/*
 * radar_sweep — servo-scanned ultrasonic rangefinder, radar-style
 *
 * Sweeps a servo across a field of view, pings an HC-SR04 at each step,
 * and streams one CSV-ish line per return over serial.
 *
 * Wiring:
 *   Servo signal -> D9      HC-SR04 TRIG -> D10
 *   Servo 5V/GND -> 5V/GND  HC-SR04 ECHO -> D11
 *                           HC-SR04 VCC/GND -> 5V/GND
 *
 * Protocol (115200 baud):
 *   # <free text>                    banner / comments, ignore
 *   S <frame>                        start of sweep
 *   R <index> <angle_deg> <range_m>  one return; range -1.0 means no echo
 *   E <frame> <count>                end of sweep
 *
 * The Python side (radar/serial_link.py) parses exactly this.
 */

#include <Servo.h>

// ---------------------------------------------------------------- config ---
const int PIN_SERVO = 9;
const int PIN_TRIG  = 10;
const int PIN_ECHO  = 11;

const int   FOV_MIN_DEG   = 0;      // servo travel, inclusive
const int   FOV_MAX_DEG   = 180;
const int   STEP_DEG      = 5;      // 5 deg -> 37 returns -> ~2 s per frame
const int   ANGLE_OFFSET  = 0;      // mechanical zero correction, degrees

const int   SETTLE_MS     = 40;     // let the servo stop ringing before pinging
const int   PING_GAP_MS   = 60;     // min spacing so old echoes die out
const int   PINGS_PER_STEP = 3;     // median-of-N rejects flyers cheaply

const float SPEED_OF_SOUND = 343.0; // m/s at 20 C (68 F). 331.0 + 0.606 * (degF - 32) / 1.8
const float MAX_RANGE_M    = 4.0;
const unsigned long ECHO_TIMEOUT_US = 25000UL;  // ~4.3 m round trip

// ------------------------------------------------------------------ state ---
Servo head;
unsigned long frame = 0;
int angle = FOV_MIN_DEG;
int direction = +1;   // sweep back and forth rather than snapping home

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  digitalWrite(PIN_TRIG, LOW);

  head.attach(PIN_SERVO);
  head.write(FOV_MIN_DEG + ANGLE_OFFSET);
  delay(500);   // servo needs a moment to reach the start of travel

  Serial.print(F("# radar_sweep v1 fov="));
  Serial.print(FOV_MAX_DEG - FOV_MIN_DEG);
  Serial.print(F(" step="));
  Serial.print(STEP_DEG);
  Serial.print(F(" c="));
  Serial.println(SPEED_OF_SOUND, 1);
}

/*
 * One ping. Returns range in metres, or -1.0 on timeout / out of range.
 */
float pingOnce() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(4);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);          // HC-SR04 wants a 10 us trigger
  digitalWrite(PIN_TRIG, LOW);

  unsigned long dt = pulseIn(PIN_ECHO, HIGH, ECHO_TIMEOUT_US);
  if (dt == 0) return -1.0;       // no echo came back before the timeout

  float range = (dt * 1e-6 * SPEED_OF_SOUND) / 2.0;
  if (range > MAX_RANGE_M || range < 0.02) return -1.0;
  return range;
}

/*
 * Median of PINGS_PER_STEP pings. Ultrasonic returns are occasionally
 * wildly wrong (a stray echo, a missed edge); a median throws those out
 * without the lag an average would add. Misses (-1) are voted on too:
 * if most pings missed, the cell is a miss.
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

  // insertion sort; misses sort to the front and get skipped below
  for (int i = 1; i < PINGS_PER_STEP; i++) {
    float key = v[i];
    int j = i - 1;
    while (j >= 0 && v[j] > key) { v[j + 1] = v[j]; j--; }
    v[j + 1] = key;
  }
  // median of the valid entries only
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

  // sweep across the FOV in whichever direction we're currently going
  int start = (direction > 0) ? FOV_MIN_DEG : FOV_MAX_DEG;
  int stop  = (direction > 0) ? FOV_MAX_DEG : FOV_MIN_DEG;

  for (angle = start;
       (direction > 0) ? (angle <= stop) : (angle >= stop);
       angle += direction * STEP_DEG) {

    head.write(constrain(angle + ANGLE_OFFSET, 0, 180));
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
  direction = -direction;   // reverse for the next sweep
}
