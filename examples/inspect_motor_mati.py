import urllib.request
import json
import time

print("=== MEMERIKSA STATUS CAN BUS SAAT MOTOR MATI & LAMPU MATI ===")

try:
    req = urllib.request.urlopen('http://127.0.0.1:8080/api/snapshot', timeout=5)
    data = json.loads(req.read().decode())
    stats = data['stats']
    frames = data['frames']

    print(f"COM3 Status : {'TERHUBUNG' if stats['com3_connected'] else 'TERPUTUS'}")
    print(f"Bus Rate    : {stats['fps']} fps | Total Frame: {stats['total_frames']}")
    print(f"Jumlah ID Aktif: {len(frames)} CAN ID\n")

    print(f"{'CAN ID':<8} | {'DLC':<4} | {'Hex Payload':<26} | {'Analisa / Catatan Status MATI'}")
    print("-" * 75)

    for cid in sorted(frames.keys()):
        f = frames[cid]
        b = f['bytes']
        hex_str = f['hex']
        note = ""

        if cid == '0x233':
            duty_l = b[6] if len(b) > 6 else 0
            duty_r = b[7] if len(b) > 7 else 0
            note = f"DRL: Duty={duty_l}/{duty_r}"
        elif cid == '0x112':
            note = f"Ignition/Pwr Status: Byte 1 = 0x{b[1]:02X}"
        elif cid == '0x262':
            note = f"Stand/Safety: Byte 4 = 0x{b[4]:02X}"
        elif cid == '0x272':
            odo = ((b[5] << 8) | b[6]) / 10.0 if len(b) > 6 else 0
            range_km = b[7] if len(b) > 7 else 0
            note = f"ODO={odo} km, Range={range_km} km"
        elif cid == '0x236':
            tq = (b[0] << 8) | b[1]
            if tq & 0x8000: tq -= 0x10000
            note = f"Regen Tq={tq} Nm"
        elif cid.startswith('0x5'):
            note = "BMS Telemetry"

        print(f"{cid:<8} | {f['dlc']:<4} | {hex_str:<26} | {note}")

except Exception as e:
    print(f"Error fetching snapshot: {e}")
