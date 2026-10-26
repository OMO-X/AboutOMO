import json
import csv

with open('examples/can_speed_15kmh.json', 'r') as f:
    records = json.load(f)

moving_frames = {}
for r in records:
    moving_frames[r['CAN_ID']] = r['Bytes']

with open('examples/can_capture.csv', 'r') as f:
    reader = csv.DictReader(f)
    stat_frames = {}
    for r in reader:
        cid = r['CAN_ID']
        if cid not in stat_frames:
            stat_frames[cid] = [int(r[f'Byte{i}'], 16) if r[f'Byte{i}'].startswith('0x') else int(r[f'Byte{i}']) for i in range(8)]

print('=== CHANGES BETWEEN STATIONARY (0 km/h) AND MOVING (15 km/h, ~1100 RPM) ===')
for cid in sorted(moving_frames.keys()):
    if cid in stat_frames:
        mb = moving_frames[cid]
        sb = stat_frames[cid]
        diffs = []
        for i in range(8):
            if mb[i] != sb[i]:
                diffs.append((i, sb[i], mb[i]))
        if diffs:
            print(f'CAN ID {cid}:')
            print(f'   Stat : {" ".join(f"{x:02X}" for x in sb)}')
            print(f'   Move : {" ".join(f"{x:02X}" for x in mb)}')
            for idx, s_val, m_val in diffs:
                print(f'     Byte {idx}: {s_val} (0x{s_val:02X}) -> {m_val} (0x{m_val:02X}) [diff: {m_val - s_val}]')
