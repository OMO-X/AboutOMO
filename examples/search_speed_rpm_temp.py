import json

with open('examples/can_speed_15kmh.json', 'r') as f:
    records = json.load(f)

latest_by_id = {}
for r in records:
    latest_by_id[r['CAN_ID']] = r

print('=== 1. SEARCH FOR MOTOR RPM (~1100 RPM, range 950..1250) ===')
for cid, r in sorted(latest_by_id.items()):
    b = r['Bytes']
    hex_str = r['Hex']
    for i in range(len(b) - 1):
        u16_be = (b[i] << 8) | b[i+1]
        u16_le = (b[i+1] << 8) | b[i]
        if 950 <= u16_be <= 1250:
            print(f"MATCH RPM BE! {cid} Bytes {i}-{i+1}: {u16_be} RPM (0x{u16_be:04X}) | Payload: {hex_str}")
        if 950 <= u16_le <= 1250:
            print(f"MATCH RPM LE! {cid} Bytes {i}-{i+1}: {u16_le} RPM (0x{u16_le:04X}) | Payload: {hex_str}")

print('\n=== 2. SEARCH FOR SPEED (15 km/h, 15, 150, 1500) ===')
for cid, r in sorted(latest_by_id.items()):
    b = r['Bytes']
    hex_str = r['Hex']
    for i in range(len(b)):
        if b[i] == 15:
            print(f"MATCH Speed 1-byte (15)! {cid} Byte {i}: 15 (0x0F) | Payload: {hex_str}")
    for i in range(len(b) - 1):
        u16_be = (b[i] << 8) | b[i+1]
        u16_le = (b[i+1] << 8) | b[i]
        if u16_be in [15, 150, 1500]:
            print(f"MATCH Speed 16-bit BE! {cid} Bytes {i}-{i+1}: {u16_be} | Payload: {hex_str}")
        if u16_le in [15, 150, 1500]:
            print(f"MATCH Speed 16-bit LE! {cid} Bytes {i}-{i+1}: {u16_le} | Payload: {hex_str}")

print('\n=== 3. SEARCH FOR TEMPERATURES: BLDC = 26 C (raw 26 or 66), Controller = 31 C (raw 31 or 71) ===')
for cid, r in sorted(latest_by_id.items()):
    b = r['Bytes']
    hex_str = r['Hex']
    # Check if a frame contains both (or either)
    has_bldc_raw = any(x == 26 for x in b)
    has_bldc_offset = any(x == 66 for x in b) # 66 - 40 = 26
    has_mcu_raw = any(x == 31 for x in b)
    has_mcu_offset = any(x == 71 for x in b)  # 71 - 40 = 31
    
    if (has_bldc_raw and has_mcu_raw) or (has_bldc_offset and has_mcu_offset):
        print(f"PERFECT COMBO! {cid} Payload: {hex_str} -> {b}")
    elif (has_bldc_raw or has_bldc_offset) and (has_mcu_raw or has_mcu_offset):
        print(f"COMBO! {cid} Payload: {hex_str} -> {b}")
    elif has_bldc_raw or has_bldc_offset or has_mcu_raw or has_mcu_offset:
        notes = []
        if has_bldc_raw: notes.append('BLDC raw 26')
        if has_bldc_offset: notes.append('BLDC offset 66 (26C)')
        if has_mcu_raw: notes.append('MCU raw 31')
        if has_mcu_offset: notes.append('MCU offset 71 (31C)')
        print(f"Candidate {cid}: {', '.join(notes)} | Payload: {hex_str}")
