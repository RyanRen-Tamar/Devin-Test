import sqlite3
import hashlib
import json
import binascii
from pathlib import Path

def extract_binary_patterns(data, min_length=8, max_patterns=100):
    """Extract repeating binary patterns from data"""
    patterns = []
    for length in range(min_length, min(32, len(data))):
        seen = {}
        for i in range(len(data) - length):
            chunk = data[i:i+length]
            if chunk.count(chunk[0]) == len(chunk):  # Skip uniform bytes
                continue
            if data.count(chunk) > 1:
                hex_chunk = binascii.hexlify(chunk).decode()
                if hex_chunk not in seen:
                    seen[hex_chunk] = {
                        'count': data.count(chunk),
                        'offsets': [i],
                        'length': length
                    }
                    if len(patterns) < max_patterns:
                        patterns.append({
                            'hex': hex_chunk,
                            'info': seen[hex_chunk]
                        })
    return patterns

def analyze_file_headers(file_path):
    """Analyze the first few KB of a file for patterns"""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4096)  # Read first 4KB
            return {
                'size': len(header),
                'patterns': extract_binary_patterns(header),
                'magic': binascii.hexlify(header[:16]).decode(),
                'hash': hashlib.md5(header).hexdigest()
            }
    except Exception as e:
        return {'error': str(e)}

def find_common_patterns(data1, data2):
    """Find patterns that appear in both data sets"""
    patterns1 = set(p['hex'] for p in data1.get('patterns', []))
    patterns2 = set(p['hex'] for p in data2.get('patterns', []))
    return list(patterns1.intersection(patterns2))

def analyze_key_value_db(db_path):
    """Try to analyze KeyValue.db structure without decryption"""
    try:
        with open(db_path, 'rb') as f:
            data = f.read()
            
        # Look for specific markers
        markers = {
            'sqlite': data.find(b'SQLite'),
            'key': data.find(b'key'),
            'salt': data.find(b'salt'),
            'cipher': data.find(b'cipher'),
            'config': data.find(b'config'),
            'encrypt': data.find(b'encrypt'),
        }
        
        # Extract potential key-like sequences
        key_candidates = []
        for marker in [b'key', b'KEY', b'salt', b'iv']:
            pos = 0
            while True:
                pos = data.find(marker, pos)
                if pos == -1:
                    break
                if pos + len(marker) + 32 <= len(data):
                    potential_key = data[pos + len(marker):pos + len(marker) + 32]
                    if any(b for b in potential_key if b != 0):
                        key_candidates.append({
                            'marker': marker.decode(),
                            'offset': pos,
                            'data': binascii.hexlify(potential_key).decode()
                        })
                pos += 1
        
        return {
            'size': len(data),
            'markers': markers,
            'key_candidates': key_candidates,
            'header_analysis': analyze_file_headers(db_path)
        }
    except Exception as e:
        return {'error': str(e)}

def analyze_msg_db(db_path):
    """Analyze msg_2.db structure"""
    try:
        with open(db_path, 'rb') as f:
            data = f.read()
        
        # Look for specific patterns
        patterns = {
            'sqlite_marker': data.find(b'SQLite'),
            'page_size': int.from_bytes(data[16:18], 'big') if len(data) >= 18 else 0,
            'write_version': data[18] if len(data) >= 19 else 0,
            'read_version': data[19] if len(data) >= 20 else 0,
            'reserved_bytes': data[20] if len(data) >= 21 else 0,
        }
        
        return {
            'size': len(data),
            'patterns': patterns,
            'header_analysis': analyze_file_headers(db_path)
        }
    except Exception as e:
        return {'error': str(e)}

def main():
    attachments_dir = Path.home() / "attachments"
    keyvalue_db = attachments_dir / "KeyValue.db"
    msg_db = attachments_dir / "msg_2.db"
    
    # Analyze both databases
    keyvalue_analysis = analyze_key_value_db(keyvalue_db)
    msg_analysis = analyze_msg_db(msg_db)
    
    # Find common patterns between the two files
    common_patterns = find_common_patterns(
        keyvalue_analysis.get('header_analysis', {}),
        msg_analysis.get('header_analysis', {})
    )
    
    # Combine results
    results = {
        'keyvalue_db': keyvalue_analysis,
        'msg_db': msg_analysis,
        'common_patterns': common_patterns,
        'potential_relationships': []
    }
    
    # Look for potential relationships
    if 'key_candidates' in keyvalue_analysis:
        for candidate in keyvalue_analysis['key_candidates']:
            # Check if candidate key appears in msg_db
            with open(msg_db, 'rb') as f:
                msg_data = f.read()
                if isinstance(candidate, dict):  # Ensure candidate is a dictionary
                    key_hex = candidate.get('data', '')  # Now safe to use get()
                    if isinstance(key_hex, str):  # Ensure we have a string
                        try:
                            key_data = binascii.unhexlify(key_hex)
                            if msg_data.find(key_data) != -1:
                                results['potential_relationships'].append({
                                    'type': 'key_match',
                                    'key_info': candidate,
                                    'found_in_msg_db': True
                                })
                        except binascii.Error:
                            pass  # Skip invalid hex strings
    
    # Save detailed analysis
    with open('db_relationship_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Extract potential keys for testing
    keys_to_test = set()
    
    # Add common patterns as potential keys
    for pattern in common_patterns:
        if len(pattern) >= 16:  # Only consider patterns of reasonable key length
            keys_to_test.add(pattern)
    
    # Add key candidates from KeyValue.db
    for candidate in keyvalue_analysis.get('key_candidates', []):
        if isinstance(candidate, dict):  # Ensure candidate is a dictionary
            data = candidate.get('data', '')
            if isinstance(data, str):
                keys_to_test.add(data)
    
    # Save potential keys
    with open('relationship_derived_keys.txt', 'w') as f:
        for key in keys_to_test:
            f.write(f"{key}\n")
    
    print(f"Analysis complete. Found {len(common_patterns)} common patterns and {len(keys_to_test)} potential keys.")
    print("Results saved to db_relationship_analysis.json and relationship_derived_keys.txt")

if __name__ == '__main__':
    main()
