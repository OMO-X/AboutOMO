#!/usr/bin/env python3
"""
OMOWAY CAN Bus Differential Analyzer
Compares baseline capture vs action capture to isolate control signals (Brake, Throttle, Switches)
"""

import sys
import csv
import argparse
from collections import defaultdict, Counter

def load_capture(filepath):
    """
    Loads capture CSV and returns:
    {
        can_id: {
            'count': int,
            'byte_counts': [Counter() for _ in range(8)],
            'most_common': [byte_val, ...]
        }
    }
    """
    frames = defaultdict(list)
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row['CAN_ID']
            bytes_list = []
            for i in range(8):
                val_str = row.get(f'Byte{i}', '')
                if val_str and val_str.startswith('0x'):
                    bytes_list.append(int(val_str, 16))
                elif val_str:
                    bytes_list.append(int(val_str))
                else:
                    bytes_list.append(0)
            frames[cid].append(bytes_list)

    stats = {}
    for cid, rows in frames.items():
        byte_counts = [Counter() for _ in range(8)]
        for r in rows:
            for i in range(8):
                byte_counts[i][r[i]] += 1
        
        most_common = [c.most_common(1)[0][0] if c else 0 for c in byte_counts]
        stats[cid] = {
            'count': len(rows),
            'byte_counts': byte_counts,
            'most_common': most_common,
            'rows': rows
        }
    return stats

def compare_captures(baseline_path, action_path, action_name="Action"):
    print(f"=== Comparing Baseline vs {action_name} ===")
    print(f"Baseline: {baseline_path}")
    print(f"Action  : {action_path}\n")

    base_stats = load_capture(baseline_path)
    act_stats = load_capture(action_path)

    common_ids = sorted(set(base_stats.keys()).intersection(set(act_stats.keys())))
    diffs = []

    for cid in common_ids:
        b_common = base_stats[cid]['most_common']
        a_common = act_stats[cid]['most_common']

        # Compare bytes 0 to 5 (bytes 6-7 are often Rolling Counter & CRC)
        byte_changes = []
        for i in range(8):
            b_val = b_common[i]
            a_val = a_common[i]
            
            # Check if value shifted significantly
            if b_val != a_val:
                # Is it just rolling counter in byte 6?
                b_unique = len(base_stats[cid]['byte_counts'][i])
                a_unique = len(act_stats[cid]['byte_counts'][i])
                
                # If byte is constant or near constant in baseline, but changes in action:
                xor_diff = b_val ^ a_val
                byte_changes.append({
                    'byte_index': i,
                    'baseline_hex': f"0x{b_val:02X}",
                    'action_hex': f"0x{a_val:02X}",
                    'xor_diff': f"0x{xor_diff:02X}",
                    'b_unique': b_unique,
                    'a_unique': a_unique,
                    'is_likely_counter': (i >= 6 and (b_unique > 4 or a_unique > 4))
                })

        if byte_changes:
            # Filter out pure counter noise
            significant_changes = [c for c in byte_changes if not c['is_likely_counter']]
            diffs.append({
                'cid': cid,
                'changes': byte_changes,
                'significant': significant_changes,
                'b_payload': ' '.join(f"{b:02X}" for b in b_common),
                'a_payload': ' '.join(f"{b:02X}" for b in a_common),
            })

    # Sort: IDs with significant changes first
    diffs.sort(key=lambda d: len(d['significant']), reverse=True)

    print(f"{'CAN ID':<8} | {'Status':<18} | {'Baseline Hex':<24} -> {'Action Hex':<24}")
    print("-" * 80)
    for d in diffs:
        sig_count = len(d['significant'])
        status = f"[*] {sig_count} byte(s) changed" if sig_count > 0 else "(Counter/CRC shift)"
        print(f"{d['cid']:<8} | {status:<24} | {d['b_payload']:<24} -> {d['a_payload']:<24}")
        for c in d['significant']:
            print(f"         +-- Byte {c['byte_index']}: {c['baseline_hex']} -> {c['action_hex']} (XOR: {c['xor_diff']})")

    return diffs

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="OMOWAY Differential Analyzer")
    parser.add_argument('--baseline', default='examples/can_capture.csv', help="Baseline CSV")
    parser.add_argument('--action', required=True, help="Action CSV")
    parser.add_argument('--name', default="Brake Test", help="Name of action")
    args = parser.parse_args()

    compare_captures(args.baseline, args.action, action_name=args.name)
