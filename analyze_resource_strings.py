#!/usr/bin/env python3
import os
import re
import binascii
import hashlib
from collections import defaultdict

def extract_md5_hashes(content):
    """Extract potential MD5 hashes from content."""
    # Look for 32-character hex strings
    md5_pattern = re.compile(r'[a-fA-F0-9]{32}')
    return md5_pattern.findall(content)

def analyze_resource_strings(filepath):
    """Analyze strings related to resources and their context."""
    results = {
        'md5_hashes': [],
        'resource_contexts': [],
        'potential_keys': [],
        'patterns': defaultdict(list)
    }
    
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
            hex_content = binascii.hexlify(content).decode('ascii')
            
            # Look for resource-related strings
            resource_patterns = [
                b'EMOTICON_RESOURCE',
                b'MD5_TYPE',
                b'getDnsVcode',
                b'KEY_MMKV',
                b'STICKY_STATUS'
            ]
            
            # Extract context around each pattern
            for pattern in resource_patterns:
                pos = 0
                while True:
                    pos = content.find(pattern, pos)
                    if pos == -1:
                        break
                    
                    # Get 64 bytes before and after the pattern
                    start = max(0, pos - 64)
                    end = min(len(content), pos + len(pattern) + 64)
                    context = content[start:end]
                    
                    # Look for MD5 hashes in context
                    context_hex = binascii.hexlify(context).decode('ascii')
                    md5_hashes = extract_md5_hashes(context_hex)
                    
                    if md5_hashes:
                        results['md5_hashes'].extend(md5_hashes)
                        results['resource_contexts'].append({
                            'pattern': pattern.decode('ascii'),
                            'position': pos,
                            'context': context_hex,
                            'md5_hashes': md5_hashes
                        })
                    
                    # Look for potential key patterns
                    # Check for sequences that look like keys (e.g., consistent byte patterns)
                    for i in range(len(context) - 31):
                        chunk = context[i:i+32]
                        # Check if chunk could be a key (entropy check)
                        if len(set(chunk)) > 12:  # Reasonable entropy threshold
                            hex_chunk = binascii.hexlify(chunk).decode('ascii')
                            results['potential_keys'].append({
                                'position': start + i,
                                'key': hex_chunk,
                                'pattern': pattern.decode('ascii')
                            })
                    
                    pos += 1
            
            # Look for patterns in MD5 hashes
            for md5_hash in set(results['md5_hashes']):
                # Try using the MD5 hash as a key derivation input
                derived_keys = []
                
                # MD5 hash as direct key
                derived_keys.append(md5_hash)
                
                # MD5 hash of MD5 hash
                double_md5 = hashlib.md5(md5_hash.encode()).hexdigest()
                derived_keys.append(double_md5)
                
                # First/last 16 bytes combinations
                derived_keys.append(md5_hash[:16] + md5_hash[:16])
                derived_keys.append(md5_hash[-16:] + md5_hash[-16:])
                
                # Save derived keys
                results['patterns']['derived_keys'].extend(derived_keys)
    
    except Exception as e:
        print(f"Error analyzing resource strings: {str(e)}")
        return None
    
    return results

def test_derived_keys(results):
    """Save derived keys for testing with SQLCipher."""
    if not results:
        return
    
    try:
        with open('resource_derived_keys.txt', 'w') as f:
            # Write MD5 hashes
            f.write("=== MD5 Hashes ===\n")
            for md5_hash in set(results['md5_hashes']):
                f.write(f"{md5_hash}\n")
            
            # Write potential keys
            f.write("\n=== Potential Keys ===\n")
            for key_info in results['potential_keys']:
                f.write(f"Pattern: {key_info['pattern']}\n")
                f.write(f"Position: {key_info['position']}\n")
                f.write(f"Key: {key_info['key']}\n")
                f.write("-" * 50 + "\n")
            
            # Write derived keys
            f.write("\n=== Derived Keys ===\n")
            for key in results['patterns']['derived_keys']:
                f.write(f"{key}\n")
    
    except Exception as e:
        print(f"Error saving derived keys: {str(e)}")

def main():
    print("=== Resource String Analysis Tool ===")
    print(f"Timestamp: {os.popen('date').read().strip()}")
    print("=" * 50)
    
    mmkv_file = '/home/ubuntu/attachments/mmkv.default'
    if not os.path.exists(mmkv_file):
        print(f"Error: {mmkv_file} not found")
        return
    
    print(f"\nAnalyzing: {mmkv_file}")
    print("-" * 40)
    
    results = analyze_resource_strings(mmkv_file)
    if results:
        # Print MD5 hashes found
        print("\n=== MD5 Hashes Found ===")
        for md5_hash in set(results['md5_hashes']):
            print(md5_hash)
        
        # Print resource contexts
        print("\n=== Resource Contexts ===")
        for context in results['resource_contexts']:
            print(f"\nPattern: {context['pattern']}")
            print(f"Position: {context['position']}")
            print(f"MD5 Hashes: {context['md5_hashes']}")
        
        # Print potential keys
        print("\n=== Potential Keys ===")
        for key_info in results['potential_keys']:
            print(f"\nPattern: {key_info['pattern']}")
            print(f"Position: {key_info['position']}")
            print(f"Key: {key_info['key']}")
        
        # Save results for further testing
        test_derived_keys(results)
        print("\nDerived keys saved to resource_derived_keys.txt")

if __name__ == '__main__':
    main()
