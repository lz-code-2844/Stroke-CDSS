# 模型配置系统使用指南

## 📋 目录

1. [概述](#概述)
2. [配置文件结构](#配置文件结构)
3. [快速开始](#快速开始)
4. [高级用法](#高级用法)
5. [常见问题](#常见问题)

---

## 概述

本项目支持灵活的模型配置系统，允许你为每个 Agent 指定使用不同的 LLM 模型。

### 主要特性

- ✅ **配置驱动**: 通过 YAML 文件集中管理所有模型配置
- ✅ **自动路由**: 根据 Agent 名称自动选择合适的模型
- ✅ **多模型支持**: 同时支持视觉模型 (Qwen-VL) 和纯文本模型 (GPT-OSS)
- ✅ **灵活覆盖**: 支持运行时动态指定模型
- ✅ **参数定制**: 为每个模型配置独立的参数 (temperature, max_tokens 等)

---

## 配置文件结构

配置文件位于: `config/model_config.yaml`

### 1. 全局配置

```yaml
global:
  api_key: "my-secret-key"
  api_timeout: 120
  media_base_url: "http://192.168.8.17:8866"

  # 视频/图像参数
  video_max_pixels: 163840  # 32*32*160
  image_max_pixels: 4096    # 64*64
  video_fps: 1.0
  max_video_count: 4
```

### 2. 模型定义

```yaml
models:
  # 视觉模型 (Qwen-VL)
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

  # 纯文本模型 (GPT-OSS)
  gpt_oss:
    name: "gpt_oss_120b"
    base_url: "http://192.168.8.17:9001/v1"
    type: "text"
    default_params:
      temperature: 0.01
      max_tokens: 8192
```

### 3. Agent 模型映射

```yaml
agent_models:
  # 纯文本类 Agent
  triage: gpt_oss
  time_calc: gpt_oss
  summary: gpt_oss

  # 视觉类 Agent
  hemorrhage: qwen_vl
  ncct_imaging: qwen_vl
  aneurysm: qwen_vl
```

---

## 快速开始

### 方式 1: 使用默认配置 (推荐)

Agent 会根据名称自动选择模型:

```python
from agents.react_agent import ReActClinicalAgent

# 自动使用配置文件中的映射
agent = ReActClinicalAgent("01_triage_agent.md")
result = agent.run(video_paths, context, logger)
```

### 方式 2: 指定模型键名

```python
# 强制使用 GPT-OSS 模型
agent = ReActClinicalAgent("01_triage_agent.md", model_key="gpt_oss")

# 强制使用 Qwen-VL 模型
agent = ReActClinicalAgent("02_hemorrhage_agent.md", model_key="qwen_vl")
```

### 方式 3: 直接调用 LLM

```python
from utils.llm_client import call_llm_with_config

# 根据 agent 名称自动选择
response = call_llm_with_config(
    prompt_text="分析这个病例...",
    agent_name="triage",
    logger=logger
)

# 指定模型键名
response = call_llm_with_config(
    prompt_text="分析这个影像...",
    model_key="qwen_vl",
    video_path="/path/to/video.mp4",
    logger=logger
)
```

---

## 高级用法

### 1. 添加新模型

在 `config/model_config.yaml` 中添加:

```yaml
models:
  # 新增模型
  claude_sonnet:
    name: "claude-sonnet-4"
    base_url: "https://api.anthropic.com/v1"
    type: "text"
    default_params:
      temperature: 0.7
      max_tokens: 4096
```

### 2. 为 Agent 指定新模型

```yaml
agent_models:
  director: claude_sonnet  # Director Agent 使用 Claude
  summary: claude_sonnet   # Summary Agent 使用 Claude
```

### 3. 运行时覆盖参数

```python
response = call_llm_with_config(
    prompt_text="...",
    agent_name="triage",
    temperature=0.9,      # 覆盖默认 temperature
    max_tokens=2048,      # 覆盖默认 max_tokens
    logger=logger
)
```

### 4. 使用环境变量

```python
import os
os.environ['MODEL_CONFIG_PATH'] = '/custom/path/model_config.yaml'

from config.model_config_loader import get_config_loader
config_loader = get_config_loader(os.environ['MODEL_CONFIG_PATH'])
```

---

## 常见问题

### Q1: 如何查看当前使用的模型?

查看日志输出:
```
[模型选择] Agent: triage, Model: gpt_oss_120b (text)
```

### Q2: 如何为所有 Agent 切换模型?

修改 `config/model_config.yaml` 中的 `default_model`:

```yaml
default_model: gpt_oss  # 默认使用 GPT-OSS
```

### Q3: 视觉模型和文本模型有什么区别?

- **视觉模型** (`type: vision`): 支持图像/视频输入，使用 `List[Dict]` 格式的 content
- **文本模型** (`type: text`): 仅支持文本输入，使用纯字符串 content

系统会自动处理格式差异。

### Q4: 如何调试模型调用?

启用详细日志:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Q5: 配置文件修改后需要重启吗?

是的，配置文件在程序启动时加载。修改后需要重启应用。

---

## 配置示例

### 示例 1: 混合使用多个模型

```yaml
agent_models:
  # 快速响应的 Agent 使用轻量模型
  triage: gpt_oss
  time_calc: gpt_oss

  # 复杂分析的 Agent 使用强大模型
  hemorrhage: qwen_vl
  director: claude_sonnet
```

### 示例 2: 开发/生产环境切换

开发环境 (`config/model_config.dev.yaml`):
```yaml
models:
  qwen_vl:
    base_url: "http://localhost:9011/v1"
```

生产环境 (`config/model_config.prod.yaml`):
```yaml
models:
  qwen_vl:
    base_url: "http://192.168.8.17:9011/v1"
```

---

## 技术支持

如有问题，请查看:
- 配置文件: `config/model_config.yaml`
- 源代码: `utils/llm_client.py`
- 配置加载器: `config/model_config_loader.py`
