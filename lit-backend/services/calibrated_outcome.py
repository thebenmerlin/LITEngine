"""Serializable probability calibration around the existing linear pipeline."""

import numpy as np


class CalibratedOutcomeModel:
    def __init__(self, pipeline, calibrator, feature_order, version, extraction_method):
        self.pipeline = pipeline
        self.calibrator = calibrator
        self.feature_order = tuple(feature_order)
        self.version = version
        self.extraction_method = extraction_method
        self.requires_filing_date = True

    @property
    def named_steps(self):
        return self.pipeline.named_steps

    def predict_proba(self, X):
        raw = self.pipeline.predict_proba(X)[:, 1]
        p_success = self.calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
        return np.column_stack((1.0 - p_success, p_success))

    def predict(self, X):
        probabilities = self.predict_proba(X)[:, 1]
        return np.where(probabilities >= 0.5, "succeeds", "dismissed")
