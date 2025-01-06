import sqlite3
import logging
import binascii
import hashlib
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_potential_key(data):
    """Check if data matches characteristics of encryption keys."""
    if not data:
        return False
    
    # Common key lengths (16, 24, 32, 64 bytes)
    key_lengths = {16, 24, 32, 64}
    
    try:
        # Try to decode as hex
        if isinstance(data, str):
            try:
                decoded = binascii.unhexlify(data.strip())
                if len(decoded) in key_lengths:
                    return True
            except:
                pass
        
        # Check raw bytes
        if isinstance(data, bytes):
            if len(data) in key_lengths:
                return True
            
            # Try to decode as hex string
            try:
                hex_str = data.decode('utf-8')
                decoded = binascii.unhexlify(hex_str.strip())
                if len(decoded) in key_lengths:
                    return True
            except:
                pass
    except Exception as e:
        logger.debug(f"Error checking potential key: {e}")
    
    return False

def analyze_keyvalue_db(db_path):
    """Analyze KeyValue.db for potential encryption keys."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table schema
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        logger.info("=== KeyValue.db Analysis ===")
        logger.info(f"Found {len(tables)} tables")
        
        # Analyze each table
        for table in tables:
            if table[0]:  # Skip tables without schema
                logger.info(f"\nAnalyzing table schema:\n{table[0]}")
                
                # Extract table name
                table_name = table[0].split()[2].strip('"')
                
                try:
                    # Get all columns
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()
                    
                    # Search through each column for potential keys
                    for column in columns:
                        col_name = column[1]
                        try:
                            cursor.execute(f"SELECT {col_name} FROM {table_name}")
                            rows = cursor.fetchall()
                            
                            for row in rows:
                                if row[0] and is_potential_key(row[0]):
                                    logger.info(f"\nPotential key found in {table_name}.{col_name}:")
                                    if isinstance(row[0], bytes):
                                        hex_value = binascii.hexlify(row[0]).decode()
                                    else:
                                        hex_value = row[0]
                                    logger.info(f"Hex: {hex_value}")
                                    logger.info(f"Length: {len(row[0])} bytes")
                                    
                                    # If it looks like a hex string, try to decode it
                                    try:
                                        decoded = binascii.unhexlify(hex_value)
                                        logger.info(f"Decoded length: {len(decoded)} bytes")
                                    except:
                                        pass
                                        
                        except sqlite3.OperationalError as e:
                            logger.debug(f"Error reading column {col_name}: {e}")
                            continue
                            
                except sqlite3.OperationalError as e:
                    logger.debug(f"Error analyzing table {table_name}: {e}")
                    continue
                    
    except sqlite3.DatabaseError as e:
        logger.error(f"Error opening database: {e}")
        logger.info("This might indicate the database is encrypted")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
        
    finally:
        try:
            conn.close()
        except:
            pass
            
    return True

def main():
    db_path = Path("/home/ubuntu/attachments/KeyValue.db")
    if not db_path.exists():
        logger.error(f"KeyValue.db not found at {db_path}")
        return
        
    logger.info(f"Analyzing {db_path}")
    if analyze_keyvalue_db(db_path):
        logger.info("Analysis complete")
    else:
        logger.info("Analysis failed - database might be encrypted")

if __name__ == "__main__":
    main()
