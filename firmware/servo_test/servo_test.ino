// servo_test -- wiggle check for the SG90. Runs ONCE, 5 seconds total.
//
// right 1s -> left 1s -> right 1s -> left 1s -> center 1s -> stop.
// Ends pointing at center (90 degrees), then goes quiet. Press the
// board's reset button to run it again.
//
// Wiring (same as the radar): orange -> D9, red -> 5V, brown -> GND.
// When you're done testing, re-upload radar_sweep.ino to get the radar back.

#include <Servo.h>

const int SERVO_PIN = 9;

Servo servo;

// Everything lives in setup() because setup() runs exactly once after
// power-on or reset. loop() below stays empty, so nothing repeats.
void setup() {
  servo.attach(SERVO_PIN);

  servo.write(180);   // full right
  delay(1000);
  servo.write(0);     // full left
  delay(1000);
  servo.write(180);   // right again
  delay(1000);
  servo.write(0);     // left again
  delay(1000);
  servo.write(90);    // center
  delay(1000);

  servo.detach();     // stop sending commands -- servo goes limp and quiet
}

void loop() {
  // nothing: the test already ran
}
