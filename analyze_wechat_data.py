import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import seaborn as sns
from datetime import datetime

def load_chat_data(export_dir):
    """Load exported chat data for analysis."""
    data_files = list(Path(export_dir).glob("*/message_sample.csv"))
    if not data_files:
        raise FileNotFoundError("No message data files found in export directory")
    
    # Load and combine all message data
    dfs = []
    for file in data_files:
        df = pd.read_csv(file)
        dfs.append(df)
    
    return pd.concat(dfs, ignore_index=True)

def analyze_chat_history(df):
    """Analyze chat history and generate visualizations."""
    # Convert timestamp to datetime
    df['datetime'] = pd.to_datetime(df['createTime'], unit='s')
    
    # 1. Message count by participant
    plt.figure(figsize=(10, 6))
    df['talker'].value_counts().plot(kind='bar')
    plt.title('Message Count by Participant')
    plt.xlabel('Participant')
    plt.ylabel('Number of Messages')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('wechat_export/message_count.png')
    plt.close()
    
    # 2. Message direction (sent vs received)
    plt.figure(figsize=(8, 8))
    df['isSend'].value_counts().plot(kind='pie', labels=['Received', 'Sent'], autopct='%1.1f%%')
    plt.title('Message Direction Distribution')
    plt.savefig('wechat_export/message_direction.png')
    plt.close()
    
    # 3. Message type distribution
    plt.figure(figsize=(8, 6))
    df['type'].value_counts().plot(kind='bar')
    plt.title('Message Type Distribution')
    plt.xlabel('Message Type')
    plt.ylabel('Count')
    plt.tight_layout()
    plt.savefig('wechat_export/message_types.png')
    plt.close()
    
    # Generate summary statistics
    summary = {
        'total_messages': len(df),
        'unique_contacts': df['talker'].nunique(),
        'date_range': f"{df['datetime'].min()} to {df['datetime'].max()}",
        'sent_messages': df['isSend'].sum(),
        'received_messages': len(df) - df['isSend'].sum()
    }
    
    return summary

def main():
    try:
        # Load data
        df = load_chat_data('wechat_export')
        
        # Analyze and generate visualizations
        summary = analyze_chat_history(df)
        
        # Print summary
        print("\nChat History Analysis Summary:")
        print("-" * 30)
        print(f"Total Messages: {summary['total_messages']}")
        print(f"Unique Contacts: {summary['unique_contacts']}")
        print(f"Date Range: {summary['date_range']}")
        print(f"Sent Messages: {summary['sent_messages']}")
        print(f"Received Messages: {summary['received_messages']}")
        print("\nVisualizations have been saved to the wechat_export directory.")
        
    except Exception as e:
        print(f"Error analyzing chat history: {e}")

if __name__ == "__main__":
    main()
