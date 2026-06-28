# Analysis & Tuning — Technical Reference

This document captures the engineering analysis of ride data
and the theoretical foundation for tuning recommendations.
It is referenced by BACKLOG items ANL1–ANL3.

---

## NB Oxygen Sensor — Scale and Behavior

The stock narrow-band (NB) O2 sensor outputs 0.0V–1.0V analog.
The DDFI2 ECU converts this to an 8-bit ADC value (O2_ADC, 0–255).

| O2_ADC | Voltage | Mixture |
|--------|---------|---------|
| 0      | 0.0V    | Extremely lean |
| 128    | 0.5V    | Stoichiometric (14.7 AFR) |
| 255    | 1.0V    | Extremely rich |

Conversion: ~25 ADC units = 0.1V

---

## Operating States

**Open Loop (fl_closed_loop = 0)**
During warmup (CLT below threshold), O2_ADC holds a static
bias value near 101. ECU ignores the sensor. Do not use this
data for tuning analysis.

**Closed Loop (fl_closed_loop = 1)**
When warm, O2_ADC oscillates rapidly around 128:
- Peaks 147–154 (~0.6V) = rich
- Drops 74–89 (~0.3V) = lean

---

## EGO Correction Logic

EGO_Corr is the real-time closed-loop fuel correction (%).
- 100% = no correction needed
- >100% = ECU adding fuel (map is lean)
- <100% = ECU removing fuel (map is rich)

Tuning recommendation logic per RPM/Load cell:
- If avg EGO_Corr > 105%: increase VE map cell by ~5%
- If avg EGO_Corr < 95%: decrease VE map cell by ~5%
- Only use samples where fl_closed_loop = 1 AND CLT > warmup threshold

---

## VBA Tools (Excel)

Two macros developed for offline analysis:

**GenerateHeatmapFromJSON** — reads ride JSON, bins samples
by RPM/TPS into a 12x13 heatmap matrix matching EEPROM map axes.

**Smooth_Selected_Area** — applies weighted Laplacian smoothing
to a selected map region. Parameters: lambda=0.25, iterations=2.
Protects shape — ignores deltas > 6 counts. Weights neighbors
by inverse distance on RPM/TPS axes.

---

## Planned Dashboard Features

See BACKLOG items:
- BACKLOG-ANL1: EGO correction heatmap per cell
- BACKLOG-ANL2: O2_ADC trend overlay on VE heatmap  
- BACKLOG-ANL3: Ride data heatmap export from dashboard
