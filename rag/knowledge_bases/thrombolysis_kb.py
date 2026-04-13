#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
溶栓知识库 (Thrombolysis Knowledge Base)

检索溶栓(IVT)相关的文献证据
"""

from typing import Dict, List
from .base_kb import BaseKnowledgeBase


class ThrombolysisKB(BaseKnowledgeBase):
    """溶栓知识库"""

    def __init__(self, vector_store, embedder):
        super().__init__(
            collection_name="thrombolysis_literature",
            vector_store=vector_store,
            embedder=embedder
        )

    def build_query(self, context: Dict) -> str:
        """
        构建溶栓相关查询

        关键信息：
        - 发病时间（< 4.5h）
        - 禁忌症（出血、血压、血糖等）
        - 年龄、NIHSS
        """
        query_parts = ["intravenous thrombolysis rtPA alteplase acute ischemic stroke"]

        # 时间窗
        if 'onset_to_arrival_hours' in context:
            try:
                hours = float(context['onset_to_arrival_hours'])
                if hours < 3:
                    query_parts.append("0-3 hours ultra-early window")
                elif hours < 4.5:
                    query_parts.append("3-4.5 hours standard time window")
            except:
                pass

        # 禁忌症检查
        if 'hemorrhage_detected' in context and context.get('hemorrhage_detected'):
            query_parts.append("intracranial hemorrhage contraindication")

        # NIHSS评分
        if 'nihss_score' in context:
            try:
                nihss = int(context['nihss_score'])
                if nihss < 5:
                    query_parts.append("mild stroke low NIHSS thrombolysis benefit risk")
                elif nihss > 20:
                    query_parts.append("severe stroke high NIHSS thrombolysis safety")
            except:
                pass

        # 年龄
        if 'age' in context:
            try:
                age = int(context.get('age', 0))
                if age > 80:
                    query_parts.append("elderly patients age over 80 thrombolysis")
            except:
                pass

        return " ".join(query_parts)

    def format_results(self, results: List[Dict]) -> str:
        """格式化为prompt文本（完整版，包含摘要）"""
        if not results:
            return "【溶栓文献证据】\n未找到相关文献。"

        formatted = ["【溶栓文献证据】"]

        for idx, result in enumerate(results[:3], 1):
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
