#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化版 RAG 协调器（兼容版本）

支持两种模式：
1. 完整版：使用ChromaDB + Embedding模型
2. 简化版：使用TF-IDF + Pickle（无需安装ChromaDB）
"""

import os
import pickle
from typing import Dict, Optional, List


class SimpleRAGCoordinator:
    """简化版RAG协调器（使用TF-IDF，不依赖ChromaDB）"""

    # Agent到知识库的映射关系
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
        """初始化简化版RAG协调器"""
        self.persist_dir = persist_dir
        self.vectorizer = None
        self.literature_db = {}

        # 加载vectorizer
        vectorizer_path = os.path.join(persist_dir, 'vectorizer.pkl')
        if os.path.exists(vectorizer_path):
            with open(vectorizer_path, 'rb') as f:
                self.vectorizer = pickle.load(f)

        # 加载所有collection
        for coll_name in ['thrombectomy_literature', 'thrombolysis_literature',
                          'imaging_triage_literature', 'imaging_scoring_literature']:
            coll_file = os.path.join(persist_dir, f'{coll_name}.pkl')
            if os.path.exists(coll_file):
                with open(coll_file, 'rb') as f:
                    self.literature_db[coll_name] = pickle.load(f)

        print(f"✓ SimpleRAGCoordinator initialized with {len(self.literature_db)} knowledge bases")

    def retrieve(self, agent_name: str, context: Dict, top_k: int = 3) -> Optional[str]:
        """为指定Agent检索相关文献"""
        # 根据Agent名称确定使用哪个知识库
        collection_name = self.AGENT_KB_MAPPING.get(agent_name)

        if collection_name is None or collection_name not in self.literature_db:
            return None

        # 构建查询
        query = self._build_query(agent_name, context)

        # 执行检索
        results = self._search(collection_name, query, top_k)

        # 格式化结果
        return self._format_results(results, agent_name)

    def _build_query(self, agent_name: str, context: Dict) -> str:
        """根据Agent类型和上下文构建查询"""
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
        """执行检索"""
        if not self.vectorizer or collection_name not in self.literature_db:
            return []

        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        coll_data = self.literature_db[collection_name]

        # 向量化查询
        query_vec = self.vectorizer.transform([query])

        # 计算相似度
        similarities = cosine_similarity(query_vec, coll_data['vectors'])[0]

        # 获取top-k
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
        """格式化检索结果"""
        if not results:
            return f"【文献检索】\n未找到相关文献。"

        kb_type_names = {
            'thrombectomy': '取栓',
            'thrombolysis': '溶栓',
            'indication': '溶栓',
            'ncct_imaging': '影像评分',
            'cta_imaging': '影像分诊',
            'ctp_imaging': '影像分诊'
        }

        kb_type = next((v for k, v in kb_type_names.items() if k in agent_name), '临床')
        formatted = [f"【{kb_type}文献检索结果】"]

        for idx, result in enumerate(results, 1):
            metadata = result.get('metadata', {})
            title = metadata.get('title', 'No title')
            pmid = metadata.get('pmid', 'N/A')
            journal = metadata.get('journal', 'N/A')
            year = metadata.get('year', 'N/A')

            formatted.append(
                f"\n{idx}. {title}\n"
                f"   PMID: {pmid} | 期刊: {journal} | 年份: {year}"
            )

        return "\n".join(formatted)

    def check_kb_status(self) -> Dict[str, int]:
        """检查各知识库状态"""
        status = {}
        for kb_name, kb_data in self.literature_db.items():
            status[kb_name] = len(kb_data['documents'])
        return status


# 兼容性包装：自动选择可用的RAG系统
def RAGCoordinator(*args, **kwargs):
    """
    智能RAG协调器工厂函数

    自动选择：
    1. 如果simple_rag可用 → 使用SimpleRAGCoordinator
    2. 如果chromadb可用 → 使用完整版RAGCoordinator
    3. 都不可用 → 返回None
    """
    # 尝试简化版（优先）
    try:
        coordinator = SimpleRAGCoordinator()
        if coordinator.literature_db:
            print("✓ Using SimpleRAGCoordinator (TF-IDF based)")
            return coordinator
    except Exception as e:
        print(f"SimpleRAGCoordinator not available: {e}")

    # 尝试完整版
    try:
        from rag.rag_coordinator import RAGCoordinator as FullRAGCoordinator
        coordinator = FullRAGCoordinator(*args, **kwargs)
        print("✓ Using Full RAGCoordinator (ChromaDB based)")
        return coordinator
    except Exception as e:
        print(f"Full RAGCoordinator not available: {e}")

    return None


if __name__ == "__main__":
    # 测试代码
    print("Testing SimpleRAGCoordinator...")

    coordinator = RAGCoordinator()

    if coordinator:
        # 检查知识库状态
        print("\n知识库状态:")
        status = coordinator.check_kb_status()
        for kb_name, count in status.items():
            print(f"  {kb_name}: {count} documents")

        # 测试检索
        test_context = {
            'lvo_output': 'M1 segment occlusion',
            'nihss_score': 15
        }

        print("\n测试检索 (thrombectomy_agent):")
        result = coordinator.retrieve('thrombectomy_agent', test_context, top_k=2)
        if result:
            print(result[:500] + "..." if len(result) > 500 else result)
        else:
            print("  No results")
    else:
        print("✗ No RAG coordinator available")
