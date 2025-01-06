import os
import json
import binascii
import struct
import hashlib
from typing import Dict, List, Tuple, Optional
from collections import Counter

class MMKVEncryptionAnalyzer:
    """Analyze MMKV.default file for encryption patterns and key derivation hints."""
    
    def __init__(self, mmkv_path: str):
        self.mmkv_path = mmkv_path
        self.results = {
            'file_info': {},
            'block_patterns': [],
            'encryption_markers': [],
            'key_candidates': [],
            'structure_hints': []
        }
        
    def analyze_file_structure(self) -> None:
        """Analyze the overall file structure and patterns."""
        try:
            with open(self.mmkv_path, 'rb') as f:
                content = f.read()
                
            self.results['file_info'] = {
                'size': len(content),
                'sha256': hashlib.sha256(content).hexdigest(),
                'first_bytes': content[:32].hex(),
                'last_bytes': content[-32:].hex()
            }
            
            # Look for block patterns
            block_sizes = [16, 24, 32, 48, 64, 128, 256, 512, 1024]
            for size in block_sizes:
                blocks = [content[i:i+size] for i in range(0, len(content), size)]
                repeating_blocks = Counter(blocks).most_common(5)
                
                if repeating_blocks:
                    self.results['block_patterns'].append({
                        'block_size': size,
                        'repeating_patterns': [
                            {
                                'hex': block.hex(),
                                'count': count,
                                'entropy': self._calculate_entropy(block)
                            }
                            for block, count in repeating_blocks if count > 1
                        ]
                    })
        except Exception as e:
            print(f"Error analyzing file structure: {str(e)}")
            return
    
    def find_encryption_markers(self) -> None:
        """Look for common encryption-related markers and patterns."""
        with open(self.mmkv_path, 'rb') as f:
            content = f.read()
        
        # Common encryption markers
        markers = [
            b'AES', b'CBC', b'ECB', b'GCM',
            b'SHA', b'MD5', b'HMAC',
            b'SALT', b'IV', b'KEY'
        ]
        
        for marker in markers:
            pos = 0
            while True:
                pos = content.find(marker, pos)
                if pos == -1:
                    break
                    
                context = content[max(0, pos-16):min(len(content), pos+len(marker)+16)]
                self.results['encryption_markers'].append({
                    'marker': marker.decode(),
                    'position': pos,
                    'context': context.hex(),
                    'entropy': self._calculate_entropy(context)
                })
                pos += 1
    
    def analyze_potential_keys(self) -> None:
        """Analyze sections that might contain encryption keys."""
        with open(self.mmkv_path, 'rb') as f:
            content = f.read()
        
        # Look for high-entropy blocks that might be keys
        block_size = 32  # Common key size
        stride = 8  # Step size for sliding window
        
        for i in range(0, len(content) - block_size, stride):
            block = content[i:i+block_size]
            entropy = self._calculate_entropy(block)
            
            # High entropy blocks might be keys
            if entropy > 0.7:  # Threshold for potential keys
                hex_block = block.hex()
                # Check if block has characteristics of a key
                if self._looks_like_key(hex_block):
                    self.results['key_candidates'].append({
                        'position': i,
                        'hex': hex_block,
                        'entropy': entropy,
                        'characteristics': self._analyze_key_characteristics(hex_block)
                    })
    
    def find_structure_hints(self) -> None:
        """Look for patterns that might indicate the encryption scheme structure."""
        with open(self.mmkv_path, 'rb') as f:
            content = f.read()
        
        # Look for repeated sequences that might indicate structure
        for size in [4, 8, 16]:
            chunks = {}
            for i in range(0, len(content) - size):
                chunk = content[i:i+size]
                if chunk in chunks:
                    chunks[chunk].append(i)
                else:
                    chunks[chunk] = [i]
            
            # Analyze chunks that appear multiple times
            for chunk, positions in chunks.items():
                if len(positions) > 2:
                    # Calculate distances between occurrences
                    distances = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                    if len(set(distances)) == 1:  # Regular pattern
                        self.results['structure_hints'].append({
                            'pattern': chunk.hex(),
                            'size': size,
                            'positions': positions,
                            'distance': distances[0],
                            'count': len(positions)
                        })
    
    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of byte sequence."""
        if not data:
            return 0.0
        entropy = 0
        for x in range(256):
            p_x = data.count(x)/len(data)
            if p_x > 0:
                entropy += -p_x*math.log2(p_x)
        return entropy/8.0
    
    def _looks_like_key(self, hex_string: str) -> bool:
        """Check if a hex string has characteristics of a key."""
        # Keys usually have good distribution of hex digits
        hex_counts = Counter(hex_string)
        distribution = max(hex_counts.values()) / len(hex_string)
        
        # Keys shouldn't have long sequences of same digit
        max_repeat = max(len(list(g)) for _, g in itertools.groupby(hex_string))
        
        return distribution < 0.2 and max_repeat < 4
    
    def _analyze_key_characteristics(self, hex_string: str) -> Dict:
        """Analyze characteristics of a potential key."""
        return {
            'length': len(hex_string),
            'hex_distribution': dict(Counter(hex_string)),
            'has_common_prefixes': any(hex_string.startswith(prefix) 
                                     for prefix in ['00', 'ff', 'aa', '55']),
            'byte_pattern': self._find_byte_pattern(hex_string)
        }
    
    def _find_byte_pattern(self, hex_string: str) -> str:
        """Find any recurring byte patterns in the hex string."""
        patterns = []
        for i in range(2, len(hex_string), 2):
            byte = hex_string[i:i+2]
            if hex_string.count(byte) > 2:
                patterns.append(byte)
        return ','.join(patterns) if patterns else ''
    
    def analyze(self) -> Dict:
        """Run all analysis methods and return results."""
        print("Analyzing MMKV file structure...")
        self.analyze_file_structure()
        
        print("Looking for encryption markers...")
        self.find_encryption_markers()
        
        print("Analyzing potential keys...")
        self.analyze_potential_keys()
        
        print("Finding structure hints...")
        self.find_structure_hints()
        
        return self.results

def main():
    mmkv_path = '/home/ubuntu/attachments/mmkv.default'
    if not os.path.exists(mmkv_path):
        print(f"Error: {mmkv_path} not found")
        return
    
    analyzer = MMKVEncryptionAnalyzer(mmkv_path)
    results = analyzer.analyze()
    
    # Save results
    output_file = 'mmkv_encryption_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_file}")
    
    # Print summary
    print("\nAnalysis Summary:")
    print(f"File size: {results['file_info']['size']} bytes")
    print(f"Found {len(results['encryption_markers'])} potential encryption markers")
    print(f"Found {len(results['key_candidates'])} potential key candidates")
    print(f"Found {len(results['structure_hints'])} structural patterns")

if __name__ == '__main__':
    import math
    import itertools
    main()
