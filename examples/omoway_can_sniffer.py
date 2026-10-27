#!/usr/bin/env python3
"""
OMOWAY CAN Bus Sniffer & Logger
MKS CANable v2 Pro (slcan firmware)
"""

import sys
import os
import time
import argparse
from datetime import datetime
import serial

def parse_slcan_frame(line: str):
    """
    Parse SLCAN format:
    Standard frame: t<id:3><len:1><data:2*len>
    Extended frame: T<id:8><len:1><data:2*len>
    """
    line = line.strip()
    if not line:
        return None
    
    is_extended = False
    if line.startswith('t'):
        # Standard: t1438000B036BDEA1DC1D
        can_id_hex = line[1:4]
        dlc_char = line[4:5]
        data_hex = line[5:]
    elif line.startswith('T'):
        # Extended: T000001438000B036BDEA1DC1D
        is_extended = True
        can_id_hex = line[1:9]
        dlc_char = line[9:10]
        data_hex = line[10:]
    else:
        return None
    
    try:
        can_id = int(can_id_hex, 16)
        dlc = int(dlc_char, 16)
        data = bytes.fromhex(data_hex[:dlc*2])
        return {
            'id': can_id,
            'id_hex': f"0x{can_id:03X}" if not is_extended else f"0x{can_id:08X}",
            'is_extended': is_extended,
            'dlc': dlc,
            'data': data,
            'data_hex': ' '.join(f"{b:02X}" for b in data),
            'raw': line
        }
    except Exception:
        return None

def run_capture(port='COM3', baud_cmd='S6', duration=10, delay=0, output_csv=None, output_log=None):
    if delay > 0:
        print(f"Persiapan! Mulai merekam dalam {int(delay)} detik...")
        for sec in range(int(delay), 0, -1):
            print(f"  {sec}...")
            time.sleep(1.0)
        print(">>> MULAI MEREKAM SEKARANG! <<<")

    print(f"Connecting to {port} (Baud {baud_cmd} = 500kbps)...")
    try:
        ser = serial.Serial(port, baudrate=115200, timeout=0.1)
    except Exception as e:
        print(f"Failed to open {port}: {e}")
        return

    # Initialize SLCAN
    ser.write(b'C\r')
    time.sleep(0.05)
    ser.write((baud_cmd + '\r').encode('ascii'))
    time.sleep(0.05)
    ser.write(b'O\r')
    time.sleep(0.05)
    ser.reset_input_buffer()

    print(f"=== Recording CAN Bus for {duration} seconds... ===")
    
    csv_file = None
    if output_csv:
        csv_file = open(output_csv, 'w', encoding='utf-8')
        csv_file.write("Timestamp,CAN_ID,DLC,Data_Hex,Byte0,Byte1,Byte2,Byte3,Byte4,Byte5,Byte6,Byte7\n")

    log_file = None
    if output_log:
        log_file = open(output_log, 'w', encoding='utf-8')

    id_stats = {}
    total_frames = 0
    start_time = time.time()
    raw_buf = ""

    try:
        while time.time() - start_time < duration:
            in_waiting = ser.in_waiting
            if in_waiting > 0:
                chunk = ser.read(in_waiting).decode('ascii', errors='ignore')
                raw_buf += chunk
                while '\r' in raw_buf:
                    line, _, raw_buf = raw_buf.partition('\r')
                    line = line.strip()
                    if not line:
                        continue
                    
                    frame = parse_slcan_frame(line)
                    if frame:
                        now = time.time()
                        total_frames += 1
                        cid = frame['id_hex']
                        
                        if cid not in id_stats:
                            id_stats[cid] = {
                                'count': 0,
                                'last_time': now,
                                'intervals': [],
                                'last_data': frame['data'],
                                'dlc': frame['dlc']
                            }
                        else:
                            interval = now - id_stats[cid]['last_time']
                            id_stats[cid]['intervals'].append(interval)
                            id_stats[cid]['last_time'] = now
                            id_stats[cid]['last_data'] = frame['data']
                        
                        id_stats[cid]['count'] += 1

                        if csv_file:
                            byte_vals = [f"0x{b:02X}" for b in frame['data']]
                            while len(byte_vals) < 8:
                                byte_vals.append("")
                            csv_file.write(f"{now:.6f},{frame['id_hex']},{frame['dlc']},{frame['data_hex']}," + ",".join(byte_vals) + "\n")
                        
                        if log_file:
                            # candump format: (timestamp) can0 143#000B036BDEA1DC1D
                            raw_data = frame['data'].hex().upper()
                            log_file.write(f"({now:.6f}) can0 {frame['id']:03X}#{raw_data}\n")
            time.sleep(0.005)

    except KeyboardInterrupt:
        print("\nStopping capture...")
    finally:
        ser.write(b'C\r')
        ser.close()
        if csv_file:
            csv_file.close()
        if log_file:
            log_file.close()

    elapsed = time.time() - start_time
    print(f"\nCapture finished: {total_frames} frames received in {elapsed:.2f}s (~{total_frames/elapsed:.1f} fps)")
    print(f"{'CAN ID':<10} | {'DLC':<4} | {'Count':<7} | {'Freq (Hz)':<10} | {'Last Data (Hex)':<26}")
    print("-" * 68)

    for cid in sorted(id_stats.keys()):
        stat = id_stats[cid]
        cnt = stat['count']
        freq = (cnt / elapsed) if elapsed > 0 else 0
        data_str = ' '.join(f"{b:02X}" for b in stat['last_data'])
        print(f"{cid:<10} | {stat['dlc']:<4} | {cnt:<7} | {freq:>8.1f} Hz | {data_str:<26}")

    return id_stats

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="OMOWAY CAN Bus Sniffer")
    parser.add_argument('--port', default='COM3', help="Serial port (default: COM3)")
    parser.add_argument('--baud', default='S6', help="SLCAN baud code (default: S6 = 500k)")
    parser.add_argument('--duration', type=float, default=5.0, help="Duration in seconds (default: 5.0)")
    parser.add_argument('--delay', type=float, default=0.0, help="Countdown delay before capture in seconds")
    parser.add_argument('--csv', default='can_capture.csv', help="CSV output path")
    parser.add_argument('--log', default='can_capture.candump.log', help="candump log path")
    args = parser.parse_args()

    run_capture(port=args.port, baud_cmd=args.baud, duration=args.duration, delay=args.delay, output_csv=args.csv, output_log=args.log)
