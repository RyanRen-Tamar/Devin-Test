#!/usr/bin/env python3
import os
import struct
import binascii
import json
from collections import defaultdict

def analyze_mmkv_file(filepath):
    """Analyze MMKV file for potential encryption keys and configuration."""
    results = {
        'potential_keys': [],
        'key_patterns': defaultdict(list),
        'config_markers': [],
        'structure': []
    }
    
    try:
        with open(filepath, 'rb') as f:
            # Read the entire file
            content = f.read()
            
            # Look for common key derivation patterns
            patterns = [
                b'key', b'KEY', b'salt', b'SALT',
                b'iv', b'IV', b'config', b'CONFIG',
                b'STICKY', b'sticky', b'crypt', b'CRYPT',
                b'WeChat', b'wechat', b'Tencent', b'tencent'
            ]
            
            # Track positions of patterns
            for pattern in patterns:
                positions = []
                pos = 0
                while True:
                    pos = content.find(pattern, pos)
                    if pos == -1:
                        break
                    positions.append(pos)
                    # Get 32 bytes after the pattern
                    if len(content) >= pos + len(pattern) + 32:
                        key_candidate = content[pos + len(pattern):pos + len(pattern) + 32]
                        # Check if it looks like a hex string
                        if all(c in b'0123456789abcdefABCDEF' for c in key_candidate):
                            results['potential_keys'].append({
                                'pattern': pattern.decode('ascii'),
                                'offset': pos,
                                'key': binascii.hexlify(key_candidate).decode('ascii')
                            })
                    pos += 1
                if positions:
                    results['key_patterns'][pattern.decode('ascii')] = positions
            
            # Look for JSON-like structures
            try:
                # Search for { and } pairs
                start = 0
                while True:
                    start = content.find(b'{', start)
                    if start == -1:
                        break
                    end = content.find(b'}', start)
                    if end == -1:
                        break
                    # Try to decode as JSON
                    try:
                        json_data = content[start:end+1].decode('utf-8')
                        json.loads(json_data)
                        results['config_markers'].append({
                            'offset': start,
                            'content': json_data
                        })
                    except:
                        pass
                    start = end + 1
            except:
                pass
            
            # Analyze file structure
            chunk_size = 1024
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i+chunk_size]
                # Look for repeating patterns
                if len(set(chunk)) == 1:
                    results['structure'].append({
                        'offset': i,
                        'type': 'repeating',
                        'byte': hex(chunk[0])
                    })
                # Look for potential length markers
                if len(chunk) >= 4:
                    length = struct.unpack('>I', chunk[:4])[0]
                    if length < len(content) and length > 0:
                        results['structure'].append({
                            'offset': i,
                            'type': 'length',
                            'value': length
                        })
    except Exception as e:
        print(f"Error analyzing MMKV file: {str(e)}")
        return None
    
    return results

def analyze_key_patterns(results):
    """Analyze patterns in potential keys."""
    if not results:
        return
    
    print("\n=== Key Pattern Analysis ===")
    
    # Analyze distances between patterns
    for pattern, positions in results['key_patterns'].items():
        if len(positions) > 1:
            distances = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
            print(f"\nPattern '{pattern}' found at positions: {positions}")
            print(f"Distances between occurrences: {distances}")
    
    # Analyze potential keys
    if results['potential_keys']:
        print("\n=== Potential Keys ===")
        for key_info in results['potential_keys']:
            print(f"\nPattern: {key_info['pattern']}")
            print(f"Offset: {key_info['offset']}")
            print(f"Key: {key_info['key']}")
            
            # Save potential keys to file
            with open('mmkv_keys.txt', 'a') as f:
                f.write(f"Pattern: {key_info['pattern']}\n")
                f.write(f"Offset: {key_info['offset']}\n")
                f.write(f"Key: {key_info['key']}\n")
                f.write("-" * 50 + "\n")
    
    # Analyze configuration markers
    if results['config_markers']:
        print("\n=== Configuration Markers ===")
        for config in results['config_markers']:
            print(f"\nOffset: {config['offset']}")
            print(f"Content: {config['content']}")
    
    # Analyze file structure
    if results['structure']:
        print("\n=== File Structure Analysis ===")
        for struct_info in results['structure']:
            if struct_info['type'] == 'repeating':
                print(f"\nRepeating byte {struct_info['byte']} at offset {struct_info['offset']}")
            elif struct_info['type'] == 'length':
                print(f"\nPossible length marker {struct_info['value']} at offset {struct_info['offset']}")

def main():
    print("=== MMKV Analysis Tool v3 ===")
    print(f"Timestamp: {os.popen('date').read().strip()}")
    print("=" * 50)
    
    mmkv_file = '/home/ubuntu/attachments/mmkv.default'
    if not os.path.exists(mmkv_file):
        print(f"Error: {mmkv_file} not found")
        return
    
    print(f"\nAnalyzing: {mmkv_file}")
    print("-" * 40)
    
    results = analyze_mmkv_file(mmkv_file)
    if results:
        analyze_key_patterns(results)
        
        # Save results to file
        with open('mmkv_analysis_v3.json', 'w') as f:
            # Convert defaultdict to dict for JSON serialization
            results['key_patterns'] = dict(results['key_patterns'])
            json.dump(results, f, indent=2)
        print("\nDetailed analysis saved to mmkv_analysis_v3.json")

if __name__ == '__main__':
    main()
