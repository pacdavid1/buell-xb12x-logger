# DDFI2 Serial Protocol & EEPROM Burn — Technical Reference

Last updated: 2026-05-31
Status: Read confirmed in production. Write confirmed experimentally (2026-05-31).

---

## Overview

The Buell XB12X uses a **Delphi DDFI-2** ECU connected via serial at 9600,8N1.
The Pi communicates through a CH343P USB-to-serial adapter symlinked to `/dev/ttyECU`.

EcmSpy (the reference Windows tool) reads and writes the ECU using this same protocol.
Everything documented here was reverse-engineered from the Pi's own implementation
and confirmed against EcmSpy's behavior and byte traces.

---

## 1. PDU Frame Structure

Every message in both directions uses the same envelope:

```
SOH  DROID_ID  ECM_ID  LENGTH  EOH  SOT  [PAYLOAD]  EOT  CHECKSUM
0x01   0x00     0x42    N+1    0xFF  0x02  N bytes   0x03   XOR
```

| Field    | Value  | Notes                                     |
|----------|--------|-------------------------------------------|
| SOH      | `0x01` | Start of header                           |
| DROID_ID | `0x00` | Always 0x00 for this ECU                 |
| ECM_ID   | `0x42` | DDFI-2 ECU identifier                    |
| LENGTH   | N+1    | Payload bytes + 1                         |
| EOH      | `0xFF` | End of header                             |
| SOT      | `0x02` | Start of transmission                     |
| PAYLOAD  | —      | Command-specific (see below)              |
| EOT      | `0x03` | End of transmission                       |
| CHECKSUM | XOR    | XOR of all bytes from DROID_ID to EOT    |

Checksum calculation (from `build_pdu()`):
```python
cs = 0
for b in frame[1:]:   # everything after SOH
    cs ^= b
```

ECU response uses the same frame structure with ECM_ID and DROID_ID swapped.

---

## 2. Known Commands

| Command    | Byte   | Direction | Description          |
|------------|--------|-----------|----------------------|
| `CMD_GET`  | `0x52` | PC → ECU  | Read EEPROM bytes    |
| `CMD_SET`  | `0x57` | PC → ECU  | Write EEPROM bytes   |
| VERSION    | `0x56` | PC → ECU  | Get firmware version |
| RT_DATA    | `0x43` | PC → ECU  | Get real-time data   |
| `ACK`      | `0x06` | ECU → PC  | Acknowledge / OK     |

---

## 3. Read EEPROM — CMD_GET (0x52)

**Payload:** `[0x52, offset, page, count]`

- `offset`: byte offset within the page (0-based)
- `page`: page number (1–6 for BUEIB)
- `count`: number of bytes to read (max 16 per chunk)

**Response payload:** `[ACK, data_byte_0, data_byte_1, …]`

**Example** — read 4 bytes from page 1, offset 0:
```
Sent:     01 00 42 05 FF 02 52 00 01 04 03 <cs>
Received: 01 42 00 06 FF 02 06 <4 bytes> 03 <cs>
```

**Implementation:** `DDFI2Connection.read_eeprom_page(page_nr, offset, length)`

---

## 4. Write EEPROM — CMD_SET (0x57)

