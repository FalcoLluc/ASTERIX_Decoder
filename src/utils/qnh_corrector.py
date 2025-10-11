"""
POSSIBLE IMPROVEMENT -> Preguntar profe si és el cas.

If input BP can vary by 0.01 hPa due to quantization, compare with a tiny epsilon: abs(bp_mb - self.QNH_STD) < 1e-6 instead of direct equality, still without broader tolerance logic.
"""

class QNHCorrector:
    TRANSITION_ALTITUDE_FT = 6000.0
    QNH_STD = 1013.25
    FT_PER_HPA = 30.0

    def __init__(self):
        self._last_qnh: dict[str, float] = {}

    def correct(self, ta_hex: str | None, fl: float | None, bp_mb: float | None):
        """
        Returns (altitude_ft, corrected_flag).
        - 0: no correction applied
        - 1: correction applied
        """
        if fl is None:
            return None, 0

        alt_ft = float(fl) * 100.0

        # At/above transition altitude: no correction, clear persistence
        if alt_ft >= self.TRANSITION_ALTITUDE_FT:
            if ta_hex and ta_hex in self._last_qnh:
                del self._last_qnh[ta_hex]
            return alt_ft, 0

        qnh_to_use = None

        # Update storage only when a non-standard BP arrives
        if bp_mb is not None and bp_mb != self.QNH_STD:
            qnh_to_use = bp_mb
            if ta_hex:
                self._last_qnh[ta_hex] = bp_mb
        elif ta_hex and ta_hex in self._last_qnh:
            # Keep using previously stored non-standard BP
            qnh_to_use = self._last_qnh[ta_hex]
        else:
            # No non-standard BP known -> no correction possible
            qnh_to_use = None

        if qnh_to_use is None:
            return alt_ft, 0

        correction_ft = (qnh_to_use - self.QNH_STD) * self.FT_PER_HPA
        return alt_ft + correction_ft, 1
