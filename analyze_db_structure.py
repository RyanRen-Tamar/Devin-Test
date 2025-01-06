#!/usr/bin/env python3
import os
import struct
import binascii

def read_file_header(filepath, size=100):
    """Read and analyze the first bytes of a file."""
    with open(filepath, 'rb') as f:
        header = f.read(size)
    return header

def analyze_header(header):
    """Analyze header bytes for patterns and structures."""
    results = {
        'hex': binascii.hexlify(header).decode('ascii'),
        'patterns': [],
        'potential_markers': []
    }
    
    # Look for SQLite magic string
    if header[:16].startswith(b'SQLite format 3'):
        results['patterns'].append('SQLite3 database')
        # Check page size
        page_size = struct.unpack('>H', header[16:18])[0]
        results['patterns'].append(f'Page size: {page_size}')
    
    # Look for SQLCipher markers
    if b'sqlcipher' in header.lower():
        results['patterns'].append('SQLCipher encrypted')
    
    # Look for repeating patterns
    for i in range(0, len(header)-4):
        chunk = header[i:i+4]
        if chunk.count(chunk[0]) == 4:  # Four identical bytes
            results['patterns'].append(f'Repeating byte {hex(chunk[0])} at offset {i}')
    
    # Look for potential key markers
    key_markers = [b'key', b'KEY', b'salt', b'SALT', b'iv', b'IV']
    for marker in key_markers:
        if marker in header:
            results['potential_markers'].append(f'Found {marker} at offset {header.index(marker)}')
    
    return results

def analyze_wal_file(filepath):
    """Analyze Write-Ahead Log file structure."""
    results = []
    try:
        with open(filepath, 'rb') as f:
            # WAL header is 32 bytes
            header = f.read(32)
            if len(header) == 32:
                magic = header[:4]
                file_format = struct.unpack('>I', header[4:8])[0]
                page_size = struct.unpack('>I', header[8:12])[0]
                results.append(f'WAL Magic: {binascii.hexlify(magic).decode()}')
                results.append(f'WAL Format: {file_format}')
                results.append(f'WAL Page Size: {page_size}')
    except Exception as e:
        results.append(f'Error analyzing WAL: {str(e)}')
    return results

def analyze_shm_file(filepath):
    """Analyze Shared Memory file structure."""
    results = []
    try:
        with open(filepath, 'rb') as f:
            # SHM header analysis
            header = f.read(32)
            if len(header) > 0:
                results.append(f'SHM Header: {binascii.hexlify(header[:16]).decode()}')
                # Look for any patterns in the shared memory
                if all(x == header[0] for x in header):
                    results.append('SHM appears to be initialized with same byte')
    except Exception as e:
        results.append(f'Error analyzing SHM: {str(e)}')
    return results

def main():
    base_dir = '/home/ubuntu/attachments'
    files_to_analyze = [
        'msg_2.db',
        'msg_2.db-wal',
        'msg_2.db-shm',
        'msg_2.db-backup',
        'KeyValue.db'
    ]
    
    print("=== WeChat Database Structure Analysis ===")
    print(f"Timestamp: {os.popen('date').read().strip()}")
    print("=" * 50)
    
    for filename in files_to_analyze:
        filepath = os.path.join(base_dir, filename)
        if not os.path.exists(filepath):
            print(f"\nFile not found: {filename}")
            continue
            
        print(f"\nAnalyzing: {filename}")
        print("-" * 40)
        
        # Basic file info
        size = os.path.getsize(filepath)
        print(f"File size: {size} bytes")
        
        # Header analysis
        header = read_file_header(filepath)
        results = analyze_header(header)
        
        print("\nHeader Analysis:")
        print(f"First 32 bytes (hex): {results['hex'][:64]}")
        
        if results['patterns']:
            print("\nDetected Patterns:")
            for pattern in results['patterns']:
                print(f"- {pattern}")
        
        if results['potential_markers']:
            print("\nPotential Markers:")
            for marker in results['potential_markers']:
                print(f"- {marker}")
        
        # Specific analysis for different file types
        if filename.endswith('-wal'):
            print("\nWAL File Analysis:")
            wal_results = analyze_wal_file(filepath)
            for result in wal_results:
                print(f"- {result}")
        
        elif filename.endswith('-shm'):
            print("\nSHM File Analysis:")
            shm_results = analyze_shm_file(filepath)
            for result in shm_results:
                print(f"- {result}")
        
        print("\nFile Structure:")
        # Read and analyze file structure in chunks
        with open(filepath, 'rb') as f:
            chunk_size = 16384  # 16KB chunks
            offset = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                    
                # Look for interesting patterns
                if b'SQLite' in chunk or b'sqlcipher' in chunk:
                    print(f"- Found database marker at offset: {offset}")
                if b'WAL' in chunk:
                    print(f"- Found WAL marker at offset: {offset}")
                if b'salt' in chunk or b'SALT' in chunk:
                    print(f"- Found salt marker at offset: {offset}")
                    
                offset += len(chunk)

if __name__ == '__main__':
    main()
