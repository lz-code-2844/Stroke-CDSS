# utils/llm_client.py

import os
import time
import json
from openai import OpenAI
from typing import Optional, Union, List, Dict, Any
from config.model_config_loader import get_config_loader

# ==================== Configuration Loading ====================
config_loader = get_config_loader()
global_config = config_loader.get_global_config()

# Global configuration
API_KEY = global_config.get('api_key', 'my-secret-key')
MEDIA_BASE_URL = global_config.get('media_base_url', 'http://192.168.8.17:8866')
VIDEO_MAX_PIXELS = global_config.get('video_max_pixels', 163840)
IMAGE_MAX_PIXELS = global_config.get('image_max_pixels', 4096)
VIDEO_FPS = global_config.get('video_fps', 1.0)
MAX_VIDEO_COUNT = global_config.get('max_video_count', 4)
API_TIMEOUT = global_config.get('api_timeout', 120)

# ==================== Client Cache ====================
_client_cache: Dict[str, OpenAI] = {}

def get_client(base_url: str) -> OpenAI:
    """
    Get or create an OpenAI client (with caching)

    Args:
        base_url: API base URL

    Returns:
        OpenAI client instance
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
    Build content payload for vision models (including text and video)

    Args:
        prompt_text: Prompt text
        video_paths: Video path(s) (string or list)
        logger: Logger instance

    Returns:
        Content payload list
    """
    content_payload = [{"type": "text", "text": prompt_text}]

    # Process video paths
    paths_to_process = []
    if video_paths:
        if isinstance(video_paths, list):
            paths_to_process = video_paths
        elif isinstance(video_paths, str):
            paths_to_process = [p.strip() for p in video_paths.split(';') if p.strip()]

    # Video count circuit breaker
    original_count = len(paths_to_process)
    if original_count > MAX_VIDEO_COUNT:
        paths_to_process = paths_to_process[:MAX_VIDEO_COUNT]
        if logger:
            logger.warning(f"    Video count exceeded limit: {original_count} -> {MAX_VIDEO_COUNT}")

    # Build video payload
    video_log_info = []
    for path in paths_to_process:
        full_video_url = path
        # Construct URL
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
        logger.info(f"    [Video Payload] Added {len(video_log_info)} videos (original: {original_count})")

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
    Call LLM using configuration file (recommended)

    Args:
        prompt_text: Prompt text
        agent_name: Agent name (for automatic model selection)
        model_key: Model key (overrides agent_name selection if specified)
        video_path: Video path (optional)
        logger: Logger instance
        **override_params: Override default parameters (e.g. temperature, max_tokens)

    Returns:
        Model response text
    """
    # 1. Determine which model to use
    if model_key is None:
        if agent_name:
            model_key = config_loader.get_agent_model_key(agent_name)
        else:
            model_key = config_loader.config.get('default_model', 'qwen_vl')

    # 2. Get model configuration
    model_config = config_loader.get_model_config(model_key)
    model_name = model_config['name']
    base_url = model_config['base_url']
    model_type = model_config.get('type', 'vision')
    default_params = model_config.get('default_params', {})

    # 3. Merge parameters
    request_params = {**default_params, **override_params}

    if logger:
        logger.info(f"    [Model Selection] Agent: {agent_name or 'N/A'}, Model: {model_name} ({model_type})")

    # 4. Call underlying function
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
    Call remote LLM (supports automatic routing and format adaptation for vision and text models)

    Args:
        prompt_text: Prompt text
        video_path: Video path (optional)
        model_name: Model name
        base_url: API base URL
        model_type: Model type ('vision' or 'text')
        logger: Logger instance
        **request_params: Additional request parameters

    Returns:
        Model response text
    """
    # Backward compatibility (use default config if base_url not specified)
    if model_name is None:
        default_model_key = config_loader.config.get('default_model', 'qwen_vl')
        model_config = config_loader.get_model_config(default_model_key)
        model_name = model_config['name']
        base_url = model_config['base_url']
        model_type = model_config.get('type', 'vision')

    # Get client
    current_client = get_client(base_url)

    # Determine if text-only model
    is_text_model = (model_type == "text")

    # Build messages
    messages = []

    # === Build Content Payload ===
    if is_text_model:
        # Text model: Must send plain string content
        messages.append({"role": "user", "content": prompt_text})
        if logger:
            logger.info(f"    [Text Payload] Model: {model_name}, Prompt Length: {len(prompt_text)}")
    else:
        # Vision model: Must send List[Dict] format
        content_payload = _build_video_content(prompt_text, video_path, logger)
        messages.append({"role": "user", "content": content_payload})

    # === Debug Logging ===
    if logger:
        log_msgs = json.dumps(messages, ensure_ascii=False)
        if len(log_msgs) > 2000:
            log_msgs = log_msgs[:2000] + "...(truncated)"
        # logger.debug(f"    Messages Preview: {log_msgs}")  # Optional debug

    # === Send Request ===
    start_time = time.time()
    try:
        if logger:
            logger.info(f"    >>> Sending request to {model_name} (Timeout {API_TIMEOUT}s)...")

        # Build request parameters
        api_params = {
            "model": model_name,
            "messages": messages,
        }

        # Merge user-provided parameters
        api_params.update(request_params)

        # Send API request
        response = current_client.chat.completions.create(**api_params)

        elapsed = time.time() - start_time
        if logger:
            logger.info(f"    ✓ Success! ({elapsed:.2f}s)")

        content = response.choices[0].message.content

        # Log response
        if logger:
            log_content = str(content)
            if len(log_content) > 200:
                log_content = log_content[:200] + "..."
            logger.info(f"    Content: {log_content.replace(chr(10), ' ')}")

        # === Result Cleaning ===
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
