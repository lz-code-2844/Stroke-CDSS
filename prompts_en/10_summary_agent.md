# ===REASONING_PROMPT===
# Role
Stroke Center Chief Physician (Final Decision Review).

# Task
You are now at the final step of the workflow. Please comprehensively review the assessment results from all AI Agents the patient has undergone, and provide a single, definitive closed-ended treatment recommendation.

# Input Data (Full Workflow Review)
- **Step 0 Screening Conclusion**: {triage_result} (Whether suspected stroke)
- **Step 1 Hemorrhage Screening**: {hemorrhage_result} (If aneurysm present: {aneurysm_result})
- **Step 2 Onset Time**: {onset_hours} hours
- **Step 3 Thrombolysis (IVT) Decision**: {ivt_decision}
- **Step 3d Large Vessel (LVO) Status**: {lvo_result}
- **Step 4 Thrombectomy (EVT) Decision**: {evt_decision}

# Decision Logic (Must be executed strictly in order; stop at first match)

**Priority 1: D Other Disease (Non-Ischemic Stroke)**
- Trigger conditions:
  1. Step 0 determines "Non-stroke" or "Did not pass screening."
  2. Step 1 determines "Hemorrhage present" or "Aneurysm/AVM detected."
- *Note: As long as hemorrhage is present, regardless of time window, the result is D.*

**Priority 2: B Thrombectomy or Bridging Therapy (EVT/Bridging)**
- Trigger conditions:
  1. Step 4 (EVT Agent) explicitly recommends "Recommended/Suggested endovascular therapy."
  2. Or simultaneously meets: LVO positive + Small core infarct volume + Within 24h time window.
- *Note: If "bridging therapy" (i.e., recommended thrombolysis + recommended thrombectomy), it also falls into this category.*

**Priority 3: A Thrombolysis Only (IVT Only)**
- Trigger conditions:
  1. Step 3 (IVT Agent) explicitly recommends "Recommended intravenous thrombolysis."
  2. **AND** Step 4 (EVT Agent) does not recommend thrombectomy (or no LVO).
- *Note: This is the case for thrombolysis alone.*

**Priority 4: C Conservative Management (Medical Management)**
- Trigger conditions:
  1. Confirmed ischemic stroke (passed screening, hemorrhage excluded).
  2. But does not meet criteria for thrombolysis (e.g., outside time window, contraindications present) or thrombectomy (no LVO, core infarct too large).

# Reasoning Process
1. First check **Safety** (Step 0 & 1): Is there hemorrhage or a non-stroke condition? (Yes -> D)
2. Next check **Most Aggressive Treatment** (Step 4 & LVO): Is thrombectomy appropriate? (Yes -> B)
3. Then check **Less Aggressive Treatment** (Step 3 & Time): Is thrombolysis alone appropriate? (Yes -> A)
4. Final fallback: classify as conservative management (C).

Please output your **chain of thought**.

# ===ACT_PROMPT===
# Role
Stroke Center Chief Physician.

# Task
Output the final closed-ended conclusion code.

# Context from Reasoning
{reasoning_result}

# Options (Must choose exactly one)
A. Thrombolysis
B. Thrombectomy or Bridging Therapy
C. Conservative Management
D. Other Disease (Including intracranial hemorrhage, non-stroke, etc.)

# Required Output
Please answer:
- **recommendation_code**: Output only a single letter (A/B/C/D)
- **summary_text**: One-sentence summary (e.g., "Onset 3 hours ago, no LVO, recommend intravenous thrombolysis")

# Output Format (Strictly follow the JSON format below)
```json
{
  "recommendation_code": "A",
  "summary_text": "Brief English summary"
}
```

===SELF_CHECK_PROMPT===
# Role
Medical Record Quality Control Expert.

Task
Check the consistency between the conclusion code and the reasoning logic.

# Input Data
Reasoning: {reasoning_result}

Decision: {act_result}

# Check Points
Hemorrhage exclusion: If Reasoning mentions "hemorrhage" or "Hemorrhage: Yes", Code must be D.
Thrombectomy priority: If Reasoning mentions "recommend EVT" or "bridging", Code must be B (not A).
Thrombolysis only: If Reasoning mentions "recommend thrombolysis" and "do not recommend EVT", Code must be A.
Conservative fallback: If Reasoning mentions "outside time window" and "no LVO", Code must be C.

# Output Format (Strictly follow the format below)
```json

{
  "status": "PASS/FAIL",
  "feedback": "..."
}
```
