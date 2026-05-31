# 02_utils/rag_engine.py

import os

class SimpleRAG:
    def __init__(self, knowledge_dir="data/knowledge_base"):
        self.knowledge = {}
        # Assume guideline filenames are ivt_guidelines.txt and evt_guidelines.txt
        if os.path.exists(knowledge_dir):
            for f in os.listdir(knowledge_dir):
                if f.endswith('.txt'):
                    with open(os.path.join(knowledge_dir, f), 'r', encoding='utf-8') as file:
                        self.knowledge[f] = file.read()
    
    def retrieve(self, query_type):
        """Return guideline context based on query type"""
        if query_type == "thrombolysis":
            return self.knowledge.get("ivt_guidelines.txt", "IVT guidelines not found, please exercise caution.")
        elif query_type == "thrombectomy":
            return self.knowledge.get("evt_guidelines.txt", "EVT guidelines not found, please exercise caution.")
        return "No relevant guidelines found."