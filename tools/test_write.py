#!/usr/bin/env python3
"""
DDFI2 write protocol test.
Reads current EEPROM, writes same bytes back (no actual change),
reads again and verifies. Safe: ECU content unchanged.

Usage: python3 test_write.py [--dry-run]
"""
import sys, time
sys.path.insert(0, '/home/pi/buell')

from ecu.connection import (
    DDFI2Connection, BUEIB_PAGES, build_pdu,
    SOH, DROID_ID, EOH, SOT, EOT, ACK, CMD_GET
)

CMD_SET = 0x57  # candidate write command ('W')

DRY_RUN = '--dry-run' in sys.argv

def write_eeprom_page(conn, page_nr, offset, data):
    """
    Attempt to write `data` bytes to ECU EEPROM at page/offset.
    Returns True on ACK, False on NACK/timeout.
    """
    payload = bytes([CMD_SET, offset & 0xFF, page_nr & 0xFF, len(data) & 0xFF]) + bytes(data)
    pdu = build_pdu(payload)

    print(f'  WRITE page={page_nr} offset={offset} len={len(data)}')
    print(f'    PDU:  {pdu.hex()}')

    conn._send(pdu)
    try:
        h = conn._read_exact(6, 2.0)
    except TimeoutError:
        print(f'    TIMEOUT waiting for response header')
        return False

    print(f'    RESP: {h.hex()}')

    if h[0] != SOH:
        print(f'    BAD: expected SOH 0x01, got 0x{h[0]:02x}')
        return False

    length_field = h[3]
    try:
        rest = conn._read_exact(length_field - 1 + 2, 2.0)
    except TimeoutError:
        print(f'    TIMEOUT reading response body')
        return False

    full = h + rest
    print(f'    FULL: {full.hex()}')

    if full[6] == ACK:
        print(f'    ACK ✓')
        return True
    else:
        print(f'    NACK: byte[6]=0x{full[6]:02x}')
        return False


def main():
    print('=== DDFI2 Write Protocol Test ===')
    print(f'CMD_SET candidate: 0x{CMD_SET:02x} ({chr(CMD_SET)})')
    print(f'Mode: {"DRY RUN (no writes)" if DRY_RUN else "LIVE (will write same data back)"}')
    print()

    conn = DDFI2Connection('/dev/ttyECU')
    try:
        conn.connect()
    except Exception as e:
        print(f'Connect failed: {e}')
        sys.exit(1)

    ver = conn.get_version()
    if not ver:
        print('ERROR: could not get ECU version')
        sys.exit(1)
    print(f'ECU version: {ver}')

    print('\n--- Step 1: Read full EEPROM ---')
    eeprom_before = conn.read_full_eeprom()
    if not eeprom_before:
        print('ERROR: read failed')
        sys.exit(1)
    print(f'Read OK: {len(eeprom_before)} bytes')
    print(f'  [0:8]  = {eeprom_before[:8].hex()}')
    print(f'  [12:14]= {eeprom_before[12:14].hex()}  (serial = {int.from_bytes(eeprom_before[12:14], "little")})')

    if DRY_RUN:
        print('\nDRY RUN: skipping write test.')
        print('Run without --dry-run to test the write command.')
        sys.exit(0)

    print('\n--- Step 2: Write first page chunk (4 bytes) back ---')
    print('Writing page 1, offset 0, 4 bytes (same data = no change)')
    test_data = eeprom_before[0:4]
    print(f'  Data to write: {test_data.hex()}')

    ok = write_eeprom_page(conn, page_nr=1, offset=0, data=test_data)

    if ok:
        print('\n✓ ACK received — write command 0x57 confirmed!')
        print('\n--- Step 3: Read back and verify ---')
        eeprom_after = conn.read_full_eeprom()
        if eeprom_after:
            if eeprom_after[:4] == test_data:
                print(f'✓ Read-back matches: {eeprom_after[:4].hex()}')
            else:
                print(f'! Read-back differs: got {eeprom_after[:4].hex()}, expected {test_data.hex()}')
            if eeprom_after == eeprom_before:
                print('✓ Full EEPROM unchanged (safe write confirmed)')
            else:
                diffs = sum(1 for a,b in zip(eeprom_after, eeprom_before) if a != b)
                print(f'! {diffs} bytes differ from original (unexpected)')
    else:
        print('\n✗ Write with 0x57 failed — wrong command byte or different protocol')
        print('\nTrying alternative command 0x53 (S)...')
        # Try CMD_SET2 = 0x53 as fallback
        import ecu.connection as _ec
        _ec_orig = _ec.CMD_GET
        CMD_SET2 = 0x53
        payload2 = bytes([CMD_SET2, 0, 1, 4]) + bytes(test_data)
        pdu2 = build_pdu(payload2)
        conn._send(pdu2)
        try:
            h2 = conn._read_exact(6, 2.0)
            print(f'  0x53 response header: {h2.hex()}')
            if h2[0] == SOH:
                rest2 = conn._read_exact(h2[3] - 1 + 2, 2.0)
                full2 = h2 + rest2
                print(f'  0x53 full response: {full2.hex()}')
                if full2[6] == ACK:
                    print('✓ ACK with 0x53!')
                else:
                    print(f'  NACK: 0x{full2[6]:02x}')
        except TimeoutError:
            print('  0x53 → TIMEOUT')

    conn.ser.close()
    print('\nDone.')

if __name__ == '__main__':
    main()
