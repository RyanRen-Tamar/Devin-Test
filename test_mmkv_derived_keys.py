import sqlite3
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import binascii

def extract_key_fragments():
    """Extract potential key fragments from MMKV analysis"""
    with open('mmkv_encryption_analysis.json', 'r') as f:
        data = json.load(f)
    
    key_fragments = set()
    for marker in data['encryption_markers']:
        if marker['marker'] == 'KEY':
            # Extract the hex part after KEY
            context = marker['context']
            # Look for patterns like "05fbe0d7bb06" in the context
            for i in range(0, len(context)-11, 2):
                fragment = context[i:i+12]
                if all(c in '0123456789abcdef' for c in fragment.lower()):
                    key_fragments.add(fragment.lower())
    
    return list(key_fragments)

def generate_test_keys(fragments):
    """Generate test keys using fragments from MMKV"""
    keys = set()
    
    # Add raw fragments
    keys.update(fragments)
    
    # Add MD5 hashes of fragments
    for fragment in fragments:
        md5_hash = hashlib.md5(fragment.encode()).hexdigest()
        keys.add(md5_hash)
    
    # Add combinations of fragments
    for i in range(len(fragments)):
        for j in range(i+1, len(fragments)):
            combined = fragments[i] + fragments[j]
            keys.add(combined)
            keys.add(hashlib.md5(combined.encode()).hexdigest())
    
    # Add known patterns
    status_key = "STATUS_LAST_REPORT_KEY"
    for fragment in fragments:
        keys.add(hashlib.md5((status_key + fragment).encode()).hexdigest())
        keys.add(hashlib.md5((fragment + status_key).encode()).hexdigest())
    
    return list(keys)

def is_valid_key(key):
    """Pre-filter obviously invalid keys"""
    if len(key) < 16:  # Too short to be valid
        return False
    try:
        # Check if it's valid hex
        if all(c in '0123456789abcdefABCDEF' for c in key):
            return len(key) in [32, 64, 128]  # Common key lengths
        # Check if it contains common markers
        return any(marker in key for marker in ['MMKV', 'KEY', 'AES', 'HMAC'])
    except:
        return False

def test_key_batch(args):
    """Test a batch of keys with optimized logging"""
    keys, db_path = args
    db_name = os.path.basename(db_path)
    results = []
    
    # Detect database type once
    db_type = 'unknown'
    try:
        with open(db_path, 'rb') as f:
            data = f.read(4096)
            if b'aes' in data[56:64] or b'CBC' in data[64:72]:
                db_type = 'cache'
            elif data[:16].hex() == '53f5c7c56b6c98c9d921441f6402bb38':
                db_type = 'keyvalue'
            elif data[:16].hex() == '8541671c1a2395cd690ae0b1781119b3':
                db_type = 'message'
    except Exception as e:
        print(f"Error reading database header: {str(e)}")
        return results
    
    # Get database-specific configurations
    configs = []
    if db_type == 'cache':
        configs = [
            [f"PRAGMA key = '{{key}}';", "PRAGMA cipher_page_size = 4096;", "PRAGMA kdf_iter = 64000;"],
            [f"PRAGMA key = '{{key}}';", "PRAGMA cipher_page_size = 4096;", "PRAGMA kdf_iter = 4000;"]
        ]
    elif db_type == 'keyvalue':
        configs = [
            [f"PRAGMA key = '{{key}}';", "PRAGMA cipher_page_size = 36165;", "PRAGMA kdf_iter = 64000;"],
            [f"PRAGMA key = '{{key}}';", "PRAGMA cipher_page_size = 36165;", "PRAGMA kdf_iter = 4000;"]
        ]
    elif db_type == 'message':
        configs = [
            [f"PRAGMA key = '{{key}}';", "PRAGMA cipher_page_size = 3254;", "PRAGMA kdf_iter = 64000;"],
            [f"PRAGMA key = '{{key}}';", "PRAGMA cipher_page_size = 3254;", "PRAGMA kdf_iter = 4000;"]
        ]
    
    # Add fallback configs
    configs.extend([
        [f"PRAGMA key = '{{key}}';"],
        [f"PRAGMA key = '{{key}}';", "PRAGMA cipher_compatibility = 3;"],
        [f"PRAGMA key = '{{key}}';", "PRAGMA cipher_compatibility = 4;"]
    ])
    
    total_keys = len(keys)
    for idx, key in enumerate(keys, 1):
        if idx % 100 == 0:  # Progress update every 100 keys
            print(f"\rTesting keys on {db_name}: {idx}/{total_keys} ({idx/total_keys*100:.1f}%)", end='', flush=True)
        
        if not is_valid_key(key):
            continue
            
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Try both raw key and hex encoding
            for test_key in [key, binascii.hexlify(key.encode()).decode()]:
                for config in configs:
                    try:
                        # Apply configuration
                        for pragma in config:
                            cursor.execute(pragma.format(key=test_key))
                        
                        # Handle WAL mode
                        if os.path.exists(db_path + '-wal'):
                            cursor.execute('PRAGMA journal_mode=WAL;')
                        
                        # Test database access
                        cursor.execute("SELECT count(*) FROM sqlite_master")
                        count = cursor.fetchone()[0]
                        
                        print(f"\nDecryption successful!")
                        print(f"Database: {db_name}")
                        print(f"Key: {test_key[:32]}...")
                        print(f"Config: {config}")
                        print(f"Tables found: {count}")
                        
                        results.append({
                            'success': True,
                            'key': test_key,
                            'config': config,
                            'db_type': db_type,
                            'error': None
                        })
                        return results  # Early return on success
                    except sqlite3.DatabaseError:
                        continue
                    except Exception as e:
                        print(f"\nUnexpected error with key {test_key[:16]}: {str(e)}")
                        continue
        except Exception as e:
            print(f"\nError connecting to database: {str(e)}")
            continue
        finally:
            try:
                conn.close()
            except:
                pass
    
    print(f"\rCompleted testing {total_keys} keys on {db_name}")
    return results

