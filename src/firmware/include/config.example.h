#pragma once

// Copy this file to config.h for a local lab build and fill in your own values.
// Do not commit real Wi-Fi or broker credentials.
#define WIFI_SSID "YOUR_AP_SSID"
#define WIFI_PASSWORD "YOUR_AP_PASSWORD"
#define MQTT_BROKER_HOST "192.168.4.2"
#define MQTT_BROKER_PORT 1883

#define MQTT_DEVICE_ID "esp32-wroom32-laser-01"
#define MQTT_STATION_ID "CN-SUZHOU-LW-01"
#define MACHINE_NAME "Cell 01 - ESP32 prototype"
#define MACHINE_LOCATION "Suzhou - Jiangsu"
#define MACHINE_LINE "Battery enclosure A"
#define MACHINE_ASSET "SIASUN SR12A"
#define MQTT_TELEMETRY_TOPIC "orchestra/laser-welding/esp32-wroom32-laser-01/telemetry"
#define MQTT_COMMAND_TOPIC "orchestra/laser-welding/esp32-wroom32-laser-01/command"
#define MQTT_STATUS_TOPIC "orchestra/laser-welding/esp32-wroom32-laser-01/status"

#define USE_SIMULATED_SENSORS true
#define TELEMETRY_INTERVAL_MS 2500UL
