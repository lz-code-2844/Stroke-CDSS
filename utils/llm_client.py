# utils/llm_client.py

import os
import time
import json
from openai import OpenAI
from typing import Optional, Union, List, Dict, Any
from config.model_config_loader import get_config_loader

# ==================== 配置加载 ====================
config_loader = get_config_loader()
global_config = config_loader.get_global_config()

# 全局配置
API_KEY = global_config.get('api_key', 'my-secret-key')
MEDIA_BASE_URL = global_config.get('media_base_url', 'http://192.168.8.17:8866')
VIDEO_MAX_PIXELS = global_config.get('video_max_pixels', 163840)
IMAGE_MAX_PIXELS = global_config.get('image_max_pixels', 4096)
VIDEO_FPS = global_config.get('video_fps', 1.0)
MAX_VIDEO_COUNT = global_config.get('max_video_count', 4)
API_TIMEOUT = global_config.get('api_timeout', 120)

# ==================== 客户端缓存 ====================
_client_cache: Dict[str, OpenAI] = {}

def get_client(base_url: str) -> OpenAI:
    """
    获取或创建 OpenAI 客户端 (带缓存)

    Args:
        base_url: API 基础 URL

    Returns:
        OpenAI 客户端实例
    """
    if base_url not in _client_cache:
        _client_cache[base_url] = OpenAI(
            base_url=base_url,
            api_key=API_KEY,
            timeout=API_TIMEOUT
        )
    return _client_cache[base_url]


def _build_video_content(
    prompt_text: str,
    video_paths: Optional[Union[str, List[str]]],
    logger=None
) -> List[Dict[str, Any]]:
    """
    构建视觉模型的 content payload (包含文本和视频)

    Args:
        prompt_text: 提示文本
        video_paths: 视频路径 (字符串或列表)
        logger: 日志记录器

    Returns:
        Content payload 列表
    """
    content_payload = [{"type": "text", "text": prompt_text}]

    # 处理视频路径
    paths_to_process = []
    if video_paths:
        if isinstance(video_paths, list):
            paths_to_process = video_paths
        elif isinstance(video_paths, str):
            paths_to_process = [p.strip() for p in video_paths.split(';') if p.strip()]

    # 数量熔断
    original_count = len(paths_to_process)
    if original_count > MAX_VIDEO_COUNT:
        paths_to_process = paths_to_process[:MAX_VIDEO_COUNT]
        if logger:
            logger.warning(f"    视频数量超限: {original_count} -> {MAX_VIDEO_COUNT}")

    # 构建视频 payload
    video_log_info = []
    for path in paths_to_process:
        full_video_url = path
        # 拼接 URL
        if not path.startswith("http"):
            clean_rel_path = path.lstrip('/')
            full_video_url = f"{MEDIA_BASE_URL.rstrip('/')}/{clean_rel_path}"

        video_payload = {
            "type": "video_url",
            "video_url": {"url": full_video_url},
            "total_pixels": VIDEO_MAX_PIXELS,
            "fps": VIDEO_FPS
        }
        content_payload.append(video_payload)
        video_log_info.append(full_video_url)

    if logger and video_log_info:
        logger.info(f"    [Video Payload] 添加 {len(video_log_info)} 个视频 (原始: {original_count})")

    return content_payload


