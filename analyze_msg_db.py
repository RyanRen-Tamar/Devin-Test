#!/usr/bin/env python3
import sys
import json
import sqlite3
import binascii
from pathlib import Path

def analyze_msg_db(db_path):
    """Analyze msg_2.db for encryption patterns and potential key material."""
    results = {
        'status': 'Unknown',
        'encrypted': False,
        'page_structure': {},
        'encryption_markers': {},
        'schema': {},
        'blob_analysis': {}
    }
    
    try:
        # Try to open as SQLite first
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if readable as SQLite
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            results['status'] = 'Unencrypted SQLite database'
            results['encrypted'] = False
            
            # Analyze schema
            for table in tables:
                table_name = table[0]
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                
                results['schema'][table_name] = {
                    'columns': [col[1] for col in columns],
                    'row_count': row_count
                }
                
                # Analyze potential encryption-related columns
                for col in columns:
                    col_name = col[1]
                    if any(key in col_name.lower() for key in ['key', 'hash', 'iv', 'salt', 'cipher', 'crypt']):
                        cursor.execute(f"SELECT DISTINCT {col_name} FROM {table_name} LIMIT 10")
                        sample_values = cursor.fetchall()
                        if not 'encryption_columns' in results['schema'][table_name]:
                            results['schema'][table_name]['encryption_columns'] = {}
                        results['schema'][table_name]['encryption_columns'][col_name] = [str(val[0]) for val in sample_values]
                    
                    # Check BLOB columns for encryption markers
                    if col[2].upper() == 'BLOB':
                        cursor.execute(f"SELECT {col_name} FROM {table_name} WHERE {col_name} IS NOT NULL LIMIT 5")
                        blobs = cursor.fetchall()
                        
                        if not table_name in results['blob_analysis']:
                            results['blob_analysis'][table_name] = {}
                        
                        blob_patterns = []
                        key_material = []
                        
                        for blob in blobs:
                            if blob[0]:
                                hex_data = binascii.hexlify(blob[0]).decode('utf-8')
                                
                                # Look for encryption markers
                                if 'aes' in hex_data.lower():
                                    blob_patterns.append('AES marker')
                                if 'hmac' in hex_data.lower():
                                    blob_patterns.append('HMAC marker')
                                if 'pbkdf2' in hex_data.lower():
                                    blob_patterns.append('PBKDF2 marker')
                                
                                # Extract potential key material (32-byte sequences)
                                for i in range(0, len(hex_data)-63, 2):
                                    key_candidate = hex_data[i:i+64]
                                    if all(c in '0123456789abcdefABCDEF' for c in key_candidate):
                                        key_material.append(key_candidate)
                        
                        results['blob_analysis'][table_name][col_name] = {
                            'patterns': list(set(blob_patterns)),
                            'potential_key_material': list(set(key_material))[:5]  # Limit to 5 unique candidates
                        }
        
        except sqlite3.DatabaseError:
            results['status'] = 'Encrypted or corrupted SQLite database'
            results['encrypted'] = True
            
            # Read file as binary to check for encryption markers
            with open(db_path, 'rb') as f:
                data = f.read()
                hex_data = binascii.hexlify(data).decode('utf-8')
                
                # Check for known markers
                markers = {
                    'aes_cbc': ['616573', '434243'],  # 'aes', 'CBC'
                    'hmac_sha1': ['686D6163', '736861'],  # 'hmac', 'sha'
                    'sqlite_header': ['53514C69746520666F726D6174'],  # SQLite format
                    'pbkdf2': ['706264666B6632']  # 'pbkdf2'
                }
                
                for marker_name, patterns in markers.items():
                    positions = []
                    for pattern in patterns:
                        pos = hex_data.find(pattern.lower())
                        if pos >= 0:
                            positions.append(pos // 2)  # Convert hex position to byte position
                    if positions:
                        results['encryption_markers'][marker_name] = positions
                
                # Analyze page structure (standard 4096-byte pages)
                page_size = 4096
                for i in range(min(3, len(data) // page_size)):
                    page_data = data[i*page_size:(i+1)*page_size]
                    page_hex = binascii.hexlify(page_data).decode('utf-8')
                    
                    # Check for IV and HMAC in page structure
                    hex_end = binascii.hexlify(page_data[-48:-32]).decode().lower()
                    hex_last = binascii.hexlify(page_data[-32:]).decode().lower()
                    
                    results['page_structure'][f'page_{i}'] = {
                        'iv_marker': '616573' in hex_end or '434243' in hex_end,
                        'hmac_marker': '686d6163' in hex_last or '736861' in hex_last
                    }
                    
                    # For first page, also check salt
                    if i == 0:
                        results['page_structure']['salt'] = binascii.hexlify(page_data[:16]).decode()
                        
                        # Check if page size matches SQLite standard
                        try:
                            detected_page_size = int.from_bytes(page_data[16:18], byteorder='big')
                            results['page_structure']['detected_page_size'] = detected_page_size
                        except:
                            results['page_structure']['detected_page_size'] = None
        
        finally:
            conn.close()
    
    except Exception as e:
        results['status'] = f'Error: {str(e)}'
    
    # Save results
    output_path = Path(db_path).stem + '_analysis.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print(f"\nmsg_2.db Analysis:")
    print(f"Status: {results['status']}")
    print(f"Encrypted: {results['encrypted']}")
    
    if results['page_structure']:
        print("\nPage Structure Analysis:")
        for page, info in results['page_structure'].items():
            if isinstance(info, dict):
                if 'detected_page_size' in info:
                    print(f"Detected page size: {info['detected_page_size']}")
                else:
                    print(f"{page}: IV={info['iv_marker']}, HMAC={info['hmac_marker']}")
            else:
                print(f"{page}: {info}")
    
    if results['encryption_markers']:
        print("\nEncryption Markers:")
        for marker, positions in results['encryption_markers'].items():
            print(f"{marker}: Found at positions {positions}")
    
    if results['schema']:
        print("\nDatabase Schema Summary:")
        print(f"Number of tables: {len(results['schema'])}\n")
        for table, info in results['schema'].items():
            print(f"Table: {table}")
            print(f"Row count: {info['row_count']}")
            print("Columns:")
            for col in info['columns']:
                print(f"  - {col}")
            if 'encryption_columns' in info:
                print("\nEncryption-related columns:")
                for col, values in info['encryption_columns'].items():
                    print(f"  - {col}")
                    print(f"    Values: {', '.join(map(str, values))}")
            print()
    
    if results['blob_analysis']:
        print("\nBLOB Analysis:")
        for table, columns in results['blob_analysis'].items():
            print(f"\nTable: {table}")
            for col, analysis in columns.items():
                print(f"\nColumn: {col}")
                if analysis['patterns']:
                    print("Patterns found:")
                    for pattern in analysis['patterns']:
                        print(f"  - {pattern}")
                if analysis['potential_key_material']:
                    print("Potential key material:")
                    for key in analysis['potential_key_material']:
                        print(f"  - {key}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 analyze_msg_db.py path/to/msg_2.db")
        sys.exit(1)
    
    analyze_msg_db(sys.argv[1])
