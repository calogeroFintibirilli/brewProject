from machine import I2C, Pin
from time import sleep
import network
import urandom
from lcd1602 import LCD1602

# ---- CONFIG WI-FI ----
SSID = "TIM-29"
PASSWORD = "pippo1234"

# ---- I2C + LCD ----
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
lcd = LCD1602(i2c, addr=0x3F)

# ---- Funzione per mostrare messaggio Wi-Fi ----
def show_wifi_status():
    if sta.isconnected():
        lcd.clear()
        lcd.putstr("Wi-Fi OK")
        lcd.move_to(0, 1)
        lcd.putstr(sta.ifconfig()[0])
    else:
        lcd.clear()
        lcd.putstr("Wi-Fi Perso!")
        lcd.move_to(0, 1)
        lcd.putstr("Riconnessione...")

# ---- Connessione iniziale Wi-Fi ----
lcd.clear()
lcd.putstr("Connessione Wi-Fi")
lcd.move_to(0, 1)
lcd.putstr("In corso...")

sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.connect(SSID, PASSWORD)

timeout = 20
while not sta.isconnected() and timeout > 0:
    sleep(0.5)
    timeout -= 1

show_wifi_status()

# ---- LOOP PRINCIPALE ----
while True:
    if sta.isconnected():
        # Genera temperatura casuale
        temperatura = 20 + urandom.getrandbits(3)  # 20..27
        lcd.move_to(0, 0)
        lcd.putstr("Temp: {:2d} C     ".format(temperatura))

        # Mostra IP sulla seconda riga
        lcd.move_to(0, 1)
        lcd.putstr(sta.ifconfig()[0])
    else:
        show_wifi_status()
        sta.connect(SSID, PASSWORD)

    sleep(2)


