from pysqlcipher3 import dbapi2 as sqlcipher
import hashlib
import logging
from pathlib import Path

# Configure logging to show more detail for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('decryption_attempts.log')
    ]
)
logger = logging.getLogger(__name__)

def hash_key(key):
    """Generate SHA-256 hash of the key."""
    return hashlib.sha256(key.encode()).hexdigest()

def try_decrypt_db(db_path, key, page_size=4096, kdf_iter=256000, salt_size=32):
    """Attempt to decrypt the database with SQLCipher v4 parameters."""
    try:
        conn = sqlcipher.connect(db_path)
        cursor = conn.cursor()
        
        # Configure SQLCipher v4 parameters
        cursor.execute(f"PRAGMA key = '{key}'")
        cursor.execute(f"PRAGMA cipher_page_size = {page_size}")
        cursor.execute(f"PRAGMA kdf_iter = {kdf_iter}")
        cursor.execute("PRAGMA cipher_compatibility = 4")
        cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
        cursor.execute(f"PRAGMA cipher_salt_size = {salt_size}")
        cursor.execute("PRAGMA cipher_plaintext_header_size = 0")
        cursor.execute("PRAGMA cipher_memory_security = OFF")  # For better performance during testing
        cursor.execute("PRAGMA cipher_use_hmac = ON")  # Ensure HMAC is enabled for v4
        cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")  # Use SHA512 for key derivation
        
        # Test if we can read the database
        try:
            # Try to read the schema
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            if tables:
                logger.info(f"Successfully decrypted with key: {key}")
                logger.info(f"Configuration: page_size={page_size}, kdf_iter={kdf_iter}, salt_size={salt_size}")
                logger.info("Tables found:")
                for table in tables:
                    logger.info(f"- {table[0]}")
                return True
            
        except sqlcipher.DatabaseError as e:
            if "not a database" in str(e) or "file is encrypted" in str(e) or "file is not a database" in str(e):
                logger.debug(f"Failed with key {key}: wrong key or parameters")
            elif "key spec" in str(e).lower():
                logger.debug(f"Failed with key {key}: invalid key format")
            else:
                logger.warning(f"Unexpected error: {e}")
            return False
            
    except Exception as e:
        logger.debug(f"Decryption attempt failed: {e}")
        return False
    finally:
        try:
            conn.close()
        except:
            pass
    
    return False

def test_key_variations(db_path, base_key):
    """Test different variations of a key with SQLCipher v4 parameters."""
    variations = [
        base_key,                    # Raw key
        hash_key(base_key),         # SHA-256 hash
        base_key.lower(),           # Lowercase
        base_key.upper(),           # Uppercase
        base_key.replace('-', ''),  # Remove dashes
    ]
    
    # SQLCipher v4 parameters based on header analysis
    configs = [
        # Default v4 configuration
        {'page_size': 4096, 'kdf_iter': 256000, 'salt_size': 32},
        # Alternative configurations based on header patterns
        {'page_size': 4096, 'kdf_iter': 256000, 'salt_size': 16},
        {'page_size': 1024, 'kdf_iter': 256000, 'salt_size': 32},
    ]
    
    for key in variations:
        # Only log if key matches certain patterns
        if any(pattern in key.lower() for pattern in ['wx', 'mm', 'chat', '8541671c', '53f5c7c5', 'e79382b1']):
            logger.info(f"\nTesting promising key variation: {key}")
        else:
            logger.debug(f"Testing key: {key}")
            
        for config in configs:
            if try_decrypt_db(db_path, key, **config):
                return True
    return False

