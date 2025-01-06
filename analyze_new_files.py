import os
import json
import sqlite3
import hashlib
from pathlib import Path
import struct
import binascii

def read_binary_file(filepath, max_size=None):
    """Safely read binary file contents"""
    try:
        with open(filepath, 'rb') as f:
            if max_size:
                return f.read(max_size)
            return f.read()
    except Exception as e:
        return None

def analyze_config_file(filepath):
    """Analyze configuration files for potential encryption info"""
    data = read_binary_file(filepath)
    if not data:
        return None
    
    results = {
        'filename': os.path.basename(filepath),
        'size': len(data),
        'hex_header': data[:32].hex(),
        'text_samples': [],
        'potential_keys': []
    }
    
    # Look for text patterns
    try:
        text = data.decode('utf-8', errors='ignore')
        # Extract strings that might be keys or identifiers
        import re
        patterns = [
            r'[0-9a-f]{32}',  # MD5-like hashes
            r'key["\':]\s*["\']([^"\']+)["\']',  # Key patterns
            r'salt["\':]\s*["\']([^"\']+)["\']',  # Salt patterns
            r'version["\':]\s*["\']([^"\']+)["\']'  # Version info
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                results['potential_keys'].extend(matches)
                
        # Extract readable text samples
        text_lines = [line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) > 5]
        results['text_samples'] = text_lines[:10]  # First 10 valid lines
        
    except Exception as e:
        pass
    
    return results

def analyze_sqlite_header(data):
    """Analyze SQLite database header"""
    if len(data) < 100:
        return None
        
    header_info = {
        'magic_string': data[:16].hex(),
        'page_size': struct.unpack('>H', data[16:18])[0],
        'write_version': data[18],
        'read_version': data[19],
        'reserved_space': data[20],
        'max_payload_fraction': data[21],
        'min_payload_fraction': data[22],
        'leaf_payload_fraction': data[23],
        'file_change_counter': struct.unpack('>I', data[24:28])[0],
    }
    
    return header_info

def analyze_db_file(filepath):
    """Analyze database file structure and header"""
    data = read_binary_file(filepath, 1024)  # Read first 1KB
    if not data:
        return None
        
    results = {
        'filename': os.path.basename(filepath),
        'size': os.path.getsize(filepath),
        'header_analysis': analyze_sqlite_header(data),
        'encryption_markers': []
    }
    
    # Check for SQLCipher markers
    sqlcipher_markers = [b'SQLite format 3', b'encrypted', b'sqlcipher']
    for marker in sqlcipher_markers:
        pos = data.find(marker)
        if pos >= 0:
            results['encryption_markers'].append({
                'marker': marker.decode('utf-8', errors='ignore'),
                'position': pos
            })
            
    return results

def analyze_all_files():
    """Analyze all relevant files in the attachments directory"""
    attachments_dir = os.path.expanduser('~/attachments')
    results = {
        'databases': {},
        'mmkv_files': {},
        'config_files': {},
        'version_files': {}
    }
    
    # Analyze main database files
    db_files = ['KeyValue.db', 'msg_2.db']
    for db_file in db_files:
        filepath = os.path.join(attachments_dir, db_file)
        if os.path.exists(filepath):
            results['databases'][db_file] = analyze_db_file(filepath)
    
    # Analyze configuration and version files
    config_files = ['topinfo.data', 'upgradeHistoryFile', 'whatsNewVersionFileV2', 
                   'checkVersionFile', 'whatsNewVersionFile']
    for config_file in config_files:
        filepath = os.path.join(attachments_dir, config_file)
        if os.path.exists(filepath):
            results['config_files'][config_file] = analyze_config_file(filepath)
    
    # Analyze MMKV files
    mmkv_patterns = ['*.mmkv*', '*.ContactMMKV*', '*.CheckPointMMKV*']
    for pattern in mmkv_patterns:
        for filepath in Path(attachments_dir).glob(pattern):
            if filepath.is_file() and not filepath.name.endswith('.crc'):
                results['mmkv_files'][filepath.name] = analyze_config_file(str(filepath))
    
    # Save results
    output_file = os.path.join(os.path.dirname(__file__), 'full_analysis.json')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Analysis complete. Results saved to {output_file}")

if __name__ == '__main__':
    analyze_all_files()
