#!/usr/bin/env python3
import os
import binascii
import sqlite3
import subprocess
from pathlib import Path

def extract_key_patterns():
    """Extract and transform potential key patterns from MMKV analysis."""
    patterns = [
        "05fbe0d7bb06",
        "05808cddbb06",
        "05cc85e3bb06",
        "05afb3e8bb06",
        "05d195c5bb06",
        "05d5f6cabb06",
        "05b0b5d2bb06"
    ]
    
    # Generate variations of the keys
    key_variations = []
    for pattern in patterns:
        # Convert hex string to bytes
        pattern_bytes = binascii.unhexlify(pattern)
        
        # Original pattern
        key_variations.append(pattern)
        
        # Repeat pattern to 32 bytes
        repeated = pattern * (32 // len(pattern_bytes) + 1)
        key_variations.append(repeated[:64])  # Take first 64 hex chars (32 bytes)
        
        # Pattern as prefix with padding
        padded = pattern + "0" * (64 - len(pattern))
        key_variations.append(padded)
        
        # Pattern as suffix with padding
        padded_prefix = "0" * (64 - len(pattern)) + pattern
        key_variations.append(padded_prefix)
        
        # Pattern with its own hex as padding
        hex_pattern = binascii.hexlify(pattern_bytes).decode('ascii')
        padded_hex = (hex_pattern * (64 // len(hex_pattern) + 1))[:64]
        key_variations.append(padded_hex)
    
    return key_variations

def test_key_with_sqlcipher(db_path, key_hex):
    """Test a potential key with SQLCipher."""
    try:
        # Convert hex to raw key
        key_raw = binascii.unhexlify(key_hex)
        
        # Create a temporary config file
        config_path = Path('temp_sqlcipher_config.txt')
        config_path.write_text(f"""
PRAGMA key = "x'{key_hex}'";
PRAGMA cipher_page_size = 4096;
PRAGMA kdf_iter = 64000;
PRAGMA cipher_hmac_algorithm = HMAC_SHA1;
PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1;
SELECT count(*) FROM sqlite_master;
""")
        
        # Use SQLCipher to test the key
        result = subprocess.run(
            ['sqlcipher', db_path, '.read temp_sqlcipher_config.txt'],
            capture_output=True,
            text=True
        )
        
        # Check if the command succeeded and returned a valid result
        if "Error" not in result.stderr and "0" in result.stdout:
            print(f"Potential valid key found: {key_hex}")
            print("SQLCipher output:", result.stdout)
            
            # Save working configuration
            with open('mmkv_working_keys.txt', 'a') as f:
                f.write(f"Working key: {key_hex}\n")
                f.write("Configuration:\n")
                f.write(config_path.read_text())
                f.write("-" * 50 + "\n")
            
            return True
        
    except Exception as e:
        print(f"Error testing key {key_hex}: {str(e)}")
    
    return False

def main():
    print("=== MMKV Key Testing Tool ===")
    print(f"Timestamp: {os.popen('date').read().strip()}")
    print("=" * 50)
    
    # Get key variations from MMKV patterns
    key_variations = extract_key_patterns()
    print(f"\nGenerated {len(key_variations)} key variations to test")
    
    # Test each key variation
    msg_db_path = '/home/ubuntu/attachments/msg_2.db'
    keyvalue_db_path = '/home/ubuntu/attachments/KeyValue.db'
    
    print("\nTesting keys on msg_2.db...")
    for key in key_variations:
        print(f"\nTrying key: {key}")
        if test_key_with_sqlcipher(msg_db_path, key):
            print("Success with msg_2.db!")
            
            # Try the same key with KeyValue.db
            print("\nTrying successful key on KeyValue.db...")
            if test_key_with_sqlcipher(keyvalue_db_path, key):
                print("Success with both databases!")
                break
    
    # Clean up
    if os.path.exists('temp_sqlcipher_config.txt'):
        os.remove('temp_sqlcipher_config.txt')

if __name__ == '__main__':
    main()
