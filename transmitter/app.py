import time
import paho.mqtt.client as mqtt
import max6675

# MQTT CONFIG
MQTT_BROKER = "pi" 
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

MQTT_BROKER = "mqtt_broker"
MQTT_PORT = 1883

def connect_mqtt():
    client = mqtt.Client("pi-temp-sender")

    while True:
        time.sleep(5)
        try:
            print(f"Connecting to MQTT broker {MQTT_BROKER}:{MQTT_PORT} ...")
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            print("Connected to MQTT!")
            return client
        except Exception as e:
            print(f"MQTT connection failed: {e}")
            print("Retrying in 5 seconds...")
            

client = connect_mqtt()


print("Connected to MQTT Broker:", MQTT_BROKER)

try:
    while True:
        t1 = max6675.read_temp(cs1)
        t2 = max6675.read_temp(cs2)

        # print(f"TT01 = {t1} °C")
        # print(f"TT02 = {t2} °C")

        # Publish to MQTT
        result1 = client.publish(TOPIC_1, t1)
        
        result2 = client.publish(TOPIC_2, t2)

        # print("Publish result:", result1.rc, result2.rc)

        time.sleep(60)

except KeyboardInterrupt:
    print("Stopping transmitter...")
