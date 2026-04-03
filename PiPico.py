import uasyncio as asyncio
from machine import Pin

# Motor 1 output pins
m1_pins = [Pin(19, Pin.OUT), Pin(18, Pin.OUT), Pin(17, Pin.OUT), Pin(16, Pin.OUT)]

# Motor 2 output pins
m2_pins = [Pin(6, Pin.OUT), Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)]

# Movement buttons — press = HIGH
btn_m1_cw  = Pin(10, Pin.IN, Pin.PULL_DOWN)
btn_m1_ccw = Pin(11, Pin.IN, Pin.PULL_DOWN)
btn_m2_cw  = Pin(12, Pin.IN, Pin.PULL_DOWN)
btn_m2_ccw = Pin(13, Pin.IN, Pin.PULL_DOWN)

# Limit buttons — held down when motor has hit a bound
lim_m1 = Pin(14, Pin.IN, Pin.PULL_DOWN)
lim_m2 = Pin(15, Pin.IN, Pin.PULL_DOWN)

# 8-phase half-step sequence for 28BYJ-48
step_sequence = [
    [1, 0, 0, 1],
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
]

STEPS_PER_PRESS = 256
STEP_DELAY_MS = 1

async def step_motor(motor_pins, steps, direction, name, limit_btn, ignore_limit=False):
    step_index = 0

    for _ in range(steps):
        # Stop immediately if the limit is pressed,
        # unless we are moving away from the limit
        if not ignore_limit and limit_btn.value() == 1:
            for pin in motor_pins:
                pin.value(0)
            print(f"{name}: Limit reached, stopping")
            return True

        for i in range(4):
            motor_pins[i].value(step_sequence[step_index][i])

        step_index = (step_index + direction) % len(step_sequence)
        await asyncio.sleep_ms(STEP_DELAY_MS)

    for pin in motor_pins:
        pin.value(0)

    print(f"{name}: Done")
    return False

async def motor_controller(cw_btn, ccw_btn, pins, name, limit_btn):
    while True:
        at_limit = limit_btn.value() == 1

        if ccw_btn.value() == 1 and not at_limit:
            print(f"{name}: CCW button pressed")
            await step_motor(pins, STEPS_PER_PRESS, -1, name, limit_btn, ignore_limit=False)

        elif cw_btn.value() == 1:
            print(f"{name}: CW button pressed")
            # Always allowed — CW moves away from the bound
            await step_motor(pins, STEPS_PER_PRESS, 1, name, limit_btn, ignore_limit=True)

        await asyncio.sleep_ms(10)

async def main():
    print("System ready. Press buttons to move motors.")
    await asyncio.gather(
        motor_controller(btn_m1_cw, btn_m1_ccw, m1_pins, "Motor 1", lim_m1),
        motor_controller(btn_m2_cw, btn_m2_ccw, m2_pins, "Motor 2", lim_m2)
    )

asyncio.run(main())