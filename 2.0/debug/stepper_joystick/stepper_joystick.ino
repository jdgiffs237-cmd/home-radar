/*
 * stepper_joystick — steer the 28BYJ-48 stepper with the joystick
 *
 * The 2.0 version of joystick_debug: same idea, new motor. Push the
 * stick and the motor turns that way; further = faster; let go = stop.
 *
 * Wiring (full diagram on the "Stepper Upgrade Wiring" page):
 *   D2 -> IN1     D4 -> IN3        Joystick VCC -> 5V
 *   D3 -> IN2     D5 -> IN4        Joystick GND -> GND
 *   5V -> «+»     GND -> «−»       Joystick VRx -> A0
 *   Motor cable -> white socket on the ULN2003 board (only fits one way)
 *
 * The big difference from the servo: a stepper doesn't know where it's
 * pointing. It only knows "I've taken N steps since power-on." So this
 * sketch counts steps and prints the angle it THINKS it's at — point the
 * motor straight ahead by hand before plugging in, and the count starts
 * out true.
 *
 * Numbers: 2048 steps per full turn, so one step = ~0.18 degrees.
 * (Your servo could only be told whole degrees — 5x coarser!)
 */

#include <Stepper.h>

const int STEPS_PER_REV = 2048;   // 28BYJ-48 with its internal gearbox

// Gotcha: the Stepper library wants the coils in 1-3-2-4 order,
// so the pin list reads D2, D4, D3, D5 — not a typo.
Stepper motor(STEPS_PER_REV, 2, 4, 3, 5);

const int PIN_JOY_X = A0;
const int DEADBAND = 60;          // stick wobble around center to ignore

long position = 0;                // steps away from where it started
long lastPrinted = 0;

void setup() {
  Serial.begin(115200);
  Serial.println(F("# stepper_joystick: push the stick to turn the motor"));
  Serial.println(F("# it starts at 0 deg -- point it straight ahead by hand first"));
}

void releaseCoils() {
  // The Stepper library leaves the coils energized (~240 mA!) even when
  // the motor is sitting still. On USB power that's most of our budget,
  // so cut them off while idle -- the next motor.step() re-energizes
  // them automatically. The gearbox has enough friction to hold position.
  for (int p = 2; p <= 5; p++) digitalWrite(p, LOW);
}

void loop() {
  int raw = analogRead(PIN_JOY_X);   // 0..1023, ~512 centered
  int deflection = raw - 512;

  if (abs(deflection) < DEADBAND) {  // stick centered: rest, coils off
    releaseCoils();
    return;
  }

  // further push = faster spin (5..15 RPM is this motor's happy range)
  int rpm = map(abs(deflection), DEADBAND, 512, 5, 15);
  motor.setSpeed(rpm);

  // small chunks keep the stick responsive; sign sets direction.
  // stick left (raw low) = positive steps = counterclockwise-ish;
  // if yours turns the wrong way, swap to (deflection > 0) below.
  int chunk = (deflection < 0) ? 8 : -8;
  motor.step(chunk);
  position += chunk;

  long angleDeg = (position * 360L) / STEPS_PER_REV;
  if (labs(angleDeg - lastPrinted) >= 2) {
    lastPrinted = angleDeg;
    Serial.print(F("angle "));
    Serial.println(angleDeg);
  }
}
