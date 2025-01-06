import struct
import logging
import binascii
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MMKVAnalyzer:
    def __init__(self, file_path):
        self.file_path = Path(file_path)
        
    def read_mmkv_header(self):
        """Read and parse MMKV file header."""
        try:
            with open(self.file_path, 'rb') as f:
                # Read first 64 bytes for thorough analysis
                header = f.read(64)
                if len(header) < 4:
                    return None
                
                logger.info(f'\n=== Analyzing {self.file_path.name} ===')
                
                # Check for known WeChat signatures
                signatures = {
                    b'dBmSt': 'WeChat Backup Store',
                    b'MMKVwx': 'WeChat MMKV Store',
                    b'KeyVal': 'WeChat Key-Value Store',
                    b'SQLite': 'SQLite Database'
                }
                
                file_type = 'Unknown'
                for sig, desc in signatures.items():
                    if header.startswith(sig):
                        file_type = desc
                        logger.info(f'File Type: {desc} (signature: {sig})')
                        break
                
                # Parse size and version info
                size = struct.unpack('<I', header[:4])[0]
                logger.info(f'Total Size: {size:,} bytes')
                
                if file_type == 'WeChat Backup Store':
                    version = header[4] if len(header) > 4 else None
                    if version is not None:
                        logger.info(f'Version: {version}')
                    
                    # Parse backup store specific header
                    if len(header) > 8:
                        backup_size = struct.unpack('<I', header[4:8])[0]
                        logger.info(f'Backup Size: {backup_size:,} bytes')
                
                # Detailed hex dump of header
                logger.info('\nHeader Analysis:')
                for i in range(0, min(64, len(header)), 16):
                    chunk = header[i:i+16]
                    hex_dump = ' '.join(f'{b:02x}' for b in chunk)
                    ascii_dump = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
                    logger.info(f'{i:04x}: {hex_dump:48s}  {ascii_dump}')
                
                # Look for potential key material in header
                key_patterns = [
                    (b'_key', 'Key Reference'),
                    (b'KEY', 'Key Identifier'),
                    (b'salt', 'Salt Value'),
                    (b'iv', 'IV Value'),
                    (b'crypt', 'Encryption Reference')
                ]
                
                logger.info('\nKey Pattern Analysis:')
                for pattern, desc in key_patterns:
                    if pattern in header.lower():
                        pos = header.lower().find(pattern)
                        context = header[max(0, pos-8):min(len(header), pos+24)]
                        logger.info(f'Found {desc} at offset {pos}:')
                        logger.info(f'Context: {context.hex()}')
                        if all(32 <= b <= 126 for b in context):
                            logger.info(f'ASCII: {context.decode("ascii", errors="replace")}')
                
                return header, file_type
                
        except Exception as e:
            logger.error(f'Error reading {self.file_path}: {e}')
            return None, 'Unknown'
    
    def extract_potential_keys(self):
        """Extract potential key material from MMKV file."""
        try:
            with open(self.file_path, 'rb') as f:
                data = f.read()
                
                # WeChat-specific key patterns
                key_patterns = {
                    'db_key': (b'DB_KEY', b'db_key', b'dbkey'),
                    'enc_key': (b'ENC_KEY', b'enc_key', b'encryption_key'),
                    'salt': (b'SALT', b'salt', b'_salt_'),
                    'iv': (b'IV', b'iv', b'_iv_'),
                    'key': (b'_key', b'KEY', b'key'),
                    'crypt': (b'crypt', b'CRYPT', b'encrypt')
                }
                
                logger.info('\n=== Key Material Analysis ===')
                
                # First pass: look for known patterns
                for category, patterns in key_patterns.items():
                    for pattern in patterns:
                        pos = 0
                        while True:
                            pos = data.find(pattern, pos)
                            if pos == -1:
                                break
                                
                            # Extract context around the pattern
                            start = max(0, pos - 16)
                            end = min(len(data), pos + len(pattern) + 48)
                            context = data[start:end]
                            
                            logger.info(f'\nFound {category} pattern at offset {pos}:')
                            logger.info(f'Pattern: {pattern}')
                            logger.info(f'Context (hex): {context.hex()}')
                            
                            # Try to decode as ASCII if printable
                            if all(32 <= b <= 126 for b in context):
                                logger.info(f'Context (ASCII): {context.decode("ascii", errors="replace")}')
                            
                            # Look for potential key material after pattern
                            key_material = data[pos + len(pattern):pos + len(pattern) + 64]
                            if len(key_material) >= 16:
                                logger.info('\nPotential key material:')
                                logger.info(f'Hex: {key_material.hex()}')
                                
                                # Check if it looks like various encodings
                                if all(c in b'0123456789abcdefABCDEF' for c in key_material):
                                    logger.info('Appears to be hex-encoded')
                                elif all(c in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in key_material):
                                    logger.info('Appears to be base64-encoded')
                                elif all(32 <= b <= 126 for b in key_material):
                                    logger.info(f'ASCII: {key_material.decode("ascii", errors="replace")}')
                                
                                
                                # Check for common key sizes
                                if len(key_material) in [16, 24, 32, 64]:
                                    logger.info(f'*** Matches common key size: {len(key_material)} bytes ***')
                            
                            pos += len(pattern)
                
                # Second pass: structured key-value parsing
                pos = 8  # Skip header
                entry_count = 0
                key_related_count = 0
                
                logger.info('\n=== Structured Key-Value Analysis ===')
                
                while pos < len(data):
                    try:
                        if pos + 4 > len(data):
                            break
                            
                        # Read entry header
                        key_size = struct.unpack('<I', data[pos:pos+4])[0]
                        if key_size > 256 or key_size == 0:  # Reasonable size limit
                            pos += 1
                            continue
                            
                        pos += 4
                        if pos + key_size > len(data):
                            break
                            
                        # Read key
                        key = data[pos:pos+key_size]
                        pos += key_size
                        
                        # Read value size
                        if pos + 4 > len(data):
                            break
                            
                        val_size = struct.unpack('<I', data[pos:pos+4])[0]
                        if val_size > 1024 or val_size == 0:  # Reasonable size limit
                            pos += 1
                            continue
                            
                        pos += 4
                        if pos + val_size > len(data):
                            break
                            
                        # Read value
                        value = data[pos:pos+val_size]
                        
                        # Process if key or value looks interesting
                        key_str = key.decode('utf-8', errors='replace').lower()
                        is_interesting = False
                        
                        for category, patterns in key_patterns.items():
                            if any(p.lower() in key.lower() for p in patterns):
                                is_interesting = True
                                key_related_count += 1
                                logger.info(f'\nKey-Value Entry {key_related_count}:')
                                logger.info(f'Category: {category}')
                                logger.info(f'Key: {key_str}')
                                logger.info(f'Value size: {val_size}')
                                logger.info(f'Value (hex): {value.hex()}')
                                
                                if len(value) in [16, 24, 32, 64]:
                                    logger.info(f'*** Potential key material (size: {len(value)}) ***')
                                    
                                if all(32 <= b <= 126 for b in value):
                                    logger.info(f'Value (ASCII): {value.decode("ascii", errors="replace")}')
                                break
                        
                        pos += val_size
                        entry_count += 1
                        
                    except Exception as e:
                        logger.debug(f'Error parsing at position {pos}: {e}')
                        pos += 1
                
                logger.info(f'\nProcessed {entry_count} total entries')
                logger.info(f'Found {key_related_count} key-related entries')
                            
                        # Even if key doesn't contain interesting patterns,
                        # check the value size and skip it
                        if pos + 4 <= len(data):
                            try:
                                val_size = struct.unpack('<I', data[pos:pos+4])[0]
                                if val_size > 1024:  # Sanity check
                                    pos += 1
                                    continue
                                pos += 4 + val_size
                            except Exception as e:
                                logger.debug(f'Error parsing value size at position {pos}: {e}')
                                pos += 1
                                continue
                        
                    except Exception as e:
                        logger.debug(f'Error parsing key at position {pos}: {e}')
                        pos += 1
                        continue
                
        except Exception as e:
            logger.error(f'Error analyzing {self.file_path}: {e}')

def main():
    """Analyze all MMKV files in the attachments directory."""
    attachments_dir = Path('/home/ubuntu/attachments')
    mmkv_files = [
        'mmkv.default',
        'resourcekvmap',
        'xweb'
    ]
    
    logger.info('Starting MMKV analysis...')
    for filename in mmkv_files:
        file_path = attachments_dir / filename
        if file_path.exists():
            analyzer = MMKVAnalyzer(file_path)
            logger.info(f'\nAnalyzing {filename}:')
            analyzer.read_mmkv_header()
            analyzer.extract_potential_keys()

if __name__ == '__main__':
    main()
