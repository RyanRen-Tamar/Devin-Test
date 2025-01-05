import os
import sys
import sqlite3
import argparse
import pandas as pd
from pathlib import Path
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
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    parser.add_argument('--key', type=str, help='Encryption key for databases')
    parser.add_argument('--auto-key', action='store_true', help='Automatically extract encryption key')
    parser.add_argument('--output', type=str, default='wechat_export', help='Output directory')
    parser.add_argument('--format', type=str, choices=['csv', 'json'], default='csv', help='Export format (csv or json)')
    parser.add_argument('--verbose', action='store_true', help='Print detailed debugging information')
    return parser.parse_args()

class WeChatExtractor:
    def _log(self, message):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
            
    def __init__(self, test_mode=False, custom_path=None, output_dir='wechat_export', verbose=False):
        """
        Initialize the WeChat extractor.
        
        Args:
            test_mode (bool): If True, use test data directory
            custom_path (str): Custom path to WeChat data directory (for Mac users)
            output_dir (str): Directory for exported data
        """
        self.verbose = verbose
        self.user = os.environ.get('USER')
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
            # Create directory structure
            test_dir = Path('./test_data/WeChat/3.8.9/Backup')
            test_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a sample SQLite database
            sample_db_path = test_dir / 'test_messages.sqlite'
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
                
            print("Test environment created successfully")
        except Exception as e:
            print(f"Error creating test environment: {e}")
            
    def find_version_path(self):
        """Find the correct version path based on installed WeChat version."""
        try:
            # If path already contains version and hash, use it directly
            if '2.0b4.0.9' in str(self.base_path):
                print(f"Found version identifier '2.0b4.0.9' in path: {self.base_path}")
                if 'Message' in str(self.base_path):
                    print("Found Message directory in path")
                    self.version_path = self.base_path.parent.parent
                    self.backup_path = self.base_path
                else:
                    print("Looking for Message directory in subdirectories...")
                    self.version_path = self.base_path
                    # Look for Message directory in hash subdirectories
                    for hash_dir in self.base_path.glob("*"):
                        if not hash_dir.is_dir():
                            continue
                        print(f"Checking hash directory: {hash_dir.name}")
                        if (hash_dir / 'Message').exists():
                            self.backup_path = hash_dir / 'Message'
                            print(f"Found WeChat Message directory in: {hash_dir.name}")
                            return True
                        else:
                            print(f"No Message directory found in: {hash_dir.name}")
                return True

            # Check if we're already in a hash directory
            if (self.base_path / 'Message').exists():
                self._log(f"Found Message directory directly in path: {self.base_path}")
                self.version_path = self.base_path
                self.backup_path = self.base_path / 'Message'
                return True
                
            # Otherwise, search through directories
            version_dirs = list(self.base_path.glob("*"))
            if not version_dirs:
                print(f"Error: No subdirectories found in: {self.base_path}")
                return False
                
            self._log(f"Searching through {len(version_dirs)} potential version directories...")
            for dir in version_dirs:
                if not dir.is_dir():
                    continue
                    
                self._log(f"Checking directory: {dir.name}")
                
                # Check if this is a version directory (contains hash directories)
                hash_dirs = [d for d in dir.glob("*") if d.is_dir() and len(d.name) == 32]
                if hash_dirs:
                    self._log(f"Found {len(hash_dirs)} potential hash directories in {dir.name}")
                    
                    # Check immediate subdirectories (hash directories)
                    for hash_dir in hash_dirs:
                        self._log(f"Checking hash directory: {hash_dir.name}")
                        
                        # Check for Message directory in hash directory
                        msg_dir = hash_dir / 'Message'
                        if msg_dir.exists():
                            # Validate Message directory contains expected files
                            db_files = list(msg_dir.glob("*.db"))
                            if db_files:
                                self.version_path = dir
                                self.backup_path = msg_dir
                                print(f"Success: Found WeChat Message directory with {len(db_files)} database files in: {hash_dir.name}")
                                return True
                            else:
                                self._log(f"Message directory found but contains no database files in: {hash_dir.name}")
                        else: 
                            self._log(f"No Message directory found in hash directory: {hash_dir.name}")
                else:
                    self._log(f"No hash directories found in: {dir.name}")
                    
                    # Also check the version directory itself for Message directory
                    msg_dir = dir / 'Message'
                    if msg_dir.exists():
                        db_files = list(msg_dir.glob("*.db"))
                        if db_files:
                            self.version_path = dir
                            self.backup_path = msg_dir
                            print(f"Success: Found WeChat Message directory with {len(db_files)} database files in: {dir.name}")
                            return True
                        else:
                            self._log(f"Message directory found but contains no database files in: {dir.name}")
                            
            print("Error: No compatible WeChat version directory found with valid Message directory structure")
        except Exception as e:
            print(f"Error finding version path: {e}")
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
                
            conn = sqlcipher.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(f'PRAGMA key = "{key}";')
            cursor.execute('SELECT count(*) FROM sqlite_master;')
            cursor.fetchone()
            conn.close()
            return True
        except Exception as e:
            self._log(f"Key validation failed: {e}")
            return False
            
    def extract_key_from_keyvalue(self):
        """Extract and validate encryption key from KeyValue.db."""
        try:
            print("\nAnalyzing KeyValue database for encryption keys...")
            if not self.version_path:
                print("Error: Version path not set")
                return None
                
            keyvalue_path = self.version_path / 'KeyValue' / 'KeyValue.db'
            if not keyvalue_path.exists():
                print(f"Error: KeyValue.db not found at {keyvalue_path}")
                return None
                
            try:
                conn = sqlite3.connect(str(keyvalue_path))
                cursor = conn.cursor()
                
                # Get all tables
                print("\nAnalyzing database structure...")
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                print(f"Found {len(tables)} tables")
                
                potential_keys = []
                for table in tables:
                    table_name = table[0]
                    try:
                        # Get and display table schema
                        cursor.execute(f"PRAGMA table_info({table_name})")
                        columns = cursor.fetchall()
                        self._log(f"\nSchema for table {table_name}:")
                        for col in columns:
                            self._log(f"  {col[1]} ({col[2]})")
                        
                        # Look for columns that might contain keys
                        key_columns = [col[1] for col in columns 
                                     if any(key_term in col[1].lower() 
                                           for key_term in ['key', 'password', 'secret', 'token', 'cipher'])]
                        
                        if key_columns:
                            print(f"\nFound potential key columns in {table_name}: {', '.join(key_columns)}")
                            for col in key_columns:
                                cursor.execute(f"SELECT {col}, COUNT(*) as count FROM {table_name} WHERE {col} IS NOT NULL GROUP BY {col}")
                                values = cursor.fetchall()
                                for value, count in values:
                                    if value and len(str(value)) >= 16:  # Minimum key length
                                        potential_keys.append(value)
                                        self._log(f"Found potential key in {table_name}.{col}")
                                        self._log(f"  Length: {len(str(value))} chars")
                                        self._log(f"  Appears {count} times")
                    except sqlite3.Error as e:
                        print(f"Error analyzing table {table_name}: {e}")
                        continue
                
                conn.close()
                
                if not potential_keys:
                    print("No potential encryption keys found")
                    return None
                    
                # Try to validate keys using a known encrypted database
                print(f"\nFound {len(potential_keys)} potential keys, validating...")
                valid_keys = []
                
                # Look for encrypted databases to test keys
                test_dbs = list(self.backup_path.glob("*.db")) if self.backup_path else []
                if not test_dbs:
                    print("No databases found to validate encryption keys")
                    return potential_keys
                    
                test_db = test_dbs[0]  # Use first database for testing
                for key in potential_keys:
                    if self._try_decrypt_database(test_db, key):
                        print(f"Found valid encryption key!")
                        valid_keys.append(key)
                        
                return valid_keys if valid_keys else potential_keys
                
            except sqlite3.Error as e:
                print(f"Error connecting to KeyValue.db: {e}")
                return None
                
        except Exception as e:
            print(f"Error extracting key: {e}")
            return None
            
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
                print("Could not find WeChat version path")
                return []
            if not self.backup_path or not self.backup_path.exists():
                print("Backup path does not exist")
                return []
        
        try:
            # Get all database files
            db_files = []
            
            # Get msg_*.db files
            msg_dbs = list(self.backup_path.glob("msg_*.db"))
            db_files.extend(msg_dbs)
            
            # Get other .db files
            other_dbs = [f for f in self.backup_path.glob("*.db") 
                        if not f.name.startswith("msg_")]
            db_files.extend(other_dbs)
            
            # Get .sqlite files
            sqlite_files = list(self.backup_path.glob("*.sqlite"))
            db_files.extend(sqlite_files)
            
            # Check KeyValue directory
            keyvalue_path = self.version_path / 'KeyValue'
            if keyvalue_path.exists():
                keyvalue_dbs = list(keyvalue_path.glob("*.db"))
                db_files.extend(keyvalue_dbs)
            
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
    
    def extract_messages(self, db_path, key=None):
        """
        Extract messages from the specified database file.
        
        Args:
            db_path: Path to the database file
            key: Encryption key for SQLCipher database (if encrypted)
        """
        if not os.path.exists(db_path):
            print(f"Database file not found: {db_path}")
            return None
            
        try:
            # Try normal SQLite first
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
            except sqlite3.DatabaseError:
                # If normal SQLite fails, try SQLCipher
                if SQLCIPHER_AVAILABLE and key:
                    print("Attempting to open as encrypted database...")
                    conn = sqlcipher.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute(f"PRAGMA key = '{key}';")
                else:
                    if not SQLCIPHER_AVAILABLE:
                        print("Database appears to be encrypted but pysqlcipher3 is not available")
                    elif not key:
                        print("Database appears to be encrypted but no key was provided")
                    return None
            
            # Start with a small sample to understand the schema
            tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
            print(f"Tables found in database: {tables['name'].tolist()}")
            
            # For each table, get schema and a sample of data
            data = {}
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
                    data[table] = {
                        'schema': schema,
                        'sample': sample,
                        'row_count': pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table};", conn).iloc[0]['count']
                    }
                except Exception as e:
                    print(f"Error reading table {table}: {e}")
            
            conn.close()
            return data
            
        except Exception as e:
            print(f"Error connecting to database: {e}")
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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Extract WeChat chat history')
    parser.add_argument('--test', action='store_true', help='Run in test mode with sample data')
    parser.add_argument('--path', type=str, help='Custom path to WeChat data directory')
    parser.add_argument('--key', type=str, help='Encryption key for encrypted databases')
    parser.add_argument('--output', type=str, default='./wechat_export', help='Output directory for exported data')
    parser.add_argument('--auto-key', action='store_true', help='Attempt to automatically extract encryption key')
    args = parser.parse_args()
    
    # Initialize extractor
    extractor = WeChatExtractor(test_mode=args.test, custom_path=args.path)
    print("\n=== WeChat Data Extractor ===")
    
    # Try to get encryption key
    encryption_key = args.key
    if args.auto_key and not encryption_key:
        print("\nAttempting to extract encryption key...")
        potential_keys = extractor.extract_key_from_keyvalue()
        if potential_keys:
            print(f"Found {len(potential_keys)} potential encryption keys")
            encryption_key = potential_keys[0]  # Use first key found
    
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
            data = extractor.extract_messages(db_file, key=encryption_key)
            
            if data:
                # Create output directory based on database name
                db_name = Path(db_file).stem
                output_dir = Path(args.output) / db_name
                
                print(f"Exporting data to {output_dir}...")
                if extractor.export_data(data, output_dir):
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
