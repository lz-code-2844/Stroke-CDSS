#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Imaging Scoring Knowledge Base

Retrieves imaging scoring (ASPECTS, Collateral, etc.) related literature
"""

from typing import Dict, List
from .base_kb import BaseKnowledgeBase


class ImagingScoringKB(BaseKnowledgeBase):
    """Imaging Scoring Knowledge Base"""

    def __init__(self, vector_store, embedder):
        super().__init__(
            collection_name="imaging_scoring_literature",
            vector_store=vector_store,
            embedder=embedder
        )

    def build_query(self, context: Dict) -> str:
        """
        Build imaging scoring query

        Key information:
        - ASPECTS score
        - Collateral score
        - Alberta score
        """
        query_parts = ["imaging scoring stroke"]

        # ASPECTS score
        if 'aspects_score' in context or 'ncct_output' in context:
            query_parts.append("ASPECTS score Alberta Stroke Program Early CT Score")

        # CTA score (collateral circulation)
        if 'cta_output' in context:
            query_parts.append("collateral circulation grading collateral score")

        # Infarct core volume
        if 'ctp_output' in context:
            query_parts.append("infarct core volume ischemic penumbra measurement")

        return " ".join(query_parts)

    def format_results(self, results: List[Dict]) -> str:
        """Format as prompt text (full version with abstracts)"""
        if not results:
            return "[Imaging Scoring Literature]\nNo relevant literature found."

        formatted = ["[Imaging Scoring Literature]"]

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
