# ORCHESTRA live dashboard

The UI is a Next.js control room for a laser-welding pilot context in China. It is split into four layers:

1. ESP32 publishes a JSON frame over MQTT.
2. The Next.js Node gateway subscribes, validates the 17-feature payload and exposes an SSE stream to the browser.
3. scripts/live_inference_service.py reuses the repository PredictiveAgent, uncertainty estimator and human-review agent.
4. The dashboard renders a 10-machine fleet board, the human gate, operator decisions and the scheduling recommendation.

The dashboard starts in an explicit demo mode when MQTT is not configured. Demo frames are synthetic/lab-informed and are labelled as such in the UI; they must not be presented as production evidence.

## Run the complete local stack

From the ui directory:

    npm install
    npm run dev:stack

Open http://localhost:3000.

The main operations view is `/`. The experimental model observatory is `/models`; it shows ingestion rate, fleet risk/uncertainty, review-gate events, the model matrix and the operator audit session.

dev:stack starts the Python model service on port 8787 and the Next.js gateway on port 3000. If optional Python ML dependencies are not installed, the gateway uses the clearly-labelled fallback_rule path while preserving the same data contract.

## Connect an MQTT broker

Copy .env.example to .env.local, set MQTT_BROKER_URL, and restart the stack. The server subscribes to:

    orchestra/laser-welding/+/telemetry

An ESP32 payload can be flat:

    {
      "device_id": "esp32-lw-01",
      "station_id": "CN-SUZHOU-LW-01",
      "timestamp": "2026-09-22T10:00:00.000Z",
      "laser_power_w": 1810,
      "welding_speed_mm_s": 34.8,
      "focal_position_error_mm": 0.08,
      "shielding_gas_flow_l_min": 18.1,
      "melt_pool_temp_c": 1454,
      "back_reflection_intensity": 0.34,
      "plume_intensity": 0.43,
      "spatter_count": 3,
      "vibration_rms": 0.08,
      "robot_path_error_mm": 0.05,
      "bead_width_mm": 2.01,
      "bead_height_mm": 0.62,
      "porosity_risk": 0.12,
      "visual_defect_score": 7,
      "lens_contamination_level": 0.12,
      "cooling_system_alarm": 0,
      "time_since_lens_cleaning_h": 24
    }

The nested form { "features": { ...17 fields... } } is also accepted. The gateway rejects incomplete or non-numeric frames and reports the error in the event panel.

## Human-in-the-loop command path

Selecting a machine on the operations board opens a decision rail. Every action requires a second confirmation and an operator note. The browser posts to `POST /api/command` with:

    {
      "deviceId": "esp32-lw-01",
      "action": "hold_production",
      "operator": "JM",
      "note": "Review shielding gas before the next weld"
    }

When MQTT is unavailable, the command is accepted only by the local simulation and appears in the audit trail as `simulated`. When MQTT is connected, the gateway publishes to `orchestra/laser-welding/<device_id>/command` and records the transport as `mqtt`. This prototype does not claim certified machine-stop authority; it is an inspectable decision-support path for the research validation.

## Evidence boundary

The 10-machine feed is deterministic synthetic telemetry designed to exercise the complete 17-feature contract, uncertainty gate and operator workflow. It is not a substitute for sensor calibration, production validation, safety interlocks, causal claims or a statistically powered comparison against a baseline.
