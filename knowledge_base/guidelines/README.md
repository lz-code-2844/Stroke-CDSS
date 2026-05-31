# Guidelines

This directory is intended for placing relevant clinical guidelines used by the Stroke-CDSS system.

You may place guideline text files (`.txt`) here, such as:

- `ivt_guidelines.txt` - Intravenous Thrombolysis (IVT) guidelines
- `evt_guidelines.txt` - Endovascular Thrombectomy (EVT) guidelines

These guidelines are loaded by `utils/rag_engine.py` via the `SimpleRAG` class to provide clinical context during the decision-making process.

This directory can also be left empty if no guideline files are available.
