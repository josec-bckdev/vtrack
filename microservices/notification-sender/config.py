import os
import yaml
from pathlib import Path
from typing import List, Dict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    POLL_INTERVAL: int = 2
    
    # Telegram (will be set via environment variables)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""  # Kept for backward compatibility, but users.yaml takes precedence
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

def load_users() -> List[Dict[str, str]]:
    """
    Load user configuration from users.yaml
    
    Returns:
        List of user dictionaries with keys: name, telegram_id, role
        
    Example:
        [
            {"name": "Admin User", "telegram_id": "123456789", "role": "admin"},
            {"name": "User 2", "telegram_id": "987654321", "role": "user"}
        ]
    """
    # Get the directory where this config.py file is located
    config_dir = Path(__file__).parent
    users_file = config_dir / "users.yaml"
    
    if not users_file.exists():
        raise FileNotFoundError(
            f"users.yaml not found at {users_file}. "
            "Please create it with user configuration."
        )
    
    try:
        with open(users_file, 'r') as f:
            data = yaml.safe_load(f)
        
        users = data.get('users', [])
        
        if not users:
            raise ValueError("No users defined in users.yaml")
        
        # Validate and normalize user data
        validated_users = []
        for user in users:
            if not all(key in user for key in ['name', 'telegram_id', 'role']):
                raise ValueError(f"User missing required fields: {user}")
            
            if user['role'] not in ['admin', 'user']:
                raise ValueError(f"Invalid role '{user['role']}' for user {user['name']}. Must be 'admin' or 'user'.")
            
            validated_users.append({
                'name': str(user['name']),
                'telegram_id': str(user['telegram_id']),  # Convert to string for consistency
                'role': str(user['role']).lower()
            })
        
        return validated_users
        
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing users.yaml: {e}")

settings = Settings()