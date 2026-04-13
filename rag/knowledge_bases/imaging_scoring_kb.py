#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
影像评分知识库 (Imaging Scoring Knowledge Base)

检索影像评分（ASPECTS、Collateral等）相关文献
"""

from typing import Dict, List
from .base_kb import BaseKnowledgeBase


class ImagingScoringKB(BaseKnowledgeBase):
    """影像评分知识库"""

    def __init__(self, vector_store, embedder):
        super().__init__(
            collection_name="imaging_scoring_literature",
            vector_store=vector_store,
            embedder=embedder
        )

    def build_query(self, context: Dict) -> str:
        """
        构建影像评分查询

        关键信息：
        - ASPECTS评分
        - Collateral评分
        - Alberta评分
        """
        query_parts = ["imaging scoring stroke"]

        # ASPECTS评分
        if 'aspects_score' in context or 'ncct_output' in context:
            query_parts.append("ASPECTS score Alberta Stroke Program Early CT Score")

        # CTA评分（侧支循环）
        if 'cta_output' in context:
            query_parts.append("collateral circulation grading collateral score")

        # 梗死核心体积
        if 'ctp_output' in context:
            query_parts.append("infarct core volume ischemic penumbra measurement")

        return " ".join(query_parts)

    def format_results(self, results: List[Dict]) -> str:
        """格式化为prompt文本（完整版，包含摘要）"""
        if not results:
            return "【影像评分文献】\n未找到相关文献。"

        formatted = ["【影像评分文献】"]

        for idx, result in enumerate(results[:3], 1):
            metadata = result.get('metadata', {})
            title = metadata.get('title', 'No title')
            pmid = metadata.get('pmid', 'N/A')
            journal = metadata.get('journal', 'N/A')
            year = metadata.get('year', 'N/A')

            # 优先从metadata获取完整摘要
            abstract = metadata.get('abstract', '')

            # 如果metadata中没有，才尝试从document解析
            if not abstract:
                document = result.get('document', '')
                if 'Abstract:' in document:
                    abstract = document.split('Abstract:', 1)[1].strip()
                elif 'BACKGROUND:' in document or 'METHODS:' in document or 'RESULTS:' in document:
                    abstract = document
                else:
                    abstract = document

            # 清理摘要内容
            abstract = str(abstract).strip()
            if abstract.lower() == 'nan':
                abstract = ""

            # 限制摘要长度（1500字符）
            if len(abstract) > 1500:
                abstract = abstract[:1497] + "..."

            key_findings = metadata.get('key_findings', '')
            conclusion_line = f"\n   关键结论: {key_findings}" if key_findings else ""

            formatted.append(
                f"\n{idx}. {title}\n"
                f"   PMID: {pmid} | 期刊: {journal} | 年份: {year}\n"
                f"   摘要: {abstract or '[无摘要]'}{conclusion_line}"
            )

        return "\n".join(formatted)
