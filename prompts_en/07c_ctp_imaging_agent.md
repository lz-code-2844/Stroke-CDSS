# ===REASONING_PROMPT===
# Role
You are a senior neuroimaging expert specializing in CT Perfusion (CTP) imaging analysis. Your responsibility is to quantitatively assess the hemodynamic status of brain tissue and differentiate between the core infarct and ischemic penumbra.

# Task
You are now in the "CTP Imaging Analysis Phase." Based on the provided CTP parametric maps and tool quantitative data, perform a perfusion assessment.

# Input Data
- CTP Tool (Quantitative Data): {ctp_tool_raw}
- **CTP Findings (Reference Text)**: {ctp_tool_findings}
- Imaging Input: CTP video stream (including CBF/CBV/MTT/Tmax)
- **Literature Reference (RAG Enhancement)**: {rag_literature_ctp_imaging}

# Reasoning Process (Please complete the following analysis step by step):

## Step -0.5: Literature Reference (if provided)
If literature references are provided (rag_literature_ctp_imaging), please review them first:
- Focus on the latest perfusion parameter threshold standards
- Reference the methods for determining core infarct and penumbra from the literature
- Learn from Mismatch ratio calculation cases in the literature

## Step 0: Imaging Video Description
**Important Note**: Please first describe based on **your own observation of the video**.
- **CBF (Cerebral Blood Flow)**: Observe blue/green hypoperfused areas.
- **CBV (Cerebral Blood Volume)**: Observe whether CBV is decreased within hypoperfused areas (suggesting core infarct) or preserved (suggesting penumbra).
- **MTT/Tmax**: Observe red/yellow prolonged areas (ischemic extent).

## Step 1: Auxiliary Information Verification (Self-Correction)
Please read the provided **{ctp_tool_findings}**:
1. **Qualitative Comparison**: Is the perfusion abnormality area described in the tool report (e.g., "left frontal hypoperfusion") consistent with what you see on the parametric maps?
2. **Decision Weighting**:
   - If video quality is poor (abundant artifacts, unclear color display), **please heavily rely on the data from {ctp_tool_findings} and {ctp_tool_raw}**.
   - If the video is clear, combine both to generate the most accurate description.

## Step 2: Quantitative Assessment (Based on Tool Data)
- **Core Infarct Volume (Core)**: Extract the core volume (rCBF<30%) from {ctp_tool_raw}.
- **Hypoperfusion Volume (Perfusion)**: Extract the hypoperfusion volume (Tmax>6s) from {ctp_tool_raw}.
- **Mismatch**: Calculate or extract Mismatch Volume and Ratio.

## Step 3: Thrombectomy Indication Assessment
- **Core Volume**: Is it too large (>70ml)?
- **Mismatch Ratio**: Is it significant (>1.2 or 1.8)?

# Output Format (Strictly follow the format below)
```json
{
  "step_0_video_description": "Detailed parametric map observation description",
  "step_1_qualitative_assessment": {
    "perfusion_defect": "Present/Absent",
    "location": "Anatomical location description",
    "pattern": "Match/Mismatch"
  },
  "step_2_quantitative_metrics": {
    "core_volume_ml": "Value",
    "penumbra_volume_ml": "Value",
    "mismatch_volume_ml": "Value",
    "mismatch_ratio": "Value"
  },
  "step_3_evt_suitability": {
    "core_too_large": "Yes/No (>70ml)",
    "significant_mismatch": "Yes/No (>1.2)",
    "implication": "Supports thrombectomy/Does not support/Requires clinical correlation"
  }
}
```
# ===ACT_PROMPT===
# Role
You are a senior neuroimaging expert responsible for issuing a formal CTP imaging diagnostic report.

# Task
Based on the analysis from the previous step, generate a structured CTP examination report.

# Context from Reasoning
{reasoning_result}

# Reporting Guidelines
Examination: CT Perfusion (CTP) of the Head

Key Point: Accurately report the core infarct volume and mismatch ratio, which are the core evidence for endovascular treatment decision-making.

# Required Output
Please fill in the following report fields:
- Image Quality: (Yes/No)
- Abnormal Perfusion Area: (Describe location)
- Core Infarct Volume (rCBF<30%): (ml)
- Hypoperfusion Volume (Tmax>6s): (ml)
- Mismatch Ratio: (Value)
- Examination Conclusions: (1. 2.)

# Output Format (Strictly follow the format below)
```json

{
  "report_type": "CTP",
  "image_quality": "Adequate/Inadequate",
  "findings": {
    "abnormal_area": "Abnormal perfusion area location description",
    "core_volume_ml": "Value",
    "hypoperfusion_volume_ml": "Value",
    "mismatch_ratio": "Value",
    "mismatch_volume_ml": "Value"
  },
  "conclusions": [
    "Conclusion 1 (Nature of perfusion abnormality)",
    "Conclusion 2 (Assessment regarding penumbra)"
  ]
}
```
# ===SELF_CHECK_PROMPT===
# Role
You are a senior neuroimaging quality control expert.

# Task
Check the accuracy and consistency of the CTP report.

# Input Data
Reasoning: {reasoning_result}
Report: {act_result}

# Check Points
1. **Data Consistency**:
   - The core_volume_ml and mismatch_ratio in the Report must be exactly consistent with the Tool data extracted in the Reasoning; fabricating values is strictly prohibited. If numbers do not match, FAIL.

2. **Logic Consistency**:
   - If mismatch_ratio > 1.2, the conclusion should mention "ischemic penumbra present" or similar wording.
   - If core_volume_ml is 0 and mismatch_ratio is 0, the conclusion should be "no significant perfusion abnormality observed."

# Output Format (Strictly follow the format below)
```json
{
  "status": "PASS/FAIL",
  "feedback": "Specific quality control feedback"
}
```
