import sqlite3
import os
import json
import binascii
from typing import List, Dict, Optional

class KeyValueAnalyzer:
    """Analyze KeyValue.db for potential encryption-related metadata."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.results = {
            'tables': [],
            'key_related_entries': [],
            'potential_keys': [],
            'metadata': {}
        }
    
    def analyze_file_header(self) -> Dict:
        """Analyze the SQLite file header and page structure for encryption indicators."""
        header_info = {}
        try:
            with open(self.db_path, 'rb') as f:
                # Read first page (4096 bytes)
                first_page = f.read(4096)
                
                # Analyze header
                header_info['magic_bytes'] = binascii.hexlify(first_page[:16]).decode()
                header_info['page_size'] = int.from_bytes(first_page[16:18], byteorder='big')
                header_info['file_format'] = first_page[18]
                header_info['reserved_bytes'] = first_page[19:24].hex()
                
                # Check for encryption markers at known positions
                markers = {
                    'aes_cbc': [56, 64, 4093],  # Positions found in Cache.db
                    'hmac_sha1': [59, 67, 4096]  # Positions found in Cache.db
                }
                
                header_info['encryption_markers'] = {}
                for marker_name, positions in markers.items():
                    found_positions = []
                    for pos in positions:
                        if pos < len(first_page):
                            # Check 8 bytes around position for markers
                            window = first_page[max(0, pos-4):min(len(first_page), pos+4)]
                            hex_window = binascii.hexlify(window).decode().lower()
                            
                            if marker_name == 'aes_cbc' and ('616573' in hex_window or '434243' in hex_window):
                                found_positions.append(pos)
                            elif marker_name == 'hmac_sha1' and ('686d6163' in hex_window or '736861' in hex_window):
                                found_positions.append(pos)
                    
                    if found_positions:
                        header_info['encryption_markers'][marker_name] = found_positions
                
                # Check for PBKDF2 markers (from Windows implementation)
                pbkdf2_marker = b'pbkdf2'
                pbkdf2_pos = first_page.lower().find(pbkdf2_marker)
                if pbkdf2_pos >= 0:
                    header_info['encryption_markers']['pbkdf2'] = [pbkdf2_pos]
                
                # Analyze page structure
                hex_end = binascii.hexlify(first_page[-48:-32]).decode().lower()
                hex_last = binascii.hexlify(first_page[-32:]).decode().lower()
                header_info['page_structure'] = {
                    'salt': binascii.hexlify(first_page[:16]).decode(),
                    'iv_marker': '616573' in hex_end or '434243' in hex_end,
                    'hmac_marker': '686d6163' in hex_last or '736861' in hex_last
                }
                
                # Read a few more pages to confirm pattern
                for i in range(1, 3):
                    page = f.read(4096)
                    if not page:
                        break
                    
                    hex_end = binascii.hexlify(page[-48:-32]).decode().lower()
                    hex_last = binascii.hexlify(page[-32:]).decode().lower()
                    page_info = {
                        'iv_marker': '616573' in hex_end or '434243' in hex_end,
                        'hmac_marker': '686d6163' in hex_last or '736861' in hex_last
                    }
                    header_info['page_structure'][f'page_{i}'] = page_info
                
        except Exception as e:
            header_info['error'] = str(e)
        return header_info
    
    def find_key_related_patterns(self) -> List[Dict]:
        """Search for patterns that might indicate encryption keys or parameters."""
        patterns = []
        try:
            with open(self.db_path, 'rb') as f:
                content = f.read()
                # Look for common key-related strings
                key_indicators = [
                    b'key', b'KEY', b'salt', b'SALT',
                    b'cipher', b'CIPHER', b'crypt', b'CRYPT',
                    b'hash', b'HASH', b'iv', b'IV'
                ]
                
                for indicator in key_indicators:
                    pos = 0
                    while True:
                        pos = content.find(indicator, pos)
                        if pos == -1:
                            break
                        
                        # Get surrounding bytes for context
                        start = max(0, pos - 16)
                        end = min(len(content), pos + 16 + len(indicator))
                        context = content[start:end]
                        
                        patterns.append({
                            'indicator': indicator.decode(),
                            'position': pos,
                            'context': context.hex(),
                            'ascii_context': ''.join(chr(b) if 32 <= b <= 126 else '.' for b in context)
                        })
                        pos += 1
        except Exception as e:
            patterns.append({'error': str(e)})
        return patterns
    
    def analyze_db_structure(self) -> None:
        """Attempt to analyze database structure without decryption."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                self.results['tables'].append({
                    'name': table_name,
                    'columns': []
                })
                
                # Get column info
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                for col in columns:
                    self.results['tables'][-1]['columns'].append({
                        'name': col[1],
                        'type': col[2]
                    })
                
                # Try to find key-related column names
                key_columns = [col for col in columns if 
                             any(k in col[1].lower() 
                                 for k in ['key', 'hash', 'salt', 'cipher', 'crypt'])]
                if key_columns:
                    self.results['key_related_entries'].extend([{
                        'table': table_name,
                        'column': col[1],
                        'type': col[2]
                    } for col in key_columns])
            
            conn.close()
            
        except sqlite3.DatabaseError as e:
            # If we can't read the database directly, it's likely encrypted
            self.results['metadata']['encrypted'] = True
            self.results['metadata']['error'] = str(e)
    
    def analyze(self) -> Dict:
        """Run all analysis methods and return results."""
        # Analyze file header
        self.results['metadata']['header'] = self.analyze_file_header()
        
        # Find potential key patterns in raw file
        self.results['potential_keys'] = self.find_key_related_patterns()
        
        # Try to analyze database structure
        self.analyze_db_structure()
        
        return self.results

def main():
    # Analyze both KeyValue.db and its backup if available
    db_paths = [
        '/home/ubuntu/attachments/KeyValue.db',
        '/home/ubuntu/attachments/KeyValue.db-shm'
    ]
    
    for db_path in db_paths:
        if os.path.exists(db_path):
            print(f"\nAnalyzing {db_path}...")
            analyzer = KeyValueAnalyzer(db_path)
            results = analyzer.analyze()
            
            # Save results
            output_file = f"keyvalue_analysis_{os.path.basename(db_path)}.json"
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {output_file}")
            
            # Print key findings
            if results['key_related_entries']:
                print("\nFound key-related columns:")
                for entry in results['key_related_entries']:
                    print(f"- Table: {entry['table']}, Column: {entry['column']}, Type: {entry['type']}")
            
            if results['potential_keys']:
                print("\nFound potential key patterns:")
                for pattern in results['potential_keys'][:5]:  # Show first 5 patterns
                    print(f"- {pattern['indicator']} at position {pattern['position']}")
                    print(f"  Context (ASCII): {pattern['ascii_context']}")

if __name__ == '__main__':
    main()
