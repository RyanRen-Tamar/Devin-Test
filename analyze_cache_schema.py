import sqlite3
import json
import os
from typing import Dict, List, Any

def analyze_schema(db_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Analyze the schema of Cache.db"""
    schema_info = {}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            # Get sample data
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
            sample_data = cursor.fetchall()
            
            schema_info[table_name] = {
                'columns': [{'name': col[1], 'type': col[2]} for col in columns],
                'sample_data': [dict(zip([col[1] for col in columns], row)) for row in sample_data]
            }
            
            # Look for encryption-related columns
            encryption_keywords = ['key', 'iv', 'salt', 'hash', 'encrypt', 'cipher', 'secret']
            encryption_columns = []
            for col in columns:
                if any(keyword in col[1].lower() for keyword in encryption_keywords):
                    encryption_columns.append(col[1])
            
            if encryption_columns:
                schema_info[table_name]['encryption_related_columns'] = encryption_columns
                # Get distinct values for these columns
                for col in encryption_columns:
                    cursor.execute(f"SELECT DISTINCT {col} FROM {table_name} WHERE {col} IS NOT NULL LIMIT 10;")
                    values = cursor.fetchall()
                    schema_info[table_name][f'{col}_values'] = [str(val[0]) for val in values]
        
        conn.close()
        return schema_info
        
    except sqlite3.Error as e:
        return {'error': str(e)}

def analyze_binary_columns(db_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Analyze columns containing binary data for encryption patterns"""
    binary_analysis = {}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            # Look for BLOB columns
            blob_columns = [col[1] for col in columns if 'BLOB' in col[2].upper()]
            
            if blob_columns:
                binary_analysis[table_name] = {'blob_columns': {}}
                
                for col in blob_columns:
                    # Get sample of binary data
                    cursor.execute(f"SELECT {col} FROM {table_name} WHERE {col} IS NOT NULL LIMIT 5;")
                    blobs = cursor.fetchall()
                    
                    patterns = []
                    for blob in blobs:
                        if blob[0]:
                            # Check for common encryption markers
                            data = blob[0]
                            if isinstance(data, (bytes, bytearray)):
                                if b'\x00\x00\x00\x01' in data:  # AES-CBC marker
                                    patterns.append('AES-CBC marker found')
                                if b'\x01\x00\x00\x00' in data:  # HMAC marker
                                    patterns.append('HMAC marker found')
                                if b'SQLite format 3' in data:  # SQLite header
                                    patterns.append('SQLite header found')
                    
                    if patterns: 
                        binary_analysis[table_name]['blob_columns'][col] = list(set(patterns))
        
        conn.close()
        return binary_analysis
        
    except sqlite3.Error as e:
        return {'error': str(e)}

def main():
    cache_db = os.path.expanduser("~/attachments/Cache.db")
    if not os.path.exists(cache_db):
        print(f"Error: {cache_db} not found")
        return
        
    # Analyze schema
    print("\nAnalyzing Cache.db schema...")
    schema_info = analyze_schema(cache_db)
    
    # Save schema analysis
    with open('cache_db_schema.json', 'w') as f:
        json.dump(schema_info, f, indent=2, default=str)
    print("Schema analysis saved to cache_db_schema.json")
    
    # Analyze binary columns
    print("\nAnalyzing binary data...")
    binary_analysis = analyze_binary_columns(cache_db)
    
    # Save binary analysis
    with open('cache_db_binary.json', 'w') as f:
        json.dump(binary_analysis, f, indent=2, default=str)
    print("Binary analysis saved to cache_db_binary.json")
    
    # Print summary
    print("\nDatabase Summary:")
    print(f"Number of tables: {len(schema_info)}")
    
    encryption_related_tables = []
    for table, info in schema_info.items():
        if 'encryption_related_columns' in info:
            encryption_related_tables.append(table)
            print(f"\nTable '{table}' has encryption-related columns:")
            for col in info['encryption_related_columns']:
                print(f"  - {col}")
                if f'{col}_values' in info:
                    print(f"    Values: {', '.join(info[f'{col}_values'])}")
    
    if binary_analysis:
        print("\nBinary Data Analysis:")
        for table, info in binary_analysis.items():
            if 'blob_columns' in info and info['blob_columns']:
                print(f"\nTable '{table}' has interesting binary patterns:")
                for col, patterns in info['blob_columns'].items():
                    if patterns:
                        print(f"  Column '{col}': {', '.join(patterns)}")

if __name__ == "__main__":
    main()
