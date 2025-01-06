import os
import re
import json
from collections import defaultdict

def analyze_file_context(file_path, window_size=256):
    """Analyze the context around key markers in binary file."""
    # Define markers in hex format for consistency
    markers = [
        '535449434b595f535441545553',  # STICKY_STATUS
        '454d4f5449434f4e5f5245534f55524345',  # EMOTICON_RESOURCE
        '676574446e7356636f64654c696d6974',  # getDnsVcodeLimit
        '05fbe0d7bb06',  # Known pattern
        '4b45595f4d4d4b56',  # KEY_MMKV
        '5f4d44355f545950455f',  # _MD5_TYPE_
        '4d53475f54595045',  # MSG_TYPE
        '5245534f555243455f4944',  # RESOURCE_ID
        'e81b0000',  # Known pattern
        '8a041d53'  # Known pattern
    ]
    
    contexts = defaultdict(list)
    
    try:
        # Read file as binary and convert to hex
        with open(file_path, 'rb') as f:
            content = f.read().hex()
            
        # Find all occurrences of markers
        for marker in markers:
            positions = []
            start = 0
            while True:
                pos = content.find(marker, start)
                if pos == -1:
                    break
                positions.append(pos // 2)  # Convert hex position to byte position
                start = pos + len(marker)
            
            # Get context around each occurrence
            for pos in positions:
                start_pos = max(0, pos - window_size)
                end_pos = min(len(content), pos + len(marker) + window_size)
                context = content[start_pos:end_pos]
                
                # Calculate context window in hex
                start_pos_hex = max(0, (pos * 2) - (window_size * 2))
                end_pos_hex = min(len(content), (pos * 2) + (len(marker) + window_size) * 2)
                context_hex = content[start_pos_hex:end_pos_hex]
                
                # Look for hex patterns in context
                hex_pattern = re.compile(r'[0-9a-fA-F]{32,64}')
                hex_matches = hex_pattern.findall(context_hex)
                
                # Look for potential key patterns
                key_candidates = []
                for hex_match in hex_matches:
                    # Basic key
                    key_candidates.append(hex_match)
                    
                    # Try combining with marker
                    # Marker is already in hex format
                    key_candidates.append(hex_match + marker)
                    key_candidates.append(marker + hex_match)
                
                # Look for specific patterns around known markers
                if marker == '05fbe0d7bb06':
                    marker_pos = context_hex.find(marker)
                    if marker_pos != -1:
                        # Get 32 bytes after marker
                        if marker_pos + 38 <= len(context_hex):
                            key_candidates.append(context_hex[marker_pos:marker_pos+64])
                
                context_info = {
                    'position': pos,
                    'hex_matches': hex_matches,
                    'key_candidates': key_candidates,
                    'context_hex': context_hex
                }
                
                contexts[marker].append(context_info)
    
    except Exception as e:
        print(f"Error analyzing file: {str(e)}")
        return None
    
    return contexts

def find_key_patterns(contexts):
    """Analyze contexts to find potential key patterns."""
    patterns = []
    
    # Look for recurring patterns across different markers
    hex_sequences = set()
    for marker, context_list in contexts.items():
        for context in context_list:
            # Add original hex matches
            hex_sequences.update(context['hex_matches'])
            
            # Add key candidates
            hex_sequences.update(context['key_candidates'])
            
            # Look for patterns in raw context using sliding window
            try:
                raw_context = bytes.fromhex(context['context_hex'])
                for i in range(0, len(raw_context) - 31, 2):  # Step by 2 to maintain hex alignment
                    window = raw_context[i:i+32]
                    if len(window) == 32:
                        window_hex = window.hex()
                        # Check if window looks like a potential key
                        if all(c in '0123456789abcdefABCDEF' for c in window_hex):
                            hex_sequences.add(window_hex)
            except ValueError:
                continue  # Skip invalid hex strings
    
    # Find common subsequences
    common_sequences = []
    for seq in hex_sequences:
        if len(seq) >= 32:  # Only consider sequences long enough to be keys
            count = 0
            positions = []
            for marker, context_list in contexts.items():
                for context in context_list:
                    if seq in context['context_hex']:
                        count += 1
                        positions.append(context['position'])
            
            # Consider sequences that appear multiple times or near known markers
            if count > 1 or any(pos < 1024 for pos in positions):  # Also include sequences near file start
                common_sequences.append({
                    'sequence': seq,
                    'occurrences': count,
                    'positions': positions
                })
    
    # Generate potential keys from common sequences
    for seq in common_sequences:
        # Basic sequence
        patterns.append(seq['sequence'])
        
        # Try padding
        patterns.append(seq['sequence'] + '0' * 32)
        patterns.append('0' * 32 + seq['sequence'])
        
        # Try combining with known marker
        patterns.append('05fbe0d7bb06' + seq['sequence'])
        patterns.append(seq['sequence'] + '05fbe0d7bb06')
    
    return list(set(patterns))

def main():
    mmkv_path = "/home/ubuntu/attachments/mmkv.default"
    output_file = "mmkv_context_analysis.json"
    key_patterns_file = "context_derived_keys.txt"
    
    print("Analyzing MMKV file context...")
    contexts = analyze_file_context(mmkv_path)
    
    if contexts:
        # Save full context analysis
        with open(output_file, 'w') as f:
            json.dump(contexts, f, indent=2)
        print(f"Full context analysis saved to {output_file}")
        
        # Find and save key patterns
        patterns = find_key_patterns(contexts)
        with open(key_patterns_file, 'w') as f:
            for pattern in patterns:
                f.write(pattern + '\n')
        print(f"Found {len(patterns)} potential key patterns")
        print(f"Key patterns saved to {key_patterns_file}")
        
        # Update test script with new patterns
        update_test_script(patterns)

def update_test_script(new_patterns):
    """Update test_mmkv_patterns.py with new key patterns."""
    script_path = "test_mmkv_patterns.py"
    
    try: 
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Find the key_patterns list
        pattern_start = content.find("key_patterns = [")
        if pattern_start == -1:
            print("Could not find key_patterns list in test script")
            return
        
        # Find the end of the list
        pattern_end = content.find("]", pattern_start)
        if pattern_end == -1:
            print("Could not find end of key_patterns list")
            return
        
        # Create new patterns string
        new_patterns_str = "key_patterns = [\n"
        for pattern in new_patterns:
            new_patterns_str += f'    "{pattern}",\n'
        new_patterns_str += "]\n"
        
        # Replace the old patterns
        new_content = (
            content[:pattern_start] +
            new_patterns_str +
            content[pattern_end + 1:]
        )
        
        with open(script_path, 'w') as f:
            f.write(new_content)
        
        print("Updated test script with new patterns")
        
    except Exception as e:
        print(f"Error updating test script: {str(e)}")

if __name__ == "__main__":
    main()
