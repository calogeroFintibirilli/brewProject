import time
import paho.mqtt.client as mqtt
import max6675

# MQTT CONFIG
MQTT_BROKER = "127.0.0.1" 
MQTT_PORT = 1883
TOPIC_1 = "sensori/TT01"
TOPIC_2 = "sensori/TT02"

# MAX6675 pins
cs1 = 22
cs2 = 21
sck = 18
so = 16

max6675.set_pin(cs1, sck, so, 1)
max6675.set_pin(cs2, sck, so, 1)

client = mqtt.Client("pi-temp-sender")
client.connect(MQTT_BROKER, MQTT_PORT, 60)

print("Connected to MQTT Broker:", MQTT_BROKER)

try:
    while True:
        t1 = max6675.read_temp(cs1)
        t2 = max6675.read_temp(cs2)

        print(f"TT01 = {t1} °C")
        print(f"TT02 = {t2} °C")

        # Publish to MQTT
        client.publish(TOPIC_1, t1)
        client.publish(TOPIC_2, t2)

        time.sleep(2)

except KeyboardInterrupt:
    print("Stopping transmitter...")
