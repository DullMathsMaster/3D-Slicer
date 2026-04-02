#!/usr/bin/env python3
"""
X-Y Rack Stepper Motor Controller
===================================
Hardware:  Raspberry Pi 2B  +  2x ULN2003 driver  +  2x 28BYJ-48 motor
           1 limit switch per axis (at the BACKWARD end of each rack)
           4 control buttons (forward/backward per axis)

Behaviour:
  - Hold a control button to drive the motor in that direction.
  - When the limit switch is triggered the motor stops immediately.
  - After a limit switch event the motor may only travel MAX_ROTATIONS
    rotations in the FORWARD direction (software cap).
"""

import RPi.GPIO as GPIO
import time
import threading

# =============================================================================
# PIN CONFIGURATION  (BCM / GPIO numbering)
# =============================================================================

# Motor X  →  ULN2003 #1  (IN1, IN2, IN3, IN4)
MOTOR_X_PINS = [17, 18, 27, 22]

# Motor Y  →  ULN2003 #2  (IN1, IN2, IN3, IN4)
MOTOR_Y_PINS = [5, 6, 13, 19]

# Limit switches – one per motor, at the BACKWARD end of each rack
# Wire each switch between its GPIO pin and GND (active LOW)
X_LIMIT = 23
Y_LIMIT = 25

# Control buttons – wire each button between its GPIO pin and GND (active LOW)
BTN_X_FWD = 12   # Move X forward  (hold)
BTN_X_BWD = 16   # Move X backward (hold)
BTN_Y_FWD = 20   # Move Y forward  (hold)
BTN_Y_BWD = 21   # Move Y backward (hold)

# =============================================================================
# CONSTANTS
# =============================================================================
MAX_ROTATIONS = 80       # Max rotations allowed in forward direction from bound
STEPS_PER_REV = 4096     # 28BYJ-48 in half-step mode
STEP_DELAY    = 0.0005   # Seconds between steps (~2 s per full revolution)

# 8-phase half-step sequence for 28BYJ-48
HALF_STEP_SEQ = [
    [1, 0, 0, 1],
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
]

# =============================================================================
# GPIO SETUP
# =============================================================================
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

for pin in MOTOR_X_PINS + MOTOR_Y_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

for pin in [X_LIMIT, Y_LIMIT,
            BTN_X_FWD, BTN_X_BWD, BTN_Y_FWD, BTN_Y_BWD]:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# =============================================================================
# MOTOR CONTROLLER
# =============================================================================

