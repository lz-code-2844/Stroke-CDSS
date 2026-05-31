#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hybrid Retrieval Coordinator - Runtime Usage
HybridRAGCoordinator for runtime retrieval

Usage:
    coordinator = HybridRAGCoordinator()
    results = coordinator.retrieve('thrombectomy_agent', context, top_k=5)
"""

import os
import pickle
import numpy as np
from typing import List, Dict
from pathlib import Path

class HybridRAGCoordinator:
    """Hybrid Retrieval RAG Coordinator"""

    # Agent-to-knowledge-base mapping
    AGENT_KB_MAPPING = {
        'thrombectomy_agent': 'thrombectomy_literature',
        'thrombolysis_agent': 'thrombolysis_literature',
        'indication': 'thrombolysis_literature',
        'ncct_imaging': 'imaging_scoring_literature',
        'cta_imaging': 'imaging_triage_literature',
        'ctp_imaging': 'imaging_triage_literature',
        'nihss_scorer': 'imaging_scoring_literature',
    }

    def __init__(self, persist_dir="knowledge_base/hybrid_rag"):
        """Initialize hybrid retrieval coordinator"""
        self.persist_dir = persist_dir
        self.knowledge_bases = {}
        self.embedding_model = None
        self.reranker_model = None

        # Load knowledge bases
        self._load_knowledge_bases()

        # Lazy load models (loaded on first retrieval)
        self.models_loaded = False

    def _load_knowledge_bases(self):
        """Load all knowledge bases"""
        if not os.path.exists(self.persist_dir):
            print(f"⚠️  Hybrid retrieval directory not found: {self.persist_dir}")
            return

        pkl_files = list(Path(self.persist_dir).glob("*.pkl"))

        for pkl_file in pkl_files:
            collection_name = pkl_file.stem

            try:
                with open(pkl_file, 'rb') as f:
                    data = pickle.load(f)

                self.knowledge_bases[collection_name] = data
                print(f"✓ Loaded knowledge base: {collection_name} ({len(data['documents'])} docs)")

            except Exception as e:
                print(f"⚠️  Failed to load {collection_name}: {e}")

        print(f"\n✓ HybridRAGCoordinator initialized")
        print(f"  Knowledge bases: {len(self.knowledge_bases)}")
        print(f"  Retrieval mode: Hybrid (Semantic + BM25 + Reranking)")

    def _load_models(self):
        """Lazy load models"""
        if self.models_loaded:
            return

        print("\nLoading hybrid retrieval models...")

        try:
            from sentence_transformers import SentenceTransformer, CrossEncoder

            # Load embedding model
            self.embedding_model = SentenceTransformer('BAAI/bge-large-zh-v1.5')
            print("✓ Embedding model loaded")

            # Load reranking model
            self.reranker_model = CrossEncoder('BAAI/bge-reranker-base')
            print("✓ Reranking model loaded")

            self.models_loaded = True

        except Exception as e:
            print(f"⚠️  Model loading failed: {e}")
            print("  Falling back to simple retrieval mode")
            self.models_loaded = False

    def _semantic_search(self, query, kb_data, top_k=20):
        """Semantic retrieval"""
        query_embedding = self.embedding_model.encode([query], normalize_embeddings=True)[0]
        embeddings = kb_data['embeddings']

        # Compute cosine similarity
        scores = np.dot(embeddings, query_embedding)
        top_indices = np.argsort(scores)[-top_k:][::-1]

        return top_indices, scores[top_indices]

    def _bm25_search(self, query, kb_data, top_k=20):
        """BM25 keyword retrieval"""
        bm25 = kb_data['bm25']
        query_tokens = query.lower().split()

        scores = bm25.get_scores(query_tokens)
        top_indices = np.argsort(scores)[-top_k:][::-1]

        return top_indices, scores[top_indices]

    def _rerank(self, query, documents, top_k=5):
        """Reranking"""
        pairs = [[query, doc] for doc in documents]
        scores = self.reranker_model.predict(pairs)
        top_indices = np.argsort(scores)[-top_k:][::-1]

        return top_indices, scores[top_indices]

    def _build_query(self, agent_name: str, context: Dict) -> str:
        """Build intelligent query"""
        query_parts = []

        if 'thrombectomy' in agent_name:
            query_parts.append("endovascular thrombectomy mechanical thrombectomy")
            if context.get('lvo_output'):
                query_parts.append(str(context['lvo_output']))
            if context.get('nihss_score'):
                query_parts.append(f"NIHSS {context['nihss_score']}")

        elif 'thrombolysis' in agent_name or agent_name == 'indication':
            query_parts.append("intravenous thrombolysis rtPA alteplase")
            if context.get('onset_hours'):
                query_parts.append(f"time window {context['onset_hours']} hours")

        elif 'ncct' in agent_name or 'scoring' in agent_name:
            query_parts.append("ASPECTS score early ischemic changes")

        elif 'cta' in agent_name or 'ctp' in agent_name or 'triage' in agent_name:
            query_parts.append("CT angiography perfusion vessel occlusion")

        return ' '.join(query_parts) if query_parts else "stroke treatment"

    def retrieve(self, agent_name: str, context: Dict, top_k: int = 5) -> str:
        """
        Hybrid retrieval main method

        Process:
        1. Semantic retrieval Top-20
        2. BM25 retrieval Top-20
        3. Merge and deduplicate Top-30
        4. Rerank Top-K
        """
        # Load models (on first call)
        if not self.models_loaded:
            self._load_models()

        if not self.models_loaded:
            return ""  # Model loading failed, return empty

        # Get knowledge base
        collection_name = self.AGENT_KB_MAPPING.get(agent_name)
        if not collection_name or collection_name not in self.knowledge_bases:
            return ""

        kb_data = self.knowledge_bases[collection_name]

        # Build query
        query = self._build_query(agent_name, context)

        try:
            # Step 1: Semantic retrieval
            semantic_indices, semantic_scores = self._semantic_search(query, kb_data, top_k=20)

            # Step 2: BM25 retrieval
            bm25_indices, bm25_scores = self._bm25_search(query, kb_data, top_k=20)

            # Step 3: Merge candidates (deduplicate)
            candidate_indices = list(set(semantic_indices) | set(bm25_indices))

            # Step 4: Reranking
            candidate_docs = [kb_data['documents'][idx] for idx in candidate_indices]
            rerank_indices, rerank_scores = self._rerank(query, candidate_docs, top_k=top_k)

            # Get final results
            final_indices = [candidate_indices[idx] for idx in rerank_indices]
            results = []

            for idx in final_indices:
                metadata = kb_data['metadatas'][idx]
                results.append({
                    'pmid': metadata['pmid'],
                    'title': metadata['title'],
                    'journal': metadata['journal'],
                    'year': metadata['year'],
                    'abstract': metadata.get('abstract', 'Abstract missing')
                })

            # Format output
            return self._format_results(results, agent_name)

        except Exception as e:
            print(f"⚠️  Hybrid retrieval failed: {e}")
            return ""

    def _format_results(self, results: List[Dict], agent_name: str) -> str:
        """Format retrieval results"""
        if not results:
            return ""

        # Customize title based on Agent type
        titles = {
            'thrombectomy': 'Thrombectomy Literature Search Results',
            'thrombolysis': 'Thrombolysis Literature Search Results',
            'indication': 'Thrombolysis Literature Search Results',
            'ncct': 'Imaging Scoring Literature Results',
            'cta': 'Imaging Triage Literature Results',
            'ctp': 'Imaging Triage Literature Results',
        }

        title = 'Literature Search Results'
        for key, val in titles.items():
            if key in agent_name:
                title = val
                break

        lines = [f"[{title}]", ""]

        for i, result in enumerate(results, 1):
            lines.append(f"{i}. {result['title']}")
            lines.append(f"   PMID: {result['pmid']} | Journal: {result['journal']} | Year: {result['year']}")
            lines.append(f"   Abstract: {result.get('abstract', 'Abstract missing')}")
            lines.append("")

        return '\n'.join(lines)
