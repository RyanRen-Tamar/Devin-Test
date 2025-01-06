import os
import sys
import hashlib
import hmac
import binascii
import sqlite3
import json
from typing import List, Tuple, Dict, Any

def analyze_file_header(file_path: str) -> Tuple[bool, bytes, str]:
    """Analyze the file header for SQLite and encryption markers"""
    with open(file_path, 'rb') as f:
        header = f.read(100)  # Read enough for SQLite header and potential salt
        
    # Check if it's a standard SQLite file
    if header.startswith(b'SQLite format 3\x00'):
        return False, header[:16], "Unencrypted SQLite database"
        
    # Check for potential salt (first 16 bytes)
    potential_salt = header[:16]
    
    # Look for known patterns
    patterns = {
        'aes_marker': b'\x00\x00\x00\x01',  # Common AES block marker
        'hmac_marker': b'\x01\x00\x00\x00',  # HMAC marker from Windows impl
    }
    
    found_patterns = []
    for name, pattern in patterns.items():
        if pattern in header:
            found_patterns.append(name)
            
    return True, potential_salt, f"Encrypted database. Found patterns: {found_patterns}"

def analyze_page_structure(file_path: str, page_size: int = 4096) -> List[dict]:
    """Analyze the structure of database pages"""
    page_info = []
    file_size = os.path.getsize(file_path)
    
    with open(file_path, 'rb') as f:
        for page_num in range(file_size // page_size):
            page_data = f.read(page_size)
            if not page_data:
                break
                
            # Analyze page structure
            page_info.append({
                'page_num': page_num,
                'has_iv': bool(page_data[-48:-32]),  # Check for IV in last 48 bytes
                'has_hmac': bool(page_data[-32:-12]),  # Check for HMAC
                'potential_salt': binascii.hexlify(page_data[:16]).decode() if page_num == 0 else None
            })
            
    return page_info

def check_encryption_markers(file_path: str) -> dict:
    """Check for known encryption markers and patterns"""
    markers = {
        'aes_cbc': b'\x00\x00\x00\x01',
        'hmac_sha1': b'\x01\x00\x00\x00',
        'sqlite_header': b'SQLite format 3\x00'
    }
    
    results = {}
    with open(file_path, 'rb') as f:
        content = f.read()
        
    for name, marker in markers.items():
        positions = []
        pos = -1
        while True:
            pos = content.find(marker, pos + 1)
            if pos == -1:
                break
            positions.append(pos)
        results[name] = positions
        
    return results

def analyze_schema(db_path: str) -> dict:
    """Analyze the schema and content of Cache.db"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        schema_info = {}
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            row_count = cursor.fetchone()[0]
            
            # Get sample data
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
            sample_data = cursor.fetchall()
            
            schema_info[table_name] = {
                'columns': [{'name': col[1], 'type': col[2]} for col in columns],
                'row_count': row_count,
                'sample_data': [dict(zip([col[1] for col in columns], row)) for row in sample_data]
            }
            
            # Look for encryption-related columns
            encryption_keywords = ['key', 'iv', 'salt', 'hash', 'encrypt', 'cipher', 'secret', 'token', 'auth']
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
            
            # Analyze BLOB data for encryption patterns
            blob_columns = [col[1] for col in columns if 'BLOB' in col[2].upper()]
            if blob_columns and table_name == 'cfurl_cache_blob_data':
                schema_info[table_name]['blob_analysis'] = {}
                for col in blob_columns:
                    cursor.execute(f"SELECT {col} FROM {table_name} WHERE {col} IS NOT NULL LIMIT 5;")
                    blobs = cursor.fetchall()
                    
                    patterns = []
                    key_candidates = []
                    for blob in blobs:
                        if blob[0]:
                            data = blob[0]
                            if isinstance(data, (bytes, bytearray)):
                                # Look for common encryption markers
                                if b'\x00\x00\x00\x01' in data:
                                    patterns.append('AES-CBC marker')
                                if b'\x01\x00\x00\x00' in data:
                                    patterns.append('HMAC marker')
                                if b'SQLite format 3' in data:
                                    patterns.append('SQLite header')
                                
                                # Look for potential key material (32-byte sequences)
                                for i in range(len(data) - 32):
                                    chunk = data[i:i+32]
                                    # Check if chunk looks like key material (high entropy)
                                    if all(32 <= x <= 126 for x in chunk) or all(x != 0 for x in chunk):
                                        key_candidates.append(binascii.hexlify(chunk).decode())
                    
                    if patterns or key_candidates:
                        schema_info[table_name]['blob_analysis'][col] = {
                            'patterns': list(set(patterns)),
                            'key_candidates': list(set(key_candidates[:5]))  # Limit to first 5 unique candidates
                        }
        
        conn.close()
        return schema_info
        
    except sqlite3.Error as e:
        return {'error': str(e)}

def main():
    cache_db = os.path.expanduser("~/attachments/Cache.db")
    if not os.path.exists(cache_db):
        print(f"Error: {cache_db} not found")
        return
        
    # Analyze main database file
    is_encrypted, salt, status = analyze_file_header(cache_db)
    print(f"\nCache.db Analysis:")
    print(f"Status: {status}")
    print(f"Encrypted: {is_encrypted}")
    if is_encrypted:
        print(f"Potential salt: {binascii.hexlify(salt).decode()}")
        
    # Analyze page structure
    print("\nPage Structure Analysis:")
    page_info = analyze_page_structure(cache_db)
    for page in page_info[:3]:  # Show first 3 pages
        print(f"Page {page['page_num']}: IV={page['has_iv']}, HMAC={page['has_hmac']}")
        if page['potential_salt']:
            print(f"Salt: {page['potential_salt']}")
            
    # Check encryption markers
    print("\nEncryption Markers:")
    markers = check_encryption_markers(cache_db)
    for marker, positions in markers.items():
        if positions:
            print(f"{marker}: Found at positions {positions[:3]}")
            
    # Analyze schema
    print("\nAnalyzing Cache.db schema...")
    schema_info = analyze_schema(cache_db)
    
    # Save schema analysis
    with open('cache_db_schema.json', 'w') as f:
        json.dump(schema_info, f, indent=2, default=str)
    print("Schema analysis saved to cache_db_schema.json")
    
    # Print schema summary
    print("\nDatabase Schema Summary:")
    print(f"Number of tables: {len(schema_info)}")
    
    encryption_related_tables = []
    for table, info in schema_info.items():
        print(f"\nTable: {table}")
        print(f"Row count: {info['row_count']}")
        print("Columns:")
        for col in info['columns']:
            print(f"  - {col['name']} ({col['type']})")
        
        if 'encryption_related_columns' in info:
            encryption_related_tables.append(table)
            print("\nEncryption-related columns:")
            for col in info['encryption_related_columns']:
                print(f"  - {col}")
                if f'{col}_values' in info:
                    print(f"    Values: {', '.join(info[f'{col}_values'])}")
        
        if 'blob_analysis' in info:
            print("\nBLOB Analysis:")
            for col, analysis in info['blob_analysis'].items():
                print(f"\nColumn: {col}")
                if analysis['patterns']:
                    print("Patterns found:")
                    for pattern in analysis['patterns']:
                        print(f"  - {pattern}")
                if analysis['key_candidates']:
                    print("Potential key material:")
                    for key in analysis['key_candidates']:
                        print(f"  - {key}")

if __name__ == "__main__":
    main()
