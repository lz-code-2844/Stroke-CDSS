#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Knowledge Base Base Class

Defines unified knowledge base interface
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from rag.vector_store import VectorStore
from rag.embedder import EmbeddingService


class BaseKnowledgeBase(ABC):
    """Knowledge Base Base Class"""

    def __init__(self,
                 collection_name: str,
                 vector_store: VectorStore,
                 embedder: EmbeddingService):
        """
        Initialize knowledge base

        Args:
            collection_name: Vector store collection name
            vector_store: Vector store instance
            embedder: Embedding service instance
        """
        self.collection_name = collection_name
        self.vector_store = vector_store
        self.embedder = embedder

    def search(self,
               query: str,
               top_k: int = 5,
               filters: Optional[Dict] = None) -> List[Dict]:
        """
        Retrieve relevant literature

        Args:
            query: Query text
            top_k: Return top-k results
            filters: Metadata filter conditions (e.g. year, journal)

        Returns:
            List of retrieval results
        """
        # Generate query embedding
        query_embedding = self.embedder.embed(query)[0]

        # Vector retrieval
        results = self.vector_store.search(
            collection_name=self.collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            where=filters
        )

        # Format results
        formatted_results = []
        if results and 'documents' in results:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if 'metadatas' in results else {},
                    'distance': results['distances'][0][i] if 'distances' in results else None,
                    'id': results['ids'][0][i] if 'ids' in results else None
                })

        return formatted_results

    @abstractmethod
    def build_query(self, context: Dict) -> str:
        """
        Build query string based on context (to be implemented by subclass)

        Args:
            context: Patient context information

        Returns:
            Query string
        """
        pass

    @abstractmethod
    def format_results(self, results: List[Dict]) -> str:
        """
        Format retrieval results as prompt-usable text (to be implemented by subclass)

        Args:
            results: Retrieval results

        Returns:
            Formatted text
        """
        pass

    def retrieve_for_agent(self, context: Dict, top_k: int = 3) -> str:
        """
        Provide retrieval service for Agent (full pipeline)

        Args:
            context: Patient context
            top_k: Return top-k results

        Returns:
            Formatted retrieval result text
        """
        # 1. Build query
        query = self.build_query(context)

        # 2. Retrieve
        results = self.search(query, top_k=top_k)

        # 3. Format
        formatted_text = self.format_results(results)

        return formatted_text
