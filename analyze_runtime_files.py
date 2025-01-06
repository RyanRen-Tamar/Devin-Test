import os
import json
import hashlib
import binascii
import time
from pathlib import Path
from typing import Dict, List, Set, Any

class RuntimeAnalyzer:
    def __init__(self):
        self.known_files: Set[str] = set()
        self.new_files: Set[str] = set()
        self.file_changes: Dict[str, Dict[str, Any]] = {}
        self.interesting_patterns = [
            b'SQLite',
            b'WeChat',
            b'key',
            b'KEY',
            b'salt',
            b'iv',
            b'cipher',
            b'encrypt',
            b'auth',
            b'token',
            b'session'
        ]

    def scan_directory(self, directory: str) -> Set[str]:
        """Scan a directory and return set of files with metadata"""
        files = set()
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                try:
                    if os.path.isfile(full_path):
                        files.add(full_path)
                except (PermissionError, FileNotFoundError):
                    continue
        return files

    def get_file_metadata(self, filepath: str) -> Dict[str, Any]:
        """Get metadata for a file including size and modification time"""
        try:
            stat = os.stat(filepath)
            return {
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'ctime': stat.st_ctime
            }
        except (PermissionError, FileNotFoundError):
            return {}

    def analyze_file_content(self, filepath: str, max_size: int = 1024*1024) -> Dict[str, Any]:
        """Analyze file content for interesting patterns"""
        try:
            file_size = os.path.getsize(filepath)
            if file_size > max_size:
                return {'error': 'File too large'}

            with open(filepath, 'rb') as f:
                content = f.read()

            analysis = {
                'size': file_size,
                'md5': hashlib.md5(content).hexdigest(),
                'patterns': [],
                'potential_keys': []
            }

            # Look for interesting patterns
            for pattern in self.interesting_patterns:
                positions = []
                pos = 0
                while True:
                    pos = content.find(pattern, pos)
                    if pos == -1:
                        break
                    positions.append(pos)
                    pos += 1
                if positions:
                    analysis['patterns'].append({
                        'pattern': pattern.decode('utf-8', errors='ignore'),
                        'positions': positions
                    })

            # Look for potential key-like sequences
            for i in range(len(content) - 31):
                chunk = content[i:i+32]
                # Check if chunk looks like a key (hex string, base64, etc)
                try:
                    hex_chunk = binascii.hexlify(chunk).decode()
                    if all(c in '0123456789abcdefABCDEF' for c in hex_chunk):
                        analysis['potential_keys'].append({
                            'offset': i,
                            'hex': hex_chunk
                        })
                except:
                    continue

            return analysis
        except (PermissionError, FileNotFoundError):
            return {'error': 'Access denied'}
        except Exception as e:
            return {'error': str(e)}

    def monitor_directories(self, directories: List[str], interval: float = 1.0) -> Dict[str, Any]:
        """Monitor directories for new files and changes"""
        print(f"Monitoring directories: {directories}")
        
        # Initial scan
        for directory in directories:
            self.known_files.update(self.scan_directory(directory))
        
        initial_metadata = {}
        for filepath in self.known_files:
            initial_metadata[filepath] = self.get_file_metadata(filepath)
        
        results = {
            'new_files': [],
            'modified_files': [],
            'interesting_files': []
        }
        
        try:
            while True:
                time.sleep(interval)
                
                # Scan for new and modified files
                current_files = set()
                for directory in directories:
                    current_files.update(self.scan_directory(directory))
                
                # Check for new files
                new_files = current_files - self.known_files
                for filepath in new_files:
                    print(f"New file detected: {filepath}")
                    metadata = self.get_file_metadata(filepath)
                    analysis = self.analyze_file_content(filepath)
                    if analysis.get('patterns') or analysis.get('potential_keys'):
                        results['interesting_files'].append({
                            'file': filepath,
                            'metadata': metadata,
                            'analysis': analysis
                        })
                    results['new_files'].append({
                        'file': filepath,
                        'metadata': metadata
                    })
                
                # Check for modified files
                for filepath in current_files & self.known_files:
                    current_metadata = self.get_file_metadata(filepath)
                    if filepath in initial_metadata:
                        if current_metadata.get('mtime') != initial_metadata[filepath].get('mtime'):
                            print(f"Modified file detected: {filepath}")
                            analysis = self.analyze_file_content(filepath)
                            if analysis.get('patterns') or analysis.get('potential_keys'):
                                results['interesting_files'].append({
                                    'file': filepath,
                                    'metadata': current_metadata,
                                    'analysis': analysis
                                })
                            results['modified_files'].append({
                                'file': filepath,
                                'metadata': current_metadata
                            })
                
                # Update known files and metadata
                self.known_files = current_files
                initial_metadata = {f: self.get_file_metadata(f) for f in current_files}
                
                # Save results periodically
                with open('runtime_analysis.json', 'w') as f:
                    json.dump(results, f, indent=2)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
            return results

def main():
    analyzer = RuntimeAnalyzer()
    
    # Define directories to monitor
    base_dir = "/Users/lincifeng/Library/Containers/com.tencent.xinWeChat/Data"
    directories = [
        os.path.join(base_dir, "Library/Caches"),
        os.path.join(base_dir, "Library/Logs"),
        os.path.join(base_dir, "tmp"),
        "/private/var/folders"  # System temp directories
    ]
    
    print("Starting runtime file analysis...")
    print("Press Ctrl+C to stop monitoring")
    
    results = analyzer.monitor_directories(directories)
    
    # Save final results
    with open('runtime_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Extract potential keys
    keys = set()
    for file_info in results['interesting_files']:
        analysis = file_info.get('analysis', {})
        for key_info in analysis.get('potential_keys', []):
            keys.add(key_info['hex'])
    
    # Save potential keys
    if keys:
        with open('runtime_derived_keys.txt', 'w') as f:
            for key in keys:
                f.write(f"{key}\n")
        print(f"Found {len(keys)} potential keys")
    
    print("Analysis complete. Results saved to runtime_analysis.json")
    if keys:
        print("Potential keys saved to runtime_derived_keys.txt")

if __name__ == '__main__':
    main()
