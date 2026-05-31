# config/model_config_loader.py

import os
import yaml
from typing import Dict, Any, Optional

class ModelConfigLoader:
    """Model Configuration Loader - Handles loading and managing model configs"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration loader

        Args:
            config_path: Configuration file path; if None, uses default path
        """
        if config_path is None:
            # Default configuration file path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "model_config.yaml")

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load YAML configuration file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Config file format error: {e}")

    def get_global_config(self) -> Dict[str, Any]:
        """Get global configuration"""
        return self.config.get('global', {})

    def get_model_config(self, model_key: str) -> Dict[str, Any]:
        """
        Get configuration for specified model

        Args:
            model_key: Model key (e.g. 'qwen_vl', 'gpt_oss')

        Returns:
            Model configuration dictionary
        """
        models = self.config.get('models', {})
        if model_key not in models:
            raise ValueError(f"Model '{model_key}' not defined in config file")
        return models[model_key]

    def get_agent_model_key(self, agent_name: str) -> str:
        """
        Get the model key that an Agent should use

        Args:
            agent_name: Agent name (e.g. 'triage', 'hemorrhage')

        Returns:
            Model key (e.g. 'gpt_oss', 'qwen_vl')
        """
        agent_models = self.config.get('agent_models', {})
        default_model = self.config.get('default_model', 'qwen_vl')

        # Support fuzzy matching (e.g. '01_triage_agent' matches 'triage')
        for key in agent_models:
            if key in agent_name.lower():
                return agent_models[key]

        return default_model

    def get_all_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all model configurations"""
        return self.config.get('models', {})

    def get_agent_models_mapping(self) -> Dict[str, str]:
        """Get Agent-to-model mapping"""
        return self.config.get('agent_models', {})


# Global singleton instance
_config_loader = None

def get_config_loader(config_path: Optional[str] = None) -> ModelConfigLoader:
    """
    Get configuration loader singleton

    Args:
        config_path: Configuration file path (only effective on first call)

    Returns:
        ModelConfigLoader instance
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ModelConfigLoader(config_path)
    return _config_loader
