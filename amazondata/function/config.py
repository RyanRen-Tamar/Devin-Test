"""Configuration loader for amazondata project."""
import json
import os

def load_config():
    """Load configuration from data.json file."""
    config_path = os.path.join(os.path.dirname(__file__), 'data.json')
    with open(config_path, 'r') as f:
        return json.load(f)

def get_sellersprite_config():
    """Get Sellersprite API configuration."""
    config = load_config()
    return config.get('sellersprite', {})
