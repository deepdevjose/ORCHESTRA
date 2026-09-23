# ORCHESTRA ESP32-WROOM-32 firmware

This PlatformIO project connects the ESP32 to `Jose's Network`, publishes the 17-field ORCHESTRA telemetry contract, and subscribes to a device command topic.

## 1. Configure the broker address

The computer running Mosquitto and the dashboard must also be connected to `Jose's Network`. Find the computer's IPv4 address on that network and set `MQTT_BROKER_HOST` in `include/config.h`. The default `192.168.4.2` is only a common hotspot example; it is not guaranteed.

For a local lab broker, Mosquitto needs a listener reachable from the AP. A minimal development configuration is:

```conf
listener 1883 0.0.0.0
allow_anonymous true
```

Use authentication and TLS before exposing this broker beyond the isolated lab network.

## 2. Upload

Install PlatformIO, connect the ESP32-WROOM-32 over USB, then run from this directory:

```bash
pio run
pio run --target upload
pio device monitor
```

The firmware publishes to:

```text
orchestra/laser-welding/esp32-wroom32-laser-01/telemetry
```

It subscribes to:

```text
orchestra/laser-welding/esp32-wroom32-laser-01/command
```

The Next.js gateway can subscribe to every device with `MQTT_TOPIC=orchestra/laser-welding/+/telemetry`.

## 3. Smoke test from the computer

After the computer joins `Jose's Network` and Mosquitto is running:

```bash
mosquitto_sub -h <COMPUTER_IP_ON_JOSES_NETWORK> -p 1883 \
  -t 'orchestra/laser-welding/+/telemetry' -v
```

Run the UI with the broker address in `ui/.env.local`:

```env
MQTT_BROKER_URL=mqtt://127.0.0.1:1883
MQTT_TOPIC=orchestra/laser-welding/+/telemetry
```

Because the dashboard gateway runs on the same computer as Mosquitto, `127.0.0.1` is correct for the UI even though the ESP32 uses the computer's AP address.

## Sensor mode

`USE_SIMULATED_SENSORS` is `true` by default so the whole ESP32 -> MQTT -> dashboard path can be tested before the physical sensors are wired. Set it to `false` only after calibrating the generic ADC/GPIO mappings in `src/main.cpp`; the actual sensor pinout was not specified in the project request.

