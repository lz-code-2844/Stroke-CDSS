# 02_utils/rag_engine.py

import os

class SimpleRAG:
    def __init__(self, knowledge_dir="data/knowledge_base"):
        self.knowledge = {}
        # 假设指南文件名为 ivt_guidelines.txt 和 evt_guidelines.txt
        if os.path.exists(knowledge_dir):
            for f in os.listdir(knowledge_dir):
                if f.endswith('.txt'):
                    with open(os.path.join(knowledge_dir, f), 'r', encoding='utf-8') as file:
                        self.knowledge[f] = file.read()
    
    def retrieve(self, query_type):
        """根据查询类型返回对应的指南上下文"""
        if query_type == "thrombolysis":
            return self.knowledge.get("ivt_guidelines.txt", "未找到溶栓指南，请谨慎决策。")
        elif query_type == "thrombectomy":
            return self.knowledge.get("evt_guidelines.txt", "未找到取栓指南，请谨慎决策。")
        return "未找到相关指南。"