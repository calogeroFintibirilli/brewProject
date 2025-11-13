import lgpio
import time

chip = lgpio.gpiochip_open(0)

# pin numbers will be BCM numbers (BOARD mode does not exist in lgpio)
def set_pin(CS, SCK, SO, UNIT):
    global cs_pin, sck, so, unit

    cs_pin = CS
    sck = SCK
    so = SO
    unit = UNIT

    # Claim pins
    lgpio.gpio_claim_output(chip, cs_pin, 1)
    lgpio.gpio_claim_output(chip, sck, 0)
    lgpio.gpio_claim_input(chip, so)

def read_temp(cs_no):
    # Start signal
    lgpio.gpio_write(chip, cs_no, 0)
    time.sleep(0.002)
    lgpio.gpio_write(chip, cs_no, 1)
    time.sleep(0.22)

    # Begin reading
    lgpio.gpio_write(chip, cs_no, 0)
    lgpio.gpio_write(chip, sck, 1)
    time.sleep(0.001)
    lgpio.gpio_write(chip, sck, 0)

    Value = 0
    for i in range(11, -1, -1):
        lgpio.gpio_write(chip, sck, 1)
        Value = Value + (lgpio.gpio_read(chip, so) * (2 ** i))
        lgpio.gpio_write(chip, sck, 0)

    # Error bit
    lgpio.gpio_write(chip, sck, 1)
    error_tc = lgpio.gpio_read(chip, so)
    lgpio.gpio_write(chip, sck, 0)

    # Skip remaining 2 bits
    for _ in range(2):
        lgpio.gpio_write(chip, sck, 1)
        time.sleep(0.001)
        lgpio.gpio_write(chip, sck, 0)

    lgpio.gpio_write(chip, cs_no, 1)

    # Unit conversion
    if unit == 0:
        temp = Value
    elif unit == 1:
        temp = Value * 0.25
    else:
        temp = Value * 0.25 * 9.0 / 5.0 + 32.0

    # Fault detection
    if error_tc != 0:
        return -cs_no
    else:
        return temp
