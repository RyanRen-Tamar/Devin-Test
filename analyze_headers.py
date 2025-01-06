import logging
import binascii
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_sqlcipher_patterns(header):
    """Analyze header for SQLCipher-specific patterns."""
    # Known SQLCipher version patterns
    sqlcipher_patterns = {
        'v3': {
            'salt_size': 16,
            'header_size': 16,
            'page_size': 1024,
            'kdf_iter': 64000,
        },
        'v4': {
            'salt_size': 32,
            'header_size': 32,
            'page_size': 4096,
            'kdf_iter': 256000,
        }
    }
    
    results = []
    
    # Check for common SQLCipher patterns
    for version, props in sqlcipher_patterns.items():
        salt = header[:props['salt_size']]
        header_block = header[props['salt_size']:props['salt_size'] + props['header_size']]
        
        results.append(f"\nChecking {version} patterns:")
        results.append(f"Salt (first {props['salt_size']} bytes): {binascii.hexlify(salt).decode()}")
        results.append(f"Header block: {binascii.hexlify(header_block).decode()}")
        
        # Check for typical SQLCipher characteristics
        entropy = sum(1 for b in salt if b > 32 and b < 127) / len(salt)
        results.append(f"Salt entropy: {entropy:.2f}")
        
    return results

def analyze_file_header(file_path, read_size=256):
    """Analyze the header of a file to identify encryption method and patterns."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(read_size)
            
        logger.info(f"\nAnalyzing header of {file_path}")
        logger.info("=" * 50)
        
        # Show raw hex
        hex_header = binascii.hexlify(header).decode()
        logger.info(f"Raw hex header: {hex_header}")
        
        # Show ASCII representation
        ascii_header = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in header)
        logger.info(f"ASCII representation: {ascii_header}")
        
        # Check for SQLite/SQLCipher signatures
        sqlite_magic = b'SQLite format 3\x00'
        
        # Always analyze as potentially encrypted
        logger.info("\nAnalyzing encryption characteristics:")
        
        # Check if standard SQLite
        if header[:16] == sqlite_magic:
            logger.info("File appears to be a standard SQLite database")
            is_encrypted = False
        else:
            logger.info("File appears to be an encrypted database")
            logger.info("First 16 bytes differ from standard SQLite header")
            logger.info("This suggests SQLCipher or similar encryption")
            is_encrypted = True
            
        # Calculate header statistics
        zero_bytes = header[:16].count(0)
        printable_bytes = sum(1 for b in header[:16] if 32 <= b <= 126)
        entropy = printable_bytes / 16.0
        
        logger.info(f"\nHeader statistics:")
        logger.info(f"Zero bytes in header: {zero_bytes}")
        logger.info(f"Printable bytes in header: {printable_bytes}")
        logger.info(f"Header entropy: {entropy:.2f}")
        
        if is_encrypted:
            
            # Compare headers to identify encryption patterns
            logger.info("\nHeader comparison:")
            logger.info(f"Expected: {binascii.hexlify(sqlite_magic).decode()}")
            logger.info(f"Actual  : {binascii.hexlify(header[:16]).decode()}")
            
            # Calculate differences
            xored = bytes(a ^ b for a, b in zip(header[:16], sqlite_magic))
            logger.info(f"XOR diff: {binascii.hexlify(xored).decode()}")
            
            # Analyze SQLCipher patterns
            for result in analyze_sqlcipher_patterns(header):
                logger.info(result)
            
            # Look for repeating patterns
            for i in range(4, 33):  # Check for patterns of various lengths
                pattern = header[:i]
                count = header.count(pattern)
                if count > 1:
                    logger.info(f"\nFound repeating pattern of length {i}:")
                    logger.info(f"Pattern: {binascii.hexlify(pattern).decode()}")
                    logger.info(f"Occurrences: {count}")
                    
            # Check for potential key material
            key_lengths = [16, 24, 32, 64]  # Common encryption key lengths
            for i in range(len(header) - max(key_lengths)):
                for length in key_lengths:
                    chunk = header[i:i+length]
                    # Look for high-entropy sequences
                    if all(32 < b < 127 for b in chunk):
                        logger.info(f"\nPotential key material at offset {i}:")
                        logger.info(f"Hex: {binascii.hexlify(chunk).decode()}")
                        logger.info(f"ASCII: {chunk.decode(errors='replace')}")
                        
        # Analyze related files (WAL, SHM)
        base_path = Path(file_path)
        related_files = [
            (base_path.with_suffix(base_path.suffix + '-wal'), 'Write-Ahead Log'),
            (base_path.with_suffix(base_path.suffix + '-shm'), 'Shared Memory File'),
            (base_path.with_suffix(base_path.suffix + '-journal'), 'Rollback Journal'),
        ]
        
        for related_file, desc in related_files:
            if related_file.exists():
                logger.info(f"\nAnalyzing {desc}: {related_file}")
                try:
                    with open(related_file, 'rb') as f:
                        related_header = f.read(32)
                        
                    logger.info(f"Header (hex): {binascii.hexlify(related_header).decode()}")
                    logger.info(f"Header (ASCII): {''.join(chr(b) if 32 <= b <= 126 else '.' for b in related_header)}")
                    
                    # Check for WAL/SHM signatures
                    if str(related_file).endswith('-wal'):
                        # WAL files typically start with 0x377f0682 or 0x377f0683
                        wal_magic = related_header[:4]
                        logger.info(f"WAL magic number: 0x{binascii.hexlify(wal_magic).decode()}")
                    elif str(related_file).endswith('-shm'):
                        # SHM files typically have a specific structure
                        shm_header = related_header[:8]
                        logger.info(f"SHM header: 0x{binascii.hexlify(shm_header).decode()}")
                except Exception as e:
                    logger.error(f"Error reading {desc}: {e}")
        
        # Look for common patterns
        patterns = {
            'sqlcipher': b'SQLCipher',
            'encrypted': b'encrypted',
            'salt': b'salt',
            'key': b'key',
            'iv': b'iv',
        }
        
        for name, pattern in patterns.items():
            if pattern in header:
                logger.info(f"Found pattern '{name}' in header")
        
        # Check for potential key material in header
        potential_keys = []
        for i in range(len(header) - 31):
            chunk = header[i:i+32]
            # Look for hex-like sequences
            if all(c in b'0123456789abcdefABCDEF' for c in chunk):
                potential_keys.append(chunk.decode())
        
        if potential_keys:
            logger.info("\nPotential key material found in header:")
            for key in potential_keys:
                logger.info(f"- {key}")
        
    except Exception as e:
        logger.error(f"Error analyzing file: {e}")

def main():
    files = [
        Path("/home/ubuntu/attachments/msg_2.db"),
        Path("/home/ubuntu/attachments/KeyValue.db"),
    ]
    
    for file_path in files:
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            continue
        
        analyze_file_header(str(file_path))

if __name__ == "__main__":
    main()
