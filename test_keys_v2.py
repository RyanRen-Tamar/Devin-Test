
import logging
import sqlite3
from pathlib import Path
from pysqlcipher3 import dbapi2 as sqlcipher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def try_decrypt_db(db_path, key, page_size=4096, kdf_iter=256000, salt_size=32):
    try:
        conn = sqlcipher.connect(db_path)
        
        # Configure SQLCipher parameters
        conn.execute(f"PRAGMA key = '{key}'")
        conn.execute(f"PRAGMA cipher_page_size = {page_size}")
        conn.execute(f"PRAGMA kdf_iter = {kdf_iter}")
        
        # Test if we can read the database
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        if tables:
            logger.info(f"Successfully decrypted {db_path} with key: {key}")
            logger.info(f"Tables found: {tables}")
            return True
            
        conn.close()
        return False
        
    except Exception as e:
        if "not a database" in str(e) or "file is encrypted" in str(e):
            return False
        logger.error(f"Error testing key {key}: {e}")
        return False

def main():
    # Load new key candidates
    with open('new_key_candidates.txt', 'r') as f:
        key_candidates = [line.strip() for line in f]
    
    databases = [
        Path('/home/ubuntu/attachments/KeyValue.db'),
        Path('/home/ubuntu/attachments/msg_2.db')
    ]
    
    configs = [
        {'page_size': 4096, 'kdf_iter': 256000},
        {'page_size': 1024, 'kdf_iter': 256000},
        {'page_size': 36165, 'kdf_iter': 256000},  # From KeyValue.db analysis
        {'page_size': 3254, 'kdf_iter': 256000},   # From msg_2.db analysis
    ]
    
    for db in databases:
        logger.info(f"\nTesting database: {db}")
        for key in key_candidates:
            logger.info(f"\nTesting key: {key}")
            for config in configs:
                if try_decrypt_db(str(db), key, **config):
                    return  # Success!

if __name__ == '__main__':
    main()