def derive_keys(base_key):
    """Generate additional key variations based on WeChat patterns and header analysis."""
    derived = []
    
    # Try different hash algorithms
    derived.append(hashlib.md5(base_key.encode()).hexdigest())
    derived.append(hashlib.sha1(base_key.encode()).hexdigest())
    derived.append(hashlib.sha256(base_key.encode()).hexdigest())
    
    # Try concatenating with common salts and patterns from header analysis
    salts = [
        'wechat', 'WeChat', 'wx', 'WX', 'mm', 'MM',
        '8541671c1a2395cd',  # From msg_2.db header
        '53f5c7c56b6c98c9',  # From KeyValue.db header
        'e79382b1a59f5ac4',  # From user ID
        '7e77ed537a6b9352',  # From user ID (second half)
    ]
    
    for salt in salts:
        # Try salt combinations
        derived.append(hashlib.sha256((base_key + salt).encode()).hexdigest())
        derived.append(hashlib.sha256((salt + base_key).encode()).hexdigest())
        derived.append(hashlib.sha512((base_key + salt).encode()).hexdigest()[:64])
        derived.append(hashlib.sha512((salt + base_key).encode()).hexdigest()[:64])
        
        # Try with WeChat-specific prefixes
        derived.append(f"wx{salt}")
        derived.append(f"mm{salt}")
        
    # If the base key looks like a device ID or user ID (32 chars)
    if len(base_key) == 32:
        # Try splitting and combining
        first_half = base_key[:16]
        second_half = base_key[16:]
        derived.append(first_half)
        derived.append(second_half)
        derived.append(second_half + first_half)
        
        # Try with common WeChat key prefixes
        derived.append(f"wx_{base_key}")
        derived.append(f"mm_{base_key}")
        derived.append(f"chat_{base_key}")
        
    return list(set(derived))  # Remove duplicates

def test_database(db_path, key_candidates):
    """Test decryption of a specific database file."""
    logger.info(f"\nTesting decryption of {db_path}")
    
    for candidate in key_candidates:
        logger.info(f"\n=== Testing key candidate: {candidate} ===")
        
        # Test base key
        if test_key_variations(str(db_path), candidate):
            logger.info(f"Successfully found working key configuration!")
            return True
            
        # Test derived keys
        derived_keys = derive_keys(candidate)
        for derived in derived_keys:
            logger.info(f"\n=== Testing derived key: {derived} ===")
            if test_key_variations(str(db_path), derived):
                logger.info(f"Successfully found working key configuration!")
                return True
    
    return False

def main():
    # Key candidates from header analysis
    key_candidates = [
        # From msg_2.db header
        "8541671c1a2395cd690ae0b1781119b3",  # Salt from header
        "0cb654d03daec54e4320013589b89225",  # Header block
        # From KeyValue.db header
        "53f5c7c56b6c98c9d921441f6402bb38",  # Salt from header
        "8d452d23d76047ee3f2ed288e1d23fd9",  # Header block
        # From MMKV analysis
        "e79382b1a59f5ac47e77ed537a6b9352",  # User ID from path
        "Qe79382b1a59f5ac47e77ed537a6b9352", # With Q prefix
        # Combinations of header values
        "8541671c1a2395cd53f5c7c56b6c98c9",  # Combined salts
        "0cb654d03daec54e8d452d23d76047ee",  # Combined blocks
    ]
    
    # Additional patterns from analysis
    patterns = [
        "wx_",       # WeChat prefix
        "mm_",       # MM prefix
        "chat_",     # Chat prefix
        "2.0b4.0.9", # Version
    ]
    
    # Generate variations with patterns
    for pattern in patterns:
        for key in key_candidates[:]:  # Use slice to avoid modifying during iteration
            key_candidates.append(f"{pattern}{key}")
    
    # Add derived keys
    for key in key_candidates[:]:
        key_candidates.extend(derive_keys(key))
    
    databases = [
        Path("/home/ubuntu/attachments/KeyValue.db"),
        Path("/home/ubuntu/attachments/msg_2.db"),
    ]
    
    logger.info("Starting decryption attempts with header-based keys...")
    success = False
    for db in databases:
        if not db.exists():
            logger.error(f"Database file not found: {db}")
            continue
            
        logger.info(f"\nTesting database: {db}")
        if test_database(db, key_candidates):
            success = True
            break
    
    if not success:
        logger.info("\nNo successful decryption found with header-based key candidates")

if __name__ == "__main__":
    main()
