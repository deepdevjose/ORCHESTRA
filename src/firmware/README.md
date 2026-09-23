# ORCHESTRA ESP32-WROOM-32 firmware

This PlatformIO project is the edge-side contract for one laser-welding cell. It publishes the complete 17-feature ORCHESTRA telemetry frame and listens for human decisions from the dashboard. The repository contains safe placeholders only; add local Wi-Fi values to `include/config.h` before a lab build.

## Configure the isolated lab network

1. Copy the values from `include/config.example.h` into `include/config.h`.
2. Set `WIFI_SSID` and `WIFI_PASSWORD` to the local access point values.
3. Set `MQTT_BROKER_HOST` to the computer's IPv4 address on that access point. The dashboard itself can use `mqtt://127.0.0.1:1883` when Mosquitto runs on the same computer.
4. Keep `USE_SIMULATED_SENSORS true` for the end-to-end smoke test. Set it to `false` only after the generic ADC/GPIO mappings and calibration ranges in `src/main.cpp` have been replaced with the actual sensor interface.

For an isolated development broker, Mosquitto may use a listener reachable from the AP:

```conf
listener 1883 0.0.0.0
allow_anonymous true
```

Use authentication and TLS before exposing the broker beyond the lab network.

## Build and upload

```bash
pio run
pio run --target upload
pio device monitor
```

The node publishes to `orchestra/laser-welding/<device_id>/telemetry`, publishes online/offline status to the matching status topic, and subscribes to `orchestra/laser-welding/<device_id>/command`.

The Next.js gateway can receive every cell with:

```env
MQTT_BROKER_URL=mqtt://127.0.0.1:1883
MQTT_TOPIC=orchestra/laser-welding/+/telemetry
MQTT_COMMAND_TOPIC=orchestra/laser-welding/{device_id}/command
```

## Payload and human-in-the-loop commands

Every telemetry frame contains the 17 numeric fields consumed by the model:

`laser_power_w`, `welding_speed_mm_s`, `focal_position_error_mm`, `shielding_gas_flow_l_min`, `melt_pool_temp_c`, `back_reflection_intensity`, `plume_intensity`, `spatter_count`, `vibration_rms`, `robot_path_error_mm`, `bead_width_mm`, `bead_height_mm`, `porosity_risk`, `visual_defect_score`, `lens_contamination_level`, `cooling_system_alarm`, and `time_since_lens_cleaning_h`.

The frame also carries device identity, location, line, source, Wi-Fi RSSI, signal quality, and the current simulated operational state. The dashboard command shape is:

```json
{
  "action": "hold_production",
  "operator": "JM",
  "note": "Review low shielding gas before the next weld"
}
```

Accepted actions are `acknowledge`, `inspect`, `hold_production`, `schedule_minor_maintenance`, `schedule_major_maintenance`, `urgent_intervention`, and `resume_production`. The firmware acknowledges the command and updates its local operational state; this prototype is not a certified safety controller.

## Smoke test

```bash
mosquitto_sub -h <COMPUTER_IP_ON_AP> -p 1883 \
  -t 'orchestra/laser-welding/+/telemetry' -v
```

The UI starts with a deterministic 10-machine synthetic feed when MQTT is unavailable. One physical ESP32 can then be introduced as a live MQTT source without changing the 17-field contract.
