#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Imaging Triage Knowledge Base

Retrieves imaging triage-related literature
"""

from typing import Dict, List
from .base_kb import BaseKnowledgeBase


class ImagingTriageKB(BaseKnowledgeBase):
    """Imaging Triage Knowledge Base"""

    def __init__(self, vector_store, embedder):
        super().__init__(
            collection_name="imaging_triage_literature",
            vector_store=vector_store,
            embedder=embedder
        )

    def build_query(self, context: Dict) -> str:
        """
        Build imaging triage query

        Key information:
        - Imaging type (NCCT/CTA/CTP)
        - Detected abnormal signs
        - Triage decision needed
        """
        query_parts = ["neuroimaging stroke triage"]

        # NCCT related
        if 'ncct_output' in context:
            query_parts.append("non-contrast CT early ischemic changes hyperdense artery sign")

        # CTA related
        if 'cta_output' in context:
            query_parts.append("CT angiography large vessel occlusion collateral assessment")

        # CTP related
        if 'ctp_output' in context:
            query_parts.append("CT perfusion penumbra mismatch infarct core")

        # Hemorrhage detection
        if context.get('hemorrhage_detected'):
            query_parts.append("intracranial hemorrhage subarachnoid hemorrhage")

        return " ".join(query_parts)

    def format_results(self, results: List[Dict]) -> str:
        """Format as prompt text (full version with abstracts)"""
        if not results:
            return "[Imaging Triage Literature]\nNo relevant literature found."

        formatted = ["[Imaging Triage Literature]"]

        for idx, result in enumerate(results[:3], 1):
            metadata = result.get('metadata', {})
            title = metadata.get('title', 'No title')
            pmid = metadata.get('pmid', 'N/A')
            journal = metadata.get('journal', 'N/A')
            year = metadata.get('year', 'N/A')

            # Prefer getting full abstract from metadata
            abstract = metadata.get('abstract', '')

            # If not in metadata, try parsing from document
            if not abstract:
                document = result.get('document', '')
                if 'Abstract:' in document:
                    abstract = document.split('Abstract:', 1)[1].strip()
                elif 'BACKGROUND:' in document or 'METHODS:' in document or 'RESULTS:' in document:
                    abstract = document
                else:
                    abstract = document

            # Clean abstract content
            abstract = str(abstract).strip()
            if abstract.lower() == 'nan':
                abstract = ""

            # Limit abstract length (1500 chars)
            if len(abstract) > 1500:
                abstract = abstract[:1497] + "..."

            key_findings = metadata.get('key_findings', '')
            conclusion_line = f"\n   Key conclusion: {key_findings}" if key_findings else ""

            formatted.append(
                f"\n{idx}. {title}\n"
                f"   PMID: {pmid} | Journal: {journal} | Year: {year}\n"
                f"   Abstract: {abstract or '[No abstract]'}{conclusion_line}"
            )

        return "\n".join(formatted)
