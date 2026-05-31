# Model Configuration System User Guide

## 📋 Table of Contents

1. [Overview](#overview)
2. [Configuration File Structure](#configuration-file-structure)
3. [Quick Start](#quick-start)
4. [Advanced Usage](#advanced-usage)
5. [FAQ](#faq)

---

## Overview

This project supports a flexible model configuration system that allows you to specify different LLM models for each Agent.

### Key Features

- ✅ **Configuration-Driven**: Centrally manage all model configurations through a YAML file
- ✅ **Automatic Routing**: Automatically select the appropriate model based on the Agent name
- ✅ **Multi-Model Support**: Simultaneously supports vision models (Qwen-VL) and text-only models (GPT-OSS)
- ✅ **Flexible Override**: Supports dynamic model specification at runtime
- ✅ **Parameter Customization**: Configure independent parameters (temperature, max_tokens, etc.) for each model

---

## Configuration File Structure

The configuration file is located at: `config/model_config.yaml`

### 1. Global Configuration

```yaml
global:
  api_key: "my-secret-key"
  api_timeout: 120
  media_base_url: "http://192.168.8.17:8866"

  # Video/image parameters
  video_max_pixels: 163840  # 32*32*160
  image_max_pixels: 4096    # 64*64
  video_fps: 1.0
  max_video_count: 4
```

### 2. Model Definition

```yaml
models:
  # Vision model (Qwen-VL)
  qwen_vl:
    name: "qwen3vl_235b_2507"
    base_url: "http://192.168.8.17:9011/v1"
    type: "vision"
    default_params:
      temperature: 0.01
      max_tokens: 4096
      extra_body:
        mm_processor_kwargs:
          fps: 1
          do_sample_frames: true

  # Text-only model (GPT-OSS)
  gpt_oss:
    name: "gpt_oss_120b"
    base_url: "http://192.168.8.17:9001/v1"
    type: "text"
    default_params:
      temperature: 0.01
      max_tokens: 8192
```

### 3. Agent Model Mapping

```yaml
agent_models:
  # Text-only Agents
  triage: gpt_oss
  time_calc: gpt_oss
  summary: gpt_oss

  # Vision Agents
  hemorrhage: qwen_vl
  ncct_imaging: qwen_vl
  aneurysm: qwen_vl
```

---

## Quick Start

### Method 1: Use Default Configuration (Recommended)

The Agent automatically selects the model based on its name:

```python
from agents.react_agent import ReActClinicalAgent

# Automatically uses the mapping from the configuration file
agent = ReActClinicalAgent("01_triage_agent.md")
result = agent.run(video_paths, context, logger)
```

### Method 2: Specify Model Key

```python
# Force use of GPT-OSS model
agent = ReActClinicalAgent("01_triage_agent.md", model_key="gpt_oss")

# Force use of Qwen-VL model
agent = ReActClinicalAgent("02_hemorrhage_agent.md", model_key="qwen_vl")
```

### Method 3: Direct LLM Call

```python
from utils.llm_client import call_llm_with_config

# Automatic selection based on agent name
response = call_llm_with_config(
    prompt_text="Analyze this case...",
    agent_name="triage",
    logger=logger
)

# Specify model key
response = call_llm_with_config(
    prompt_text="Analyze this image...",
    model_key="qwen_vl",
    video_path="/path/to/video.mp4",
    logger=logger
)
```

---

## Advanced Usage

### 1. Adding a New Model

Add to `config/model_config.yaml`:

```yaml
models:
  # New model
  claude_sonnet:
    name: "claude-sonnet-4"
    base_url: "https://api.anthropic.com/v1"
    type: "text"
    default_params:
      temperature: 0.7
      max_tokens: 4096
```

### 2. Assign a New Model to an Agent

```yaml
agent_models:
  director: claude_sonnet  # Director Agent uses Claude
  summary: claude_sonnet   # Summary Agent uses Claude
```

### 3. Override Parameters at Runtime

```python
response = call_llm_with_config(
    prompt_text="...",
    agent_name="triage",
    temperature=0.9,      # Override default temperature
    max_tokens=2048,      # Override default max_tokens
    logger=logger
)
```

### 4. Using Environment Variables

```python
import os
os.environ['MODEL_CONFIG_PATH'] = '/custom/path/model_config.yaml'

from config.model_config_loader import get_config_loader
config_loader = get_config_loader(os.environ['MODEL_CONFIG_PATH'])
```

---

## FAQ

### Q1: How to check which model is currently in use?

Check the log output:
```
[Model Selection] Agent: triage, Model: gpt_oss_120b (text)
```

### Q2: How to switch models for all Agents?

Modify `default_model` in `config/model_config.yaml`:

```yaml
default_model: gpt_oss  # Use GPT-OSS by default
```

### Q3: What is the difference between vision models and text models?

- **Vision model** (`type: vision`): Supports image/video input, uses `List[Dict]` format for content
- **Text model** (`type: text`): Only supports text input, uses plain string content

The system automatically handles format differences.

### Q4: How to debug model calls?

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Q5: Do I need to restart after modifying the configuration file?

Yes, the configuration file is loaded when the program starts. You need to restart the application after making changes.

---

## Configuration Examples

### Example 1: Using Multiple Models in Combination

```yaml
agent_models:
  # Agents requiring fast responses use lightweight models
  triage: gpt_oss
  time_calc: gpt_oss

  # Agents performing complex analysis use powerful models
  hemorrhage: qwen_vl
  director: claude_sonnet
```

### Example 2: Development/Production Environment Switching

Development environment (`config/model_config.dev.yaml`):
```yaml
models:
  qwen_vl:
    base_url: "http://localhost:9011/v1"
```

Production environment (`config/model_config.prod.yaml`):
```yaml
models:
  qwen_vl:
    base_url: "http://192.168.8.17:9011/v1"
```

---

## Technical Support

If you have questions, please refer to:
- Configuration file: `config/model_config.yaml`
- Source code: `utils/llm_client.py`
- Configuration loader: `config/model_config_loader.py`
