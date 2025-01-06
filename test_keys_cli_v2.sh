#!/bin/bash

# Function to test a key on a database with various SQLCipher configurations
test_key() {
    local db=$1
    local key=$2
    local page_size=$3
    
    # Create a temporary command file with various PRAGMA combinations
    cat > /tmp/sqlcipher_command.txt << EOL
PRAGMA key = "x'${key}'";
PRAGMA cipher_page_size = ${page_size};
PRAGMA cipher_compatibility = 3;
SELECT name FROM sqlite_master WHERE type='table';

PRAGMA key = "x'${key}'";
PRAGMA cipher_page_size = ${page_size};
PRAGMA cipher_compatibility = 4;
SELECT name FROM sqlite_master WHERE type='table';

PRAGMA key = "x'${key}'";
PRAGMA cipher_page_size = ${page_size};
PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1;
PRAGMA cipher_hmac_algorithm = HMAC_SHA1;
SELECT name FROM sqlite_master WHERE type='table';

PRAGMA key = "x'${key}'";
PRAGMA cipher_page_size = ${page_size};
PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA256;
PRAGMA cipher_hmac_algorithm = HMAC_SHA256;
SELECT name FROM sqlite_master WHERE type='table';

-- Try with raw key
PRAGMA key = '${key}';
PRAGMA cipher_page_size = ${page_size};
SELECT name FROM sqlite_master WHERE type='table';

-- Try with different key formats
PRAGMA key = "pragma key '${key}'";
PRAGMA cipher_page_size = ${page_size};
SELECT name FROM sqlite_master WHERE type='table';

PRAGMA key = "x'${key}'";
PRAGMA cipher_page_size = ${page_size};
PRAGMA kdf_iter = 4000;
SELECT name FROM sqlite_master WHERE type='table';

PRAGMA key = "x'${key}'";
PRAGMA cipher_page_size = ${page_size};
PRAGMA kdf_iter = 64000;
SELECT name FROM sqlite_master WHERE type='table';
EOL

    echo "Testing database: $db with key: $key, page_size: $page_size"
    result=$(sqlcipher "$db" < /tmp/sqlcipher_command.txt 2>&1)
    
    # Check if we got any meaningful results
    if [[ ! $result =~ "Error:" ]] && [[ ! $result =~ "not an SQLite 3 database" ]]; then
        echo "Potential success!"
        echo "Output:"
        echo "$result"
        
        # If we found any tables, save the working configuration
        if [[ $result =~ "table" ]]; then
            echo "Found tables! Saving configuration..."
            echo "Database: $db" >> working_configs.txt
            echo "Key: $key" >> working_configs.txt
            echo "Page size: $page_size" >> working_configs.txt
            echo "Output: $result" >> working_configs.txt
            echo "----------------------------------------" >> working_configs.txt
        fi
    fi
}

# Initialize working_configs.txt
echo "=== Working Configurations ===" > working_configs.txt
date >> working_configs.txt
echo "----------------------------------------" >> working_configs.txt

# Read key candidates
while IFS= read -r key; do
    echo "Testing key: $key"
    
    # Test KeyValue.db
    echo "Testing KeyValue.db..."
    for page_size in 36165 4096 1024; do
        test_key "/home/ubuntu/attachments/KeyValue.db" "$key" "$page_size"
    done
    
    # Test msg_2.db
    echo "Testing msg_2.db..."
    for page_size in 3254 4096 1024; do
        test_key "/home/ubuntu/attachments/msg_2.db" "$key" "$page_size"
    done
done < new_key_candidates.txt

# Cleanup
rm /tmp/sqlcipher_command.txt

echo "Testing complete. Check working_configs.txt for successful configurations."