class MotorController:
    """
    Controls a single ULN2003-driven stepper motor with:
      - One hardware limit switch at the BACKWARD end.
      - A soft rotation cap of MAX_ROTATIONS in the FORWARD direction
        once the limit switch has been triggered.
    """

    FWD =  1
    BWD = -1

    def __init__(self, name: str, pins: list, limit_pin: int):
        self.name      = name
        self.pins      = pins
        self.limit_pin = limit_pin   # GPIO pin for the limit switch

        self._step_idx  = 0
        self._position  = 0          # Absolute step counter (signed)

        # Step position recorded when the limit switch was triggered.
        # None = switch has not been triggered yet this session.
        self._bound_pos = None

        self._running   = False
        self._direction = 0
        self._thread    = None
        self._lock      = threading.Lock()

    # ------------------------------------------------------------------ #
    # Coil helpers                                                         #
    # ------------------------------------------------------------------ #

    def _set_coils(self, row):
        for pin, val in zip(self.pins, row):
            GPIO.output(pin, val)

    def _release_coils(self):
        """De-energise all coils to save power and reduce heat."""
        for pin in self.pins:
            GPIO.output(pin, GPIO.LOW)

    def _do_step(self, direction):
        self._step_idx = (self._step_idx + direction) % len(HALF_STEP_SEQ)
        self._set_coils(HALF_STEP_SEQ[self._step_idx])
        self._position += direction

    # ------------------------------------------------------------------ #
    # Movement permission logic                                            #
    # ------------------------------------------------------------------ #

    def _movement_allowed(self, direction):
        """
        Returns True if one more step in `direction` is permitted.

        BACKWARD rules:
          1. Limit switch is active (LOW)  → record bound, hard stop.
          2. Already at the recorded bound position → block.

        FORWARD rules:
          3. Soft cap: if the limit switch has ever been triggered,
             allow at most MAX_ROTATIONS steps forward from that position.
        """
        if direction == self.BWD:
            # Rule 1: hardware limit switch
            if GPIO.input(self.limit_pin) == GPIO.LOW:
                # Always update to the outermost (smallest) position seen
                if self._bound_pos is None or self._position < self._bound_pos:
                    self._bound_pos = self._position
                    print(f"[Motor {self.name}] Limit switch triggered "
                          f"(position={self._position})")
                return False

            # Rule 2: already at recorded bound
            if self._bound_pos is not None and self._position <= self._bound_pos:
                return False

        elif direction == self.FWD:
            # Rule 3: soft rotation cap (only active once bound is known)
            if self._bound_pos is not None:
                ceiling = self._bound_pos + MAX_ROTATIONS * STEPS_PER_REV
                if self._position >= ceiling:
                    print(f"[Motor {self.name}] Forward limit reached "
                          f"({MAX_ROTATIONS} rotations from bound)")
                    return False

        return True

    # ------------------------------------------------------------------ #
    # Run loop (background thread)                                         #
    # ------------------------------------------------------------------ #

    def _run(self):
        while self._running:
            if not self._movement_allowed(self._direction):
                self._running = False
                break
            self._do_step(self._direction)
            time.sleep(STEP_DELAY)
        self._release_coils()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self, direction):
        """Begin continuous movement in `direction` (FWD=+1, BWD=-1)."""
        with self._lock:
            if not self._movement_allowed(direction):
                label = "FWD" if direction == self.FWD else "BWD"
                print(f"[Motor {self.name}] {label} blocked – at limit or bound")
                return

            # Stop any current movement first
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)

            self._direction = direction
            self._running   = True
            self._thread    = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        """Immediately stop movement and de-energise coils."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._release_coils()

    @property
    def position(self):
        return self._position


# =============================================================================
# INSTANTIATE MOTORS
# =============================================================================

motor_x = MotorController("X", MOTOR_X_PINS, X_LIMIT)
motor_y = MotorController("Y", MOTOR_Y_PINS, Y_LIMIT)


# =============================================================================
# BUTTON CALLBACKS
# Both-edge detection: LOW = pressed → start moving, HIGH = released → stop
# =============================================================================

_BUTTON_MAP = {
    BTN_X_FWD: (motor_x, MotorController.FWD),
    BTN_X_BWD: (motor_x, MotorController.BWD),
    BTN_Y_FWD: (motor_y, MotorController.FWD),
    BTN_Y_BWD: (motor_y, MotorController.BWD),
}

def _btn_event(channel):
    motor, direction = _BUTTON_MAP[channel]
    if GPIO.input(channel) == GPIO.LOW:   # pressed
        motor.start(direction)
    else:                                  # released
        motor.stop()

for btn_pin in _BUTTON_MAP:
    GPIO.add_event_detect(
        btn_pin,
        GPIO.BOTH,
        callback=_btn_event,
        bouncetime=50          # 50 ms debounce
    )


# =============================================================================
# MAIN LOOP
# =============================================================================

print("=" * 60)
print("  X-Y Rack Controller  –  Raspberry Pi 2B")
print("=" * 60)
print(f"  X Forward   →  GPIO {BTN_X_FWD}  (hold)")
print(f"  X Backward  →  GPIO {BTN_X_BWD}  (hold)  [limit on GPIO {X_LIMIT}]")
print(f"  Y Forward   →  GPIO {BTN_Y_FWD}  (hold)")
print(f"  Y Backward  →  GPIO {BTN_Y_BWD}  (hold)  [limit on GPIO {Y_LIMIT}]")
print(f"\n  Max forward rotations from limit : {MAX_ROTATIONS}")
print("\n  Press Ctrl-C to exit.\n")

try:
    while True:
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nShutting down...")

finally:
    motor_x.stop()
    motor_y.stop()
    GPIO.cleanup()
    print("GPIO cleaned up. Goodbye.")