#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
混合检索协调器 - 运行时使用
HybridRAGCoordinator for runtime retrieval

使用方法:
    coordinator = HybridRAGCoordinator()
    results = coordinator.retrieve('thrombectomy_agent', context, top_k=5)
"""

import os
import pickle
import numpy as np
from typing import List, Dict
from pathlib import Path

class HybridRAGCoordinator:
    """混合检索 RAG 协调器"""

    # Agent到知识库的映射
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
        """初始化混合检索协调器"""
        self.persist_dir = persist_dir
        self.knowledge_bases = {}
        self.embedding_model = None
        self.reranker_model = None

        # 加载知识库
        self._load_knowledge_bases()

        # 延迟加载模型（首次检索时加载）
        self.models_loaded = False

    def _load_knowledge_bases(self):
        """加载所有知识库"""
        if not os.path.exists(self.persist_dir):
            print(f"⚠️  混合检索目录不存在: {self.persist_dir}")
            return

        pkl_files = list(Path(self.persist_dir).glob("*.pkl"))

        for pkl_file in pkl_files:
            collection_name = pkl_file.stem

            try:
                with open(pkl_file, 'rb') as f:
                    data = pickle.load(f)

                self.knowledge_bases[collection_name] = data
                print(f"✓ 加载知识库: {collection_name} ({len(data['documents'])} 篇)")

            except Exception as e:
                print(f"⚠️  加载失败 {collection_name}: {e}")

        print(f"\n✓ HybridRAGCoordinator 初始化完成")
        print(f"  知识库数量: {len(self.knowledge_bases)}")
        print(f"  检索模式: 混合检索 (Semantic + BM25 + Reranking)")

    def _load_models(self):
        """延迟加载模型"""
        if self.models_loaded:
            return

        print("\n加载混合检索模型...")

        try:
            from sentence_transformers import SentenceTransformer, CrossEncoder

            # 加载嵌入模型
            self.embedding_model = SentenceTransformer('BAAI/bge-large-zh-v1.5')
            print("✓ 嵌入模型加载完成")

            # 加载重排序模型
            self.reranker_model = CrossEncoder('BAAI/bge-reranker-base')
            print("✓ 重排序模型加载完成")

            self.models_loaded = True

        except Exception as e:
            print(f"⚠️  模型加载失败: {e}")
            print("  将回退到简单检索模式")
            self.models_loaded = False

    def _semantic_search(self, query, kb_data, top_k=20):
        """语义检索"""
        query_embedding = self.embedding_model.encode([query], normalize_embeddings=True)[0]
        embeddings = kb_data['embeddings']

        # 计算余弦相似度
        scores = np.dot(embeddings, query_embedding)
        top_indices = np.argsort(scores)[-top_k:][::-1]

        return top_indices, scores[top_indices]

    def _bm25_search(self, query, kb_data, top_k=20):
        """BM25 关键词检索"""
        bm25 = kb_data['bm25']
        query_tokens = query.lower().split()

        scores = bm25.get_scores(query_tokens)
        top_indices = np.argsort(scores)[-top_k:][::-1]

        return top_indices, scores[top_indices]

    def _rerank(self, query, documents, top_k=5):
        """重排序"""
        pairs = [[query, doc] for doc in documents]
        scores = self.reranker_model.predict(pairs)
        top_indices = np.argsort(scores)[-top_k:][::-1]

        return top_indices, scores[top_indices]

    def _build_query(self, agent_name: str, context: Dict) -> str:
        """构建智能查询"""
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
        混合检索主方法

        流程:
        1. 语义检索 Top-20
        2. BM25 检索 Top-20
        3. 合并去重 Top-30
        4. 重排序 Top-K
        """
        # 加载模型（首次调用时）
        if not self.models_loaded:
            self._load_models()

        if not self.models_loaded:
            return ""  # 模型加载失败，返回空

        # 获取知识库
        collection_name = self.AGENT_KB_MAPPING.get(agent_name)
        if not collection_name or collection_name not in self.knowledge_bases:
            return ""

        kb_data = self.knowledge_bases[collection_name]

        # 构建查询
        query = self._build_query(agent_name, context)

        try:
            # Step 1: 语义检索
            semantic_indices, semantic_scores = self._semantic_search(query, kb_data, top_k=20)

            # Step 2: BM25 检索
            bm25_indices, bm25_scores = self._bm25_search(query, kb_data, top_k=20)

            # Step 3: 合并候选（去重）
            candidate_indices = list(set(semantic_indices) | set(bm25_indices))

            # Step 4: 重排序
            candidate_docs = [kb_data['documents'][idx] for idx in candidate_indices]
            rerank_indices, rerank_scores = self._rerank(query, candidate_docs, top_k=top_k)

            # 获取最终结果
            final_indices = [candidate_indices[idx] for idx in rerank_indices]
            results = []

            for idx in final_indices:
                metadata = kb_data['metadatas'][idx]
                results.append({
                    'pmid': metadata['pmid'],
                    'title': metadata['title'],
                    'journal': metadata['journal'],
                    'year': metadata['year'],
                    'abstract': metadata.get('abstract', '摘要缺失')
                })

            # 格式化输出
            return self._format_results(results, agent_name)

        except Exception as e:
            print(f"⚠️  混合检索失败: {e}")
            return ""

    def _format_results(self, results: List[Dict], agent_name: str) -> str:
        """格式化检索结果"""
        if not results:
            return ""

        # 根据Agent类型定制标题
        titles = {
            'thrombectomy': '取栓文献检索结果',
            'thrombolysis': '溶栓文献检索结果',
            'indication': '溶栓文献检索结果',
            'ncct': '影像评分文献检索结果',
            'cta': '影像分诊文献检索结果',
            'ctp': '影像分诊文献检索结果',
        }

        title = '文献检索结果'
        for key, val in titles.items():
            if key in agent_name:
                title = val
                break

        lines = [f"【{title}】", ""]

        for i, result in enumerate(results, 1):
            lines.append(f"{i}. {result['title']}")
            lines.append(f"   PMID: {result['pmid']} | 期刊: {result['journal']} | 年份: {result['year']}")
            lines.append(f"   摘要: {result.get('abstract', '摘要缺失')}")
            lines.append("")

        return '\n'.join(lines)