def call_llm_with_config(
    prompt_text: str,
    agent_name: Optional[str] = None,
    model_key: Optional[str] = None,
    video_path: Optional[Union[str, List[str]]] = None,
    logger=None,
    **override_params
) -> str:
    """
    使用配置文件调用 LLM (推荐使用此函数)

    Args:
        prompt_text: 提示文本
        agent_name: Agent 名称 (用于自动选择模型)
        model_key: 模型键名 (如果指定则覆盖 agent_name 的选择)
        video_path: 视频路径 (可选)
        logger: 日志记录器
        **override_params: 覆盖默认参数 (如 temperature, max_tokens)

    Returns:
        模型响应文本
    """
    # 1. 确定使用哪个模型
    if model_key is None:
        if agent_name:
            model_key = config_loader.get_agent_model_key(agent_name)
        else:
            model_key = config_loader.config.get('default_model', 'qwen_vl')

    # 2. 获取模型配置
    model_config = config_loader.get_model_config(model_key)
    model_name = model_config['name']
    base_url = model_config['base_url']
    model_type = model_config.get('type', 'vision')
    default_params = model_config.get('default_params', {})

    # 3. 合并参数
    request_params = {**default_params, **override_params}

    if logger:
        logger.info(f"    [模型选择] Agent: {agent_name or 'N/A'}, Model: {model_name} ({model_type})")

    # 4. 调用底层函数
    return call_video_model(
        prompt_text=prompt_text,
        video_path=video_path,
        model_name=model_name,
        base_url=base_url,
        model_type=model_type,
        logger=logger,
        **request_params
    )


def call_video_model(
    prompt_text: str,
    video_path: Optional[Union[str, List[str]]] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    model_type: str = "vision",
    logger=None,
    **request_params
) -> str:
    """
    调用远程大模型 (支持视觉模型与纯文本模型的自动路由与格式适配)

    Args:
        prompt_text: 提示文本
        video_path: 视频路径 (可选)
        model_name: 模型名称
        base_url: API 基础 URL
        model_type: 模型类型 ('vision' 或 'text')
        logger: 日志记录器
        **request_params: 额外的请求参数

    Returns:
        模型响应文本
    """
    # 兼容旧版调用 (如果没有指定 base_url，使用默认配置)
    if model_name is None:
        default_model_key = config_loader.config.get('default_model', 'qwen_vl')
        model_config = config_loader.get_model_config(default_model_key)
        model_name = model_config['name']
        base_url = model_config['base_url']
        model_type = model_config.get('type', 'vision')

    # 获取客户端
    current_client = get_client(base_url)

    # 判断是否为纯文本模型
    is_text_model = (model_type == "text")

    # 构建消息
    messages = []

    # === 构建 Content Payload ===
    if is_text_model:
        # 纯文本模型: 必须发送纯字符串 Content
        messages.append({"role": "user", "content": prompt_text})
        if logger:
            logger.info(f"    [Text Payload] Model: {model_name}, Prompt Length: {len(prompt_text)}")
    else:
        # 视觉模型: 必须发送 List[Dict] 格式
        content_payload = _build_video_content(prompt_text, video_path, logger)
        messages.append({"role": "user", "content": content_payload})

    # === 调试日志 ===
    if logger:
        log_msgs = json.dumps(messages, ensure_ascii=False)
        if len(log_msgs) > 2000:
            log_msgs = log_msgs[:2000] + "...(truncated)"
        # logger.debug(f"    Messages Preview: {log_msgs}")  # 可选调试

    # === 发送请求 ===
    start_time = time.time()
    try:
        if logger:
            logger.info(f"    >>> 发送请求至 {model_name} (Timeout {API_TIMEOUT}s)...")

        # 构建请求参数
        api_params = {
            "model": model_name,
            "messages": messages,
        }

        # 合并用户传入的参数
        api_params.update(request_params)

        # 发送 API 请求
        response = current_client.chat.completions.create(**api_params)

        elapsed = time.time() - start_time
        if logger:
            logger.info(f"    ✓ 成功! ({elapsed:.2f}s)")

        content = response.choices[0].message.content

        # 记录响应
        if logger:
            log_content = str(content)
            if len(log_content) > 200:
                log_content = log_content[:200] + "..."
            logger.info(f"    Content: {log_content.replace(chr(10), ' ')}")

        # === 结果清洗 ===
        if isinstance(content, list):
            text_parts = [part['text'] for part in content if part.get('type') == 'text']
            return "\n".join(text_parts).strip()

        return str(content).strip()

    except Exception as e:
        elapsed = time.time() - start_time
        if logger:
            logger.error(f"    ❌ [API Error] ({elapsed:.2f}s): {e}")
            logger.error(f"    Exception Type: {type(e).__name__}")
        return f"ERROR: {e}"
