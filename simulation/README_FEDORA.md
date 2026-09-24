# ORCHESTRA hybrid simulation on Fedora

I use this guide to run the same hybrid stack as Windows: Robot 1 can arrive
from an ESP32 through MQTT, while robots 2–6 remain synthetic in the Next.js
gateway. The dashboard exposes production orders, shifts, checkpoints,
maintenance, model traces, and simulation reset controls.

## Daily startup

1. Connect Fedora and the ESP32 to the same isolated laboratory network.
2. Find the current PC IPv4 address:

```bash
ip -4 -o addr show scope global
```

3. Put that address in the ignored
   `src/firmware/include/config.local.h`. I never use `127.0.0.1` in ESP32
   firmware.
4. Start the native broker:

```bash
cd simulation
mosquitto -c mosquitto/mosquitto.conf -v
```

5. Observe traffic from another terminal:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'orchestra/#' -v
```

6. Start the dashboard:

```bash
cd src/ui
npm install
npm run dev:stack
```

7. Open `http://localhost:3000`. Robot 1 should report `MQTT`; robots 2–6
   should report `SIM`.

## Requirements and installation

I use Fedora, Node.js LTS, Git, Mosquitto, VS Code with PlatformIO, an
ESP32-WROOM-32, and a private Wi-Fi network.

```bash
sudo dnf upgrade --refresh
sudo dnf install -y git curl python3 python3-pip
sudo dnf install -y mosquitto mosquitto-clients
```

I enable Docker only if I prefer the Compose-based broker:

```bash
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
docker --version
docker compose version
```

I sign in again after changing the Docker group. I keep port 1883 restricted
to the laboratory network.

## Firewall and broker

If the ESP32 needs to reach the broker from the private access point, I open
TCP 1883 only on the lab network:

```bash
sudo firewall-cmd --permanent --add-port=1883/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

The broker configuration is in `simulation/mosquitto/mosquitto.conf`. It is a
development configuration without authentication or persistence. I do not use
it outside an isolated network.

## Dashboard settings

From `src/ui`, I create `.env.local` once:

```bash
cp .env.example .env.local
```

The minimum values are:

```env
MQTT_BROKER_URL=mqtt://127.0.0.1:1883
MQTT_TOPIC=orchestra/laser-welding/+/telemetry
MQTT_COMMAND_TOPIC=orchestra/laser-welding/{device_id}/command
ORCHESTRA_LIVE_DEVICE_ID=esp32-wroom32-laser-01
ORCHESTRA_STATION_ID=CN-SUZHOU-LW-01
ORCHESTRA_MODEL_URL=http://127.0.0.1:8787/score
```

I run:

```bash
npm install
npm run dev:stack
```

## ESP32 configuration

I copy the example configuration once:

```bash
cp src/firmware/include/config.example.h src/firmware/include/config.local.h
```

I edit the ignored local file with the private network name, password, PC
IPv4, device ID, station ID, and `USE_SIMULATED_SENSORS=true`.

```bash
python3 -m pip install --user platformio
export PATH="$HOME/.local/bin:$PATH"
cd src/firmware
pio run
pio run --target upload
pio device monitor
```

Simulated sensors validate the MQTT path before physical sensors are wired.
They do not provide calibrated measurements.

## Scenarios and reset controls

I can publish `normal`, `low_shielding_gas`, `lens_contamination`,
`focal_offset`, `fixture_vibration`, or `high_laser_power` from the Operations
view. I can also configure a production order, advance shifts, reset the
simulation, schedule maintenance, and restore robot/firmware lifetime.

These controls demonstrate decision flow and state handling. They do not
provide automatic stop authority or safety control.

## Troubleshooting

- I verify the actual wireless-interface IPv4 before changing
  `MQTT_BROKER_HOST`.
- I confirm port 1883 with `firewall-cmd` and inspect `mosquitto_sub` output.
- I restart Next.js after creating or changing `.env.local`.
- I remove only `src/ui/.next` if a stale development bundle causes an
  `ENOENT` error.
- I run `pio device monitor -p /dev/ttyUSB0 -b 115200` when the board is already
  flashed.
