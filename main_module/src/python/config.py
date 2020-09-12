ntp_delta = 3155673600
host = "pool.ntp.org"

# Modify below section as required
CONFIG = {
    "MQTT_BROKER": "mqtt.site.ru",
    "MQTT_USER": "user",
    "MQTT_PASSWORD": "pass",
    "MQTT_PORT": 31883,
    "MQTT_CLIENT": "ESP_DACHA_LEAK_01",
    "MQTT_MAX_ERR": 5,
    "MQTT_CRIT_ERR": 10,
    "HA_PREFIX": "homeassistant",
    "DEVICE_PLACE": "/dacha",
    "DEVICE_TYPE": "/leakcontrol",
    "DEVICE_ID": "/01",
    "WIFI_LOGIN": "AP-Name",
    "WIFI_PASSWORD": "pass",
    "INT_MAX_ERR": 20,
    "INT_CRIT_ERR": 50
}

NRFCFG = {"spi": 1, "miso": 12, "mosi": 13, "sck": 14, "csn": 4, "ce": 5}
PIPES = (b'\x78\x78\x78\x78\x78',
         b'\xA1\xF0\xF0\xF0\xF0',
         b'\xB1\xF0\xF0\xF0\xF0',
         b'\xC1\xF0\xF0\xF0\xF0',
         b'\xD1\xF0\xF0\xF0\xF0',
         b'\xE1\xF0\xF0\xF0\xF0')

HAMQTTPrefix = CONFIG['HA_PREFIX'] + CONFIG['DEVICE_PLACE'] + CONFIG['DEVICE_TYPE'] + CONFIG['DEVICE_ID']
