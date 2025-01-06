import logging
import sqlite3
from pathlib import Path
import signal
import sys
from contextlib import contextmanager
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TimeoutException(Exception):
    pass

@contextmanager
def timeout(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    
    # Register a signal handler
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Disable the alarm
        signal.alarm(0)

def try_decrypt_db(db_path, key, page_size=4096):
    """Attempts to decrypt database with better error handling"""
    try:
        # First try reading the file header safely
        with open(db_path, 'rb') as f:
            header = f.read(100)
            if len(header) < 16:
                logger.error(f"File {db_path} is too small to be a valid database")
                return False
        
        # Try connecting with sqlite3 first to check if it's encrypted
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master")
            logger.info(f"Database {db_path} is not encrypted!")
            conn.close()
            return False
        except sqlite3.DatabaseError:
            logger.info(f"Database {db_path} appears to be encrypted, trying key...")
        
        # Now try with sqlcipher
        with timeout(5):  # Timeout after 5 seconds
            from pysqlcipher3 import dbapi2 as sqlcipher
            conn = sqlcipher.connect(db_path)
            
            # Configure SQLCipher with careful error handling
            try:
                conn.execute(f"PRAGMA key = '{key}'")
            except Exception as e:
                logger.error(f"Error setting key: {e}")
                return False
                
            try:
                conn.execute(f"PRAGMA cipher_page_size = {page_size}")
            except Exception as e:
                logger.error(f"Error setting page size: {e}")
                return False
            
            # Test if we can read the database
            try:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                if tables:
                    logger.info(f"Successfully decrypted {db_path} with key: {key}")
                    logger.info(f"Tables found: {tables}")
                    
                    # Try to get more database info
                    try:
                        cursor = conn.execute("PRAGMA page_size")
                        actual_page_size = cursor.fetchone()[0]
                        logger.info(f"Actual page size: {actual_page_size}")
                        
                        cursor = conn.execute("PRAGMA cipher_version")
                        cipher_version = cursor.fetchone()[0]
                        logger.info(f"SQLCipher version: {cipher_version}")
                    except Exception as e:
                        logger.warning(f"Could not get additional database info: {e}")
                    
                    return True
            except Exception as e:
                if "not a database" in str(e) or "file is encrypted" in str(e):
                    return False
                logger.error(f"Error reading database: {e}")
                return False
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
                    
    except TimeoutException:
        logger.warning(f"Operation timed out for key: {key}")
        return False
    except ImportError as e:
        logger.error(f"SQLCipher import error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
    
    return False

def main():
    # Load key candidates
    try:
        with open('new_key_candidates.txt', 'r') as f:
            key_candidates = [line.strip() for line in f]
    except Exception as e:
        logger.error(f"Error loading key candidates: {e}")
        return
    
    databases = [
        Path('/home/ubuntu/attachments/KeyValue.db'),
        Path('/home/ubuntu/attachments/msg_2.db')
    ]
    
    # Use discovered page sizes
    configs = [
        {'page_size': 36165},  # From KeyValue.db analysis
        {'page_size': 3254},   # From msg_2.db analysis
        {'page_size': 4096},   # Standard size
        {'page_size': 1024},   # Alternative size
    ]
    
    for db in databases:
        if not db.exists():
            logger.error(f"Database file not found: {db}")
            continue
            
        logger.info(f"\nTesting database: {db}")
        for key in key_candidates:
            logger.info(f"\nTesting key: {key}")
            for config in configs:
                try:
                    if try_decrypt_db(str(db), key, **config):
                        return  # Success!
                except Exception as e:
                    logger.error(f"Error testing configuration {config}: {e}")
                    continue

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nDecryption testing interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
