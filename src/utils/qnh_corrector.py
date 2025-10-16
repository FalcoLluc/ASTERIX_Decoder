class QNHCorrector:
    TRANSITION_ALTITUDE_FT = 6000.0
    QNH_STD = 1013.25
    FT_PER_HPA = 30.0

    def __init__(self):
        self._last_qnh: dict[str, float] = {}

    def correct(self, ta_hex: str | None, fl: float | None, bp_mb: float | None):
        """
        Returns (altitude_ft).
        None if not corrected
        """
        if fl is None:
            return None

        alt_ft = float(fl) * 100.0

        # At/above transition altitude: no correction, clear persistence
        if alt_ft >= self.TRANSITION_ALTITUDE_FT:
            if ta_hex and ta_hex in self._last_qnh:
                del self._last_qnh[ta_hex]
            return None

        qnh_to_use = None

        # Update storage only when a non-standard BP arrives
        if bp_mb is not None and (bp_mb > (self.QNH_STD +0.25) or bp_mb < (self.QNH_STD - 0.25)):
            qnh_to_use = bp_mb
            if ta_hex:
                self._last_qnh[ta_hex] = bp_mb
        elif ta_hex and ta_hex in self._last_qnh:
            # Keep using previously stored non-standard BP
            qnh_to_use = self._last_qnh[ta_hex]
        else:
            # No non-standard BP known -> no correction possible
            return None

        correction_ft = (qnh_to_use - self.QNH_STD) * self.FT_PER_HPA
        return alt_ft + correction_ft
