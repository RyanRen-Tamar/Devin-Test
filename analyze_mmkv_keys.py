import binascii
import json
import math
from collections import defaultdict
from typing import List, Dict, Tuple

def calculate_entropy(data: bytes, window_size: int = 32) -> float:
    """Calculate Shannon entropy for a window of bytes."""
    if len(data) < window_size:
        return 0.0
    
    freq = defaultdict(int)
    for byte in data:
        freq[byte] += 1
    
    entropy = 0
    for count in freq.values():
        probability = count / len(data)
        entropy -= probability * math.log2(probability)
    
    return entropy / 8.0  # Normalize to [0,1]

def find_potential_keys(data: bytes, min_entropy: float = 0.6) -> List[Dict]:
    """Find high-entropy regions that could be encryption keys."""
    potential_keys = []
    
    # Common key sizes in bytes
    key_sizes = [16, 24, 32, 48, 64]  # 128-bit, 192-bit, 256-bit, 384-bit, 512-bit
    
    # Known patterns that might indicate keys
    key_indicators = [
        b'key', b'KEY', b'Key',
        b'cipher', b'CIPHER', b'Cipher',
        b'crypt', b'CRYPT', b'Crypt',
        b'salt', b'SALT', b'Salt',
        b'iv', b'IV', b'Iv',
        b'hash', b'HASH', b'Hash'
    ]
    
    # First pass: look for regions near key indicators
    for indicator in key_indicators:
        pos = 0
        while True:
            pos = data.find(indicator, pos)
            if pos == -1:
                break
                
            # Check regions before and after the indicator
            for offset in [-64, -32, -16, 0, 16, 32, 64]:
                start = max(0, pos + offset)
                for size in key_sizes:
                    if start + size <= len(data):
                        window = data[start:start+size]
                        entropy = calculate_entropy(window)
                        
                        if entropy >= min_entropy:
                            potential_keys.append({
                                'position': start,
                                'size': size,
                                'entropy': entropy,
                                'byte_distribution': len(set(window)) / size,
                                'hex': binascii.hexlify(window).decode('ascii'),
                                'context': binascii.hexlify(data[max(0, start-16):start+size+16]).decode('ascii'),
                                'indicator': indicator.decode('ascii'),
                                'indicator_offset': offset
                            })
            pos += 1
    
    # Second pass: sliding window for high entropy regions
    for size in key_sizes:
        for i in range(0, len(data) - size, 8):  # Step by 8 bytes for efficiency
            window = data[i:i+size]
            entropy = calculate_entropy(window)
            
            if entropy >= min_entropy:
                # Check if window has good byte distribution
                byte_dist = len(set(window)) / size
                if byte_dist > 0.5:  # At least 50% unique bytes
                    potential_keys.append({
                        'position': i,
                        'size': size,
                        'entropy': entropy,
                        'byte_distribution': byte_dist,
                        'hex': binascii.hexlify(window).decode('ascii'),
                        'context': binascii.hexlify(data[max(0, i-16):i+size+16]).decode('ascii')
                    })
    
    return potential_keys

def analyze_key_patterns(keys: List[Dict]) -> Dict:
    """Analyze patterns in potential keys."""
    patterns = defaultdict(list)
    
    for key in keys:
        # Look for common prefixes/suffixes
        hex_key = key['hex']
        for length in [2, 4, 8]:
            prefix = hex_key[:length]
            suffix = hex_key[-length:]
            patterns[f'prefix_{length}'].append(prefix)
            patterns[f'suffix_{length}'].append(suffix)
    
    # Find most common patterns
    common_patterns = {}
    for pattern_type, values in patterns.items():
        freq = defaultdict(int)
        for value in values:
            freq[value] += 1
        common_patterns[pattern_type] = sorted(
            [(v, c) for v, c in freq.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]
    
    return common_patterns

def main():
    mmkv_path = '/home/ubuntu/attachments/mmkv.default'
    
    print(f"Analyzing MMKV file for potential encryption keys: {mmkv_path}")
    
    try:
        with open(mmkv_path, 'rb') as f:
            data = f.read()
            
        print(f"Successfully read {len(data)} bytes from MMKV file")
        print(f"First 32 bytes (hex): {binascii.hexlify(data[:32]).decode('ascii')}")
        
        if len(data) == 0:
            print("Warning: MMKV file is empty!")
            return
            
    except FileNotFoundError:
        print(f"Error: Could not find MMKV file at {mmkv_path}")
        return
    except Exception as e:
        print(f"Error reading MMKV file: {str(e)}")
        return
    
    # Find potential keys
    potential_keys = find_potential_keys(data)
    print(f"\nFound {len(potential_keys)} potential key candidates")
    
    # Analyze patterns in keys
    patterns = analyze_key_patterns(potential_keys)
    
    # Save detailed results
    results = {
        'potential_keys': potential_keys,
        'patterns': patterns
    }
    
    with open('mmkv_key_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\nKey candidates by size:")
    size_groups = defaultdict(list)
    for key in potential_keys:
        size_groups[key['size']].append(key)
    
    for size, keys in sorted(size_groups.items()):
        print(f"\n{size*8}-bit keys: {len(keys)} candidates")
        # Show top 3 highest entropy candidates
        top_keys = sorted(keys, key=lambda k: k['entropy'], reverse=True)[:3]
        for i, key in enumerate(top_keys, 1):
            print(f"\nCandidate {i}:")
            print(f"Position: {key['position']}")
            print(f"Entropy: {key['entropy']:.3f}")
            print(f"Byte distribution: {key['byte_distribution']:.3f}")
            print(f"Key: {key['hex']}")
            print(f"Context: ...{key['context']}...")
    
    # Print common patterns
    print("\nCommon patterns found:")
    for pattern_type, common in patterns.items():
        print(f"\n{pattern_type}:")
        for value, count in common: 
            print(f"  {value}: {count} occurrences")
    
    # Generate SQLCipher test keys
    print("\nGenerating SQLCipher test keys...")
    test_keys = []
    
    # Add high entropy 256-bit keys
    for key in potential_keys:
        if key['size'] == 32 and key['entropy'] > 0.8:  # Focus on 256-bit keys
            test_keys.append(key['hex'])
    
    # Save test keys
    with open('sqlcipher_test_keys.txt', 'w') as f:
        for key in test_keys:
            f.write(f"{key}\n")
    
    print(f"\nSaved {len(test_keys)} test keys to sqlcipher_test_keys.txt")

if __name__ == '__main__':
    main()
