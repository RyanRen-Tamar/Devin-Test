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
    return parser.parse_args()

class WeChatExtractor:
    def __init__(self, test_mode=False, custom_path=None, output_dir='wechat_export'):
        """
        Initialize the WeChat extractor.
        
        Args:
            test_mode (bool): If True, use test data directory
            custom_path (str): Custom path to WeChat data directory (for Mac users)
            output_dir (str): Directory for exported data
        """
        self.user = os.environ.get('USER')
        if test_mode:
            self.base_path = Path('./test_data/WeChat')
        elif custom_path:
            self.base_path = Path(custom_path)
        else:
            self.base_path = Path(f'/Users/{self.user}/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat')
        
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
                if 'Message' in str(self.base_path):
                    self.version_path = self.base_path.parent.parent
                    self.backup_path = self.base_path
                else:
                    self.version_path = self.base_path
                    # Look for Message directory in hash subdirectories
                    for hash_dir in self.base_path.glob("*"):
                        if hash_dir.is_dir() and (hash_dir / 'Message').exists():
                            self.backup_path = hash_dir / 'Message'
                            print(f"Found WeChat Message directory in: {hash_dir.name}")
                            return True
                return True

            # Otherwise, search through directories
            version_dirs = list(self.base_path.glob("*"))
            for dir in version_dirs:
                if not dir.is_dir():
                    continue
                    
                print(f"Checking directory: {dir.name}")
                
                # Check immediate subdirectories (hash directories)
                for hash_dir in dir.glob("*"):
                    if not hash_dir.is_dir():
                        continue
                        
                    print(f"Checking hash directory: {hash_dir.name}")
                    
                    # Check for Message directory in hash directory
                    if (hash_dir / 'Message').exists():
                        self.version_path = dir
                        self.backup_path = hash_dir / 'Message'
                        print(f"Found WeChat Message directory in: {hash_dir.name}")
                        return True
                    
                # Also check the version directory itself
                if (dir / 'Message').exists():
                    self.version_path = dir
                    self.backup_path = dir / 'Message'
                    print(f"Found WeChat Message directory in: {dir.name}")
                    return True
            print("No compatible WeChat version directory found")
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
            
    def extract_key_from_keyvalue(self):
        """Extract encryption key from KeyValue.db."""
        try:
            if not self.version_path:
                print("Version path not set")
                return None
                
            keyvalue_path = self.version_path / 'KeyValue' / 'KeyValue.db'
            if not keyvalue_path.exists():
                print("KeyValue.db not found")
                return None
                
            try:
                conn = sqlite3.connect(str(keyvalue_path))
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                potential_keys = []
                for table in tables:
                    table_name = table[0]
                    try:
                        # Look for columns that might contain keys
                        cursor.execute(f"PRAGMA table_info({table_name})")
                        columns = cursor.fetchall()
                        
                        key_columns = [col[1] for col in columns 
                                     if any(key_term in col[1].lower() 
                                           for key_term in ['key', 'password', 'secret', 'token'])]
                        
                        if key_columns:
                            for col in key_columns:
                                cursor.execute(f"SELECT {col} FROM {table_name} WHERE {col} IS NOT NULL LIMIT 5")
                                values = cursor.fetchall()
                                potential_keys.extend([v[0] for v in values if v[0]])
                    except sqlite3.Error as e:
                        print(f"Error querying table {table_name}: {e}")
                        continue
                
                conn.close()
                return potential_keys
                
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

    def export_data(self, data, output_dir):
        """Export extracted data to CSV files."""
        if not data: 
            return False
            
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for table_name, table_data in data.items():
            try:
                # Export schema
                schema_df = pd.DataFrame(table_data['schema'], 
                                       columns=['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'])
                schema_df.to_csv(output_path / f"{table_name}_schema.csv", index=False)
                
                # Export sample data
                table_data['sample'].to_csv(output_path / f"{table_name}_sample.csv", index=False)
                
                # Create summary file
                with open(output_path / f"{table_name}_summary.txt", 'w') as f:
                    f.write(f"Table: {table_name}\n")
                    f.write(f"Total rows: {table_data['row_count']}\n")
                    f.write("\nSchema:\n")
                    for col in table_data['schema']:
                        f.write(f"  {col[1]} ({col[2]})\n")
                    
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
