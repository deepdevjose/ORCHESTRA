# Dashboard simulation captures

These screenshots were rendered from the local Next.js dashboard on 2026-09-24 at 1600 × 1100 px.

| File | Suggested paper/defence use |
| --- | --- |
| `01_control_room_simulation.png` | First-run production-order setup, six-cell fleet context, SIASUN SR12A scene, 17-feature contract, and explicit simulation boundary. |
| `02_model_observatory_simulation.png` | Three-agent observability view: telemetry validation, XGBoost predictive risk, checkpoint scheduler, urgency/uncertainty trace, and fleet comparison. |
| `03_control_room_production_started.png` | Active order with checkpoint scheduling, fleet review queue, machine urgency cards, and operator-aware decision rail. |
| `04_model_observatory_human_decision_trace.png` | Human-in-the-loop evidence: Cell 04 review gate, agent trace, maintenance-hold state, and append-only operator decision record. |
| `05_control_room_orion_mqtt_viewport.png` | Live demonstrator: Cell 01 / Orion identified as `MQTT`, accepted frames, order progress, fleet urgency, and the operator decision rail. |
| `06_model_observatory_orion_mqtt.png` | Live MQTT model path: 17-feature telemetry quality, XGBoost inference, three-agent bounded trace, and uncertainty gate for Cell 01. |
| `07_control_room_orion_process_view.png` | Live Cell 01 process view with SIASUN SR12A scene, 17 numeric signals, MQTT gateway identity, and urgency trajectory. |
| `08_control_room_orion_focal_offset_mqtt.png` | MQTT scenario response: focal-offset condition increases Orion risk and opens the review gate while the other cells remain synthetic. |
| `09_model_observatory_orion_focal_offset.png` | Model-laboratory view of the focal-offset response, including adjusted urgency, uncertainty, agent decisions, and gate activity. |
| `10_control_room_orion_focal_offset_process_view.png` | Paper-ready process detail: `Focal_offset`, focal error ≈0.407 mm, bead-width shift, MQTT live status, and review trajectory. |

## Evidence boundary

Files `01`–`04` are synthetic/local simulation captures. Files `05`–`10` were captured after reflashing the ESP32-WROOM-32 onto the external Wi-Fi network: Cell 01 published `orchestra.telemetry.v1` frames to Mosquitto, the dashboard identified it as `MQTT`, and the `focal_offset` command returned `orchestra.command_ack.v1`. `USE_SIMULATED_SENSORS=true` remains enabled, so these are live transport/integration demonstrator evidence, not calibrated physical-sensor validation, industrial deployment evidence, safety certification, or an operator study.
