#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simplified RAG Coordinator (Compatible Version)

Supports two modes:
1. Full version: Uses ChromaDB + Embedding model
2. Simplified version: Uses TF-IDF + Pickle (no ChromaDB required)
"""

import os
import pickle
from typing import Dict, Optional, List


class SimpleRAGCoordinator:
    """Simplified RAG Coordinator (using TF-IDF, no ChromaDB dependency)"""

    # Agent-to-knowledge-base mapping
    AGENT_KB_MAPPING = {
        'thrombectomy': 'thrombectomy_literature',
        'thrombectomy_agent': 'thrombectomy_literature',

        'thrombolysis': 'thrombolysis_literature',
        'thrombolysis_agent': 'thrombolysis_literature',
        'indication': 'thrombolysis_literature',

        'ncct_imaging': 'imaging_scoring_literature',
        'imaging_scoring_kb': 'imaging_scoring_literature',

        'cta_imaging': 'imaging_triage_literature',
        'ctp_imaging': 'imaging_triage_literature',
        'imaging_triage_kb': 'imaging_triage_literature',
    }

    def __init__(self, persist_dir="knowledge_base/simple_rag"):
        """Initialize simplified RAG coordinator"""
        self.persist_dir = persist_dir
        self.vectorizer = None
        self.literature_db = {}

        # Load vectorizer
        vectorizer_path = os.path.join(persist_dir, 'vectorizer.pkl')
        if os.path.exists(vectorizer_path):
            with open(vectorizer_path, 'rb') as f:
                self.vectorizer = pickle.load(f)

        # Load all collections
        for coll_name in ['thrombectomy_literature', 'thrombolysis_literature',
                          'imaging_triage_literature', 'imaging_scoring_literature']:
            coll_file = os.path.join(persist_dir, f'{coll_name}.pkl')
            if os.path.exists(coll_file):
                with open(coll_file, 'rb') as f:
                    self.literature_db[coll_name] = pickle.load(f)

        print(f"✓ SimpleRAGCoordinator initialized with {len(self.literature_db)} knowledge bases")

    def retrieve(self, agent_name: str, context: Dict, top_k: int = 3) -> Optional[str]:
        """Retrieve relevant literature for specified Agent"""
        # Determine which knowledge base to use based on Agent name
        collection_name = self.AGENT_KB_MAPPING.get(agent_name)

        if collection_name is None or collection_name not in self.literature_db:
            return None

        # Build query
        query = self._build_query(agent_name, context)

        # Execute retrieval
        results = self._search(collection_name, query, top_k)

        # Format results
        return self._format_results(results, agent_name)

    def _build_query(self, agent_name: str, context: Dict) -> str:
        """Build query based on Agent type and context"""
        query_parts = []

        if 'thrombectomy' in agent_name:
            query_parts.append("endovascular thrombectomy mechanical thrombectomy")
            if 'lvo_output' in context:
                query_parts.append(f"{context.get('lvo_output', '')} occlusion")
            if 'nihss_score' in context:
                query_parts.append(f"NIHSS {context.get('nihss_score', '')}")

        elif 'thrombolysis' in agent_name or 'indication' in agent_name:
            query_parts.append("intravenous thrombolysis rtPA alteplase")
            if 'onset_hours' in context:
                query_parts.append(f"time window {context.get('onset_hours', '')} hours")

        elif 'imaging' in agent_name:
            if 'ncct' in agent_name:
                query_parts.append("ASPECTS score early ischemic changes")
            elif 'cta' in agent_name:
                query_parts.append("CT angiography vessel occlusion collateral")
            elif 'ctp' in agent_name:
                query_parts.append("CT perfusion penumbra mismatch")

        return " ".join(query_parts) if query_parts else "acute ischemic stroke"

    def _search(self, collection_name: str, query: str, top_k: int) -> List[Dict]:
        """Execute retrieval"""
        if not self.vectorizer or collection_name not in self.literature_db:
            return []

        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        coll_data = self.literature_db[collection_name]

        # Vectorize query
        query_vec = self.vectorizer.transform([query])

        # Compute similarity
        similarities = cosine_similarity(query_vec, coll_data['vectors'])[0]

        # Get top-k
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            results.append({
                'document': coll_data['documents'][idx],
                'metadata': coll_data['metadatas'][idx],
                'score': float(similarities[idx])
            })

        return results

    def _format_results(self, results: List[Dict], agent_name: str) -> str:
        """Format retrieval results"""
        if not results:
            return f"[Literature Search]\nNo relevant literature found."

        kb_type_names = {
            'thrombectomy': 'Thrombectomy',
            'thrombolysis': 'Thrombolysis',
            'indication': 'Thrombolysis',
            'ncct_imaging': 'Imaging Scoring',
            'cta_imaging': 'Imaging Triage',
            'ctp_imaging': 'Imaging Triage'
        }

        kb_type = next((v for k, v in kb_type_names.items() if k in agent_name), 'Clinical')
        formatted = [f"[{kb_type} Literature Results]"]

        for idx, result in enumerate(results, 1):
            metadata = result.get('metadata', {})
            title = metadata.get('title', 'No title')
            pmid = metadata.get('pmid', 'N/A')
            journal = metadata.get('journal', 'N/A')
            year = metadata.get('year', 'N/A')

            formatted.append(
                f"\n{idx}. {title}\n"
                f"   PMID: {pmid} | Journal: {journal} | Year: {year}"
            )

        return "\n".join(formatted)

    def check_kb_status(self) -> Dict[str, int]:
        """Check knowledge base status"""
        status = {}
        for kb_name, kb_data in self.literature_db.items():
            status[kb_name] = len(kb_data['documents'])
        return status


# Compatibility wrapper: auto-select available RAG system
def RAGCoordinator(*args, **kwargs):
    """
    Smart RAG coordinator factory function

    Auto-selects:
    1. If simple_rag is available -> Use SimpleRAGCoordinator
    2. If chromadb is available -> Use FullRAGCoordinator
    3. If neither available -> Return None
    """
    # Try simplified version (preferred)
    try:
        coordinator = SimpleRAGCoordinator()
        if coordinator.literature_db:
            print("✓ Using SimpleRAGCoordinator (TF-IDF based)")
            return coordinator
    except Exception as e:
        print(f"SimpleRAGCoordinator not available: {e}")

    # Try full version
    try:
        from rag.rag_coordinator import RAGCoordinator as FullRAGCoordinator
        coordinator = FullRAGCoordinator(*args, **kwargs)
        print("✓ Using Full RAGCoordinator (ChromaDB based)")
        return coordinator
    except Exception as e:
        print(f"Full RAGCoordinator not available: {e}")

    return None


if __name__ == "__main__":
    # Test code
    print("Testing SimpleRAGCoordinator...")

    coordinator = RAGCoordinator()

    if coordinator:
        # Check knowledge base status
        print("\nKnowledge base status:")
        status = coordinator.check_kb_status()
        for kb_name, count in status.items():
            print(f"  {kb_name}: {count} documents")

        # Test retrieval
        test_context = {
            'lvo_output': 'M1 segment occlusion',
            'nihss_score': 15
        }

        print("\nTest retrieval (thrombectomy_agent):")
        result = coordinator.retrieve('thrombectomy_agent', test_context, top_k=2)
        if result:
            print(result[:500] + "..." if len(result) > 500 else result)
        else:
            print("  No results")
    else:
        print("✗ No RAG coordinator available")
