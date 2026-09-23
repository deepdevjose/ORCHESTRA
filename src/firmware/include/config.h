#pragma once

#if __has_include("config.local.h")
#include "config.local.h"
#else

// Copy the values from your isolated lab network into this local file.
// Never commit real Wi-Fi credentials to the repository.
#define WIFI_SSID "YOUR_AP_SSID"
#define WIFI_PASSWORD "YOUR_AP_PASSWORD"

// Set this to the computer's IPv4 address on the same isolated access point.
// For a typical phone/portable AP this may be 192.168.4.2, but verify it.
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

// Keep true for an end-to-end MQTT/dashboard smoke test before sensors are wired.
// Set false after assigning the input pins and calibration ranges in main.cpp.
#define USE_SIMULATED_SENSORS true
#define TELEMETRY_INTERVAL_MS 2500UL
#endif
