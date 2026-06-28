# ECU Definitions — Buell DDFI

ECU parameter definitions extracted from EcmSpy (open source).
Each XML defines EEPROM offsets, scaling, and parameter names for one ECU variant.

## Files

| File | ECU | Model | Params |
|------|-----|-------|--------|
| BUEIB.xml | BUEIB | XB12X/XB12R/XB12S 2006-2010 | 238 |
| B2RIB.xml | B2RIB | XB models (variant) | 243 |
| BUEGB.xml | BUEGB | XB9/XB12 variant | 231 |
| BUECB.xml | BUECB | XB variant | 213 |
| BUE3D.xml | BUE3D | Ulysses/1125 | 645 |
| BUE2D.xml | BUE2D | XB9/XB12 2004-2005 | 538 |
| BUE1D.xml | BUE1D | XB9/XB12 2003 | 533 |
| BUEOD.xml | BUEOD | variant | 411 |
| BUEWD.xml | BUEWD | variant | 514 |
| BUEYD.xml | BUEYD | variant | 528 |
| BUEZD.xml | BUEZD | variant | 534 |
| BUEIA.xml | BUEIA | Blast | 144 |
| BUEKA.xml | BUEKA | variant | 148 |
| BUEGC.xml | BUEGC | variant | 110 |

## XML Structure

Each file contains `eeoffsets` entries with:
- `offset` — byte position in XPR file (includes 4-byte header)
- `scale` / `translate` — value = raw * scale + translate
- `type` — Value, Table, Map, Array, Bits, Axis
- `units` — physical units

## ECU Detection

The logger reads `version_string` from the ECU (e.g. `BUEIB310 12-11-03`).
The first word maps to the XML filename: `BUEIB` → `ecu_defs/BUEIB.xml`.
