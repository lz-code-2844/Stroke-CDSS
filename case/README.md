# Representative Case

This folder contains one anonymized representative case used to illustrate the difference between MA-RAG, MA-Only, and baseline outputs.

## Directory structure

```text
case/
├── README.md
├── data/
│   ├── case_data_zh.json
│   └── case_data_en.json
├── results/
│   ├── zh/
│   │   ├── Result_MA-RAG.csv
│   │   ├── Result_MA-Only.csv
│   │   └── Result_baseline.csv
│   └── en/
│       ├── Result_MA-RAG_EN.csv
│       ├── Result_MA-Only_EN.csv
│       └── Result_baseline_EN.csv
└── videos/
    ├── ncct.mp4
    ├── cta_merge.mp4
    └── ctp_merge.mp4
```

## Case summary

- Gold label: `B`, endovascular thrombectomy.
- MA-RAG: predicted `B`, correct.
- MA-Only: predicted `B`, correct.
- Baseline: predicted `C`, incorrect.

The case demonstrates a typical extended-window EVT scenario. MA-RAG identifies a right M1 large-vessel occlusion with favorable perfusion profile and recommends thrombectomy, whereas the baseline model over-emphasizes the standard 6-hour window and selects medical management.

## Anonymization

The patient identifier is replaced with `xxxxx`. Imaging identifiers and video file references are also anonymized or normalized for public release.

