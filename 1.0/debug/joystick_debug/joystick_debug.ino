/*
 * joystick_debug — steer the servo with the joystick module
 *
 * Push the stick left/right and the servo (and lever) follows in real
 * time. The most direct possible test: your hand in, motion out.
 *
 * Wiring (3 wires on the joystick, that's all):
 *   Servo signal (orange/yellow) -> D9      (same as always)
 *   Servo 5V / GND               -> 5V / GND
 *
 *   Joystick VCC (+5V) -> 5V
 *   Joystick GND       -> GND
 *   Joystick VRx       -> A0    (if moving the stick does nothing, try
 *                                VRy — some modules mount the stick
 *                                rotated 90 deg)
 *
 * How to use:
 *   1. Upload, open Serial Monitor at 115200 baud (optional but nice).
 *   2. Move the stick: full left = 180, full right = 0, centered = 90.
 *      That matches the radar's angle convention (0 = right).
 *
 * What you're checking:
 *   - Servo tracks the stick smoothly -> servo and wiring are good.
 *   - Servo lags, stutters, or the board resets when you sweep fast ->
 *     power problem: the servo is starving the 5V rail.
 *   - Serial angle changes but servo doesn't move -> signal wire to D9.
 */

#include <Servo.h>

const int PIN_SERVO = 9;
const int PIN_JOY_X = A0;

Servo head;
float smoothed = 90.0;    // smoothed angle, so stick jitter doesn't buzz the servo
int lastPrinted = -100;

void setup() {
  Serial.begin(115200);
  head.attach(PIN_SERVO);
  head.write(90);

  Serial.println(F("# joystick_debug: move the stick left/right"));
}

void loop() {
  // stick position -> angle. 0..1023 maps to 180..0 so that pushing
  // the stick left points the servo left (radar convention: 0 = right).
  int raw = analogRead(PIN_JOY_X);
  float target = map(raw, 0, 1023, 180, 0);

  // light smoothing: follow the stick fast, ignore the jitter
  smoothed += 0.3 * (target - smoothed);

  head.write((int)smoothed);

  if (abs((int)smoothed - lastPrinted) >= 2) {
    lastPrinted = (int)smoothed;
    Serial.print(F("angle "));
    Serial.println(lastPrinted);
  }

  delay(15);   // ~65 updates/s -- plenty for a servo
}
