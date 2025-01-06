#!/bin/bash

# Function to test a key on a database
test_key() {
    local db=$1
    local key=$2
    local page_size=$3
    
    # Create a temporary command file
    echo ".tables" > /tmp/sqlcipher_command.txt
    
    # Try to read the database with the current key and page size
    result=$(sqlcipher -cmd "PRAGMA key = \"x'$key'\";" \
                       -cmd "PRAGMA cipher_page_size = $page_size;" \
                       "$db" < /tmp/sqlcipher_command.txt 2>&1)
    
    # Check if the command succeeded
    if [[ ! $result =~ "Error:" ]] && [[ ! $result =~ "not an SQLite 3 database" ]]; then
        echo "Success with key: $key, page_size: $page_size"
        echo "Tables found: $result"
        return 0
    fi
    return 1
}

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

rm /tmp/sqlcipher_command.txt
