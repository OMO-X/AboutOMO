import csv
from collections import defaultdict

with open('examples/can_capture.csv', 'r') as f:
    reader = csv.DictReader(f)
    stats = defaultdict(lambda: {'count': 0, 'payloads': set(), 'samples': []})
    for row in reader:
        cid = row['CAN_ID']
        payload = row['Data_Hex']
        stats[cid]['count'] += 1
        stats[cid]['payloads'].add(payload)
        if len(stats[cid]['samples']) < 2:
            stats[cid]['samples'].append(payload)

print(f"{'CAN ID':<8} | {'Count':<6} | {'Unique':<6} | {'Sample Payloads'}")
print("-" * 65)
for cid in sorted(stats.keys()):
    s = stats[cid]
    unique_count = len(s['payloads'])
    sample_str = s['samples'][0]
    if unique_count > 1 and len(s['samples']) > 1:
        sample_str += f"  -->  {s['samples'][1]}"
    print(f"{cid:<8} | {s['count']:<6} | {unique_count:<6} | {sample_str}")
