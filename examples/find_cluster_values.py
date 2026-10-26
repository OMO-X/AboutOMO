import csv
from collections import defaultdict

def search_ground_truth(csv_path):
    print(f"=== Scanning {csv_path} for Ground Truth Values ===")
    print("Targets:")
    print("  - ODO: 2117 km (2117 or 21170 / 0.1km)")
    print("  - SOC: 58 % (58, 580, 116, 145, 148)")
    print("  - Range: 121 km (121, 1210, 242)")
    print("  - Trip: 100 m (100, 1, 1000)\n")

    frames_by_id = defaultdict(list)
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row['CAN_ID']
            bytes_list = []
            for i in range(8):
                val = row.get(f'Byte{i}', '')
                if val.startswith('0x'):
                    bytes_list.append(int(val, 16))
                elif val:
                    bytes_list.append(int(val))
                else:
                    bytes_list.append(0)
            if len(frames_by_id[cid]) < 5:  # take first 5 samples
                frames_by_id[cid].append(bytes_list)

    print("--- ODO Candidates (2117 or 21170) ---")
    for cid, samples in sorted(frames_by_id.items()):
        b = samples[0]
        # Check uint16 BE & LE
        for i in range(7):
            u16_be = (b[i] << 8) | b[i+1]
            u16_le = (b[i+1] << 8) | b[i]
            if u16_be in [2117, 21170]:
                print(f"MATCH ODO! {cid} Bytes {i}-{i+1} (BE): {u16_be} (Hex: 0x{u16_be:04X}) | Payload: {' '.join(f'{x:02X}' for x in b)}")
            if u16_le in [2117, 21170]:
                print(f"MATCH ODO! {cid} Bytes {i}-{i+1} (LE): {u16_le} (Hex: 0x{u16_le:04X}) | Payload: {' '.join(f'{x:02X}' for x in b)}")
        # Check uint24 / uint32
        for i in range(5):
            u32_be = (b[i]<<24) | (b[i+1]<<16) | (b[i+2]<<8) | b[i+3]
            u32_le = (b[i+3]<<24) | (b[i+2]<<16) | (b[i+1]<<8) | b[i]
            if u32_be in [2117, 21170, 211700]:
                print(f"MATCH ODO 32-bit! {cid} Bytes {i}-{i+3} (BE): {u32_be} | Payload: {' '.join(f'{x:02X}' for x in b)}")
            if u32_le in [2117, 21170, 211700]:
                print(f"MATCH ODO 32-bit! {cid} Bytes {i}-{i+3} (LE): {u32_le} | Payload: {' '.join(f'{x:02X}' for x in b)}")

    print("\n--- SOC Candidates (58 %, 580, 116, 145, 148) ---")
    for cid, samples in sorted(frames_by_id.items()):
        b = samples[0]
        for i in range(8):
            if b[i] == 58:  # 0x3A
                print(f"MATCH SOC 1-byte (58%)! {cid} Byte {i}: 58 (0x3A) | Payload: {' '.join(f'{x:02X}' for x in b)}")
            elif b[i] in [116, 145, 148]:
                print(f"Possible scaled SOC (0.5% or 0.4%)! {cid} Byte {i}: {b[i]} (0x{b[i]:02X}) | Payload: {' '.join(f'{x:02X}' for x in b)}")
        for i in range(7):
            u16_be = (b[i] << 8) | b[i+1]
            u16_le = (b[i+1] << 8) | b[i]
            if u16_be == 580 or u16_le == 580:
                print(f"MATCH SOC (58.0% / 0.1%)! {cid} Bytes {i}-{i+1}: 580 | Payload: {' '.join(f'{x:02X}' for x in b)}")

    print("\n--- Remaining Range Candidates (121 km, 1210, 242) ---")
    for cid, samples in sorted(frames_by_id.items()):
        b = samples[0]
        for i in range(8):
            if b[i] == 121:  # 0x79
                print(f"MATCH Range 1-byte (121 km)! {cid} Byte {i}: 121 (0x79) | Payload: {' '.join(f'{x:02X}' for x in b)}")
            elif b[i] == 242:
                print(f"MATCH Range 0.5km (121 km)! {cid} Byte {i}: 242 (0xF2) | Payload: {' '.join(f'{x:02X}' for x in b)}")
        for i in range(7):
            u16_be = (b[i] << 8) | b[i+1]
            u16_le = (b[i+1] << 8) | b[i]
            if u16_be in [121, 1210]:
                print(f"MATCH Range 16-bit (BE)! {cid} Bytes {i}-{i+1}: {u16_be} | Payload: {' '.join(f'{x:02X}' for x in b)}")
            if u16_le in [121, 1210]:
                print(f"MATCH Range 16-bit (LE)! {cid} Bytes {i}-{i+1}: {u16_le} | Payload: {' '.join(f'{x:02X}' for x in b)}")

    print("\n--- Trip Candidates (100 m, 1, 10, 100) ---")
    for cid, samples in sorted(frames_by_id.items()):
        b = samples[0]
        for i in range(7):
            u16_be = (b[i] << 8) | b[i+1]
            u16_le = (b[i+1] << 8) | b[i]
            if u16_be == 100:
                print(f"MATCH Trip (100m BE)! {cid} Bytes {i}-{i+1}: 100 | Payload: {' '.join(f'{x:02X}' for x in b)}")
            if u16_le == 100:
                print(f"MATCH Trip (100m LE)! {cid} Bytes {i}-{i+1}: 100 | Payload: {' '.join(f'{x:02X}' for x in b)}")

if __name__ == '__main__':
    search_ground_truth('examples/can_capture.csv')
