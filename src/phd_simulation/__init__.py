"""Reproducible PhD-level simulation and evaluation package for ORCHESTRA.

The package is deliberately simulation-only.  It provides a transparent
latent-process simulator, uncertainty-aware review routing, a five-action
scheduling environment, and the experiment harness needed for E1-E9 in the
validation plan.
"""

__version__ = "1.0.0"

from .schema import ACTION_NAMES, FEATURE_COLUMNS

__all__ = ["ACTION_NAMES", "FEATURE_COLUMNS", "__version__"]