def main():
    # Extract key fragments from MMKV analysis
    fragments = extract_key_fragments()
    print(f"Found {len(fragments)} key fragments")
    
    # Generate test keys
    test_keys = generate_test_keys(fragments)
    print(f"Generated {len(test_keys)} test keys")
    
    # Pre-filter obviously invalid keys
    valid_keys = [k for k in test_keys if is_valid_key(k)]
    print(f"Filtered down to {len(valid_keys)} potentially valid keys")
    
    # Save valid keys for reference
    with open('mmkv_derived_keys.txt', 'w') as f:
        for key in valid_keys:
            f.write(f"{key}\n")
    
    # Test against all database types
    db_paths = [
        os.path.expanduser('~/attachments/Cache.db'),
        os.path.expanduser('~/attachments/KeyValue.db'),
        os.path.expanduser('~/attachments/msg_2.db')
    ]
    
    # Process keys in batches
    BATCH_SIZE = 1000
    all_results = {}
    
    for db_path in db_paths:
        if not os.path.exists(db_path):
            print(f"Database not found: {db_path}")
            continue
        
        db_name = os.path.basename(db_path)
        print(f"\nProcessing {db_name}...")
        
        # Split keys into batches
        key_batches = [valid_keys[i:i + BATCH_SIZE] for i in range(0, len(valid_keys), BATCH_SIZE)]
        batch_results = []
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for batch in key_batches:
                futures.append(executor.submit(test_key_batch, (batch, db_path)))
            
            # Process results as they complete
            for future in as_completed(futures):
                try:
                    results = future.result()
                    batch_results.extend(results)
                    
                    # If we found a working key, stop testing
                    if any(r['success'] for r in results):
                        for f in futures:
                            f.cancel()
                        break
                except Exception as e:
                    print(f"\nError processing batch: {str(e)}")
        
        all_results[db_name] = batch_results
        
        # Check for successful keys
        successful = [r for r in batch_results if r['success']]
        if successful:
            print(f"\nFound {len(successful)} working keys for {db_name}!")
            for result in successful:
                print(f"Working key: {result['key'][:32]}...")
                print(f"Config: {result['config']}")
                print(f"Database type: {result['db_type']}")
        else:
            print(f"\nNo working keys found for {db_name}")
    
    # Save all results
    with open('mmkv_key_test_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)

if __name__ == '__main__':
    main()
