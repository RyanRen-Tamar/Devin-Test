import os
import json
import binascii
import struct
from pathlib import Path

def analyze_binary_patterns(data):
    """Analyze binary data for patterns and structures"""
    patterns = {
        'repeating_bytes': [],
        'potential_lengths': [],
        'ascii_strings': [],
        'potential_keys': []
    }
    
    # Look for repeating byte sequences
    for length in [4, 8, 16, 32]:
        seen = {}
        for i in range(len(data) - length):
            chunk = data[i:i+length]
            if chunk.count(chunk[0]) == len(chunk):  # Skip uniform bytes
                continue
            if data.count(chunk) > 1:
                hex_chunk = binascii.hexlify(chunk).decode()
                if hex_chunk not in seen:
                    seen[hex_chunk] = data.count(chunk)
                    if len(patterns['repeating_bytes']) < 10:  # Limit to top 10
                        patterns['repeating_bytes'].append({
                            'hex': hex_chunk,
                            'count': data.count(chunk),
                            'offset': i
                        })

    # Look for length indicators (common in binary formats)
    for i in range(0, len(data) - 4, 4):
        try:
            length = struct.unpack('>I', data[i:i+4])[0]
            if 0 < length < len(data) - i - 4:
                patterns['potential_lengths'].append({
                    'offset': i,
                    'length': length,
                    'next_bytes': binascii.hexlify(data[i+4:i+4+min(length, 16)]).decode()
                })
        except:
            continue

    # Extract ASCII strings
    current_string = ''
    for i, byte in enumerate(data):
        if 32 <= byte <= 126:  # Printable ASCII
            current_string += chr(byte)
        else:
            if len(current_string) >= 4:  # Only keep strings of 4+ chars
                patterns['ascii_strings'].append({
                    'string': current_string,
                    'offset': i - len(current_string)
                })
            current_string = ''

    # Look for potential key-like sequences
    key_patterns = [
        (b'key', 32),    # Look for 'key' followed by 32 bytes
        (b'KEY', 32),
        (b'salt', 16),   # Look for 'salt' followed by 16 bytes
        (b'iv', 16),     # Look for 'iv' followed by 16 bytes
        (b'hash', 32),   # Look for 'hash' followed by 32 bytes
    ]
    
    for pattern, length in key_patterns:
        pos = 0
        while True:
            pos = data.find(pattern, pos)
            if pos == -1:
                break
            if pos + len(pattern) + length <= len(data):
                potential_key = data[pos + len(pattern):pos + len(pattern) + length]
                if any(b for b in potential_key if b != 0):  # Skip if all zeros
                    patterns['potential_keys'].append({
                        'marker': pattern.decode(),
                        'offset': pos,
                        'key': binascii.hexlify(potential_key).decode()
                    })
            pos += 1

    return patterns

def analyze_config_file(filepath):
    """Analyze a configuration file for encryption-related information"""
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
            
        results = {
            'filename': os.path.basename(filepath),
            'size': len(data),
            'header': binascii.hexlify(data[:32]).decode(),
            'patterns': analyze_binary_patterns(data)
        }
        
        # Additional analysis for specific file types
        if filepath.endswith('topinfo.data'):
            # Look for version information
            version_markers = [b'version', b'Version', b'VERSION']
            for marker in version_markers:
                pos = data.find(marker)
                if pos >= 0:
                    results['version_info'] = {
                        'offset': pos,
                        'context': binascii.hexlify(data[pos:pos+32]).decode()
                    }
        
        elif filepath.endswith('upgradeHistoryFile'):
            # Look for upgrade records
            results['upgrade_records'] = []
            current_pos = 0
            while current_pos < len(data):
                record_marker = data.find(b'upgrade', current_pos)
                if record_marker == -1:
                    break
                record_end = data.find(b'\0', record_marker)
                if record_end == -1:
                    record_end = min(record_marker + 100, len(data))
                results['upgrade_records'].append({
                    'offset': record_marker,
                    'data': binascii.hexlify(data[record_marker:record_end]).decode()
                })
                current_pos = record_end
                
        return results
    except Exception as e:
        return {'error': str(e)}

def main():
    attachments_dir = os.path.expanduser('~/attachments')
    config_files = [
        'topinfo.data',
        'upgradeHistoryFile',
        'whatsNewVersionFileV2',
        'checkVersionFile',
        'whatsNewVersionFile'
    ]
    
    results = {}
    for filename in config_files:
        filepath = os.path.join(attachments_dir, filename)
        if os.path.exists(filepath):
            results[filename] = analyze_config_file(filepath)
    
    # Save detailed analysis
    with open('config_files_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Extract potential keys and patterns
    key_candidates = set()
    for file_result in results.values():
        if 'patterns' in file_result:
            # Add potential keys
            for key_info in file_result['patterns'].get('potential_keys', []):
                key_candidates.add(key_info['key'])
            
            # Add interesting ASCII strings that might be keys
            for string_info in file_result['patterns'].get('ascii_strings', []):
                if len(string_info['string']) >= 32 and any(c.isalnum() for c in string_info['string']):
                    key_candidates.add(string_info['string'])
    
    # Save potential keys
    with open('config_derived_keys.txt', 'w') as f:
        for key in key_candidates:
            f.write(f"{key}\n")
    
    print(f"Analysis complete. Found {len(key_candidates)} potential keys.")
    print("Results saved to config_files_analysis.json and config_derived_keys.txt")

if __name__ == '__main__':
    main()
