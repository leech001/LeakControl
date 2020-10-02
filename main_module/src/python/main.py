import gc
import machine
import utime as time
import uasyncio as asyncio
import usocket as socket
import ustruct as struct
from machine import Pin, SPI, WDT
from nrf24l01 import NRF24L01
from mqtt import MQTTClient

import wifi
import config

gc.enable()
wifi.activate()

int_err_count = 0
ping_mqtt = 0
ping_fail = 0
water = False
wdt = WDT()

# Init MQTT
client = MQTTClient(config.CONFIG['MQTT_CLIENT'], config.CONFIG['MQTT_BROKER'],
                    user=config.CONFIG['MQTT_USER'],
                    password=config.CONFIG['MQTT_PASSWORD'], port=config.CONFIG['MQTT_PORT'])

# Init NRF24L01
csn = Pin(config.NRFCFG["csn"], mode=Pin.OUT, value=1)
ce = Pin(config.NRFCFG["ce"], mode=Pin.OUT, value=0)
nrf = NRF24L01(SPI(config.NRFCFG["spi"]), csn, ce, channel=76, payload_size=32)
nrf.open_rx_pipe(1, config.PIPES[1])
nrf.start_listening()


def time_now():
    ntp_query = bytearray(48)
    ntp_query[0] = 0x1b
    try:
        addr = socket.getaddrinfo(config.host, 123)[0][-1]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.sendto(ntp_query, addr)
        msg = s.recv(48)
        s.close()
        val = struct.unpack("!I", msg[40:44])[0]
        return val - config.ntp_delta
    except Exception as error:
        print("Error in time now: [Exception] %s: %s" % (type(error).__name__, error))
        time.sleep(60)
        machine.reset()


def settime():
    try:
        t = time_now()
        tm = time.localtime(t)
        tm = tm[0:3] + (0,) + tm[3:6] + (0,)
        machine.RTC().datetime(tm)
    except Exception as error:
        print("Error in set time: [Exception] %s: %s" % (type(error).__name__, error))
        time.sleep(60)
        machine.reset()


settime()


# Check Internet connection
def internet_connected(host='8.8.8.8', port=53):
    global int_err_count
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            s.connect((host, port))
            int_err_count = 0
            return True
        except Exception as error:
            print("Error Internet connect: [Exception] %s: %s" % (type(error).__name__, error))
            return False
        finally:
            s.close()


async def check_nrf_message():
    while True:
        if nrf.any():
            print('Receive!')
            while nrf.any():
                buf = nrf.recv()

                id_sensor_1 = int.from_bytes(buf[0:3], "big")
                id_sensor_2 = int.from_bytes(buf[4:7], "big")
                id_sensor_3 = int.from_bytes(buf[8:11], "big")
                id_sensor = str(id_sensor_1) + str(id_sensor_2) + str(id_sensor_3)
                print("ID sensor= %s" % id_sensor)

                for i in range(len(buf)):
                    print(i, buf[i])

                water_level = int.from_bytes(bytearray([buf[12], buf[13]]), "big")
                humidity = water_level * 100 / 4096
                print("Water level= %i" % water_level)

                battery = int.from_bytes(bytearray([buf[14], buf[15]]), "big")
                battery_voltage = battery / 1000
                print("Battery voltage= %f" % battery_voltage)

                sensor_1 = '{"name": "nrf_' + id_sensor + '_humidity",' \
                           ' "unique_id": "nrf_' + id_sensor + '_humidity",' \
                           ' "unit_of_measurement": "%",' \
                           ' "device_class": "humidity",' \
                           ' "state_topic": "homeassistant/sensor/nrf_' + id_sensor + '_humidity/state"}'
                client.publish("homeassistant/sensor/nrf_" + id_sensor + "_humidity/config", sensor_1)
                client.publish("homeassistant/sensor/nrf_" + id_sensor + "_humidity/state", str(humidity))

                sensor_2 = '{"name": "nrf_' + id_sensor + '_voltage",' \
                           ' "unique_id": "nrf_' + id_sensor + '_voltage",' \
                           ' "unit_of_measurement": "V",' \
                           ' "device_class": "battery",' \
                           ' "state_topic": "homeassistant/sensor/nrf_' + id_sensor + '_voltage/state"}'
                client.publish("homeassistant/sensor/nrf_" + id_sensor + "_voltage/config", sensor_2)
                client.publish("homeassistant/sensor/nrf_" + id_sensor + "_voltage/state", str(battery_voltage))

        await asyncio.sleep(0.1)


