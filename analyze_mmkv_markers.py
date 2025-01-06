#!/usr/bin/env python3
import os
import struct
import binascii
from collections import defaultdict

def read_around_marker(file_content, position, before=32, after=64):
    """Read bytes around a specific position."""
    start = max(0, position - before)
    end = min(len(file_content), position + after)
    return {
        'position': position,
        'content': file_content[start:end],
        'start_offset': start,
        'end_offset': end,
        'hex': binascii.hexlify(file_content[start:end]).decode('ascii')
    }

def analyze_marker_context(filepath):
    """Analyze the context around KEY and STICKY markers."""
    results = {
        'key_contexts': [],
        'sticky_contexts': [],
        'patterns': defaultdict(list),
        'potential_keys': []
    }
    
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
            
            # Find all KEY markers
            pos = 0
            while True:
                pos = content.find(b'KEY', pos)
                if pos == -1:
                    break
                context = read_around_marker(content, pos)
                results['key_contexts'].append(context)
                
                # Look for patterns in the bytes after KEY
                after_key = content[pos+3:pos+35]  # 32 bytes after "KEY"
                if len(after_key) == 32:
                    hex_after = binascii.hexlify(after_key).decode('ascii')
                    results['potential_keys'].append({
                        'type': 'after_key',
                        'position': pos+3,
                        'hex': hex_after
                    })
                pos += 1
            
            # Find all STICKY markers
            pos = 0
            while True:
                pos = content.find(b'STICKY', pos)
                if pos == -1:
                    break
                context = read_around_marker(content, pos)
                results['sticky_contexts'].append(context)
                
                # Look for patterns in the bytes after STICKY
                after_sticky = content[pos+6:pos+38]  # 32 bytes after "STICKY"
                if len(after_sticky) == 32:
                    hex_after = binascii.hexlify(after_sticky).decode('ascii')
                    results['potential_keys'].append({
                        'type': 'after_sticky',
                        'position': pos+6,
                        'hex': hex_after
                    })
                pos += 1
            
            # Analyze patterns between markers
            for i in range(len(results['key_contexts'])-1):
                curr_pos = results['key_contexts'][i]['position']
                next_pos = results['key_contexts'][i+1]['position']
                distance = next_pos - curr_pos
                
                # Get the bytes between markers
                between_markers = content[curr_pos:next_pos]
                if len(between_markers) > 4:  # Look for potential length indicators
                    potential_length = struct.unpack('>I', between_markers[:4])[0]
                    if potential_length < len(content):
                        results['patterns']['length_indicators'].append({
                            'position': curr_pos,
                            'value': potential_length
                        })
            
            # Look for repeating byte sequences
            for context in results['key_contexts'] + results['sticky_contexts']:
                content_bytes = context['content']
                for i in range(len(content_bytes)-3):
                    chunk = content_bytes[i:i+4]
                    if len(chunk) == 4 and all(x == chunk[0] for x in chunk):
                        results['patterns']['repeating_bytes'].append({
                            'position': context['start_offset'] + i,
                            'byte': hex(chunk[0]),
                            'length': 4
                        })
    
    except Exception as e:
        print(f"Error analyzing markers: {str(e)}")
        return None
    
    return results

def main():
    print("=== MMKV Marker Analysis Tool ===")
    print(f"Timestamp: {os.popen('date').read().strip()}")
    print("=" * 50)
    
    mmkv_file = '/home/ubuntu/attachments/mmkv.default'
    if not os.path.exists(mmkv_file):
        print(f"Error: {mmkv_file} not found")
        return
    
    print(f"\nAnalyzing: {mmkv_file}")
    print("-" * 40)
    
    results = analyze_marker_context(mmkv_file)
    if not results:
        return
    
    # Print KEY marker contexts
    print("\n=== KEY Marker Contexts ===")
    for i, context in enumerate(results['key_contexts']):
        print(f"\nKEY Marker #{i+1} at position {context['position']}:")
        print(f"Hex dump: {context['hex']}")
        
        # Look for potential SQLCipher or encryption markers
        hex_str = context['hex']
        if 'sqlcipher' in hex_str.lower():
            print("! Found SQLCipher marker")
        if 'aes' in hex_str.lower():
            print("! Found AES marker")
    
    # Print STICKY marker contexts
    print("\n=== STICKY Marker Contexts ===")
    for i, context in enumerate(results['sticky_contexts']):
        print(f"\nSTICKY Marker #{i+1} at position {context['position']}:")
        print(f"Hex dump: {context['hex']}")
    
    # Print potential keys
    print("\n=== Potential Keys ===")
    for key_info in results['potential_keys']:
        print(f"\nType: {key_info['type']}")
        print(f"Position: {key_info['position']}")
        print(f"Hex: {key_info['hex']}")
        
        # Save potential keys to file
        with open('mmkv_marker_keys.txt', 'a') as f:
            f.write(f"Type: {key_info['type']}\n")
            f.write(f"Position: {key_info['position']}\n")
            f.write(f"Key: {key_info['hex']}\n")
            f.write("-" * 50 + "\n")
    
    # Print patterns
    print("\n=== Patterns ===")
    if 'length_indicators' in results['patterns']:
        print("\nLength Indicators:")
        for indicator in results['patterns']['length_indicators']:
            print(f"Position: {indicator['position']}, Value: {indicator['value']}")
    
    if 'repeating_bytes' in results['patterns']:
        print("\nRepeating Byte Sequences:")
        for sequence in results['patterns']['repeating_bytes']:
            print(f"Position: {sequence['position']}, Byte: {sequence['byte']}, Length: {sequence['length']}")

if __name__ == '__main__':
    main()
