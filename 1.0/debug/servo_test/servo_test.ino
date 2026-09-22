/*
 * servo_test — is the servo alive?
 *
 * Drives ONLY the servo, nothing else. If it doesn't move with this
 * sketch, the problem is the servo, its wiring, or its power — not the
 * radar code.
 *
 * Wiring (same as the radar):
 *   Servo signal (orange/yellow) -> D9
 *   Servo 5V (red)               -> 5V
 *   Servo GND (brown/black)      -> GND
 *
 * How to use:
 *   1. Upload this sketch.
 *   2. Open the Serial Monitor at 115200 baud.
 *   3. It sweeps left-right twice on its own, then listens for commands:
 *        l  = go full LEFT   (180 deg)
 *        r  = go full RIGHT  (0 deg)
 *        c  = go to CENTER   (90 deg)
 *        s  = do one slow sweep
 *
 * What the results mean:
 *   - Moves on command            -> servo is fine; suspect wiring order,
 *                                    the sensor, or the Python side.
 *   - Never moves, no sound       -> check wiring first (signal on D9?
 *                                    ground shared with the Arduino?),
 *                                    then try another servo.
 *   - Buzzes/hums but won't move  -> stripped gears or stalled: replace it.
 *   - Twitches once on power-up   -> it's getting power; signal wire or a
 *                                    weak 5V rail is the likely problem.
 *   - Moves but resets the board  -> power brown-out; servo needs its own
 *                                    5V supply (see bill of materials).
 */

#include <Servo.h>

const int PIN_SERVO = 9;   // same pin as radar_sweep.ino

Servo head;

void goTo(int angleDeg, const char *label) {
  Serial.print(F("-> "));
  Serial.print(label);
  Serial.print(F(" ("));
  Serial.print(angleDeg);
  Serial.println(F(" deg)"));
  head.write(angleDeg);
}

void slowSweep() {
  Serial.println(F("-> slow sweep 0 to 180 and back"));
  for (int a = 0; a <= 180; a += 2) { head.write(a); delay(20); }
  for (int a = 180; a >= 0; a -= 2) { head.write(a); delay(20); }
  Serial.println(F("   sweep done"));
}

void setup() {
  Serial.begin(115200);
  head.attach(PIN_SERVO);

  Serial.println(F("# servo_test: watch the servo now"));
  Serial.println(F("# doing two automatic sweeps..."));
  slowSweep();
  slowSweep();
  head.write(90);

  Serial.println(F("# done. commands: l=left  r=right  c=center  s=sweep"));
}

void loop() {
  if (!Serial.available()) return;

  char cmd = Serial.read();
  switch (cmd) {
    case 'l': case 'L': goTo(180, "LEFT");   break;
    case 'r': case 'R': goTo(0,   "RIGHT");  break;
    case 'c': case 'C': goTo(90,  "CENTER"); break;
    case 's': case 'S': slowSweep();         break;
    case '\n': case '\r': case ' ': break;   // ignore line endings
    default:
      Serial.println(F("? use: l  r  c  s"));
  }
}
