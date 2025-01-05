import os
import sqlite3
import pandas as pd
from pathlib import Path
try:
    from pysqlcipher3 import dbapi2 as sqlcipher
    SQLCIPHER_AVAILABLE = True
except ImportError:
    SQLCIPHER_AVAILABLE = False
    print("Warning: pysqlcipher3 not available. Encrypted databases cannot be read.")

class WeChatExtractor:
    def __init__(self, test_mode=False, custom_path=None):
        """
        Initialize the WeChat extractor.
        
        Args:
            test_mode (bool): If True, use test data directory
            custom_path (str): Custom path to WeChat data directory (for Mac users)
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
            # Look for version directory (3.8.9)
            version_dirs = list(self.base_path.glob("*"))
            for dir in version_dirs:
                if dir.is_dir() and '3.8.9' in dir.name:
                    self.version_path = dir
                    self.backup_path = dir / 'Backup'
                    return True
        except Exception as e:
            print(f"Error finding version path: {e}")
        return False
    
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
            sqlite_files = list(self.backup_path.glob("*.sqlite"))
            db_files = list(self.backup_path.glob("*.db"))
            all_files = sqlite_files + db_files
            
            if not all_files:
                print("No database files found in backup directory")
            
            return [str(f) for f in all_files]
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
    args = parser.parse_args()
    
    extractor = WeChatExtractor(test_mode=args.test, custom_path=args.path)
    print("Searching for WeChat databases...")
    db_files = extractor.list_database_files()
    
    if not db_files:
        print("No database files found.")
    else:
        print(f"Found {len(db_files)} database files:")
        for db_file in db_files:
            print(f"\nAnalyzing database: {db_file}")
            data = extractor.extract_messages(db_file, key=args.key)
            
            if data:
                # Create output directory based on database name
                db_name = Path(db_file).stem
                output_dir = Path(args.output) / db_name
                
                print(f"\nExporting data to {output_dir}...")
                if extractor.export_data(data, output_dir):
                    print(f"Data successfully exported to {output_dir}")
                else:
                    print("Failed to export data")

    print("\nUsage instructions:")
    print("1. For Mac users: python wechat_extractor.py --path '/Users/YOUR_USERNAME/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat'")
    print("2. For testing: python wechat_extractor.py --test")
    print("3. For encrypted databases: python wechat_extractor.py --key YOUR_KEY")
    print("4. Custom output directory: python wechat_extractor.py --output /path/to/output")
