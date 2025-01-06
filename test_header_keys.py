#!/usr/bin/env python3
import os
import struct
import binascii
import subprocess
import tempfile

def extract_header_key(filepath, size=32):
    """Extract the first 32 bytes from file header as potential key."""
    with open(filepath, 'rb') as f:
        header = f.read(size)
    return binascii.hexlify(header).decode('ascii')

def test_sqlcipher_key(db_path, key, page_size):
    """Test SQLCipher with a key using different formats and configurations."""
    # Create temporary SQL commands file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        commands = [
            # Try original header as key
            f"PRAGMA key = \"x'{key}'\";\n"
            f"PRAGMA cipher_page_size = {page_size};\n"
            "SELECT name FROM sqlite_master;\n",
            
            # Try header as raw key
            f"PRAGMA key = '{key}';\n"
            f"PRAGMA cipher_page_size = {page_size};\n"
            "SELECT name FROM sqlite_master;\n",
            
            # Try with SHA256(header) as key
            f"PRAGMA key = \"x'{key}'\";\n"
            f"PRAGMA cipher_page_size = {page_size};\n"
            "PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA256;\n"
            "SELECT name FROM sqlite_master;\n",
            
            # Try with different KDF iteration count
            f"PRAGMA key = \"x'{key}'\";\n"
            f"PRAGMA cipher_page_size = {page_size};\n"
            "PRAGMA kdf_iter = 4000;\n"
            "SELECT name FROM sqlite_master;\n",
            
            # Try with header as salt
            "PRAGMA cipher_default_kdf_iter = 4000;\n"
            f"PRAGMA cipher_salt = \"x'{key}'\";\n"
            f"PRAGMA key = \"x'{key}'\";\n"
            f"PRAGMA cipher_page_size = {page_size};\n"
            "SELECT name FROM sqlite_master;\n"
        ]
        f.write('\n'.join(commands))
        sql_file = f.name
    
    try:
        # Run SQLCipher with the commands
        result = subprocess.run(['sqlcipher', db_path], 
                              input=open(sql_file, 'r').read(),
                              capture_output=True, 
                              text=True)
        
        # Check if we got any meaningful results
        if "Error:" not in result.stderr and "not an SQLite 3 database" not in result.stderr:
            if result.stdout.strip():
                print(f"\nPotential success with {db_path}!")
                print(f"Key: {key}")
                print(f"Page size: {page_size}")
                print("Output:")
                print(result.stdout)
                
                # Save working configuration
                with open('header_key_results.txt', 'a') as f:
                    f.write(f"\nSuccessful configuration for {db_path}:\n")
                    f.write(f"Key: {key}\n")
                    f.write(f"Page size: {page_size}\n")
                    f.write("Output:\n")
                    f.write(result.stdout)
                    f.write("-" * 50 + "\n")
                
                return True
    except Exception as e:
        print(f"Error testing key: {str(e)}")
    finally:
        os.unlink(sql_file)
    
    return False

def main():
    print("=== Testing Header-Based Keys ===")
    print(f"Timestamp: {os.popen('date').read().strip()}")
    print("=" * 50)
    
    # Initialize results file
    with open('header_key_results.txt', 'w') as f:
        f.write("=== Header-Based Key Test Results ===\n")
        f.write(f"Timestamp: {os.popen('date').read().strip()}\n")
        f.write("=" * 50 + "\n")
    
    base_dir = '/home/ubuntu/attachments'
    databases = [
        ('msg_2.db', 3254),
        ('KeyValue.db', 36165)
    ]
    
    for db_name, page_size in databases:
        db_path = os.path.join(base_dir, db_name)
        if not os.path.exists(db_path):
            print(f"\nFile not found: {db_name}")
            continue
        
        print(f"\nAnalyzing: {db_name}")
        print("-" * 40)
        
        # Extract header key
        header_key = extract_header_key(db_path)
        print(f"Header key: {header_key}")
        
        # Test the header key directly
        test_sqlcipher_key(db_path, header_key, page_size)
        
        # Try reversing the bytes
        reversed_key = ''.join(reversed([header_key[i:i+2] for i in range(0, len(header_key), 2)]))
        print(f"Testing reversed key: {reversed_key}")
        test_sqlcipher_key(db_path, reversed_key, page_size)
        
        # Try using first/last 16 bytes
        if len(header_key) >= 32:
            first_half = header_key[:32]
            last_half = header_key[-32:]
            print(f"Testing first 16 bytes: {first_half}")
            test_sqlcipher_key(db_path, first_half, page_size)
            print(f"Testing last 16 bytes: {last_half}")
            test_sqlcipher_key(db_path, last_half, page_size)

if __name__ == '__main__':
    main()
