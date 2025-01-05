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
    def __init__(self):
        self.user = os.environ.get('USER')
        self.base_path = Path(f'/Users/{self.user}/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat')
        self.version_path = None
        self.backup_path = None
        
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
    extractor = WeChatExtractor()
    print("Searching for WeChat databases...")
    db_files = extractor.list_database_files()
    
    if not db_files:
        print("No database files found.")
    else:
        print(f"Found {len(db_files)} database files:")
        for db_file in db_files:
            print(f"\nAnalyzing database: {db_file}")
            data = extractor.extract_messages(db_file)
            
            if data:
                # Create output directory based on database name
                db_name = Path(db_file).stem
                output_dir = Path(f"./wechat_export_{db_name}")
                
                print(f"\nExporting data to {output_dir}...")
                if extractor.export_data(data, output_dir):
                    print(f"Data successfully exported to {output_dir}")
                else:
                    print("Failed to export data")
