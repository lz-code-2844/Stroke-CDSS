# Prompt Templates

This directory contains prompt templates used by the Stroke-CDSS multi-agent workflow.

The paper describes agents at the clinical-task level. In the codebase, several paper-level agents are implemented as smaller prompt modules, especially the Imaging Agent.

## Primary Paper Mapping

| Paper-level agent | Runtime prompt file(s) | Notes |
|---|---|---|
| Triage Agent | `01_triage_agent.md` | AIS/non-AIS routing |
| Time-calculation Agent | `03_time_calc_agent.md` | IVT and EVT time-window assessment |
| Hemorrhage safety-routing Agent | `02_hemorrhage_agent.md` | NCCT hemorrhage screening and safety routing |
| Imaging Agent | `05_lvo_agent.md` | LVO-focused imaging consistency submodule |
| Imaging Agent | `07a_ncct_imaging_agent.md` | NCCT imaging findings |
| Imaging Agent | `07b_cta_imaging_agent.md` | CTA vascular findings |
| Imaging Agent | `07c_ctp_imaging_agent.md` | CTP perfusion findings |
| Imaging Agent | `07_imaging_agent.md` | Multimodal imaging integration and validation |
| NIHSS Agent | `11_nihss_scorer.md` | Neurological severity estimation |
| Contraindication Agent | `08_indication_agent.md` | Treatment-related risk and contraindication screening |
| Fact-extractor Agent | `12_fact_extractor.md` | Structured extraction from clinical records |
| Consistency Agent | `13_consistency_check.md` | Clinical-imaging concordance check |
| Decision-physician Agent | `14_director_agent.md` | Final treatment recommendation |

The **Supervisor Agent** is implemented in `main_flow.py`, where routing, shared state, and pathway transitions are coordinated.

## Optional or Legacy Templates

The following templates are retained for traceability of earlier workflow versions and ablation experiments. They are not part of the primary paper-level framework described in the main README.

| Template | Historical purpose |
|---|---|
| `04_aneurysm_agent.md` | Aneurysm detection in an earlier hemorrhage sub-pathway |
| `06_thrombolysis_agent.md` | Standalone IVT evaluation |
| `09_thrombectomy_agent.md` | Standalone EVT evaluation |
| `10_summary_agent.md` | MDT-style handoff summary |
