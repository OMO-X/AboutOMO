import urllib.request
import json

def get_snapshot():
    req = urllib.request.urlopen('http://127.0.0.1:8080/api/snapshot', timeout=5)
    data = json.loads(req.read().decode())
    print(f"COM3 Connected: {data['stats']['com3_connected']}")
    print(f"Total Frames  : {data['stats']['total_frames']} | FPS: {data['stats']['fps']}")
    print(f"Active CAN IDs: {len(data['frames'])}\n")
    print(f"{'CAN ID':<8} | {'DLC':<4} | {'Hex Payload':<26} | {'Decoded / Notes'}")
    print("-" * 65)

    frames = data['frames']
    for cid in sorted(frames.keys()):
        f = frames[cid]
        b = f['bytes']
        hex_str = f['hex']
        notes = []

        # Check for ODO (2117 or 21170)
        for i in range(len(b) - 1):
            u16_be = (b[i] << 8) | b[i+1]
            if u16_be == 21170:
                notes.append(f"ODO = 2117.0 km (Bytes {i}-{i+1})")
            elif u16_be == 2117:
                notes.append(f"ODO = 2117 km (Bytes {i}-{i+1})")

        # Check for SOC (58 or 580)
        for i in range(len(b)):
            if b[i] == 58:
                notes.append(f"SOC = 58% (Byte {i})")
        for i in range(len(b) - 1):
            u16_be = (b[i] << 8) | b[i+1]
            u16_le = (b[i+1] << 8) | b[i]
            if u16_be == 580:
                notes.append(f"SOC = 58.0% (Bytes {i}-{i+1} BE)")
            if u16_le == 580:
                notes.append(f"SOC = 58.0% (Bytes {i}-{i+1} LE)")

        # Check for Range (121 or 1210)
        for i in range(len(b)):
            if b[i] == 121:
                notes.append(f"Range = 121 km (Byte {i})")
        for i in range(len(b) - 1):
            u16_be = (b[i] << 8) | b[i+1]
            u16_le = (b[i+1] << 8) | b[i]
            if u16_be in [121, 1210]:
                notes.append(f"Range = {u16_be} (Bytes {i}-{i+1} BE)")
            if u16_le in [121, 1210]:
                notes.append(f"Range = {u16_le} (Bytes {i}-{i+1} LE)")

        # Check for Trip (100 or 1)
        for i in range(len(b) - 1):
            u16_be = (b[i] << 8) | b[i+1]
            u16_le = (b[i+1] << 8) | b[i]
            if u16_be == 100:
                notes.append(f"Trip = 100m (Bytes {i}-{i+1} BE)")
            if u16_le == 100:
                notes.append(f"Trip = 100m (Bytes {i}-{i+1} LE)")

        note_str = ", ".join(notes) if notes else ""
        print(f"{cid:<8} | {f['dlc']:<4} | {hex_str:<26} | {note_str}")

if __name__ == '__main__':
    get_snapshot()
