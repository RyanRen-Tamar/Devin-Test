import struct
import binascii
import math
from collections import defaultdict

def analyze_sqlite_header(file_path):
    """Analyze the header of a potentially encrypted SQLite database."""
    print(f"Analyzing file: {file_path}")
    
    with open(file_path, 'rb') as f:
        # Read first 100 bytes for header analysis
        header = f.read(100)
        
        # Convert to hex for analysis
        header_hex = binascii.hexlify(header).decode('ascii')
        print("\nHeader hex:")
        for i in range(0, len(header_hex), 32):
            print(f"{i//2:4d}: {header_hex[i:i+32]}")
        
        # Look for SQLite magic string (even if encrypted)
        if header.startswith(b'SQLite'):
            print("\nStandard SQLite header detected")
        else:
            print("\nNon-standard header - possibly encrypted")
            
        # Check for SQLCipher markers
        sqlcipher_markers = [
            b'SQLite',  # Standard SQLite
            b'\x00\x01\x01',  # SQLCipher version 1
            b'\x00\x02\x01',  # SQLCipher version 2
            b'\x00\x03\x01',  # SQLCipher version 3
            b'\x00\x04\x01',  # SQLCipher version 4
        ]
        
        for marker in sqlcipher_markers:
            if marker in header:
                print(f"Found marker: {marker!r}")
        
        # Analyze byte frequency
        freq = defaultdict(int)
        for byte in header:
            freq[byte] += 1
        
        # Calculate Shannon entropy (high entropy might indicate encryption)
        total_bytes = sum(freq.values())
        entropy = 0
        for count in freq.values():
            probability = count / total_bytes
            if probability > 0:
                entropy -= probability * math.log2(probability)
        
        # Normalize entropy (max entropy for bytes is 8 bits)
        normalized_entropy = entropy / 8.0
        print(f"\nHeader entropy: {normalized_entropy:.3f} (normalized, 1.0 = maximum randomness)")
        
        # Look for repeating patterns
        patterns = defaultdict(list)
        for size in [4, 8, 16]:
            for i in range(len(header) - size):
                pattern = header[i:i+size]
                patterns[pattern].append(i)
        
        print("\nRepeating patterns:")
        for pattern, positions in patterns.items():
            if len(positions) > 1:
                pattern_hex = binascii.hexlify(pattern).decode('ascii')
                print(f"Pattern {pattern_hex} at positions: {positions}")
        
        # Try to detect page size
        if len(header) >= 16:
            possible_page_size = struct.unpack('>H', header[16:18])[0]
            print(f"\nPossible page size: {possible_page_size}")
            
        return {
            'header_hex': header_hex,
            'entropy': entropy,
            'patterns': {k.hex(): v for k, v in patterns.items() if len(v) > 1},
            'possible_page_size': possible_page_size if len(header) >= 18 else None
        }

def main():
    # Analyze both the main database and its backup
    files = [
        '/home/ubuntu/attachments/msg_2.db',
        '/home/ubuntu/attachments/msg_2.db-backup'
    ]
    
    results = {}
    for file_path in files:
        try:
            results[file_path] = analyze_sqlite_header(file_path)
            print("\n" + "="*50 + "\n")
        except FileNotFoundError:
            print(f"File not found: {file_path}")
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
    
    # Compare headers if we have both files
    if len(results) == 2:
        print("Comparing headers:")
        file_paths = list(results.keys())
        header1 = results[file_paths[0]]['header_hex']
        header2 = results[file_paths[1]]['header_hex']
        
        if header1 == header2:
            print("Headers are identical")
        else:
            print("Headers differ:")
            for i in range(0, len(header1), 32):
                if header1[i:i+32] != header2[i:i+32]:
                    print(f"Position {i//2}:")
                    print(f"  {file_paths[0]}: {header1[i:i+32]}")
                    print(f"  {file_paths[1]}: {header2[i:i+32]}")

if __name__ == '__main__':
    main()
