# config/model_config_loader.py

import os
import yaml
from typing import Dict, Any, Optional

class ModelConfigLoader:
    """模型配置加载器 - 负责加载和管理模型配置"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置加载器

        Args:
            config_path: 配置文件路径，如果为 None 则使用默认路径
        """
        if config_path is None:
            # 默认配置文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "model_config.yaml")

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载 YAML 配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件未找到: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件格式错误: {e}")

    def get_global_config(self) -> Dict[str, Any]:
        """获取全局配置"""
        return self.config.get('global', {})

    def get_model_config(self, model_key: str) -> Dict[str, Any]:
        """
        获取指定模型的配置

        Args:
            model_key: 模型键名 (如 'qwen_vl', 'gpt_oss')

        Returns:
            模型配置字典
        """
        models = self.config.get('models', {})
        if model_key not in models:
            raise ValueError(f"模型 '{model_key}' 未在配置文件中定义")
        return models[model_key]

    def get_agent_model_key(self, agent_name: str) -> str:
        """
        获取 Agent 应该使用的模型键名

        Args:
            agent_name: Agent 名称 (如 'triage', 'hemorrhage')

        Returns:
            模型键名 (如 'gpt_oss', 'qwen_vl')
        """
        agent_models = self.config.get('agent_models', {})
        default_model = self.config.get('default_model', 'qwen_vl')

        # 支持模糊匹配 (例如 '01_triage_agent' 匹配 'triage')
        for key in agent_models:
            if key in agent_name.lower():
                return agent_models[key]

        return default_model

    def get_all_models(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模型配置"""
        return self.config.get('models', {})

    def get_agent_models_mapping(self) -> Dict[str, str]:
        """获取 Agent 到模型的映射"""
        return self.config.get('agent_models', {})


# 全局单例实例
_config_loader = None

def get_config_loader(config_path: Optional[str] = None) -> ModelConfigLoader:
    """
    获取配置加载器单例

    Args:
        config_path: 配置文件路径 (仅首次调用时有效)

    Returns:
        ModelConfigLoader 实例
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ModelConfigLoader(config_path)
    return _config_loader
