import sqlite3
import binascii
import subprocess
import json
import os
import hashlib
import base64
import time
import signal
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

class SQLCipherTester:
    """Test SQLCipher decryption with different versions and configurations."""
    
    VERSIONS = ['3', '4']  # SQLCipher versions to test
    KEY_DERIVATION = ['PBKDF2_HMAC_SHA1', 'PBKDF2_HMAC_SHA256', 'PBKDF2_HMAC_SHA512']
    ITERATIONS = [4000, 64000, 256000]  # Common iteration counts
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.results = []
        
        # Load known patterns from analysis
        self.known_patterns = {
            'header_prefix': '0064426d5374',  # From backup file
            'shared_bytes': '8541671c',       # Common between files
            'mmkv_pattern': '05fbe0d7bb06',   # Recurring pattern in MMKV
            'mmkv_id': 'e79382b1a59f5ac47e77ed537a6b9352',  # Potential key/id
            'status_key': '5455535f4c4153545f5245504f52545f4b4559',  # STATUS_LAST_REPORT_KEY
            'header_pattern': 'e81b00008a041d535449434b595f534541',  # Header pattern
            'keyvalue_magic': '53f5c7c56b6c98c9d921441f6402bb38'  # KeyValue.db magic bytes
        }
    
    def generate_test_configs(self) -> List[Dict]:
        """Generate different SQLCipher configurations to test."""
        configs = []
        
        # Custom page sizes including KeyValue.db size
        page_sizes = [4096, 8192, 16384, 36165]  # Added KeyValue.db page size
        
        # Base configuration patterns
        for version in self.VERSIONS:
            for kdf in self.KEY_DERIVATION:
                for iterations in self.ITERATIONS:
                    for page_size in page_sizes:
                        config = {
                            'version': version,
                            'kdf': kdf,
                            'iterations': iterations,
                            'page_size': page_size,
                        }
                        configs.append(config)
        
        # Add variations based on header analysis
        header_based_config = {
            'version': '4',  # Most likely version based on header
            'kdf': 'PBKDF2_HMAC_SHA256',  # Modern default
            'iterations': 256000,
            'page_size': 4096,
        }
        configs.append(header_based_config)
        
        return configs
    
    def try_decrypt(self, config: Dict, key: str, timeout: int = 5) -> Optional[str]:
        """Attempt to decrypt the database with given config and key."""
        def timeout_handler(signum, frame):
            raise TimeoutError("Decryption attempt timed out")

        temp_db = None
        conn = None
        try:
            # Set timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)
            
            # Create temporary copy of database
            temp_db = f"{self.db_path}.temp_{int(time.time())}"
            subprocess.run(['cp', self.db_path, temp_db], check=True)
            
            # Connect with SQLCipher
            conn = sqlite3.connect(temp_db, timeout=timeout)
            c = conn.cursor()
            
            # Configure SQLCipher
            c.execute(f"PRAGMA key = '{key}'")
            c.execute(f"PRAGMA cipher_compatibility = {config['version']}")
            c.execute(f"PRAGMA kdf_algorithm = {config['kdf']}")
            c.execute(f"PRAGMA cipher_page_size = {config['page_size']}")
            c.execute(f"PRAGMA kdf_iter = {config['iterations']}")
            
            # Test if decryption worked by reading sqlite_master
            try:
                c.execute("SELECT name FROM sqlite_master")
                tables = c.fetchall()
                if tables:
                    return f"Success! Found tables: {tables}"
            except sqlite3.DatabaseError as e:
                if "not an encrypted database" in str(e):
                    return "Database not encrypted"
                return None
            
        except TimeoutError:
            return "Timeout"
        except Exception as e:
            return f"Error: {str(e)}"
        finally:
            signal.alarm(0)  # Disable the alarm
            if conn:
                try:
                    conn.close()
                except:
                    pass
            if temp_db and os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except:
                    pass
        
        return None
    
    def transform_key(self, key: str) -> List[Tuple[str, str]]:
        """Apply common transformations to a key."""
        transformed = []
        try:
            # Original key
            transformed.append((key, 'original'))
            
            # Base64 variations
            try:
                # Try base64 encoding the hex string
                hex_bytes = bytes.fromhex(key)
                b64 = base64.b64encode(hex_bytes).decode('utf-8')
                transformed.append((b64, 'base64_hex'))
            except:
                pass
                
            # Try base64 encoding the string directly
            b64_str = base64.b64encode(key.encode()).decode('utf-8')
            transformed.append((b64_str, 'base64_str'))
            
            # Hash variations
            key_bytes = key.encode()
            transformed.extend([
                (hashlib.md5(key_bytes).hexdigest(), 'md5'),
                (hashlib.sha1(key_bytes).hexdigest(), 'sha1'),
                (hashlib.sha256(key_bytes).hexdigest(), 'sha256'),
                (hashlib.sha512(key_bytes).hexdigest()[:64], 'sha512')  # Truncate to 256 bits
            ])
            
            # Try interpreting as hex and using raw bytes
            try:
                raw_bytes = bytes.fromhex(key)
                transformed.append((raw_bytes.hex(), 'raw_hex'))
            except:
                pass
                
        except Exception as e:
            print(f"Error transforming key {key}: {str(e)}")
            
        return transformed

    def test_with_pattern_keys(self) -> List[Dict]:
        """Test decryption using keys derived from known patterns."""
        results = []
        configs = self.generate_test_configs()
        start_time = time.time()
        total_tests = 0
        completed_tests = 0
        
        # Generate keys from patterns with priority
        pattern_keys = []
        high_priority_patterns = [
            'mmkv_id',           # Most promising identifier
            'mmkv_pattern',      # Recurring pattern
            'header_pattern',    # Header-specific pattern
            'status_key'         # Status-related key
        ]
        
        # High priority patterns first
        for pattern_name in high_priority_patterns:
            if pattern_name in self.known_patterns:
                key = self.known_patterns[pattern_name]
                pattern_keys.append(key)
                pattern_keys.append(key[:32] if len(key) > 32 else key)  # 32-byte/256-bit keys
                pattern_keys.append(key[:16] if len(key) > 16 else key)  # 16-byte/128-bit keys
                
                # Try combining with KeyValue magic bytes
                keyvalue_magic = self.known_patterns['keyvalue_magic']
                pattern_keys.append(key + keyvalue_magic)  # Concatenate with magic bytes
                pattern_keys.append(keyvalue_magic + key)  # Magic bytes as prefix
        
        # Other patterns
        for name, key in self.known_patterns.items():
            if name not in high_priority_patterns:
                pattern_keys.append(key)
                pattern_keys.append(key[:32] if len(key) > 32 else key)
                pattern_keys.append(key[:16] if len(key) > 16 else key)
        
        # Combinations of patterns
        pattern_keys.extend([
            self.known_patterns['header_prefix'] + self.known_patterns['shared_bytes'],
            self.known_patterns['mmkv_pattern'] + self.known_patterns['mmkv_id'],
            self.known_patterns['mmkv_id'] + self.known_patterns['mmkv_pattern'],
            self.known_patterns['header_prefix'] + self.known_patterns['mmkv_pattern'],
        ])
        
        # Add variations with common prefixes
        base_keys = pattern_keys.copy()
        for key in base_keys:
            pattern_keys.extend([
                f"wx_{key}",
                f"key_{key}",
                f"{key}_key",
                f"salt_{key}",
                f"{key}_salt"
            ])
        
        for config in configs:
            # Calculate total tests for progress tracking
            if total_tests == 0:
                for key in pattern_keys:
                    total_tests += len(self.transform_key(key))
                print(f"\nTotal configurations to test: {len(configs)}")
                print(f"Total key variations to test: {total_tests}")
                print(f"Total combinations to test: {len(configs) * total_tests}\n")
            
            # Test keys with progress tracking
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                
                for key in pattern_keys:
                    for transformed_key, transform_type in self.transform_key(key):
                        futures.append(
                            executor.submit(
                                self.try_decrypt,
                                config,
                                transformed_key
                            )
                        )
                
                for future in as_completed(futures):
                    completed_tests += 1
                    if completed_tests % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = completed_tests / elapsed
                        remaining = (total_tests - completed_tests) / rate if rate > 0 else 0
                        print(f"Progress: {completed_tests}/{total_tests} tests completed "
                              f"({completed_tests/total_tests*100:.1f}%) - "
                              f"Rate: {rate:.1f} tests/sec - "
                              f"ETA: {remaining/60:.1f} minutes")
                    
                    try:
                        decrypt_result = future.result()
                        result = {
                            'config': config,
                            'original_key': key,
                            'transformed_key': transformed_key,
                            'transform_type': transform_type,
                            'result': decrypt_result
                        }
                        if decrypt_result and "Success" in decrypt_result:
                            print(f"\nPossible success with config: {json.dumps(config, indent=2)}")
                            print(f"Original key: {key}")
                            print(f"Transformed key: {transformed_key} (type: {transform_type})")
                            print(f"Result: {decrypt_result}")
                        results.append(result)
                    except Exception as e:
                        print(f"Error processing result: {str(e)}")
        
        return results
    
    def save_results(self, results: List[Dict]):
        """Save test results to file."""
        with open('sqlcipher_test_results.json', 'w') as f:
            json.dump(results, f, indent=2)

def main():
    # Test both main database and backup
    dbs = [
        '/home/ubuntu/attachments/msg_2.db',
        '/home/ubuntu/attachments/msg_2.db-backup'
    ]
    
    for db_path in dbs:
        print(f"\nTesting database: {db_path}")
        tester = SQLCipherTester(db_path)
        results = tester.test_with_pattern_keys()
        tester.save_results(results)
        
        # Check if we found any successful decryption
        successes = [r for r in results if r['result'] and "Success" in r['result']]
        if successes:
            print("\nFound successful configurations!")
            for success in successes:
                print(f"\nConfig: {json.dumps(success['config'], indent=2)}")
                print(f"Key: {success['key']}")
                print(f"Result: {success['result']}")
        else:
            print("\nNo successful decryption found with current patterns")

if __name__ == '__main__':
    main()
