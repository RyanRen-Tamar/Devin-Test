import os
import sys
import sqlite3
import argparse
import binascii
import pandas as pd
from pathlib import Path
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import HMAC, SHA1, MD5, SHA256
from Crypto.Util.Padding import unpad

try:
    from pysqlcipher3 import dbapi2 as sqlcipher
    SQLCIPHER_AVAILABLE = True
except ImportError:
    SQLCIPHER_AVAILABLE = False
    print("\nError: pysqlcipher3 not properly installed. For Mac users, please run:")
    print("\nbrew install sqlcipher")
    print("export LDFLAGS=\"-L/opt/homebrew/opt/sqlcipher/lib\"")
    print("export CPPFLAGS=\"-I/opt/homebrew/opt/sqlcipher/include\"")
    print("pip install --no-binary :all: pysqlcipher3\n")
    print("Note: Make sure to run these commands in your terminal and restart your Python environment.\n")

def parse_arguments():
    parser = argparse.ArgumentParser(description='WeChat Data Extractor')
    parser.add_argument('--path', type=str, help='Path to WeChat data directory')
    parser.add_argument('--db', type=str, help='Path to specific WeChat database file')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    parser.add_argument('--key', type=str, help='Encryption key for databases')
    parser.add_argument('--auto-key', action='store_true', help='Automatically extract encryption key')
    parser.add_argument('--output', type=str, default='wechat_export', help='Output directory')
    parser.add_argument('--format', type=str, choices=['csv', 'json'], default='csv', help='Export format (csv or json)')
    parser.add_argument('--verbose', action='store_true', help='Print detailed debugging information')
    return parser.parse_args()

def main():
    """Main execution function."""
    args = parse_arguments()
    
    # Initialize extractor with parsed arguments
    extractor = WeChatExtractor(
        args=args,
        test_mode=args.test,
        custom_path=args.path,
        output_dir=args.output,
        verbose=args.verbose
    )
    
    # Find WeChat version path
    print("\n=== WeChat Data Extractor ===\n")
    if not extractor.find_version_path():
        sys.exit(1)
        
    # Handle encryption key
    key = None
    if args.auto_key:
        print("\nAttempting to extract encryption key...")
        key = extractor.extract_key_from_keyvalue()
        if key:
            print(f"Found potential encryption key")
    elif args.key:
        key = args.key
    
    # Read server configuration
    print("\nReading server configuration...")
    server_id = extractor.read_server_id()
    if server_id:
        print("Server ID found")
    
    # List and process database files
    print("\nSearching for WeChat databases...")
    db_files = extractor.list_database_files()
    
    if not db_files:
        print("No database files found.")
    else:
        # Process message databases
        for db_file in db_files:
            print(f"\nAnalyzing database: {db_file}")
            data = extractor.extract_messages(db_file, key=key)
            
            if data:
                # Create output directory based on database name
                db_name = Path(db_file).stem
                output_dir = Path(args.output) / db_name
                
                print(f"Exporting data to {output_dir}...")
                if extractor.export_data(data, output_dir, args.format):
                    print(f"Data successfully exported to {output_dir}")
                else:
                    print("Failed to export data")
        
        # Process MessageTemp directory
        print("\nProcessing MessageTemp directory...")
        sessions = extractor.process_message_temp()
        if sessions:
            # Export session information
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            import json
            with open(output_dir / 'message_temp_sessions.json', 'w', encoding='utf-8') as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)
            print(f"Session information exported to {output_dir}/message_temp_sessions.json")
    
    print("\nUsage instructions:")
    print("1. For Mac users: python wechat_extractor.py --path '/Users/YOUR_USERNAME/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat'")
    print("2. For testing: python wechat_extractor.py --test")
    print("3. For encrypted databases: python wechat_extractor.py --key YOUR_KEY")
    print("4. To auto-extract key: python wechat_extractor.py --auto-key")
    print("4. Custom output directory: python wechat_extractor.py --output /path/to/output")
    print("5. Export format: python wechat_extractor.py --format [csv|json]")

