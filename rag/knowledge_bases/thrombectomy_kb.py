#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
取栓知识库 (Thrombectomy Knowledge Base)

检索取栓相关的文献证据
"""

from typing import Dict, List
from .base_kb import BaseKnowledgeBase


class ThrombectomyKB(BaseKnowledgeBase):
    """取栓知识库"""

    def __init__(self, vector_store, embedder):
        super().__init__(
            collection_name="thrombectomy_literature",
            vector_store=vector_store,
            embedder=embedder
        )

    def build_query(self, context: Dict) -> str:
        """
        构建取栓相关查询

        关键信息：
        - LVO位置（ICA/M1/M2/基底动脉）
        - NIHSS评分
        - 时间窗
        - 影像指标（ASPECTS、梗死核心）
        """
        query_parts = ["endovascular thrombectomy mechanical thrombectomy"]

        # 血管闭塞位置
        if 'lvo_output' in context:
            lvo_info = context['lvo_output']
            if isinstance(lvo_info, str) and any(v in lvo_info for v in ['ICA', 'M1', 'M2', 'basilar']):
                query_parts.append(f"{lvo_info} occlusion")

        # NIHSS评分范围
        if 'nihss_score' in context:
            try:
                nihss = int(context['nihss_score'])
                if nihss >= 20:
                    query_parts.append("severe stroke high NIHSS")
                elif nihss >= 10:
                    query_parts.append("moderate to severe stroke")
            except:
                pass

        # 时间窗
        if 'onset_time_category' in context:
            time_cat = context['onset_time_category']
            if '6h' in time_cat or '<6' in time_cat:
                query_parts.append("early time window 0-6 hours")
            elif '6-24' in time_cat:
                query_parts.append("extended time window DAWN DEFUSE")

        # ASPECTS评分
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
        格式化为prompt文本（完整版，包含摘要）

        格式：
        【取栓文献证据】
        1. [标题]
           PMID: xxx | 期刊: xxx | 年份: xxx
           摘要: [完整摘要内容]
           关键结论: [关键结论]
        """
        if not results:
            return "【取栓文献证据】\n未找到相关文献。"

        formatted = ["【取栓文献证据】"]

        for idx, result in enumerate(results[:3], 1):  # 只取前3篇
            metadata = result.get('metadata', {})
            title = metadata.get('title', 'No title')
            pmid = metadata.get('pmid', 'N/A')
            journal = metadata.get('journal', 'N/A')
            year = metadata.get('year', 'N/A')

            # 优先从metadata获取完整摘要（这是原始完整摘要）
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
            # 移除可能的"nan"字符串
            if abstract.lower() == 'nan':
                abstract = ""

            # 限制摘要长度（1500字符，保证足够详细但不过长）
            if len(abstract) > 1500:
                abstract = abstract[:1497] + "..."

            # 关键结论（如果有）
            key_findings = metadata.get('key_findings', '')
            conclusion_line = f"\n   关键结论: {key_findings}" if key_findings else ""

            formatted.append(
                f"\n{idx}. {title}\n"
                f"   PMID: {pmid} | 期刊: {journal} | 年份: {year}\n"
                f"   摘要: {abstract or '[无摘要]'}{conclusion_line}"
            )

        return "\n".join(formatted)
