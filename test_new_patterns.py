import os
import sqlite3
import hashlib
from pathlib import Path
import binascii
import json

def derive_key_candidates(magic_string, header_data):
    """Generate key candidates from magic string and header data"""
    candidates = []
    
    # Direct use of magic string
    candidates.append(magic_string)
    
    # MD5 of magic string
    candidates.append(hashlib.md5(magic_string.encode()).hexdigest())
    
    # Combinations with CPDataRecordTime
    if 'CPDataRecordTime' in header_data:
        combined = magic_string + 'CPDataRecordTime'
        candidates.append(hashlib.md5(combined.encode()).hexdigest())
    
    return candidates

def test_sqlcipher_key(db_path, key, version=3):
    """Test a potential SQLCipher key"""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Try different SQLCipher configurations
        pragmas = [
            f"PRAGMA key = '{key}';",
            f"PRAGMA cipher_compatibility = {version};",
            "PRAGMA cipher_page_size = 4096;",
            "PRAGMA kdf_iter = 64000;",
            "PRAGMA cipher_hmac_algorithm = HMAC_SHA1;",
            "PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1;"
        ]
        
        for pragma in pragmas:
            try:
                c.execute(pragma)
            except sqlite3.DatabaseError:
                pass
        
        # Test if we can read the database
        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = c.fetchall()
        
        if tables:
            print(f"Success with key: {key}")
            print("Tables found:", tables)
            return True
            
    except Exception as e:
        pass
    finally:
        if 'conn' in locals():
            conn.close()
    
    return False

def main():
    # Load analysis results
    with open('full_analysis.json', 'r') as f:
        analysis = json.load(f)
    
    # Extract magic strings and patterns
    key_candidates = set()
    
    # From KeyValue.db
    if 'KeyValue.db' in analysis['databases']:
        kv_magic = analysis['databases']['KeyValue.db']['header_analysis']['magic_string']
        key_candidates.update(derive_key_candidates(kv_magic, str(analysis)))
    
    # From msg_2.db
    if 'msg_2.db' in analysis['databases']:
        msg_magic = analysis['databases']['msg_2.db']['header_analysis']['magic_string']
        key_candidates.update(derive_key_candidates(msg_magic, str(analysis)))
    
    # From MMKV patterns
    if 'mmkv_files' in analysis:
        for mmkv_file, data in analysis['mmkv_files'].items():
            if 'hex_header' in data:
                key_candidates.update(derive_key_candidates(data['hex_header'], str(analysis)))
    
    # Test keys against msg_2.db
    msg_db_path = os.path.expanduser('~/attachments/msg_2.db')
    
    print(f"Testing {len(key_candidates)} key candidates...")
    
    # Save key candidates for reference
    with open('new_key_candidates.txt', 'w') as f:
        for key in key_candidates:
            f.write(f"{key}\n")
    
    # Test each key
    for key in key_candidates:
        print(f"Testing key: {key}")
        for version in [3, 4]:
            if test_sqlcipher_key(msg_db_path, key, version):
                with open('working_key.txt', 'w') as f:
                    f.write(f"Working key: {key}\nSQLCipher version: {version}")
                return True
    
    print("No working keys found")
    return False

if __name__ == '__main__':
    main()
