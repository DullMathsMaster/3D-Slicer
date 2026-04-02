from machine import Pin
import time

# Initialize Motor 1 output pins
m1_pins = [Pin(2, Pin.OUT), Pin(3, Pin.OUT), Pin(4, Pin.OUT), Pin(5, Pin.OUT)]

# Initialize Motor 2 output pins
m2_pins = [Pin(6, Pin.OUT), Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)]

# Initialize Button input pins with internal pull-down resistors
btn_m1_cw = Pin(10, Pin.IN, Pin.PULL_DOWN)
btn_m1_ccw = Pin(11, Pin.IN, Pin.PULL_DOWN)
btn_m2_cw = Pin(12, Pin.IN, Pin.PULL_DOWN)
btn_m2_ccw = Pin(13, Pin.IN, Pin.PULL_DOWN)

# 8-step sequence for 28BYJ-48 stepper motors
step_sequence = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1]
]

# 512 iterations of the 8-step sequence equals roughly 1 full revolution (4096 steps)
STEPS_PER_PRESS = 512  
STEP_DELAY = 0.001     # Time between steps; adjust to change motor speed

def step_motor(motor_pins, steps, direction):
    """
    Moves the selected motor by the specified number of steps.
    direction: 1 for clockwise, -1 for anticlockwise
    """
    step_index = 0
    for _ in range(steps):
        for i in range(4):
            motor_pins[i].value(step_sequence[step_index][i])
        
        # Advance the sequence based on direction
        step_index = (step_index + direction) % len(step_sequence)
        time.sleep(STEP_DELAY)
        
    # Turn off all coils to prevent the motor from overheating while idle
    for pin in motor_pins:
        pin.value(0)

print("System ready. Press buttons to move motors.")

# Main loop
while True:
    # Check Motor 1 buttons
    if btn_m1_cw.value() == 1:
        step_motor(m1_pins, STEPS_PER_PRESS, 1)
        time.sleep(0.2)  # Short delay for button debouncing
        
    elif btn_m1_ccw.value() == 1:
        step_motor(m1_pins, STEPS_PER_PRESS, -1)
        time.sleep(0.2)
        
    # Check Motor 2 buttons
    if btn_m2_cw.value() == 1:
        step_motor(m2_pins, STEPS_PER_PRESS, 1)
        time.sleep(0.2)
        
    elif btn_m2_ccw.value() == 1:
        step_motor(m2_pins, STEPS_PER_PRESS, -1)
        time.sleep(0.2)