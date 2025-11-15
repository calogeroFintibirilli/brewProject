from machine import I2C
from time import sleep_ms

class LCD1602:
    def __init__(self, i2c, addr=0x27):
        self.i2c = i2c
        self.addr = addr
        self.bl = 0x08  # backlight on
        self.cmd(0x33)
        self.cmd(0x32)
        self.cmd(0x28)
        self.cmd(0x0C)
        self.cmd(0x06)
        self.cmd(0x01)
        sleep_ms(5)

    def cmd(self, data):
        self.send(data, 0)

    def write(self, data):
        self.send(data, 1)

    def send(self, data, mode):
        high = mode | (data & 0xF0) | self.bl
        low = mode | ((data << 4) & 0xF0) | self.bl
        self.i2c.writeto(self.addr, bytes([high | 0x04]))
        self.i2c.writeto(self.addr, bytes([high]))
        self.i2c.writeto(self.addr, bytes([low | 0x04]))
        self.i2c.writeto(self.addr, bytes([low]))

    def clear(self):
        self.cmd(0x01)
        sleep_ms(5)

    def move_to(self, col, row):
        self.cmd(0x80 + col + row * 0x40)

    def putstr(self, string):
        for c in string:
            self.write(ord(c))

