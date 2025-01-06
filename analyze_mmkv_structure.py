import struct
import json
from collections import defaultdict, Counter
import binascii
import re
import math
from collections import Counter

# Constants for analysis
MARKER = b'\x05\xfb\xe0\xd7\xbb\x06'
MARKER_HEX = '05fbe0d7bb06'
KEY_INDICATORS = [
    b'KEY',
    b'MMKV',
    b'SALT',
    b'IV',
    b'EMOTICON',
    b'STATUS'
]

def analyze_file_structure(file_path):
    """Analyze the structure of MMKV file looking for encryption parameters."""
    patterns = defaultdict(list)
    block_sizes = defaultdict(int)
    header_blocks = []
    
    with open(file_path, 'rb') as f:
        # Read file in chunks
        chunk_size = 16  # Standard block size for many encryption algorithms
        position = 0
        
        # Read first 64 bytes separately as header
        header = f.read(64)
        header_blocks.append({
            'position': 0,
            'data': header.hex(),
            'ascii': ''.join(chr(b) if 32 <= b <= 126 else '.' for b in header)
        })
        
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
                
            # Look for potential encryption markers
            if b'\x05\xfb\xe0\xd7\xbb\x06' in chunk:
                context_size = 64
                f.seek(position - context_size if position > context_size else 0)
                context = f.read(context_size * 2)
                patterns['marker_context'].append({
                    'position': position,
                    'context': context.hex(),
                    'ascii': ''.join(chr(b) if 32 <= b <= 126 else '.' for b in context)
                })
                f.seek(position + len(chunk))
            
            # Analyze block structure
            if len(chunk) == chunk_size:
                # Check for repeating patterns
                hex_chunk = chunk.hex()
                block_sizes[hex_chunk[:8]] += 1
                
                # Look for potential IV or key schedule patterns
                if all(b == 0 for b in chunk):
                    patterns['zero_blocks'].append(position)
                elif all(32 <= b <= 126 for b in chunk):
                    patterns['ascii_blocks'].append({
                        'position': position,
                        'text': chunk.decode('ascii')
                    })
            
            position += len(chunk)
    
    # Analyze results
    analysis = {
        'file_size': position,
        'header_blocks': header_blocks,
        'common_patterns': {
            pattern: count for pattern, count in block_sizes.items()
            if count > 1  # Only include repeating patterns
        },
        'marker_contexts': patterns['marker_context'],
        'zero_blocks': patterns['zero_blocks'],
        'ascii_blocks': patterns['ascii_blocks'],
        'block_statistics': {
            'total_blocks': position // chunk_size,
            'pattern_distribution': dict(block_sizes)
        }
    }
    
    # Save analysis results
    with open('mmkv_structure_analysis.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    
    return analysis

def analyze_byte_patterns(data_hex, window_size=8, entropy_threshold=0.7):
    """Analyze repeating byte patterns in hex data with entropy analysis."""
    patterns = defaultdict(list)
    high_entropy_patterns = []
    
    def calculate_entropy(hex_str):
        """Calculate Shannon entropy of a hex string."""
        freq = Counter(hex_str)
        entropy = 0
        for count in freq.values():
            probability = count / len(hex_str)
            entropy -= probability * math.log2(probability)
        return entropy / 4  # Normalize by max entropy for hex (4 bits)
    
    for i in range(0, len(data_hex) - window_size * 2, 2):
        pattern = data_hex[i:i + window_size * 2]
        entropy = calculate_entropy(pattern)
        
        # High entropy patterns might be encryption-related
        if entropy > entropy_threshold:
            high_entropy_patterns.append({
                'pattern': pattern,
                'position': i // 2,
                'entropy': entropy
            })
        
        patterns[pattern].append(i // 2)
    
    return {
        'repeating': {k: v for k, v in patterns.items() if len(v) > 1},
        'high_entropy': high_entropy_patterns
    }

def identify_encryption_parameters(analysis):
    """Try to identify encryption parameters from the analysis."""
    potential_params = {
        'possible_key_lengths': set(),
        'possible_ivs': [],
        'key_schedule_candidates': [],
        'iv_contexts': [],  # New field for storing IV context analysis
        'marker_patterns': [],  # Store patterns found near our known marker
        'key_indicators': []  # Store positions of potential key-related strings
    }
    
    # Initialize pattern tracking
    iv_pattern_context = defaultdict(int)
    iv_neighbors = defaultdict(list)
    marker_contexts = []
    
    # Look for patterns near our known marker
    for context in analysis['marker_contexts']:
        hex_context = context['context']
        if MARKER_HEX in hex_context:
            marker_pos = hex_context.index(MARKER_HEX)
            # Look at 64 bytes before and after marker
            start = max(0, marker_pos - 128)
            end = min(len(hex_context), marker_pos + 128 + len(MARKER_HEX))
            marker_context = hex_context[start:end]
            
            # Analyze patterns around marker
            before_marker = hex_context[max(0, marker_pos - 64):marker_pos]
            after_marker = hex_context[marker_pos + len(MARKER_HEX):marker_pos + len(MARKER_HEX) + 64]
            
            # Look for high-entropy regions that might be keys
            before_patterns = analyze_byte_patterns(before_marker, window_size=32)
            after_patterns = analyze_byte_patterns(after_marker, window_size=32)
            
            marker_contexts.append({
                'position': context['position'] + marker_pos // 2,
                'context': marker_context,
                'offset': marker_pos - start,
                'high_entropy_before': before_patterns['high_entropy'],
                'high_entropy_after': after_patterns['high_entropy']
            })
    
    # Check header blocks for standard encryption markers
    for header in analysis['header_blocks']:
        # Look for common encryption header markers
        hex_data = header['data']
        if 'SALTED__' in header['ascii']:
            potential_params['salt_marker'] = True
            potential_params['possible_salt'] = hex_data[16:32]
        
        # Check for key length indicators
        for key_length in [16, 24, 32]:  # Common AES key lengths
            if hex_data.count('0' * (key_length * 2)) > 0:
                potential_params['possible_key_lengths'].add(key_length)
    
    # Analyze marker contexts for encryption parameters
    for context in analysis['marker_contexts']:
        hex_context = context['context']
        
        # Look for potential IVs (16 bytes of random-looking data)
        for i in range(0, len(hex_context) - 31, 2):
            block = hex_context[i:i+32]
            if all(c in '0123456789abcdef' for c in block):
                # Get context around the potential IV
                start_idx = max(0, i - 32)
                end_idx = min(len(hex_context), i + 64)
                before_block = hex_context[start_idx:i]
                after_block = hex_context[i+32:end_idx]
                
                # Look for patterns in surrounding data
                if len(before_block) >= 8:
                    iv_pattern_context[before_block[-8:]] += 1
                if len(after_block) >= 8:
                    iv_pattern_context[after_block[:8]] += 1
                
                # Store IV with its context
                iv_data = {
                    'position': context['position'] + i//2,
                    'value': block,
                    'before': before_block,
                    'after': after_block,
                    'ascii_before': ''.join(chr(int(before_block[j:j+2], 16)) 
                                          if 32 <= int(before_block[j:j+2], 16) <= 126 else '.' 
                                          for j in range(0, len(before_block), 2)),
                    'ascii_after': ''.join(chr(int(after_block[j:j+2], 16)) 
                                         if 32 <= int(after_block[j:j+2], 16) <= 126 else '.' 
                                         for j in range(0, len(after_block), 2))
                }
                
                potential_params['possible_ivs'].append(iv_data)
                
                # Look for patterns between consecutive IVs
                if potential_params['possible_ivs']:
                    last_iv = potential_params['possible_ivs'][-2]['value'] if len(potential_params['possible_ivs']) > 1 else None
                    if last_iv:
                        iv_neighbors[last_iv].append(block)
    
    # Convert set to list for JSON serialization
    potential_params['possible_key_lengths'] = list(potential_params['possible_key_lengths'])
    potential_params['iv_pattern_context'] = {k: v for k, v in iv_pattern_context.items()}
    potential_params['marker_contexts'] = marker_contexts
    
    # Save encryption parameter analysis
    with open('encryption_parameters.json', 'w') as f:
        json.dump(potential_params, f, indent=2)
    
    return potential_params, iv_pattern_context, marker_contexts

def main():
    mmkv_path = '/home/ubuntu/attachments/mmkv.default'
    print(f"Analyzing MMKV file structure: {mmkv_path}")
    
    
    analysis = analyze_file_structure(mmkv_path)
    print("\nFile structure analysis complete. Results saved to mmkv_structure_analysis.json")
    
    params, iv_pattern_context, marker_contexts = identify_encryption_parameters(analysis)
    print("\nPotential encryption parameters identified:")
    print(f"- Possible key lengths: {params['possible_key_lengths']}")
    print(f"- Number of potential IVs found: {len(params['possible_ivs'])}")
    print(f"- Number of marker contexts found: {len(marker_contexts)}")
    
    # Analyze IV patterns
    common_patterns = sorted([(pattern, count) 
                            for pattern, count in params['iv_pattern_context'].items()
                            if count > 1],
                           key=lambda x: x[1], reverse=True)
    
    print("\nMost common patterns around IVs:")
    for pattern, count in common_patterns[:5]:
        print(f"- Pattern {pattern}: appears {count} times")
        # Try to interpret as ASCII
        try:
            ascii_repr = ''.join(chr(int(pattern[i:i+2], 16)) 
                               if 32 <= int(pattern[i:i+2], 16) <= 126 else '.' 
                               for i in range(0, len(pattern), 2))
            print(f"  ASCII: {ascii_repr}")
        except ValueError:
            pass
            
    # Analyze high-entropy regions near markers
    print("\nHigh-entropy regions near markers:")
    for ctx in marker_contexts:
        if ctx.get('high_entropy_before'):
            print(f"\nPosition {ctx['position']} - Before marker:")
            for pattern in ctx['high_entropy_before']:
                print(f"- Pattern: {pattern['pattern'][:32]}... (entropy: {pattern['entropy']:.3f})")
        if ctx.get('high_entropy_after'):
            print(f"\nPosition {ctx['position']} - After marker:")
            for pattern in ctx['high_entropy_after']:
                print(f"- Pattern: {pattern['pattern'][:32]}... (entropy: {pattern['entropy']:.3f})")
        
    # Look for ASCII strings near IVs
    ascii_contexts = [iv for iv in params['possible_ivs'] 
                     if any(c.isalnum() for c in iv['ascii_before']) 
                     or any(c.isalnum() for c in iv['ascii_after'])]
    
    if ascii_contexts:
        print("\nIVs with interesting ASCII context:")
        for iv in ascii_contexts[:3]:  # Show first 3 examples
            print(f"\nPosition: {iv['position']}")
            if any(c.isalnum() for c in iv['ascii_before']):
                print(f"Before: {iv['ascii_before']}")
            if any(c.isalnum() for c in iv['ascii_after']):
                print(f"After: {iv['ascii_after']}")
    
    if 'salt_marker' in params:
        print(f"\nSalt marker found with possible salt: {params['possible_salt']}")

if __name__ == '__main__':
    main()
