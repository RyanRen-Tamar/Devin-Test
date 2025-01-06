import hashlib
import sqlite3
import binascii
import subprocess
import json
from pathlib import Path

def generate_version_based_keys():
    """Generate potential keys based on version information"""
    keys = set()
    
    # Current version info
    current_version = "3.8.9.16"
    current_build = "28588"
    current_hash = "89ba93b000"
    
    # Basic version-based keys
    keys.add(current_version)
    keys.add(current_build)
    keys.add(current_hash)
    
    # Combined version info
    keys.add(f"v{current_version}")
    keys.add(f"{current_version}_{current_build}")
    keys.add(f"{current_version}_{current_hash}")
    keys.add(f"{current_build}_{current_hash}")
    
    # Hash-based keys
    keys.add(hashlib.md5(current_version.encode()).hexdigest())
    keys.add(hashlib.md5(current_build.encode()).hexdigest())
    keys.add(hashlib.md5(current_hash.encode()).hexdigest())
    
    # Combined hash-based keys
    combined = f"{current_version}_{current_build}_{current_hash}"
    keys.add(hashlib.md5(combined.encode()).hexdigest())
    
    # Version components
    version_parts = current_version.split('.')
    for i in range(len(version_parts)):
        key = '.'.join(version_parts[:i+1])
        keys.add(key)
        keys.add(hashlib.md5(key.encode()).hexdigest())
    
    # Build number variations
    build_int = int(current_build)
    keys.add(hex(build_int)[2:])  # Hex without '0x'
    keys.add(hashlib.md5(hex(build_int)[2:].encode()).hexdigest())
    
    # Hash variations
    keys.add(current_hash[:16])  # First 16 chars
    keys.add(current_hash[:8])   # First 8 chars
    
    return list(keys)

def test_sqlcipher_key(db_path, key, config=None):
    """Test if a key works with SQLCipher"""
    try:
        conn = sqlite3.connect(db_path)
        if config:
            conn.execute(f"PRAGMA key = '{key}'; {config}")
        else:
            conn.execute(f"PRAGMA key = '{key}'")
        
        # Try to read the database
        try:
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            return True
        except sqlite3.DatabaseError:
            return False
        finally:
            conn.close()
    except Exception:
        return False

def main():
    # Generate keys based on version information
    keys = generate_version_based_keys()
    print(f"Generated {len(keys)} version-based keys")
    
    # Save keys for reference
    with open('version_derived_keys.txt', 'w') as f:
        for key in keys:
            f.write(f"{key}\n")
    
    # Test configurations
    configs = [
        None,  # Default SQLCipher config
        "PRAGMA cipher_compatibility = 3",
        "PRAGMA cipher_compatibility = 4",
        "PRAGMA cipher_page_size = 1024",
        "PRAGMA cipher_page_size = 4096",
        "PRAGMA kdf_iter = 4000",
        "PRAGMA kdf_iter = 64000",
    ]
    
    # Test each key with each configuration
    results = []
    db_path = str(Path.home() / "attachments" / "msg_2.db")
    
    print("Testing keys against msg_2.db...")
    for key in keys:
        for config in configs:
            if test_sqlcipher_key(db_path, key, config):
                result = {
                    'key': key,
                    'config': config if config else 'default',
                    'success': True
                }
                results.append(result)
                print(f"Found working key: {key}")
                print(f"With config: {config if config else 'default'}")
                
                # Save working configuration immediately
                with open('working_version_key.txt', 'w') as f:
                    f.write(f"Key: {key}\n")
                    f.write(f"Config: {config if config else 'default'}\n")
                
                return  # Exit after finding first working key
    
    # Save test results
    with open('version_key_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    if not results:
        print("No working keys found")

if __name__ == '__main__':
    main()
