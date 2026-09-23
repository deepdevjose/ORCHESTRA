"""Small HTTP inference service for the ORCHESTRA live dashboard.

The dashboard gateway calls this service for every validated ESP32 frame.
It deliberately reuses the repository's PredictiveAgent, uncertainty logic,
and HumanOperatorAgent instead of duplicating the research model in TypeScript.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orchestra_laser.config import Paths, load_config
from orchestra_laser.human_agent import HumanOperatorAgent
from orchestra_laser.predictive_agent import PredictiveAgent
from orchestra_laser.preprocessing import clean_laser_welding_data, load_or_create_dataset, train_test_split
from orchestra_laser.uncertainty import estimate_uncertainty
from orchestra_laser.urgency import add_maintenance_urgency


class LiveModel:
    """Load the repository predictor and human-review adapter for HTTP scoring."""

    def __init__(self) -> None:
        paths = Paths()
        config = load_config(paths.config)
        self.config = config
        self.features = list(config["feature_columns"])
        base = load_or_create_dataset(config)
        base = clean_laser_welding_data(base, self.features)
        self.reference_features = base[self.features].copy()
        labelled = add_maintenance_urgency(base)
        train, _ = train_test_split(labelled, float(config["train_fraction"]), int(config["random_seed"]))
        self.agent = PredictiveAgent(self.features, prefer_xgboost=True)
        self.agent.fit(train)
        human = config["human_review"]
        self.human_agent = HumanOperatorAgent(
            uncertainty_threshold=float(config["uncertainty_threshold"]),
            high_urgency_threshold=float(config["high_urgency_threshold"]),
            override_probability=float(human["override_probability"]),
            false_negative_sensitivity=float(human["false_negative_sensitivity"]),
            noise_std=float(human["noise_std"]),
            seed=int(config["random_seed"]),
        )

    def score(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Score one validated telemetry payload and return dashboard fields."""
        values = payload.get("features") if isinstance(payload.get("features"), dict) else payload
        row = {feature: values.get(feature) for feature in self.features}
        frame = clean_laser_welding_data(pd.DataFrame([row]), self.features)
        prediction = float(self.agent.predict(frame)[0])
        uncertainty = float(estimate_uncertainty(frame, np.array([prediction]))[0])
        review = self.human_agent.review(prediction, uncertainty, None)
        adjusted = float(review.adjusted_prediction)

        contextual = add_maintenance_urgency(pd.concat([self.reference_features, frame], ignore_index=True)).iloc[-1]
        process_instability = float(contextual["process_instability_score"])
        label = "high" if adjusted > 70 else "medium" if adjusted > 40 else "low"
        if adjusted >= 82:
            recommendation = "urgent_intervention"
        elif adjusted >= 65:
            recommendation = "major_maintenance"
        elif adjusted >= 45 or review.reviewed:
            recommendation = "inspect"
        else:
            recommendation = "do_nothing"

        quality_flags: list[str] = []
        if float(frame["cooling_system_alarm"].iloc[0]) > 0.5:
            quality_flags.append("Cooling alarm")
        if float(frame["shielding_gas_flow_l_min"].iloc[0]) < 13:
            quality_flags.append("Low shielding gas")
        if float(frame["lens_contamination_level"].iloc[0]) > 0.45:
            quality_flags.append("Optical maintenance drift")

        return {
            "predictedUrgency": prediction,
            "adjustedUrgency": adjusted,
            "uncertainty": uncertainty,
            "processInstability": process_instability,
            "label": label,
            "recommendation": recommendation,
            "humanReview": bool(review.reviewed),
            "humanOverride": bool(review.override),
            "modelName": self.agent.model_name,
            "modelVersion": "python-research-v0.1",
            "qualityFlags": quality_flags,
        }


MODEL: LiveModel | None = None
MODEL_ERROR: str | None = None


def get_model() -> LiveModel:
    """Lazily construct and cache the live inference adapter."""
    global MODEL, MODEL_ERROR
    if MODEL is None:
        try:
            MODEL = LiveModel()
        except Exception as exc:
            MODEL_ERROR = str(exc)
            raise
    return MODEL


class Handler(BaseHTTPRequestHandler):
    """Expose health and scoring endpoints for the local dashboard gateway."""

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("access-control-allow-origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        """Serve model health information for the dashboard health check."""
        if self.path == "/health":
            try:
                model = get_model()
                self._send(200, {"ok": True, "model": model.agent.model_name, "error": None})
            except Exception:
                self._send(503, {"ok": False, "model": None, "error": MODEL_ERROR})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        """Score a telemetry payload received at the ``/score`` endpoint."""
        if self.path != "/score":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self._send(200, get_model().score(payload))
        except Exception as exc:
            self._send(422, {"error": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        """Keep the standard HTTP server log concise and clearly scoped."""
        print("[model]", format % args)


def main() -> None:
    """Start the local HTTP inference service on the requested port."""
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    print(f"ORCHESTRA live inference service on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
