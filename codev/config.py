# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description:
"""
import os
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from codev.version import __version__


ROOT_DIR = os.getenv("CODEV_HOME", os.path.expanduser("~/.codev/"))
# Constants
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/").rstrip("/")
DEFAULT_MODEL = "gpt-4o"
CLI_VERSION = __version__


@dataclass
class AppConfig:
    """Configuration for the CLI application"""
    model: str = DEFAULT_MODEL
    instructions: Optional[str] = None
    debug: bool = False
    theme: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Set default theme if none provided
        if not self.theme:
            self.theme = {
                "user": "blue",
                "assistant": "green",
                "system": "yellow",
                "error": "red",
                "loading": "cyan"
            }


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load configuration from a config file or create default configuration
    
    Args:
        config_path: Path to the configuration file (JSON)
        
    Returns:
        AppConfig instance with loaded or default configuration
    """
    config = AppConfig()

    # Check for environment variable configuration
    if "OPENAI_API_KEY" not in os.environ:
        print("Warning: OPENAI_API_KEY environment variable is not set.")

    # Load from config file if specified
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            # Update config with file data
            if "model" in config_data:
                config.model = config_data["model"]
            if "instructions" in config_data:
                config.instructions = config_data["instructions"]
            if "debug" in config_data:
                config.debug = config_data["debug"]
            if "theme" in config_data:
                config.theme.update(config_data["theme"])

        except Exception as e:
            print(f"Error loading config file: {str(e)}")

    return config
