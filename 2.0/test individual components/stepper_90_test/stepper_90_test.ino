/*
 * stepper_90_test — is the stepper wired right?
 *
 * Moves the motor 90 degrees, pauses, and repeats 8 times: two full
 * turns, ending exactly where it started. No joystick needed — just the
 * motor, the driver, and power.
 *
 * Wiring (see docs/stepper-wiring.html):
 *   D2 -> IN1     D4 -> IN3      power module +5V -> «+»
 *   D3 -> IN2     D5 -> IN4      all GNDs on one shared rail
 *   Motor cable -> white socket on the ULN2003 board
 *
 * PASS looks like: 8 clean quarter-turns, all the same direction, and
 * the shaft finishes pointing exactly where it began. Put a piece of
 * tape on the shaft as a pointer so you can tell.
 *
 * FAIL modes and what they mean:
 *   - Buzzes/vibrates but doesn't turn  -> two of the IN wires are
 *     swapped (usually D3/D4). Check them against the diagram.
 *   - Turns, but roughly / skips        -> weak power. Module jumper on
 *     3.3V instead of 5V, tired 9V battery, or a missing ground link.
 *   - Nothing at all, no sound          -> driver has no power (its LEDs
 *     should blink while stepping) or motor cable not fully clicked in.
 *   - Ends up NOT quite where it began  -> it skipped steps somewhere;
 *     see "weak power" above.
 */

#include <Stepper.h>

const int STEPS_PER_REV = 2048;        // 28BYJ-48 with its gearbox
const int QUARTER_TURN  = STEPS_PER_REV / 4;   // 512 steps = 90 degrees

// The Stepper library wants the coils in 1-3-2-4 order,
// so the pin list reads D2, D4, D3, D5 — not a typo.
Stepper motor(STEPS_PER_REV, 2, 4, 3, 5);

void setup() {
  Serial.begin(115200);
  motor.setSpeed(10);                  // RPM — gentle and reliable

  // --- centering ---------------------------------------------------
  // A stepper can't find center on its own (no position sensor), so
  // centering works the other way around: YOU point it, IT remembers.
  Serial.println(F("# CENTERING: turn the shaft by hand to point"));
  Serial.println(F("# straight ahead. You have 5 seconds..."));
  delay(5000);

  // small wiggle: 45 deg left, back, 45 deg right, back. Proves both
  // directions work and ends exactly where you pointed it = center.
  motor.step(QUARTER_TURN / 2);
  motor.step(-QUARTER_TURN / 2);
  motor.step(-QUARTER_TURN / 2);
  motor.step(QUARTER_TURN / 2);
  Serial.println(F("# center set. this is 0 deg."));
  delay(1000);

  Serial.println(F("# stepper_90_test: 8 quarter-turns, back to center"));
  Serial.println(F("# put tape on the shaft and note where it points!"));
  delay(2000);                         // time to look at the motor

  for (int i = 1; i <= 8; i++) {
    Serial.print(F("move "));
    Serial.print(i);
    Serial.print(F(" of 8: +90 deg -> "));
    Serial.print(i * 90 % 360);
    Serial.println(F(" deg"));

    motor.step(QUARTER_TURN);
    delay(1000);                       // pause so each move is easy to see
  }

  Serial.println(F("# done: 720 deg total. The shaft should point"));
  Serial.println(F("# EXACTLY where it started. If yes, wiring is a GO."));
}

void loop() {
  // test runs once in setup(); press the board's RESET button to rerun
}
