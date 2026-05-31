# Prompt Templates

This directory contains the prompt templates for each agent in the Stroke-CDSS multi-agent system.

## Paper Agent Mapping (Supplementary Table S1)

| Paper Agent Name | Prompt File | Description |
|---|---|---|
| Triage Agent | `01_triage_agent.md` | Routes cases into the appropriate pathway (AIS/non-AIS) |
| Hemorrhage safety-routing Agent | `02_hemorrhage_agent.md` | Excludes hemorrhagic cases from reperfusion decisions |
| Time-calculation Agent | `03_time_calc_agent.md` | Determines treatment-window eligibility |
| *(Hemorrhage sub-pathway)* | `04_aneurysm_agent.md` | Aneurysm detection under hemorrhage pathway |
| *(Ischemic sub-module)* | `05_lvo_agent.md` | Large vessel occlusion detection |
| *(Ischemic sub-module)* | `06_thrombolysis_agent.md` | Intravenous thrombolysis evaluation |
| Imaging Agent | `07a_ncct_imaging_agent.md` | NCCT imaging analysis |
| Imaging Agent | `07b_cta_imaging_agent.md` | CTA imaging analysis |
| Imaging Agent | `07c_ctp_imaging_agent.md` | CTP imaging analysis |
| Imaging Agent | `07_imaging_agent.md` | Imaging integration and validation |
| Contraindication Agent | `08_indication_agent.md` | Screens treatment-related risks and contraindications |
| *(Ischemic sub-module)* | `09_thrombectomy_agent.md` | Endovascular thrombectomy evaluation |
| Summary Agent | `10_summary_agent.md` | Summarizes key findings into an MDT-style handoff |
| NIHSS Agent | `11_nihss_scorer.md` | Estimates stroke severity (NIHSS scoring) |
| Fact-extractor Agent | `12_fact_extractor.md` | Standardizes key case information from free-text |
| Consistency Agent | `13_consistency_check.md` | Checks concordance and detects mismatch |
| Decision-physician Agent | `14_director_agent.md` | Produces the final management decision |

**Note:** The **Supervisor Agent** (workflow orchestration and pathway routing) is implemented in `main_flow.py`, not as a separate prompt template.
