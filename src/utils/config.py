"""
Configuration management for the competition auto-entry system.
"""

import json
import os
from typing import Dict, Any, List
from pathlib import Path
from pydantic import BaseModel, validator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class PersonalInfo(BaseModel):
    """Personal information for form filling."""
    first_name: str
    last_name: str
    email: str
    phone: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    date_of_birth: str = ""  # YYYY-MM-DD format


class SocialMediaCredentials(BaseModel):
    """Social media login credentials."""
    instagram_username: str = ""
    instagram_password: str = ""
    twitter_username: str = ""
    twitter_password: str = ""
    facebook_username: str = ""
    facebook_password: str = ""
    youtube_username: str = ""
    youtube_password: str = ""
    bluesky_username: str = ""
    bluesky_password: str = ""


class ScrapingSettings(BaseModel):
    """Web scraping configuration."""
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    delay_min: float = 1.0
    delay_max: float = 3.0
    timeout: int = 30
    retries: int = 3
    headless: bool = True


class FilterSettings(BaseModel):
    """Competition filtering settings."""
    min_age: int = 18
    max_age: int = 99
    allowed_countries: List[str] = ["US", "UK", "CA", "AU", "NZ"]
    excluded_keywords: List[str] = ["paid", "purchase", "buy", "subscription"]
    required_keywords: List[str] = ["free", "no purchase"]


class AppConfig(BaseModel):
    """Main application configuration."""
    personal_info: PersonalInfo
    social_media: SocialMediaCredentials
    scraping: ScrapingSettings = ScrapingSettings()
    filters: FilterSettings = FilterSettings()
    aggregator_urls: List[str] = []
    max_daily_entries: int = 50
    log_level: str = "INFO"
    database_path: str = "data/competitions.db"


def load_config(config_path: str = "config/config.json") -> AppConfig:
    """
    Load configuration from JSON file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        AppConfig object with loaded configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Please copy config/config.example.json to {config_path} and fill in your details."
        )
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # Replace environment variables in config
        config_data = _replace_env_vars(config_data)
        
        return AppConfig(**config_data)
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")
    except Exception as e:
        raise ValueError(f"Error loading config: {e}")


def _replace_env_vars(data: Any) -> Any:
    """
    Recursively replace environment variable placeholders in config data.
    
    Args:
        data: Configuration data (dict, list, or string)
        
    Returns:
        Data with environment variables replaced
    """
    if isinstance(data, dict):
        return {k: _replace_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_replace_env_vars(item) for item in data]
    elif isinstance(data, str) and data.startswith("${") and data.endswith("}"):
        env_var = data[2:-1]
        return os.getenv(env_var, data)
    else:
        return data


def save_config(config: AppConfig, config_path: str = "config/config.json") -> None:
    """
    Save configuration to JSON file.
    
    Args:
        config: AppConfig object to save
        config_path: Path to save configuration file
    """
    config_file = Path(config_path)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config.dict(), f, indent=2, ensure_ascii=False)
