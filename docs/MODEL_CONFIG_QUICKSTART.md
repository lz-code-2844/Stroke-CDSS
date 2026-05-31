# Model Configuration System - Quick Start

## 🎯 Core Improvements

This upgrade implements a **configuration-driven model selection system**, allowing you to flexibly specify different LLM models for each Agent.

---

## 📁 New Files

```
agent_project_v6/
├── config/
│   ├── __init__.py                    # Configuration module initialization
│   ├── model_config.yaml              # Model configuration file (core)
│   └── model_config_loader.py         # Configuration loader
├── docs/
│   ├── MODEL_CONFIG_GUIDE.md          # Detailed usage guide
│   └── MODEL_CONFIG_QUICKSTART.md     # This file
├── examples/
│   └── model_config_example.py        # Usage example
└── utils/
    └── llm_client.py                  # Improved LLM client
```

---

## 🚀 Quick Usage

### 1. Modify the Configuration File

Edit `config/model_config.yaml`:

```yaml
agent_models:
  # Specify a model for each Agent
  triage: gpt_oss          # Triage uses GPT-OSS
  hemorrhage: qwen_vl      # Hemorrhage uses Qwen-VL
  director: gpt_oss        # Director uses GPT-OSS
```

### 2. Use an Agent (Automatic Routing)

```python
from agents.react_agent import ReActClinicalAgent

# The Agent automatically selects a model based on the configuration file
agent = ReActClinicalAgent("01_triage_agent.md")
result = agent.run(video_paths, context, logger)
```

### 3. Manually Specify a Model

```python
# Force the use of a specific model
agent = ReActClinicalAgent("01_triage_agent.md", model_key="qwen_vl")
```

---

## 🔧 Configuration Reference

### Global Parameters

```yaml
global:
  api_key: "my-secret-key"
  api_timeout: 120
  video_max_pixels: 163840
  max_video_count: 4
```

### Model Definition

```yaml
models:
  qwen_vl:                              # Model key name
    name: "qwen3vl_235b_2507"           # Actual model name
    base_url: "http://192.168.8.17:9011/v1"
    type: "vision"                      # Model type
    default_params:
      temperature: 0.01
      max_tokens: 4096
```

---

## 📊 Default Configuration

Current Agent-to-model mapping:

| Agent Type | Model Used | Description |
|-----------|---------|------|
| triage | gpt_oss | Text-only analysis |
| time_calc | gpt_oss | Text-only calculation |
| thrombolysis | gpt_oss | Text-only decision |
| indication | gpt_oss | Text-only analysis |
| thrombectomy | gpt_oss | Text-only decision |
| summary | gpt_oss | Text-only summarization |
| nihss_scorer | gpt_oss | Text-only scoring |
| fact_extractor | gpt_oss | Text-only extraction |
| consistency_check | gpt_oss | Text-only checking |
| director | gpt_oss | Text-only coordination |
| hemorrhage | qwen_vl | Visual analysis |
| ncct_imaging | qwen_vl | Visual analysis |
| aneurysm | qwen_vl | Visual analysis |
| lvo | qwen_vl | Visual analysis |
| cta_imaging | qwen_vl | Visual analysis |
| ctp_imaging | qwen_vl | Visual analysis |

---

## 💡 Common Scenarios

### Scenario 1: Switch All Text-Only Agents to Another Model

```yaml
agent_models:
  triage: claude_sonnet
  time_calc: claude_sonnet
  summary: claude_sonnet
  # ... other text-only Agents
```

### Scenario 2: Use Different Parameters for a Specific Agent

```python
response = call_llm_with_config(
    prompt_text="...",
    agent_name="director",
    temperature=0.9,      # Increase creativity
    max_tokens=8192       # Increase output length
)
```

### Scenario 3: Add a New Model

1. Define the new model in `config/model_config.yaml`:

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

2. Assign the new model to an Agent:

```yaml
agent_models:
  director: new_model
```

---

## 🔍 Debugging Tips

### View Currently Used Models

Run the example script:

```bash
cd /data/qunhui_21T/Yan-20250730/code/agent_project_v6
python examples/model_config_example.py
```

### Enable Verbose Logging

```python
import logging
logging.basicConfig(level=logging.INFO)
```

Example log output:
```
[Model Selection] Agent: triage, Model: gpt_oss_120b (text)
>>> Sending request to gpt_oss_120b (Timeout 120s)...
✓ Success! (2.34s)
```

---

## 📚 More Information

- Detailed documentation: [docs/MODEL_CONFIG_GUIDE.md](MODEL_CONFIG_GUIDE.md)
- Usage example: [examples/model_config_example.py](../examples/model_config_example.py)
- Configuration file: [config/model_config.yaml](../config/model_config.yaml)

---

## ⚠️ Important Notes

1. **You must restart the application after modifying the configuration file**
2. **Vision models (type: vision) support video/image input**
3. **Text models (type: text) only support plain text input**
4. **The system automatically handles format differences between models**

---

## 🎉 Get Started

Now you can:

1. ✅ Edit `config/model_config.yaml` to configure your models
2. ✅ Run existing code — Agents will automatically use the configured models
3. ✅ Dynamically switch models as needed without modifying code

Happy coding!
