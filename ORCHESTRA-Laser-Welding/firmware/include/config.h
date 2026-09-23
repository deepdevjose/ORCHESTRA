#pragma once

// Network shared by the ESP32 and the computer running Mosquitto.
#define WIFI_SSID "Jose's Network"
#define WIFI_PASSWORD "helloworld"

// Set this to the computer's IPv4 address on Jose's Network.
// For a typical phone/portable AP this may be 192.168.4.2, but verify it.
#define MQTT_BROKER_HOST "192.168.4.2"
#define MQTT_BROKER_PORT 1883

#define MQTT_DEVICE_ID "esp32-wroom32-laser-01"
#define MQTT_STATION_ID "CN-SUZHOU-LW-01"
#define MQTT_TELEMETRY_TOPIC "orchestra/laser-welding/esp32-wroom32-laser-01/telemetry"
#define MQTT_COMMAND_TOPIC "orchestra/laser-welding/esp32-wroom32-laser-01/command"
#define MQTT_STATUS_TOPIC "orchestra/laser-welding/esp32-wroom32-laser-01/status"

// Keep true for an end-to-end MQTT/dashboard smoke test before sensors are wired.
// Set false after assigning the input pins and calibration ranges in main.cpp.
#define USE_SIMULATED_SENSORS true
#define TELEMETRY_INTERVAL_MS 2500UL

