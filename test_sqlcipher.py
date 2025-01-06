from pysqlcipher3 import dbapi2 as sqlite
import os
import logging
import binascii

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_file_header(db_path):
    """Analyze the first 32 bytes of the file for patterns."""
    try:
        with open(db_path, 'rb') as f:
            header = f.read(32)
            logger.info(f'File header: {header.hex()}')
            
            # Check for backup format
            if header.startswith(b'dBmSt'):
                version = header[5]
                header_size = int.from_bytes(header[6:10], 'little')
                data_size = int.from_bytes(header[10:14], 'little')
                logger.info(f'Backup format detected: version={version}, header_size={header_size}, data_size={data_size}')
                return header[14:32].hex()  # Return potential key material
    except Exception as e:
        logger.error(f'Error analyzing header: {e}')
    return None

def try_open_db(db_path, key_hex, cipher_page_size=4096, kdf_iter=64000):
    """Try to open an encrypted SQLite database with given parameters."""
    try:
        conn = sqlite.connect(db_path)
        cursor = conn.cursor()
        
        # Log attempt details
        logger.debug(f'\nTrying configuration:')
        logger.debug(f'- Key (hex): {key_hex[:16]}...')
        logger.debug(f'- Page size: {cipher_page_size}')
        logger.debug(f'- KDF iterations: {kdf_iter}')
        
        # Configure SQLCipher parameters
        cursor.execute(f'PRAGMA key = "x\'{key_hex}\'"')
        cursor.execute('PRAGMA cipher_compatibility = 3')
        cursor.execute(f'PRAGMA cipher_page_size = {cipher_page_size}')
        cursor.execute(f'PRAGMA kdf_iter = {kdf_iter}')
        
        # Test if we can read the database
        cursor.execute('SELECT count(*) FROM sqlite_master')
        result = cursor.fetchone()
        logger.info(f'Successfully opened {db_path} with key {key_hex[:16]}...')
        
        # Try to get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        logger.info(f'Tables found: {tables}')
        return True
    except Exception as e:
        logger.debug(f'Failed with error: {str(e)}')
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def test_database(db_path):
    """Test various key patterns and configurations on a database."""
    if not os.path.exists(db_path):
        logger.error(f'Database not found: {db_path}')
        return

    logger.info(f'\nTesting {os.path.basename(db_path)}...')
    
    # Analyze file header for potential key material
    potential_key = analyze_file_header(db_path)
    
    # Common WeChat key patterns
    key_patterns = [
        '1234567890abcdef' * 2,  # Common test key
        'mm_key_v1',             # Common WeChat pattern
        'wx_dat_key',            # Another common pattern
        'chat.db',               # WeChat database name
        'message1',              # Message-related pattern
        'MM.dat',                # WeChat data file
        'wx.dat',                # Another WeChat data file
        'WeChat_Database_Key',   # Possible database key
        'wx_db_key_v1',         # Version-specific key
        'mm_sqlite_key'         # SQLite-specific key
    ]
    
    # Add potential key from header if found
    if potential_key:
        key_patterns.append(potential_key)
        # Also try variations of the header key
        key_patterns.extend([
            potential_key[:32],  # First 16 bytes
            potential_key[-32:], # Last 16 bytes
        ])
    
    # Try different SQLCipher configurations
    configs = [
        (4096, 64000),  # Default SQLCipher 3.x
        (1024, 64000),  # Alternative page size
        (4096, 4000),   # Lower KDF iterations
        (1024, 4000)    # Alternative combination
    ]
    
    for key in key_patterns:
        key_hex = key.encode().hex()
        for page_size, kdf_iter in configs:
            try_open_db(db_path, key_hex, page_size, kdf_iter)

def main():
    """Main function to test WeChat database decryption."""
    # Install required packages
    logger.info("Setting up dependencies...")
    os.system('sudo apt-get update')
    os.system('sudo apt-get install -y libsqlcipher-dev libsqlcipher0')
    os.system('pip3 install pysqlcipher3')
    
    # Test databases
    attachments_dir = '/home/ubuntu/attachments'
    test_database(os.path.join(attachments_dir, 'msg_2.db'))
    test_database(os.path.join(attachments_dir, 'KeyValue.db'))

if __name__ == '__main__':
    main()
