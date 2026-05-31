#!/usr/bin/env python3
"""
DDFI2 TCP-serial bridge for protocol monitoring.
Bridges EcmSpy (TCP client) <-> ECU (serial /dev/ttyECU).
Logs every byte with direction, timestamp, and hex+ASCII.
"""
import socket, serial, threading, time, os, sys

SERIAL_PORT = '/dev/ttyECU'
BAUD        = 9600
TCP_PORT    = 2323
LOG_FILE    = '/tmp/ecm_trace.log'

def ts():
    return time.strftime('%H:%M:%S') + f'.{int(time.time()*1000)%1000:03d}'

def log(line):
    print(line, flush=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def hexdump(data, direction):
    hexs  = ' '.join(f'{b:02x}' for b in data)
    chars = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    log(f'{ts()} {direction} [{len(data):3d}] {hexs:<48}  |{chars}|')

def serial_to_socket(ser, sock, stop):
    """Read from serial (ECU), write to socket (EcmSpy)."""
    while not stop.is_set():
        try:
            waiting = ser.in_waiting
            data = ser.read(waiting if waiting > 0 else 1)
            if data:
                hexdump(data, 'ECU→PC')
                sock.sendall(data)
        except Exception as e:
            if not stop.is_set():
                log(f'[serial→socket] {e}')
            break
    stop.set()

def socket_to_serial(sock, ser, stop):
    """Read from socket (EcmSpy), write to serial (ECU)."""
    while not stop.is_set():
        try:
            data = sock.recv(256)
            if not data:
                break
            hexdump(data, 'PC→ECU')
            ser.write(data)
        except Exception as e:
            if not stop.is_set():
                log(f'[socket→serial] {e}')
            break
    stop.set()

def main():
    # Clear log
    with open(LOG_FILE, 'w') as f:
        f.write(f'=== ECM bridge started {ts()} ===\n')
        f.write(f'    serial: {SERIAL_PORT} @ {BAUD}\n')
        f.write(f'    tcp: 0.0.0.0:{TCP_PORT}\n\n')

    log(f'Opening {SERIAL_PORT} @ {BAUD}...')
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.05,
                            bytesize=8, parity='N', stopbits=1)
    except Exception as e:
        log(f'ERROR: cannot open serial: {e}')
        sys.exit(1)
    log('Serial OK.')

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', TCP_PORT))
    srv.listen(1)
    log(f'Waiting for EcmSpy on TCP port {TCP_PORT}...')
    log('(connect EcmSpy to the virtual COM port now)')

    while True:
        try:
            conn, addr = srv.accept()
        except KeyboardInterrupt:
            break
        log(f'\n{"="*60}')
        log(f'CONNECTION from {addr[0]}:{addr[1]}')
        log(f'{"="*60}')

        stop = threading.Event()
        t1 = threading.Thread(target=serial_to_socket, args=(ser, conn, stop), daemon=True)
        t2 = threading.Thread(target=socket_to_serial, args=(conn, ser, stop), daemon=True)
        t1.start()
        t2.start()
        stop.wait()
        conn.close()
        log(f'{"="*60}')
        log('CONNECTION CLOSED — waiting for next connection...\n')

    ser.close()
    srv.close()

if __name__ == '__main__':
    main()
