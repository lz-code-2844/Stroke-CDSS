#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Thrombectomy Knowledge Base

Retrieves thrombectomy-related literature evidence
"""

from typing import Dict, List
from .base_kb import BaseKnowledgeBase


class ThrombectomyKB(BaseKnowledgeBase):
    """Thrombectomy Knowledge Base"""

    def __init__(self, vector_store, embedder):
        super().__init__(
            collection_name="thrombectomy_literature",
            vector_store=vector_store,
            embedder=embedder
        )

    def build_query(self, context: Dict) -> str:
        """
        Build thrombectomy-related query

        Key information:
        - LVO location (ICA/M1/M2/basilar artery)
        - NIHSS score
        - Time window
        - Imaging indicators (ASPECTS, infarct core)
        """
        query_parts = ["endovascular thrombectomy mechanical thrombectomy"]

        # Vessel occlusion location
        if 'lvo_output' in context:
            lvo_info = context['lvo_output']
            if isinstance(lvo_info, str) and any(v in lvo_info for v in ['ICA', 'M1', 'M2', 'basilar']):
                query_parts.append(f"{lvo_info} occlusion")

        # NIHSS score range
        if 'nihss_score' in context:
            try:
                nihss = int(context['nihss_score'])
                if nihss >= 20:
                    query_parts.append("severe stroke high NIHSS")
                elif nihss >= 10:
                    query_parts.append("moderate to severe stroke")
            except:
                pass

        # Time window
        if 'onset_time_category' in context:
            time_cat = context['onset_time_category']
            if '6h' in time_cat or '<6' in time_cat:
                query_parts.append("early time window 0-6 hours")
            elif '6-24' in time_cat:
                query_parts.append("extended time window DAWN DEFUSE")

        # ASPECTS score
        if 'aspects_score' in context:
            try:
                aspects = int(context['aspects_score'])
                if aspects >= 6:
                    query_parts.append("favorable ASPECTS score")
                else:
                    query_parts.append("low ASPECTS score large infarct")
            except:
                pass

        return " ".join(query_parts)

    def format_results(self, results: List[Dict]) -> str:
        """
        Format as prompt text (full version with abstracts)

        Format:
        [Thrombectomy Literature Evidence]
        1. [Title]
           PMID: xxx | Journal: xxx | Year: xxx
           Abstract: [Full abstract content]
           Key Conclusion: [Key conclusion]
        """
        if not results:
            return "[Thrombectomy Literature Evidence]\nNo relevant literature found."

        formatted = ["[Thrombectomy Literature Evidence]"]

        for idx, result in enumerate(results[:3], 1):  # Take only the first 3
            metadata = result.get('metadata', {})
            title = metadata.get('title', 'No title')
            pmid = metadata.get('pmid', 'N/A')
            journal = metadata.get('journal', 'N/A')
            year = metadata.get('year', 'N/A')

            # Prefer getting full abstract from metadata (original full abstract)
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
            # Remove possible "nan" string
            if abstract.lower() == 'nan':
                abstract = ""

            # Limit abstract length (1500 chars, detailed enough but not too long)
            if len(abstract) > 1500:
                abstract = abstract[:1497] + "..."

            # Key conclusion (if available)
            key_findings = metadata.get('key_findings', '')
            conclusion_line = f"\n   Key conclusion: {key_findings}" if key_findings else ""

            formatted.append(
                f"\n{idx}. {title}\n"
                f"   PMID: {pmid} | Journal: {journal} | Year: {year}\n"
                f"   Abstract: {abstract or '[No abstract]'}{conclusion_line}"
            )

        return "\n".join(formatted)
