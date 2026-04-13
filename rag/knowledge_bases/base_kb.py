#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知识库基类

定义统一的知识库接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from rag.vector_store import VectorStore
from rag.embedder import EmbeddingService


class BaseKnowledgeBase(ABC):
    """知识库基类"""

    def __init__(self,
                 collection_name: str,
                 vector_store: VectorStore,
                 embedder: EmbeddingService):
        """
        初始化知识库

        Args:
            collection_name: 向量库collection名称
            vector_store: 向量存储实例
            embedder: Embedding服务实例
        """
        self.collection_name = collection_name
        self.vector_store = vector_store
        self.embedder = embedder

    def search(self,
               query: str,
               top_k: int = 5,
               filters: Optional[Dict] = None) -> List[Dict]:
        """
        检索相关文献

        Args:
            query: 查询文本
            top_k: 返回top-k个结果
            filters: 元数据过滤条件（如year、journal等）

        Returns:
            检索结果列表
        """
        # 生成查询向量
        query_embedding = self.embedder.embed(query)[0]

        # 向量检索
        results = self.vector_store.search(
            collection_name=self.collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            where=filters
        )

        # 格式化结果
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
        根据上下文构建查询字符串（需子类实现）

        Args:
            context: 患者上下文信息

        Returns:
            查询字符串
        """
        pass

    @abstractmethod
    def format_results(self, results: List[Dict]) -> str:
        """
        格式化检索结果为prompt可用的文本（需子类实现）

        Args:
            results: 检索结果

        Returns:
            格式化的文本
        """
        pass

    def retrieve_for_agent(self, context: Dict, top_k: int = 3) -> str:
        """
        为Agent提供检索服务（完整流程）

        Args:
            context: 患者上下文
            top_k: 返回top-k个结果

        Returns:
            格式化的检索结果文本
        """
        # 1. 构建查询
        query = self.build_query(context)

        # 2. 检索
        results = self.search(query, top_k=top_k)

        # 3. 格式化
        formatted_text = self.format_results(results)

        return formatted_text
