# ORCHESTRA hybrid simulation on Windows

I use this guide to run the Mosquitto, Next.js, model-bridge, and ESP32
demonstrator on Windows. Robot 1 can publish MQTT telemetry from the ESP32;
robots 2–10 remain deterministic synthetic streams in the gateway.

## Daily startup

1. Connect the PC and ESP32 to the same isolated laboratory access point.
2. Open Docker Desktop and wait until Docker Engine is running.
3. Open PowerShell in the repository root.
4. Check the PC IPv4 address with `ipconfig`. The ESP32 must use this address,
   not `127.0.0.1`.
5. Start Mosquitto:

```powershell
cd simulation
docker compose up -d
docker compose ps
```

6. Observe MQTT traffic in a second PowerShell window:

```powershell
docker exec orchestra-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t "orchestra/#" -v
```

7. Start the dashboard and model bridge:

```powershell
cd src\\ui
npm install
npm run dev:stack
```

8. Open `http://localhost:3000`. Robot 1 should appear as `MQTT` after the
   first telemetry packet; robots 2–10 appear as `SIM`.

## Requirements

I install Docker Desktop with Compose, Node.js LTS, VS Code with PlatformIO,
PlatformIO Core, an ESP32-WROOM-32, and a private laboratory Wi-Fi network.
I do not expose the development broker to the Internet.

## Configure the dashboard

From `src\\ui`, I copy `.env.example` to `.env.local` once and then review the
local file before changing it:

```powershell
Copy-Item .env.example .env.local
```

The minimum local settings are:

```env
MQTT_BROKER_URL=mqtt://127.0.0.1:1883
MQTT_TOPIC=orchestra/laser-welding/+/telemetry
MQTT_COMMAND_TOPIC=orchestra/laser-welding/{device_id}/command
ORCHESTRA_LIVE_DEVICE_ID=esp32-wroom32-laser-01
ORCHESTRA_STATION_ID=CN-SUZHOU-LW-01
ORCHESTRA_MODEL_URL=http://127.0.0.1:8787/score
```

## Configure and flash the ESP32

I create the ignored local configuration once:

```powershell
Copy-Item src\\firmware\\include\\config.example.h src\\firmware\\include\\config.local.h
```

I edit only the local file:

```cpp
#define WIFI_SSID "LAB_NETWORK_NAME"
#define WIFI_PASSWORD "LAB_NETWORK_PASSWORD"
#define MQTT_BROKER_HOST "PC_IPV4_ADDRESS"
#define MQTT_DEVICE_ID "esp32-wroom32-laser-01"
#define MQTT_STATION_ID "CN-SUZHOU-LW-01"
#define USE_SIMULATED_SENSORS true
```

I compile, upload, and monitor with:

```powershell
cd src\\firmware
pio run
pio run --target upload
pio device monitor
```

`USE_SIMULATED_SENSORS=true` checks the MQTT transport before physical sensors
are connected. It does not represent calibrated sensor measurements.

## Test scenarios and maintenance commands

In Operations, I select Cell 01, choose a value in `ESP32 scenario command`,
and publish it. Supported scenarios include `normal`, `low_shielding_gas`,
`lens_contamination`, `focal_offset`, `fixture_vibration`, and
`high_laser_power`.

The dashboard also exposes maintenance, production-order, simulation-reset,
and lifetime-reset commands. These are operator-facing demonstrator actions;
they do not provide machine safety authority.

## Troubleshooting

- If the dashboard cannot connect to MQTT, I verify `.env.local`, Docker
  Compose status, and the `orchestra/#` subscription.
- If Robot 1 appears as `demo`, I restart Next.js after reviewing the MQTT
  environment variables.
- If the ESP32 connects to Wi-Fi but does not publish, I verify the current PC
  IPv4 address, TCP port 1883, and the serial monitor output.
- If Next.js reports a stale `.next` artifact, I stop the process, remove only
  `src/ui/.next`, and run `npm run dev:stack` again.

## Shutdown

I stop the dashboard with `Ctrl+C`, stop the broker with `docker compose down`
when the laboratory session is complete, and disconnect or leave the ESP32
connected for the next session.