# Pong MQTT connect
def send_mqtt_pong(pong_msg):
    print(pong_msg.decode("utf-8"))
    client.publish(config.HAMQTTPrefix + "/pong", pong_msg.decode("utf-8"))


def on_message(topic, msg):
    global ping_fail
    print("Topic: %s, Message: %s" % (topic, msg))
    print(topic.decode())

    if config.HAMQTTPrefix + "/check/mqtt" in topic:
        if int(msg) == ping_mqtt:
            print("MQTT pong true...")
            ping_fail = 0
        else:
            print("MQTT pong false... (%i)" % ping_fail)

    if config.HAMQTTPrefix + "/ping" in topic:
        send_mqtt_pong(msg)

    # if config.tap_cold.command_topic == topic.decode():
    #     print("ENTER")
    #     if msg == b"OFF":
    #         config.tap_cold.state = "CLOSE"
    #     if msg == b"ON":
    #         print("Tap cold OPEN")
    #         config.tap_cold.state = "OPEN"


# Check MQTT message
async def check_message():
    global wdt
    while True:
        wdt.feed()
        await asyncio.sleep(0.2)
        # print("Check message...")
        try:
            client.check_msg()
        except Exception as error:
            print("Error in mqtt check message: [Exception] %s: %s" % (type(error).__name__, error))
            client.disconnect()
            mqtt_reconnect()


# Check MQTT brocker
async def mqtt_check():
    global ping_fail
    global ping_mqtt
    while True:
        await asyncio.sleep(10)
        ping_mqtt = time.time()
        client.publish(config.HAMQTTPrefix + "/check/mqtt", "%s" % ping_mqtt)
        print("Send MQTT ping (%i)" % ping_mqtt)
        ping_fail += 1

        if ping_fail >= config.CONFIG['MQTT_CRIT_ERR']:
            print("MQTT ping false... reset (%i)" % ping_fail)
            machine.reset()

        if ping_fail >= config.CONFIG['MQTT_MAX_ERR']:
            print("MQTT ping false... reconnect (%i)" % ping_fail)
            client.disconnect()
            mqtt_reconnect()


# MQTT reconnect
def mqtt_reconnect():
    global client
    try:
        client.set_callback(on_message)
        client.connect(clean_session=True)
        client.subscribe(config.HAMQTTPrefix + "/#")
        print("ESP8266 is Connected to %s and subscribed to %s topic" % (
            config.CONFIG['MQTT_BROKER'], config.HAMQTTPrefix + "/#"))
    except Exception as error:
        print("Error in MQTT reconnection: [Exception] %s: %s" % (type(error).__name__, error))


# Check Internet connected and reconnect
async def check_internet():
    global int_err_count
    try:
        while True:
            await asyncio.sleep(60)
            print("Check Internet connect... ")
            if not internet_connected():
                print("Internet connect fail...")
                int_err_count += 1

                if int_err_count >= config.CONFIG['INT_CRIT_ERR']:
                    client.disconnect()
                    wifi.wlan.disconnect()
                    machine.reset()

                if int_err_count >= config.CONFIG['INT_MAX_ERR']:
                    print("Internet reconnect")
                    client.disconnect()
                    wifi.wlan.disconnect()
                    wifi.activate()
    except Exception as error:
        print("Error in Internet connection: [Exception] %s: %s" % (type(error).__name__, error))


mqtt_reconnect()

try:
    loop = asyncio.get_event_loop()
    loop.create_task(check_message())
    loop.create_task(check_internet())
    loop.create_task(mqtt_check())
    loop.create_task(check_nrf_message())
    loop.run_forever()
except Exception as e:
    print("Error: [Exception] %s: %s" % (type(e).__name__, e))
    time.sleep(60)
    machine.reset()
