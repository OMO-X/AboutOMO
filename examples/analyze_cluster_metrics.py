import urllib.request
import json

req = urllib.request.urlopen('http://127.0.0.1:8080/api/snapshot', timeout=5)
data = json.loads(req.read().decode())
frames = data['frames']

print("=== DEEP ANALYSIS OF CANDIDATE FRAMES ===")

# Check 0x272
f272 = frames.get('0x272')
if f272:
    b = f272['bytes']
    print("\n--- 0x272 (Cluster Metrics) ---")
    print(f"Payload: {f272['hex']}")
    print(f"Byte 0: {b[0]} (0x{b[0]:02X})")
    print(f"Byte 1: {b[1]} (0x{b[1]:02X})")
    print(f"Byte 2: {b[2]} (0x{b[2]:02X})")
    print(f"Byte 3: {b[3]} (0x{b[3]:02X})")
    print(f"Byte 4: {b[4]} (0x{b[4]:02X})")
    odo_raw = (b[5] << 8) | b[6]
    print(f"Byte 5-6: {odo_raw} -> {odo_raw/10.0} km (CONFIRMED ODO: 2117.1 km)")
    print(f"Byte 7: {b[7]} -> {b[7]} km (CONFIRMED REMAINING RANGE: 121 km)")

# Check 0x282
f282 = frames.get('0x282')
if f282:
    b = f282['bytes']
    print("\n--- 0x282 (Candidate Battery SOC / Cluster) ---")
    print(f"Payload: {f282['hex']}")
    for i, byte in enumerate(b):
        print(f"Byte {i}: {byte} (0x{byte:02X}) | binary: {byte:08b}")
    for i in range(len(b)-1):
        u16 = (b[i] << 8) | b[i+1]
        print(f"Bytes {i}-{i+1} BE: {u16} (0x{u16:04X}) | LE: {(b[i+1]<<8)|b[i]}")

# Check 0x223 (Trip?)
f223 = frames.get('0x223')
if f223:
    b = f223['bytes']
    print("\n--- 0x223 (Trip Candidate) ---")
    print(f"Payload: {f223['hex']}")
    for i, byte in enumerate(b):
        print(f"Byte {i}: {byte} (0x{byte:02X})")

# Check 0x303 (Odometer/Trip alternative?)
f303 = frames.get('0x303')
if f303:
    b = f303['bytes']
    print("\n--- 0x303 ---")
    print(f"Payload: {f303['hex']}")
    for i, byte in enumerate(b):
        print(f"Byte {i}: {byte} (0x{byte:02X})")

# Check 0x564 (BMS Pack SOC / Current / Voltage)
f564 = frames.get('0x564')
if f564:
    b = f564['bytes']
    print("\n--- 0x564 (BMS Pack Status) ---")
    print(f"Payload: {f564['hex']}")
    for i, byte in enumerate(b):
        print(f"Byte {i}: {byte} (0x{byte:02X})")

# Search all bits in all frames for 58 (0x3A = 0011 1010) or 58%
print("\n--- Searching for SOC ~58% in bitfields across all frames ---")
for cid, f in sorted(frames.items()):
    b = f['bytes']
    for i, byte in enumerate(b):
        # Maybe 7-bit field, or byte / 2, or byte * 0.5?
        if byte in [58, 57, 59]:
            print(f"EXACT 58 match: {cid} Byte {i} = {byte} (0x{byte:02X})")
        # If scaled 0.5% (0-200 -> 0-100%): 58 * 2 = 116 (0x74)
        if byte in [115, 116, 117]:
            print(f"Scaled 0.5% (116): {cid} Byte {i} = {byte} (0x{byte:02X}) -> {byte/2}%")
        # If scaled 0.4% (0-250 -> 0-100%): 58 * 2.5 = 145 (0x91)
        if byte in [144, 145, 146]:
            print(f"Scaled 0.4% (145): {cid} Byte {i} = {byte} (0x{byte:02X}) -> {byte*0.4}%")
        # If scaled 0.392% (0-255 -> 0-100%): 58 * 2.55 = 148 (0x94)
        if byte in [147, 148, 149]:
            print(f"Scaled 0-255 (148): {cid} Byte {i} = {byte} (0x{byte:02X}) -> {byte/2.55:.1f}%")