class WeChatExtractor:
    def _log(self, message):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
            
    def __init__(self, args=None, test_mode=False, custom_path=None, output_dir='wechat_export', verbose=False):
        """
        Initialize the WeChat extractor.
        
        Args:
            args: Parsed command line arguments
            test_mode (bool): If True, use test data directory
            custom_path (str): Custom path to WeChat data directory (for Mac users)
            output_dir (str): Directory for exported data
            verbose (bool): Enable verbose logging
        """
        self.args = args
        self.verbose = verbose
        self.user = os.environ.get('USER')
        
        # Set up encryption key options
        self.key = args.key if args else None
        self.auto_key = args.auto_key if args else False
        
        if test_mode:
            self.base_path = Path('./test_data/WeChat').resolve()
            self._log(f"Using test data path: {self.base_path}")
        elif custom_path:
            self.base_path = Path(custom_path).expanduser().resolve()
            self._log(f"Using custom path: {self.base_path}")
        else:
            self.base_path = Path(f'/Users/{self.user}/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat').expanduser().resolve()
            self._log(f"Using default WeChat path: {self.base_path}")
            
        print(f"\nBase path: {self.base_path}")
        if not self.base_path.exists():
            print("Error: Base path does not exist! Please check your path input.")
        
        self.version_path = None
        self.backup_path = None
        self.test_mode = test_mode
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test environment if in test mode
        if test_mode:
            self._create_test_environment()
    
    def _create_test_environment(self):
        """Create a test environment with sample data structure."""
        try:
            # Create directory structure matching WeChat's format
            version_dir = Path('./test_data/WeChat/2.0b4.0.9')
            hash_dir = version_dir / 'e79382b1a59f5ac47e77ed537a6b9352'  # Example hash
            message_dir = hash_dir / 'Message'
            message_dir.mkdir(parents=True, exist_ok=True)
            
            # Create KeyValue directory for encryption key testing
            keyvalue_dir = version_dir / 'KeyValue'
            keyvalue_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a sample SQLite database in Message directory
            sample_db_path = message_dir / 'msg_0.db'
            if not sample_db_path.exists():
                conn = sqlite3.connect(str(sample_db_path))
                cursor = conn.cursor()
                
                # Create sample tables
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS message (
                        msgId INTEGER PRIMARY KEY,
                        type INTEGER,
                        content TEXT,
                        createTime INTEGER,
                        talker TEXT,
                        isSend INTEGER
                    )
                ''')
                
                # Insert sample data
                sample_data = [
                    (1, 1, "Hello!", 1645000000, "friend1", 1),
                    (2, 1, "Hi there!", 1645000060, "friend1", 0),
                    (3, 1, "How are you?", 1645000120, "friend2", 1),
                ]
                cursor.executemany(
                    'INSERT OR IGNORE INTO message (msgId, type, content, createTime, talker, isSend) VALUES (?, ?, ?, ?, ?, ?)',
                    sample_data
                )
                
                conn.commit()
                conn.close()
            
            # Copy the real KeyValue.db file from attachments if available
            keyvalue_db_path = keyvalue_dir / 'KeyValue.db'
            if not keyvalue_db_path.exists():
                import shutil, os
                attachment_path = Path(os.path.expanduser('~/attachments/KeyValue.db'))
                if attachment_path.exists():
                    try:
                        print(f"Using provided KeyValue.db file for testing from {attachment_path}")
                        shutil.copy2(str(attachment_path), str(keyvalue_db_path))
                        print(f"Successfully copied KeyValue.db to {keyvalue_db_path}")
                    except Exception as e:
                        print(f"Error copying KeyValue.db: {e}")
                        print("Falling back to sample database")
                else:
                    print("No KeyValue.db found in attachments, using sample database")
                    # Create a sample KeyValue database if no real one is available
                    conn = sqlite3.connect(str(keyvalue_db_path))
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS KeyValue (
                            key TEXT PRIMARY KEY,
                            value TEXT
                        )
                    ''')
                    # Insert a sample encryption key
                    cursor.execute(
                        'INSERT OR IGNORE INTO KeyValue (key, value) VALUES (?, ?)',
                        ('key_enc_key', '0123456789abcdef0123456789abcdef')  # 32-char test key
                    )
                    conn.commit()
                    conn.close()
                
            print("Test environment created successfully")
            return True
        except Exception as e:
            print(f"Error creating test environment: {e}")
            return False
            
    def find_version_path(self):
        """Find the directory containing WeChat database files."""
        try:
            # For flat directory structure, check if required files exist
            required_files = ['msg_2.db', 'KeyValue.db']
            for file in required_files:
                file_path = self.base_path / file
                if not file_path.exists():
                    self._log(f"Required file {file} not found in {self.base_path}")
                    return False
                    
            # Check for related files
            related_files = {
                'msg_2.db': ['msg_2.db-backup', 'msg_2.db-shm', 'msg_2.db-wal'],
                'KeyValue.db': []
            }
            
            for base_file, related in related_files.items():
                for rel_file in related:
                    file_path = self.base_path / rel_file
                    if file_path.exists():
                        self._log(f"Found related file: {rel_file}")
                        
            # Also check for MMKV files
            mmkv_files = list(self.base_path.glob("*.mmkv.default"))
            mmkv_files.extend(self.base_path.glob("*.CheckPointMMKV"))
            mmkv_files.extend(self.base_path.glob("*.ContactMMKV"))
            
            if mmkv_files:
                self._log(f"Found {len(mmkv_files)} MMKV files")
                for mmkv_file in mmkv_files:
                    crc_file = Path(str(mmkv_file) + '.crc')
                    if crc_file.exists():
                        self._log(f"Found CRC file for {mmkv_file.name}")
                        
            # Set paths for flat directory structure
            self.version_path = self.base_path
            self.backup_path = self.base_path
            
            print(f"Success: Found WeChat database files in: {self.base_path}")
            return True
            
        except Exception as e:
            print(f"Error finding database files: {e}")
            return False
        
    def read_server_id(self):
        """Read ServerId.dat from CGI directory."""
        try:
            if not self.version_path:
                print("Version path not set")
                return None
                
            server_id_path = self.version_path / 'CGI' / 'ServerId.dat'
            if server_id_path.exists():
                with open(server_id_path, 'rb') as f:
                    return f.read()
            else:
                print("ServerId.dat not found")
            return None
        except Exception as e:
            print(f"Error reading ServerId.dat: {e}")
            return None
            
    def _try_decrypt_database(self, db_path, key):
        """Try to decrypt a database with a given key."""
        try:
            if not SQLCIPHER_AVAILABLE:
                self._log("SQLCipher not available - skipping encryption check")
                return False

            # Check if this is a backup file with dBmSt header
            with open(db_path, 'rb') as f:
                header = f.read(6)
                if header == b'\x00dBmSt':
                    self._log("Found backup file with dBmSt header")
                    # Read version info (2 bytes)
                    version = f.read(2)
                    if version != b'\x01\x00':
                        self._log(f"Unsupported backup version: {version.hex()}")
                        return False
                    
                    # Read file size (4 bytes)
                    size_bytes = f.read(4)
                    file_size = int.from_bytes(size_bytes, byteorder='little')
                    
                    # Read the encrypted data
                    encrypted_data = f.read(file_size)
                    
                    try:
                        # Try to decrypt the data using the key
                        from Crypto.Cipher import AES
                        from Crypto.Protocol.KDF import PBKDF2
                        from Crypto.Hash import MD5, SHA1, SHA256
                        from Crypto.Util.Padding import unpad
                        import struct
                        
                        # Check for backup format header
                        BACKUP_HEADER = b'dBmSt'
                        if encrypted_data.startswith(BACKUP_HEADER):
                            self._log("Found backup format header")
                            # Parse header
                            version = encrypted_data[5]  # Version byte after 'dBmSt'
                            header_size = struct.unpack('<I', encrypted_data[6:10])[0]
                            data_size = struct.unpack('<I', encrypted_data[10:14])[0]
                            self._log(f"Backup header: version={version}, header_size={header_size}, data_size={data_size}")
                            
                            # Extract header data (before the encrypted content)
                            header_data = encrypted_data[14:header_size]
                            self._log(f"Header data size: {len(header_data)}")
                            
                            # Look for patterns in header
                            if len(header_data) >= 16:
                                self._log(f"Header start: {header_data[:16].hex()}")
                            
                            # Skip the complete header for decryption
                            encrypted_data = encrypted_data[header_size:]
                            self._log(f"Encrypted data size: {len(encrypted_data)}")
                            if len(encrypted_data) >= 16:
                                self._log(f"Data start: {encrypted_data[:16].hex()}")
                            try:
                                # Look for potential key material in header
                                potential_keys = []
                                for i in range(0, len(header_data) - 31):
                                    # Look for 32-byte sequences that could be keys
                                    key_candidate = header_data[i:i+32]
                                    if any(x > 32 and x < 127 for x in key_candidate):
                                        # Likely printable ASCII - could be a key
                                        potential_keys.append(key_candidate)
                                if potential_keys:
                                    self._log(f"Found {len(potential_keys)} potential keys in header")
                                    for pk in potential_keys:
                                        self._log(f"Trying header key: {pk.hex()}")
                            except Exception as e:
                                self._log(f"Error parsing header: {e}")
                        
                        # Common WeChat salts and key derivation methods
                        salts = [
                            b'WeChat_Backup_Key',
                            b'wechat_backup_key',
                            b'mm_backup_key',
                            b'wx_backup_key',
                            b'wx.dat',  # Common WeChat key file name
                            b'MM.dat'   # Another common WeChat key file name
                        ]
                        
                        # Different key derivation methods
                        def try_key_derivations(base_key):
                            keys = []
                            # Direct key
                            if isinstance(base_key, str):
                                if len(base_key) == 64:  # Hex string
                                    keys.append(bytes.fromhex(base_key))
                                else:
                                    keys.append(base_key.encode())
                            
                            # Try different hashing methods
                            key_bytes = base_key.encode() if isinstance(base_key, str) else base_key
                            keys.extend([
                                MD5.new(key_bytes).digest(),
                                SHA1.new(key_bytes).digest(),
                                SHA256.new(key_bytes).digest()
                            ])
                            
                            # Try PBKDF2 with parameters based on database analysis
                            for salt in salts:
                                keys.extend([
                                    # Standard 64000 iterations found in analysis
                                    PBKDF2(key_bytes, salt, dkLen=32, count=64000),
                                    # Backup with 4000 iterations
                                    PBKDF2(key_bytes, salt, dkLen=32, count=4000),
                                    # Try with discovered salts
                                    PBKDF2(key_bytes, bytes.fromhex('8541671c1a2395cd690ae0b1781119b3'), dkLen=32, count=64000),  # msg_2.db salt
                                    PBKDF2(key_bytes, bytes.fromhex('53f5c7c56b6c98c9d921441f6402bb38'), dkLen=32, count=64000),  # KeyValue.db magic
                                ])
                            return keys
                        
                        # Try different encryption modes and paddings
                        modes = [AES.MODE_CBC, AES.MODE_ECB]
                        paddings = [
                            lambda x: x,  # No padding
                            lambda x: unpad(x, AES.block_size, style='pkcs7'),
                            lambda x: x.rstrip(b'\0')  # Null padding
                        ]
                        
                        success = False
                        try:
                            derived_keys = try_key_derivations(key)
                            
                            for derived_key in derived_keys:
                                if success:
                                    break
                                    
                                self._log(f"Trying key derivation (length={len(derived_key)})")
                                
                                for mode in modes:
                                    if success:
                                        break
                                        
                                    mode_name = 'CBC' if mode == AES.MODE_CBC else 'ECB'
                                    self._log(f"Trying {mode_name} mode")
                                    
                                    try:
                                        if mode == AES.MODE_CBC:
                                            iv = encrypted_data[:16]
                                            cipher = AES.new(derived_key[:32], mode, iv)
                                            data = encrypted_data[16:]
                                        else:
                                            cipher = AES.new(derived_key[:32], mode)
                                            data = encrypted_data
                                        
                                        # Try to decrypt with different paddings
                                        decrypted_raw = cipher.decrypt(data)
                                        
                                        for padding_idx, padding_func in enumerate(paddings):
                                            if success:
                                                break
                                                
                                            try:
                                                self._log(f"Trying padding method {padding_idx}")
                                                decrypted = padding_func(decrypted_raw)
                                                
                                                # Check if it looks like SQLite
                                                if b'SQLite' in decrypted[:16]:
                                                    self._log(f"Successfully decrypted backup file with mode={mode_name}, key_len={len(derived_key)}, padding={padding_idx}")
                                                    
                                                    # Save decrypted data to temporary file
                                                    temp_path = f"{db_path}.decrypted"
                                                    with open(temp_path, 'wb') as temp:
                                                        temp.write(decrypted)
                                                    
                                                    # Try to open as SQLite
                                                    try:
                                                        conn = sqlite3.connect(temp_path)
                                                        cursor = conn.cursor()
                                                        cursor.execute('SELECT count(*) FROM sqlite_master')
                                                        cursor.fetchone()
                                                        conn.close()
                                                        os.remove(temp_path)
                                                        success = True
                                                        break
                                                    except Exception as e:
                                                        self._log(f"Failed to open decrypted file as SQLite: {e}")
                                                        os.remove(temp_path)
                                            except Exception as e:
                                                self._log(f"Padding {padding_idx} failed: {e}")
                                    except Exception as e:
                                        self._log(f"Decryption failed with {mode_name}: {e}")
                        except Exception as e:
                            self._log(f"Key derivation failed: {e}")
                            
                        if success:
                            return True
                            
                        self._log("Failed to decrypt backup file after trying all methods")
                        return False
                    except ImportError:
                        self._log("pycryptodome not available for backup decryption")
                        return False

            # Check for WAL mode files
            wal_path = f"{db_path}-wal"
            shm_path = f"{db_path}-shm"
            has_wal = os.path.exists(wal_path)
            has_shm = os.path.exists(shm_path)
            
            if has_wal:
                self._log(f"Found WAL file: {wal_path}")
            if has_shm:
                self._log(f"Found SHM file: {shm_path}")

            # Try different encryption configurations
            conn = sqlcipher.connect(str(db_path))
            cursor = conn.cursor()
            
            # Detect database type based on markers
            db_type = 'unknown'
            with open(db_path, 'rb') as f:
                data = f.read(4096)  # Read first page
                hex_data = binascii.hexlify(data).decode('utf-8')
                
                # Check for Cache.db patterns
                if ('616573' in hex_data[112:128] or '434243' in hex_data[128:144]):  # AES-CBC markers
                    db_type = 'cache'
                # Check for KeyValue.db magic bytes
                elif data[:16].hex() == '53f5c7c56b6c98c9d921441f6402bb38':
                    db_type = 'keyvalue'
                # Check for msg_2.db salt pattern
                elif data[:16].hex() == '8541671c1a2395cd690ae0b1781119b3':
                    db_type = 'message'
            
            self._log(f"Detected database type: {db_type}")
            
            # WeChat specific configurations to try based on database type
            configs = []
            
            # Base configurations
            base_configs = [
                [f'PRAGMA key = "{key}";'],
                [f'PRAGMA key = "{key}";', 'PRAGMA cipher_compatibility = 3;'],
            ]
            
            if db_type == 'cache':
                # Standard SQLite encryption with 4096-byte pages
                configs.extend([
                    [f'PRAGMA key = "{key}";', 'PRAGMA cipher_page_size = 4096;', 'PRAGMA kdf_iter = 64000;'],
                    [f'PRAGMA key = "{key}";', 'PRAGMA cipher_page_size = 4096;', 'PRAGMA kdf_iter = 64000;', 'PRAGMA cipher_compatibility = 4;'],
                ])
            elif db_type == 'keyvalue':
                # Custom page size from KeyValue.db analysis
                configs.extend([
                    [f'PRAGMA key = "{key}";', 'PRAGMA cipher_page_size = 36165;', 'PRAGMA kdf_iter = 64000;'],
                    [f'PRAGMA key = "{key}";', 'PRAGMA cipher_page_size = 36165;', 'PRAGMA kdf_iter = 4000;'],
                ])
            elif db_type == 'message':
                # Custom page size from msg_2.db analysis
                configs.extend([
                    [f'PRAGMA key = "{key}";', 'PRAGMA cipher_page_size = 3254;', 'PRAGMA kdf_iter = 64000;'],
                    [f'PRAGMA key = "{key}";', 'PRAGMA cipher_page_size = 3254;', 'PRAGMA kdf_iter = 4000;'],
                ])
            
            # Add base configs as fallback
            configs.extend(base_configs)
            
            for config in configs:
                try:
                    for pragma in config:
                        cursor.execute(pragma)
                    
                    if has_wal:
                        cursor.execute('PRAGMA journal_mode=WAL;')
                    
                    # Test if we can read the database
                    cursor.execute('SELECT count(*) FROM sqlite_master;')
                    cursor.fetchone()
                    self._log(f"Successfully decrypted with config: {config}")
                    return True
                except Exception as e:
                    self._log(f"Failed with config {config}: {e}")
                    continue
            
            conn.close()
            return False
        except Exception as e:
            self._log(f"Key validation failed: {e}")
            return False
            
    def extract_key_from_cache(self):
        """Extract encryption key from Cache.db by analyzing proto_props column."""
        try:
            print("\nAnalyzing Cache.db for encryption keys...")
            
            # First try the provided Cache.db in attachments
            attachment_path = Path(os.path.expanduser('~/attachments/Cache.db'))
            if attachment_path.exists():
                print(f"Found Cache.db in attachments: {attachment_path}")
                with open(attachment_path, 'rb') as f:
                    data = f.read()
                    
                # Look for AES-CBC markers
                aes_positions = []
                hex_data = binascii.hexlify(data).decode('utf-8')
                pos = 0
                while True:
                    pos = hex_data.find('616573', pos)  # 'aes' in hex
                    if pos == -1:
                        break
                    aes_positions.append(pos // 2)
                    pos += 6
                
                # Look for potential keys near AES markers
                potential_keys = []
                for pos in aes_positions:
                    # Check 32 bytes before and after the marker
                    window = data[max(0, pos-32):pos+32]
                    for i in range(len(window)-31):
                        key_candidate = window[i:i+32]
                        if all(32 <= b <= 126 for b in key_candidate):  # Printable ASCII
                            potential_keys.append(key_candidate)
                
                if potential_keys:
                    print(f"Found {len(potential_keys)} potential keys in Cache.db")
                    return potential_keys[0]  # Return first candidate
            
            # If no attachment, look in version path
            if not self.version_path:
                print("Error: Version path not set")
                return None
                
            cache_path = self.version_path / 'Cache.db'
            if not cache_path.exists():
                print(f"Error: Cache.db not found at {cache_path}")
                return None
                
            print(f"Found Cache.db in version path: {cache_path}")
            with open(cache_path, 'rb') as f:
                data = f.read()
                
            # Look for AES-CBC markers
            aes_positions = []
            hex_data = binascii.hexlify(data).decode('utf-8')
            pos = 0
            while True:
                pos = hex_data.find('616573', pos)  # 'aes' in hex
                if pos == -1:
                    break
                aes_positions.append(pos // 2)
                pos += 6
            
            # Look for potential keys near AES markers
            potential_keys = []
            for pos in aes_positions:
                # Check 32 bytes before and after the marker
                window = data[max(0, pos-32):pos+32]
                for i in range(len(window)-31):
                    key_candidate = window[i:i+32]
                    if all(32 <= b <= 126 for b in key_candidate):  # Printable ASCII
                        potential_keys.append(key_candidate)
            
            if potential_keys:
                print(f"Found {len(potential_keys)} potential keys in Cache.db")
                return potential_keys[0]  # Return first candidate
                
            return None
            
        except Exception as e:
            print(f"Error extracting key from Cache.db: {e}")
            return None

    def extract_key_from_keyvalue(self):
        """Extract encryption key from KeyValue.db."""
        try:
            print("\nAnalyzing KeyValue database for encryption keys...")
            
            # First try the provided KeyValue.db in attachments
            attachment_path = Path(os.path.expanduser('~/attachments/KeyValue.db'))
            if attachment_path.exists():
                print(f"Found KeyValue.db in attachments: {attachment_path}")
                return self._analyze_keyvalue_db(attachment_path)
            
            # If no attachment, look in version path
            if not self.version_path:
                print("Error: Version path not set")
                return None
                
            keyvalue_base = self.version_path / 'KeyValue'
            if not keyvalue_base.exists():
                print(f"Error: KeyValue directory not found at {keyvalue_base}")
                return None
                
            # Search for hash directories
            hash_dirs = [d for d in keyvalue_base.iterdir() if d.is_dir()]
            if not hash_dirs:
                print("No hash directories found in KeyValue directory")
                return None
                
            # Search each hash directory for KeyValue.db
            for hash_dir in hash_dirs:
                keyvalue_path = hash_dir / 'KeyValue.db'
                if not keyvalue_path.exists():
                    continue
                    
                print(f"Found KeyValue.db in hash directory: {hash_dir.name}")
                return self._analyze_keyvalue_db(keyvalue_path)
                
            return None
            
        except Exception as e:
            print(f"Error extracting key: {e}")
            return None
            
    def _analyze_keyvalue_db(self, db_path):
        """Analyze KeyValue.db and MMKV files for encryption keys."""
        try:
            # Check for WAL and SHM files
            wal_exists = (db_path.parent / f"{db_path.name}-wal").exists()
            shm_exists = (db_path.parent / f"{db_path.name}-shm").exists()
            if wal_exists:
                self._log("Found WAL file (write-ahead log)")
            if shm_exists:
                self._log("Found SHM file (shared memory)")
            
            # First try to read the file header
            with open(db_path, 'rb') as f:
                header = f.read(16)  # Read first 16 bytes
                if header.startswith(b'SQLite'):
                    print("Found standard SQLite database")
                    key = self._extract_from_sqlite(db_path)
                    if key:
                        return key
                else:
                    print("Found potentially encrypted database")
                    key = self._extract_from_encrypted(db_path)
                    if key:
                        return key
            
            # If no key found in KeyValue.db, check MMKV files
            print("\nChecking MMKV files for encryption keys...")
            mmkv_files = []
            mmkv_patterns = ['*.mmkv.default', '*.CheckPointMMKV', '*.ContactMMKV']
            
            for pattern in mmkv_patterns:
                mmkv_files.extend(db_path.parent.glob(pattern))
            
            for mmkv_file in mmkv_files:
                try:
                    # Check for CRC file
                    crc_file = Path(str(mmkv_file) + '.crc')
                    if crc_file.exists():
                        self._log(f"Found CRC file for {mmkv_file.name}")
                        
                        # Read MMKV file
                        with open(mmkv_file, 'rb') as f:
                            mmkv_data = f.read()
                            
                        # Look for potential key patterns in MMKV data
                        key_patterns = [
                            b'mm_key',
                            b'mm_enc',
                            b'key_enc',
                            b'encrypt',
                            b'auth',
                            b'token',
                            b'session'
                        ]
                        
                        for pattern in key_patterns:
                            pos = mmkv_data.find(pattern)
                            if pos >= 0:
                                # Extract potential key (32 bytes after pattern)
                                potential_key = mmkv_data[pos:pos+64]
                                # Try to validate the key
                                if self._validate_encryption_key(potential_key.hex()):
                                    print(f"Found valid encryption key in {mmkv_file.name}")
                                    return potential_key.hex()
                                
                except Exception as e:
                    self._log(f"Error processing MMKV file {mmkv_file.name}: {e}")
                    continue
            
            return None
                    
        except Exception as e:
            print(f"Error analyzing KeyValue.db: {e}")
            return None
            
    def _extract_from_sqlite(self, db_path):
        """Extract key from unencrypted SQLite database."""
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Known key patterns in WeChat databases
            key_patterns = [
                'mm_key%',
                'mm_enc%',
                'key_enc%',
                'encrypt%',
                'auth%',
                'token%',
                'session%'
            ]
            
            potential_keys = []
            
            # Search for keys in KeyValue table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                if table_name.lower() == 'keyvalue':
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()
                    key_col = None
                    val_col = None
                    
                    # Find key and value column names
                    for col in columns:
                        if col[1].lower() in ['key', 'name', 'id']:
                            key_col = col[1]
                        elif col[1].lower() in ['value', 'val', 'data']:
                            val_col = col[1]
                    
                    if key_col and val_col:
                        # Search for potential keys
                        for pattern in key_patterns:
                            cursor.execute(f"SELECT {key_col}, {val_col} FROM {table_name} WHERE {key_col} LIKE ?", (pattern,))
                            rows = cursor.fetchall()
                            for row in rows:
                                potential_keys.append({
                                    'key_name': row[0],
                                    'value': row[1],
                                    'table': table_name
                                })
            
            conn.close()
            
            if potential_keys:
                print(f"\nFound {len(potential_keys)} potential encryption keys:")
                for idx, key in enumerate(potential_keys, 1):
                    print(f"{idx}. {key['key_name']} in {key['table']}")
                    # Try to use each key
                    if self._validate_encryption_key(key['value']):
                        print(f"Found valid encryption key: {key['key_name']}")
                        return key['value']
            
            return None
            
        except Exception as e:
            print(f"Error extracting from SQLite: {e}")
            return None
            
    def _extract_from_encrypted(self, db_path):
        """Extract key from encrypted database."""
        try:
            if not SQLCIPHER_AVAILABLE:
                print("SQLCipher not available for encrypted database")
                return None
                
            # WeChat-specific encryption configurations
            configs = [
                {'key': 'mm_key', 'compat': 3, 'page_size': 4096, 'kdf_iter': 64000},
                {'key': 'mm_key', 'compat': 4, 'page_size': 1024, 'kdf_iter': 4000},
                {'key': 'mm_enc_key', 'compat': 3, 'page_size': 4096, 'kdf_iter': 64000},
                {'key': 'key_enc_key', 'compat': 3, 'page_size': 4096, 'kdf_iter': 64000}
            ]
            
            for config in configs:
                try:
                    conn = sqlcipher.connect(str(db_path))
                    cursor = conn.cursor()
                    
                    # Apply configuration
                    cursor.execute(f"PRAGMA key = '{config['key']}'")
                    cursor.execute(f"PRAGMA cipher_compatibility = {config['compat']}")
                    cursor.execute(f"PRAGMA cipher_page_size = {config['page_size']}")
                    cursor.execute(f"PRAGMA kdf_iter = {config['kdf_iter']}")
                    
                    # Test if we can read the database
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    if cursor.fetchone():
                        print(f"\nSuccessfully decrypted with config:")
                        print(f"Key: {config['key']}")
                        print(f"Compatibility: {config['compat']}")
                        print(f"Page Size: {config['page_size']}")
                        print(f"KDF Iterations: {config['kdf_iter']}")
                        return config['key']
                        
                except Exception as e:
                    print(f"Failed config {config['key']}: {str(e)}")
                    continue
                    
            return None
            
        except Exception as e:
            print(f"Error extracting from encrypted database: {e}")
            return None
            
    def _validate_encryption_key(self, key):
        """Validate if a key can decrypt any of the message databases."""
        try:
            if not self.backup_path:
                return False
                
            # Try the key on msg_*.db files
            for db_file in self.backup_path.glob("msg_*.db"):
                if self._try_decrypt_database(db_file, key):
                    return True
                    
            # Also try MMKV files if available
            mmkv_files = list(Path('~/attachments').expanduser().glob('*.mmkv.default'))
            mmkv_files.extend(Path('~/attachments').expanduser().glob('*.CheckPointMMKV'))
            mmkv_files.extend(Path('~/attachments').expanduser().glob('*.ContactMMKV'))
            
            for mmkv_file in mmkv_files:
                # Check if there's a corresponding CRC file
                crc_file = Path(str(mmkv_file) + '.crc')
                if crc_file.exists():
                    try:
                        # Read CRC file (4 bytes)
                        with open(crc_file, 'rb') as f:
                            stored_crc = int.from_bytes(f.read(4), byteorder='little')
                            
                        # Read MMKV file
                        with open(mmkv_file, 'rb') as f:
                            data = f.read()
                            
                        # Calculate CRC32
                        import zlib
                        calculated_crc = zlib.crc32(data) & 0xFFFFFFFF
                        
                        # Verify CRC matches
                        if calculated_crc == stored_crc:
                            self._log(f"CRC check passed for {mmkv_file.name}")
                            
                            # Try to decrypt the file
                            try:
                                from Crypto.Cipher import AES
                                from Crypto.Protocol.KDF import PBKDF2
                                
                                # Generate key using PBKDF2
                                salt = b'WeChat_MMKV_Key'
                                derived_key = PBKDF2(key.encode(), salt, dkLen=32, count=10000)
                                
                                # Try different modes
                                for mode in [AES.MODE_CBC, AES.MODE_ECB]:
                                    try:
                                        if mode == AES.MODE_CBC:
                                            if len(data) < 16:  # Need at least 16 bytes for IV
                                                continue
                                            iv = data[:16]
                                            cipher = AES.new(derived_key, mode, iv)
                                            encrypted_data = data[16:]
                                        else:
                                            cipher = AES.new(derived_key, mode)
                                            encrypted_data = data
                                            
                                        # Try to decrypt
                                        decrypted = cipher.decrypt(encrypted_data)
                                        
                                        # Check if decrypted data looks valid
                                        if any(marker in decrypted for marker in [b'MMKV', b'WeChat', b'Contact']):
                                            self._log(f"Successfully decrypted {mmkv_file.name}")
                                            return True
                                    except:
                                        continue
                            except ImportError:
                                self._log("pycryptodome not available for MMKV decryption")
                    except:
                        self._log(f"Failed to process {mmkv_file.name}")
                        continue
                        
            return False
            
        except Exception as e:
            print(f"Error validating key: {e}")
            return False
            
    def process_message_temp(self):
        """Process MessageTemp directory containing individual chat sessions."""
        try:
            if not self.backup_path:
                print("Backup path not set")
                return []
                
            msg_temp_path = self.backup_path / 'MessageTemp'
            if not msg_temp_path.exists():
                print("MessageTemp directory not found")
                return []
                
            sessions = []
            for session_dir in msg_temp_path.glob("*"):
                if session_dir.is_dir():
                    try:
                        session_info = {
                            'id': session_dir.name,
                            'size': sum(f.stat().st_size for f in session_dir.rglob('*') if f.is_file()),
                            'path': str(session_dir),
                            'files': [str(f.relative_to(session_dir)) for f in session_dir.rglob('*') if f.is_file()]
                        }
                        sessions.append(session_info)
                    except Exception as e:
                        print(f"Error processing session directory {session_dir.name}: {e}")
                        continue
                        
            if sessions:
                print(f"Found {len(sessions)} chat sessions in MessageTemp")
            return sessions
        except Exception as e:
            print(f"Error processing MessageTemp: {e}")
            return []
    
    def list_database_files(self):
        """List all SQLite database files in the backup directory."""
        if not self.backup_path:
            if not self.find_version_path():
                print("Could not find WeChat database files")
                return []
            if not self.backup_path or not self.backup_path.exists():
                print("Backup path does not exist")
                return []
        
        try:
            # Get all database files
            db_files = []
            
            # Get msg_*.db files and related files
            msg_dbs = list(self.backup_path.glob("msg_*.db"))
            for msg_db in msg_dbs:
                db_files.append(msg_db)
                # Check for related files
                base_path = str(msg_db)
                related_files = [
                    f"{base_path}-backup",
                    f"{base_path}-shm",
                    f"{base_path}-wal"
                ]
                for related_file in related_files:
                    if Path(related_file).exists():
                        self._log(f"Found related file: {Path(related_file).name}")
            
            # Get KeyValue.db and other .db files
            other_dbs = [f for f in self.backup_path.glob("*.db") 
                        if not f.name.startswith("msg_")]
            db_files.extend(other_dbs)
            
            # Get MMKV files
            mmkv_files = list(self.backup_path.glob("*.mmkv.default"))
            mmkv_files.extend(self.backup_path.glob("*.CheckPointMMKV"))
            mmkv_files.extend(self.backup_path.glob("*.ContactMMKV"))
            
            if mmkv_files:
                self._log(f"Found {len(mmkv_files)} MMKV files")
                for mmkv_file in mmkv_files:
                    crc_file = Path(str(mmkv_file) + '.crc')
                    if crc_file.exists():
                        self._log(f"Found CRC file for {mmkv_file.name}")
            
            if not db_files:
                print("No database files found")
            else:
                print(f"Found {len(db_files)} database files:")
                for db in db_files:
                    print(f"- {db.name} ({db.stat().st_size / 1024:.1f} KB)")
            
            return [str(f) for f in db_files]
        except Exception as e:
            print(f"Error listing database files: {e}")
            return []
    
    def extract_messages(self, db_path=None, key=None):
        """
        Extract messages from WeChat databases.
        
        Args:
            db_path: Optional path to specific database file
            key: Optional encryption key for SQLCipher database
        """
        try:
            # If specific database provided via argument
            if hasattr(self, 'args') and self.args.db:
                db_path = Path(self.args.db)
                if not db_path.exists():
                    print(f"Error: Database file not found: {db_path}")
                    return None
                databases = [db_path]
            # If specific database provided via method parameter
            elif db_path:
                db_path = Path(db_path)
                if not db_path.exists():
                    print(f"Error: Database file not found: {db_path}")
                    return None
                databases = [db_path]
            else:
                # Otherwise use version path
                if not self.version_path:
                    print("Error: Version path not set")
                    return None
                    
                # List all database files
                databases = self.list_database_files()
                if not databases:
                    print("No database files found")
                    return None
            
            # Try to extract key if needed
            if not key and hasattr(self, 'auto_key') and self.auto_key:
                # Try Cache.db first, then KeyValue.db
                key = self.extract_key_from_cache()
                if not key:
                    key = self.extract_key_from_keyvalue()
                if key:
                    print("Successfully extracted encryption key")
            
            # Process each database
            all_data = {}
            for db in databases:
                try:
                    db_path = str(db)  # Convert Path to string for sqlite3
                    
                    # Check if this is a backup file
                    is_backup = False
                    with open(db_path, 'rb') as f:
                        header = f.read(6)
                        if header == b'\x00dBmSt':
                            is_backup = True
                            print(f"Skipping backup file: {db_path}")
                            continue
                    
                    # Check for WAL mode files
                    has_wal = Path(f"{db_path}-wal").exists()
                    has_shm = Path(f"{db_path}-shm").exists()
                    
                    # Try normal SQLite first
                    try:
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        if has_wal:
                            cursor.execute('PRAGMA journal_mode=WAL;')
                    except sqlite3.DatabaseError:
                        # If normal SQLite fails, try SQLCipher
                        if SQLCIPHER_AVAILABLE and key:
                            print(f"Attempting to decrypt database: {db_path}")
                            if not self._try_decrypt_database(db_path, key):
                                print(f"Failed to decrypt database: {db_path}")
                                continue
                            conn = sqlcipher.connect(db_path)
                            cursor = conn.cursor()
                        else:
                            if not SQLCIPHER_AVAILABLE:
                                print("Database appears to be encrypted but pysqlcipher3 is not available")
                            elif not key:
                                print("Database appears to be encrypted but no key was provided")
                            continue
                    
                    # Start with a small sample to understand the schema
                    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
                    print(f"\nTables found in {db_path}: {tables['name'].tolist()}")
                    
                    # For each table, get schema and a sample of data
                    db_data = {}
                    for table in tables['name']:
                        try:
                            # Get table schema
                            cursor.execute(f"PRAGMA table_info({table});")
                            schema = cursor.fetchall()
                            columns = [col[1] for col in schema]
                            print(f"\nSchema for table {table}:")
                            for col in schema:
                                print(f"  {col[1]} ({col[2]})")
                            
                            # Get sample data
                            sample = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 5;", conn)
                            db_data[table] = {
                                'schema': schema,
                                'sample': sample,
                                'row_count': pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table};", conn).iloc[0]['count']
                            }
                        except Exception as e:
                            print(f"Error reading table {table}: {e}")
                    
                    conn.close()
                    all_data[db_path] = db_data
                    
                except Exception as e:
                    print(f"Error processing database {db_path}: {e}")
                    continue
            
            return all_data if all_data else None
            
        except Exception as e:
            print(f"Error extracting messages: {e}")
            return None

    def export_data(self, data, output_dir, format='csv'):
        """
        Export extracted data to files.
        
        Args:
            data: Dictionary containing table data
            output_dir: Base directory for output
            format: Export format ('csv' or 'json')
        """
        if not data: 
            return False
            
        if format not in ['csv', 'json']:
            print(f"Unsupported format: {format}. Using CSV.")
            format = 'csv'
            
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for table_name, table_data in data.items():
            try:
                # Create directory for this table
                table_dir = output_path / table_name
                table_dir.mkdir(parents=True, exist_ok=True)
                
                # Export schema
                schema_df = pd.DataFrame(table_data['schema'], 
                                       columns=['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'])
                if format == 'csv':
                    schema_df.to_csv(table_dir / 'schema.csv', index=False)
                else:
                    schema_df.to_json(table_dir / 'schema.json', orient='records')
                
                # Export sample data
                if format == 'csv':
                    table_data['sample'].to_csv(table_dir / 'sample.csv', index=False)
                else:
                    table_data['sample'].to_json(table_dir / 'sample.json', orient='records')
                
                # Create summary file
                with open(table_dir / 'summary.txt', 'w') as f:
                    f.write(f"Table: {table_name}\n")
                    f.write(f"Total rows: {table_data['row_count']}\n")
                    f.write(f"Export format: {format.upper()}\n")
                    f.write("\nSchema:\n")
                    for col in table_data['schema']:
                        f.write(f"  {col[1]} ({col[2]})\n")
                
                print(f"Exported table {table_name} to {table_dir}")
                    
            except Exception as e:
                print(f"Error exporting table {table_name}: {e}")
                continue
        
        return True

if __name__ == '__main__':
    main()
