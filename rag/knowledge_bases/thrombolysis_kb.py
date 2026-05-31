#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Thrombolysis Knowledge Base

Retrieves thrombolysis (IVT) related literature evidence
"""

from typing import Dict, List
from .base_kb import BaseKnowledgeBase


class ThrombolysisKB(BaseKnowledgeBase):
    """Thrombolysis Knowledge Base"""

    def __init__(self, vector_store, embedder):
        super().__init__(
            collection_name="thrombolysis_literature",
            vector_store=vector_store,
            embedder=embedder
        )

    def build_query(self, context: Dict) -> str:
        """
        Build thrombolysis-related query

        Key information:
        - Onset time (< 4.5h)
        - Contraindications (hemorrhage, blood pressure, glucose, etc.)
        - Age, NIHSS
        """
        query_parts = ["intravenous thrombolysis rtPA alteplase acute ischemic stroke"]

        # Time window
        if 'onset_to_arrival_hours' in context:
            try:
                hours = float(context['onset_to_arrival_hours'])
                if hours < 3:
                    query_parts.append("0-3 hours ultra-early window")
                elif hours < 4.5:
                    query_parts.append("3-4.5 hours standard time window")
            except:
                pass

        # Contraindication check
        if 'hemorrhage_detected' in context and context.get('hemorrhage_detected'):
            query_parts.append("intracranial hemorrhage contraindication")

        # NIHSS score
        if 'nihss_score' in context:
            try:
                nihss = int(context['nihss_score'])
                if nihss < 5:
                    query_parts.append("mild stroke low NIHSS thrombolysis benefit risk")
                elif nihss > 20:
                    query_parts.append("severe stroke high NIHSS thrombolysis safety")
            except:
                pass

        # Age
        if 'age' in context:
            try:
                age = int(context.get('age', 0))
                if age > 80:
                    query_parts.append("elderly patients age over 80 thrombolysis")
            except:
                pass

        return " ".join(query_parts)

    def format_results(self, results: List[Dict]) -> str:
        """Format as prompt text (full version with abstracts)"""
        if not results:
            return "[Thrombolysis Literature Evidence]\nNo relevant literature found."

        formatted = ["[Thrombolysis Literature Evidence]"]

        for idx, result in enumerate(results[:3], 1):
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
