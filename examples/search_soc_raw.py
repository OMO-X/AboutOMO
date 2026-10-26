import csv

for fname in ['examples/can_capture.csv', 'examples/can_brake_pressed.csv']:
    print(f"=== Scanning all frames in {fname} ===")
    with open(fname) as f:
        r = csv.DictReader(f)
        matches = []
        for row in r:
            cid = row['CAN_ID']
            for i in range(8):
                b = row.get(f'Byte{i}', '')
                if b in ['0x3A', '58']:
                    matches.append((cid, f"Byte{i}", b, row['Data_Hex']))
                if b in ['0x58', '88']:
                    matches.append((cid, f"Byte{i} (0x58)", b, row['Data_Hex']))
        # Print unique matches
        unique_matches = set(matches)
        for m in sorted(unique_matches):
            print(f"Match: {m[0]} {m[1]} = {m[2]} in payload {m[3]}")
