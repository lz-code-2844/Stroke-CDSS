# 模型配置系统 - 快速开始

## 🎯 核心改进

本次升级实现了**配置驱动的模型选择系统**，让你可以灵活地为每个 Agent 指定使用不同的 LLM 模型。

---

## 📁 新增文件

```
agent_project_v6/
├── config/
│   ├── __init__.py                    # 配置模块初始化
│   ├── model_config.yaml              # 模型配置文件 (核心)
│   └── model_config_loader.py         # 配置加载器
├── docs/
│   ├── MODEL_CONFIG_GUIDE.md          # 详细使用指南
│   └── MODEL_CONFIG_QUICKSTART.md     # 本文件
├── examples/
│   └── model_config_example.py        # 使用示例
└── utils/
    └── llm_client.py                  # 改进后的 LLM 客户端
```

---

## 🚀 快速使用

### 1. 修改配置文件

编辑 `config/model_config.yaml`:

```yaml
agent_models:
  # 为每个 Agent 指定模型
  triage: gpt_oss          # Triage 使用 GPT-OSS
  hemorrhage: qwen_vl      # Hemorrhage 使用 Qwen-VL
  director: gpt_oss        # Director 使用 GPT-OSS
```

### 2. 使用 Agent (自动路由)

```python
from agents.react_agent import ReActClinicalAgent

# Agent 会根据配置文件自动选择模型
agent = ReActClinicalAgent("01_triage_agent.md")
result = agent.run(video_paths, context, logger)
```

### 3. 手动指定模型

```python
# 强制使用特定模型
agent = ReActClinicalAgent("01_triage_agent.md", model_key="qwen_vl")
```

---

## 🔧 配置说明

### 全局参数

```yaml
global:
  api_key: "my-secret-key"
  api_timeout: 120
  video_max_pixels: 163840
  max_video_count: 4
```

### 模型定义

```yaml
models:
  qwen_vl:                              # 模型键名
    name: "qwen3vl_235b_2507"           # 实际模型名称
    base_url: "http://192.168.8.17:9011/v1"
    type: "vision"                      # 模型类型
    default_params:
      temperature: 0.01
      max_tokens: 4096
```

---

## 📊 默认配置

当前配置的 Agent 模型映射:

| Agent 类型 | 使用模型 | 说明 |
|-----------|---------|------|
| triage | gpt_oss | 纯文本分析 |
| time_calc | gpt_oss | 纯文本计算 |
| thrombolysis | gpt_oss | 纯文本决策 |
| indication | gpt_oss | 纯文本分析 |
| thrombectomy | gpt_oss | 纯文本决策 |
| summary | gpt_oss | 纯文本总结 |
| nihss_scorer | gpt_oss | 纯文本评分 |
| fact_extractor | gpt_oss | 纯文本提取 |
| consistency_check | gpt_oss | 纯文本检查 |
| director | gpt_oss | 纯文本协调 |
| hemorrhage | qwen_vl | 视觉分析 |
| ncct_imaging | qwen_vl | 视觉分析 |
| aneurysm | qwen_vl | 视觉分析 |
| lvo | qwen_vl | 视觉分析 |
| cta_imaging | qwen_vl | 视觉分析 |
| ctp_imaging | qwen_vl | 视觉分析 |

---

## 💡 常见场景

### 场景 1: 切换所有纯文本 Agent 到另一个模型

```yaml
agent_models:
  triage: claude_sonnet
  time_calc: claude_sonnet
  summary: claude_sonnet
  # ... 其他纯文本 Agent
```

### 场景 2: 为特定 Agent 使用不同参数

```python
response = call_llm_with_config(
    prompt_text="...",
    agent_name="director",
    temperature=0.9,      # 提高创造性
    max_tokens=8192       # 增加输出长度
)
```

### 场景 3: 添加新模型

1. 在 `config/model_config.yaml` 中定义新模型:

```yaml
models:
  new_model:
    name: "new-model-name"
    base_url: "http://your-api-url/v1"
    type: "text"
    default_params:
      temperature: 0.7
      max_tokens: 4096
```

2. 为 Agent 指定新模型:

```yaml
agent_models:
  director: new_model
```

---

## 🔍 调试技巧

### 查看当前使用的模型

运行示例脚本:

```bash
cd /data/qunhui_21T/Yan-20250730/code/agent_project_v6
python examples/model_config_example.py
```

### 启用详细日志

```python
import logging
logging.basicConfig(level=logging.INFO)
```

日志输出示例:
```
[模型选择] Agent: triage, Model: gpt_oss_120b (text)
>>> 发送请求至 gpt_oss_120b (Timeout 120s)...
✓ 成功! (2.34s)
```

---

## 📚 更多信息

- 详细文档: [docs/MODEL_CONFIG_GUIDE.md](MODEL_CONFIG_GUIDE.md)
- 使用示例: [examples/model_config_example.py](../examples/model_config_example.py)
- 配置文件: [config/model_config.yaml](../config/model_config.yaml)

---

## ⚠️ 注意事项

1. **配置文件修改后需要重启应用**
2. **视觉模型 (type: vision) 支持视频/图像输入**
3. **文本模型 (type: text) 仅支持纯文本输入**
4. **系统会自动处理不同模型的格式差异**

---

## 🎉 开始使用

现在你可以:

1. ✅ 编辑 `config/model_config.yaml` 配置你的模型
2. ✅ 运行现有代码，Agent 会自动使用配置的模型
3. ✅ 根据需要动态切换模型，无需修改代码

祝使用愉快！
