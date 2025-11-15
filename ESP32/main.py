from machine import Pin
import time
from time import sleep
import network
import socket
from umqtt.simple import MQTTClient


# ---- Pin MAX6675 ----
SCK = Pin(18, Pin.OUT)
CS  = Pin(5, Pin.OUT)
SO  = Pin(19, Pin.IN)

CS.value(1)
SCK.value(0)

# ---- Lista reti Wi-Fi (SSID → Password) ----
WIFI_LIST = {
    "TIM-29": "pippo1234",
    "Familizanini": "pass2",
    
}
MQTT_SERVER = "192.168.1.57"   # IP del broker MQTT
MQTT_PORT   = 1883
MQTT_USER   = ""           # lascia "" se non serve login
MQTT_PASS   = ""       # lascia "" se non serve login
MQTT_TOPIC  = "sensori/TT03"
mqtt = None


sta = network.WLAN(network.STA_IF)
sta.active(True)

# ---- SCANSIONE E MOSTRA RETI ----
def scan_and_show():
    print("\n🔍 Scansione reti Wi-Fi...\n")
    nets = sta.scan()

    for net in nets:
        ssid = net[0].decode()
        rssi = net[3]
        channel = net[2]
        auth = net[4]
        security = {
            0: "OPEN",
            1: "WEP",
            2: "WPA-PSK",
            3: "WPA2-PSK",
            4: "WPA/WPA2-PSK",
            5: "WPA3"
        }.get(auth, "Sconosciuta")

        print(f"📡 SSID: {ssid:20} | Segnale: {rssi:4} dBm | Canale: {channel:2} | Sicurezza: {security}")

    print("\n--- Fine scansione ---\n")
    return nets


def mqtt_connect():
    global mqtt
    print("🔌 Connessione al broker MQTT...")
    mqtt = MQTTClient(
        client_id="ESP32_TEMPERATURA",
        server=MQTT_SERVER,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASS,
        keepalive=60
    )
    try:
        mqtt.connect()
        print("✔ MQTT connesso")
        return True
    except Exception as e:
        print("❌ Errore MQTT:", e)
        return False
    
    
    
# ---- SELEZIONA MIGLIOR RETE TRA QUELLE CONOSCIUTE ----
def select_best_wifi():
    nets = scan_and_show()
    found = []

    for net in nets:
        ssid = net[0].decode()
        rssi = net[3]
        if ssid in WIFI_LIST:
            found.append((ssid, rssi))

    if not found:
        print("❌ Nessuna rete conosciuta trovata")
        return None, None

    best = sorted(found, key=lambda x: x[1], reverse=True)[0]
    print(f"📡 Rete selezionata → {best[0]} (RSSI: {best[1]})\n")
    return best[0], WIFI_LIST[best[0]]

# ---- CONNESSIONE WI-FI ----
def wifi_connect():
    ssid, pwd = select_best_wifi()
    if ssid is None:
        return False

    print(f"Connessione a {ssid}...")
    sta.disconnect()
    sta.connect(ssid, pwd)

    timeout = 50
    while not sta.isconnected() and timeout > 0:
        sleep(0.5)
        timeout -= 1
        print("connessione in corso...")

    if sta.isconnected():
        print("✔ Wi-Fi OK →", sta.ifconfig()[0])
        return True
    else:
        print("❌ Connessione fallita")
        return False

# ---- LETTURA MAX6675 ----
def read_max6675():
    CS.value(0)
    time.sleep_us(10)

    value = 0
    for i in range(16):
        SCK.value(1)
        time.sleep_us(5)
        value <<= 1
        if SO.value():
            value |= 1
        SCK.value(0)
        time.sleep_us(5)

    CS.value(1)

    if value & 0x4:
        return None

    value >>= 3
    return value * 0.25  # °C



PORT_LIST = [1883,1880]

def ping(host, timeout=2):
    for port in PORT_LIST:
        try:
            addr = socket.getaddrinfo(host, port)[0][-1]
            s = socket.socket()
            s.settimeout(timeout)
            s.connect(addr)
            s.close()
            # Trovata porta aperta → dispositivo raggiungibile
            return True
        except:
            pass
    return False


# ---- PROGRAMMA PRINCIPALE ----
wifi_connect()

while True:
    # riconnessione Wi-Fi automatica
    if not sta.isconnected():
        print("⚠ Wi-Fi perso → riconnessione...")
        wifi_connect()

    target = "192.168.1.57"       # IP da pingare
    if ping(target):
        print(f"📶 PING OK → {target} raggiungibile")
        try:
            mqtt.publish(MQTT_TOPIC, str(temp))
            print(f"📤 MQTT inviato → {MQTT_TOPIC}: {temp}")
        except:
            print("⚠ MQTT disconnesso → riconnessione...")
            mqtt_connect()
    else:
        print(f"❌ PING FAIL → {target} NON raggiungibile")
    # lettura temperatura
    temp = read_max6675()
    if temp is None:
        print("⚠ Termocoppia non collegata / errore")
    else:
        print("Temperatura:", temp, "°C")

    time.sleep(1)

