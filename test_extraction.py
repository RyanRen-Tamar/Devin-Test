import os
from wechat_extractor import WeChatExtractor

def main():
    # Initialize extractor with custom path for Mac
    wechat_path = '/Users/lincifeng/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat'
    print(f"Using WeChat path: {wechat_path}")
    extractor = WeChatExtractor(custom_path=wechat_path)
    
    # Create output directory
    os.makedirs('wechat_export', exist_ok=True)
    
    # Find version path and list database files
    if extractor.find_version_path():
        print("\nListing database files...")
        db_files = extractor.list_database_files()
        
        # Try to extract encryption key
        print("\nAttempting to extract encryption key...")
        potential_keys = extractor.extract_key_from_keyvalue()
        if potential_keys:
            print(f"Found {len(potential_keys)} potential keys")
        
        # Process each database file
        print("\nProcessing database files...")
        for db_path in db_files:
            if "msg_" in os.path.basename(db_path):
                print(f"\nProcessing {os.path.basename(db_path)}...")
                # Try without key first
                messages = extractor.extract_messages(db_path)
                
                # If that fails and we have potential keys, try with keys
                if messages is None and potential_keys:
                    for key in potential_keys:
                        messages = extractor.extract_messages(db_path, key)
                        if messages is not None:
                            print(f"Successfully decrypted with key")
                            break
                
                if messages is not None:
                    # Export the messages
                    output_file = f"wechat_export/{os.path.basename(db_path)}_messages.csv"
                    extractor.export_data(messages, output_file)
                    print(f"Exported messages to {output_file}")
                else:
                    print(f"Could not extract messages from {db_path}")
        
        # Process MessageTemp directory
        print("\nProcessing MessageTemp directory...")
        sessions = extractor.process_message_temp()
        if sessions:
            print(f"Found {len(sessions)} chat sessions")
    else:
        print("Could not find WeChat version path")

if __name__ == "__main__":
    main()