**Confirmed 2026-05-31** via direct test on ECU (BUEIB310 12-11-03, serial #235).

**Payload:** `[0x57, offset, page, data_byte_0, data_byte_1, …]`

- No explicit length field — the number of bytes to write is determined by
  the PDU LENGTH field minus the 3 header bytes (CMD + offset + page).
- The ECU writes the data bytes starting at `page:offset`.
- Chunk size: up to 16 bytes per PDU (same limit as reads).

**Response:** same frame with `ACK (0x06)` on success.

**Example** — write `[0x5A, 0x3C]` to page 1, offset 8:
```
Payload:  57 08 01 5A 3C
PDU:      01 00 42 06 FF 02 57 08 01 5A 3C 03 <cs>
Response: 01 42 00 02 FF 02 06 03 <cs>       ← ACK
```

**Common mistake:** do NOT include a length byte in the payload.
The structure `[CMD_SET, offset, page, LENGTH, data...]` is wrong —
the ECU will interpret LENGTH as the first data byte and write it.
Correct: `[CMD_SET, offset, page, data...]`

---

## 5. EEPROM Layout — BUEIB

6 pages, 1206 bytes total. Page map from `ecu/connection.py`:

```python
BUEIB_PAGES = [
    (1,    0, 256),   # page 1: bytes    0-255
    (2,  256, 256),   # page 2: bytes  256-511
    (3,  512, 158),   # page 3: bytes  512-669
    (4,  670, 256),   # page 4: bytes  670-925
    (5,  926, 256),   # page 5: bytes  926-1181
    (6, 1182,  24),   # page 6: bytes 1182-1205
]
```

Key regions (from `ecu_defs/BUEIB.xml`):

| Offset | Name              | Size      |
|--------|-------------------|-----------|
| 12-13  | Bike serial #     | uint16 LE |
| 602    | Timing Load Axis  | 10 bytes  |
| 612    | Timing RPM Axis   | 10 bytes  |
| 632    | Fuel Load Axis    | 12 bytes  |
| 644    | Fuel RPM Axis     | 13 bytes  |
| 670    | Timing Front map  | 10×10     |
| 770    | Timing Rear map   | 10×10     |
| 870    | Fuel Front map    | 12×13     |
| 1038   | Fuel Rear map     | 12×13     |

Map axes (read from actual EEPROM, consistent across sessions):
```
Fuel Load (TPS): [10, 15, 20, 30, 40, 50, 60, 80, 100, 125, 175, 255]
Fuel RPM:        [0, 800, 1000, 1350, 1900, 2400, 2900, 3400, 4000, 5000, 6000, 7000, 8000]
Timing Load:     [10, 20, 30, 45, 60, 80, 100, 125, 175, 255]
Timing RPM:      [800, 1000, 1350, 2000, 3000, 4000, 4500, 5500, 6500, 7000]
```

---

## 6. XPR File Format (EcmSpy)

XPR is EcmSpy's EEPROM save/load format.

**Structure:** `eeprom.bin (1206 bytes)` + `4-byte footer`

Footer: `00 00 64 XX` where the first 3 bytes are constant and the last byte
varies. It is NOT a checksum of the EEPROM data. Likely a protocol-level
artifact from the read response. EcmSpy accepts any value in the last byte.

**Confirmed (2026-05-31):** the Pi's `eeprom.bin` for session `1E447A` is
byte-identical to `fetched_BUEIB_20260517-1804.xpr[0:1206]`.

**Generating XPR from Pi:**
```python
xpr = eeprom_bin + bytes([0x00, 0x00, 0x64, 0x00])
```

**Pi endpoint:** `GET /eeprom/msq?session=X` generates the MSQ XML equivalent
(fuel + spark tables). The XPR binary endpoint is not yet implemented but
trivial to add (`eeprom.bin + footer`).

---

## 7. MSQ File Format (EcmSpy / TunerStudio)

MSQ is an XML file containing the decoded map values (human-readable).

```xml
<?xml version="1.0"?>
<msq xmlns="http://www.ecmspy.com/">
  <bibliography author="BuellLogger/..." writeDate="..." />
  <versionInfo fileFormat="4" nPages="1" signature="BUEIB" />
  <page number="0">
    <constant name="tpsBins1" rows="12" units="TPS">...</constant>
    <constant name="rpmBins1" rows="13" units="RPM">...</constant>
    <constant name="veBins1"  rows="12" cols="13" units="fuel">...</constant>
    <!-- tpsBins2 / rpmBins2 / veBins2: Fuel Rear -->
    <!-- tpsBins3 / rpmBins3 / advTable1: Spark Front -->
    <!-- tpsBins4 / rpmBins4 / advTable2: Spark Rear -->
  </page>
</msq>
```

**Pi endpoint:** `GET /eeprom/msq?session=X`
Reads `eeprom_decoded.json` if present, otherwise decodes `eeprom.bin` live.

---

## 8. EcmSpy Burn Strategy — BurnDiffs

EcmSpy does NOT write the full 1206 bytes on every burn. It:
1. Reads the current EEPROM from the ECU
2. Compares byte-by-byte with the desired EEPROM
3. Writes only the bytes that differ (`BurnDiffs`)
4. Uses single-byte writes (`BurnByte`) or small chunks

This minimizes write cycles on the EEPROM flash cells.

**Pi implementation target:** same approach —
read → diff against proposed → write changed bytes → verify.

---

## 9. Pi Burn Workflow (planned)

```
MSQ file (proposed tune)
    │
    ▼
parse_msq() → proposed_maps{}
    │
    ▼
eeprom_from_maps() → proposed_bin (1206 bytes)
    │
    ▼
read_full_eeprom() → current_bin
    │
    ▼
diff(current_bin, proposed_bin) → [(offset_abs, new_byte), ...]
    │
    ▼  (only changed bytes)
write_eeprom_page(page, offset, [bytes])  ← CMD_SET 0x57
    │
    ▼
read_full_eeprom() → verify_bin
    │
    ▼
assert verify_bin == proposed_bin  → ✓ burn confirmed
```

Safety rules (to implement):
- Max change per cell: ±15% of current value
- Only burn if `same_bike` (serial matches)
- Require explicit confirmation before burn
- Save backup XPR before any write

---

## 10. Test History

| Date       | Test                         | Result                              |
|------------|------------------------------|-------------------------------------|
| 2026-05-31 | XPR format validation        | XPR = eeprom.bin + 4-byte footer ✓ |
| 2026-05-31 | Pi eeprom.bin vs EcmSpy XPR  | Byte-identical for session 1E447A ✓ |
| 2026-05-31 | CMD_SET 0x57 write test      | ECU ACK confirmed ✓                 |
| 2026-05-31 | Write payload format         | No length field — [CMD, off, page, data…] ✓ |
