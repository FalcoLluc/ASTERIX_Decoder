import pandas as pd
import numpy as np


class QNHCorrector:
    """Apply QNH correction to altitude (ft) under transition altitude, per aircraft.

    Stores last non-standard QNH per `ta_hex` and uses it for subsequent samples
    until a new value arrives or the aircraft is at/above the transition altitude.
    """
    TRANSITION_ALTITUDE_FT = 6000.0
    QNH_STD = 1013.25
    FT_PER_HPA = 30.0

    def __init__(self):
        self._last_qnh: dict[str, float] = {}

    def correct(self, ta_hex: str | None, fl: float | None, bp_mb: float | None):
        """Return corrected altitude in feet, uncorrected FL*100, or None.

        Args:
            ta_hex: Aircraft identifier (ICAO 24-bit hex) used for QNH persistence.
            fl: Flight Level (hundreds of feet). If None, returns None.
            bp_mb: Local QNH in hPa (mb). Only non-standard values are persisted/used.

        Returns:
            - Corrected altitude (ft) if QNH correction applied
            - FL * 100 if below TL but no correction (standard QNH or no stored QNH)
            - None if FL is None or aircraft is at/above transition altitude
        """
        if fl is None:
            return None

        alt_ft = float(fl) * 100.0

        # At/above transition altitude: no correction, clear persistence, return None
        if alt_ft >= self.TRANSITION_ALTITUDE_FT:
            if ta_hex and ta_hex in self._last_qnh:
                del self._last_qnh[ta_hex]
            return None

        qnh_to_use = None

        # Update storage only when a non-standard BP arrives
        if bp_mb is not None and (bp_mb > (self.QNH_STD + 0.25) or bp_mb < (self.QNH_STD - 0.25)):
            qnh_to_use = bp_mb
            if ta_hex:
                self._last_qnh[ta_hex] = bp_mb
        elif ta_hex and ta_hex in self._last_qnh:
            # Keep using previously stored non-standard BP (even if current BP is standard)
            qnh_to_use = self._last_qnh[ta_hex]
        else:
            # ✅ No correction available: return uncorrected altitude (FL * 100)
            return alt_ft

        # Apply correction
        correction_ft = (qnh_to_use - self.QNH_STD) * self.FT_PER_HPA
        return alt_ft + correction_ft

    def correct_dataframe(self, df: 'pd.DataFrame') -> 'pd.DataFrame':
        """Ultra-fast QNH correction using vectorized operations per aircraft."""
        if df.empty or 'FL' not in df.columns:
            df['H(ft)'] = np.nan
            df['H(m)'] = np.nan
            return df

        # Sort by aircraft and time
        if 'TA' in df.columns and 'Time_sec' in df.columns:
            df = df.sort_values(['TA', 'Time_sec']).reset_index(drop=True)

        # Initialize with NaN
        df['H(ft)'] = np.nan
        df['H(m)'] = np.nan

        alt_ft = df['FL'].fillna(0.0) * 100.0
        below_ta_mask = alt_ft < self.TRANSITION_ALTITUDE_FT

        # ✅ Above TL or no FL: stays NaN (already initialized)
        if not below_ta_mask.any():
            return df

        has_ta = 'TA' in df.columns
        has_bp = 'BP' in df.columns

        if not has_ta:
            # No aircraft ID: simple correction
            if has_bp:
                non_std_mask = below_ta_mask & (
                        (df['BP'] > self.QNH_STD + 0.25) |
                        (df['BP'] < self.QNH_STD - 0.25)
                )
                # Apply correction where non-standard
                bp = df.loc[non_std_mask, 'BP']
                correction = (bp - self.QNH_STD) * self.FT_PER_HPA
                df.loc[non_std_mask, 'H(ft)'] = alt_ft[non_std_mask] + correction

                # ✅ Standard BP or no BP: use uncorrected altitude
                std_or_no_bp = below_ta_mask & ~non_std_mask
                df.loc[std_or_no_bp, 'H(ft)'] = alt_ft[std_or_no_bp]
            else:
                # No BP column: use uncorrected altitude for all below TL
                df.loc[below_ta_mask, 'H(ft)'] = alt_ft[below_ta_mask]

            # Convert to meters
            df.loc[df['H(ft)'].notna(), 'H(m)'] = df.loc[df['H(ft)'].notna(), 'H(ft)'] * 0.3048
            return df

        # ✅ Vectorized per-aircraft processing with state persistence
        df_below = df[below_ta_mask].copy()

        for ta, group in df_below.groupby('TA'):
            indices = group.index
            fls = group['FL'].values
            bps = group['BP'].values if has_bp else np.full(len(group), np.nan)

            # Find non-standard BP
            non_std = np.abs(bps - self.QNH_STD) > 0.25

            # Forward-fill last valid QNH (persistencia temporal)
            qnh_values = np.full(len(group), np.nan)
            last_qnh = self._last_qnh.get(ta, None)

            for i in range(len(group)):
                # Update stored QNH if non-standard BP arrives
                if non_std[i] and not np.isnan(bps[i]):
                    last_qnh = bps[i]
                    self._last_qnh[ta] = last_qnh

                # Use stored QNH (even if current BP is standard)
                if last_qnh is not None:
                    qnh_values[i] = last_qnh

            # Vectorized correction
            has_qnh = ~np.isnan(qnh_values)
            has_fl = ~np.isnan(fls)

            # Apply correction where QNH is available
            correction_mask = has_qnh & has_fl
            if correction_mask.any():
                alt_vals = fls[correction_mask] * 100.0
                corrections = (qnh_values[correction_mask] - self.QNH_STD) * self.FT_PER_HPA
                corrected = alt_vals + corrections
                df.loc[indices[correction_mask], 'H(ft)'] = corrected

            # ✅ No QNH available: use uncorrected altitude (FL * 100)
            no_qnh_mask = ~has_qnh & has_fl
            if no_qnh_mask.any():
                df.loc[indices[no_qnh_mask], 'H(ft)'] = fls[no_qnh_mask] * 100.0

        # Convert to meters
        df.loc[df['H(ft)'].notna(), 'H(m)'] = df.loc[df['H(ft)'].notna(), 'H(ft)'] * 0.3048

        return df
