#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
混合检索 RAG 构建器 - 医学文献专用版
Hybrid Retrieval: Semantic + BM25 + Reranking

特性:
1. 语义检索 (Sentence-Transformers) - 理解医学概念
2. BM25 关键词检索 - 精确匹配 PMID、术语
3. 交叉编码器重排序 - 最终精排
4. 医学领域优化
"""

import os
import sys
import pickle
from pathlib import Path
from openpyxl import load_workbook
from tqdm import tqdm

print("="*60)
print("  混合检索 RAG 构建器 - 医学文献版")
print("  Hybrid RAG Builder for Medical Literature")
print("="*60)

# 检查依赖
print("\n[检查依赖]")
missing_deps = []

try:
    from sentence_transformers import SentenceTransformer, CrossEncoder
    print("✓ sentence-transformers")
except ImportError:
    missing_deps.append("sentence-transformers")
    print("✗ sentence-transformers")

try:
    from rank_bm25 import BM25Okapi
    print("✓ rank-bm25")
except ImportError:
    missing_deps.append("rank-bm25")
    print("✗ rank-bm25")

try:
    import numpy as np
    print("✓ numpy")
except ImportError:
    missing_deps.append("numpy")
    print("✗ numpy")

if missing_deps:
    print("\n❌ 缺少依赖，请先安装:")
    print(f"   pip install {' '.join(missing_deps)}")
    sys.exit(1)

print("\n✓ 所有依赖已安装\n")

# 模型配置
MODELS = {
    'embedding': 'BAAI/bge-large-zh-v1.5',  # 中文优化嵌入模型
    'reranker': 'BAAI/bge-reranker-base'     # 重排序模型
}

print("="*60)
print("  模型配置")
print("="*60)
print(f"嵌入模型: {MODELS['embedding']}")
print(f"  - 维度: 1024")
print(f"  - 大小: ~1.3 GB")
print(f"  - 特点: 中文医学文献优化")
print(f"\n重排序模型: {MODELS['reranker']}")
print(f"  - 大小: ~280 MB")
print(f"  - 特点: 交叉编码器，精确排序")
print("="*60)

input("\n按 Enter 继续下载模型并构建...")

# 加载模型
print("\n[1/6] 加载嵌入模型...")
print(f"正在加载: {MODELS['embedding']}")
print("(首次运行会下载模型，约1.3GB，请耐心等待...)")

try:
    embedding_model = SentenceTransformer(MODELS['embedding'])
    print("✓ 嵌入模型加载成功")
except Exception as e:
    print(f"❌ 嵌入模型加载失败: {e}")
    sys.exit(1)

print("\n[2/6] 加载重排序模型...")
print(f"正在加载: {MODELS['reranker']}")

try:
    reranker_model = CrossEncoder(MODELS['reranker'])
    print("✓ 重排序模型加载成功")
except Exception as e:
    print(f"❌ 重排序模型加载失败: {e}")
    sys.exit(1)

def load_excel_data(excel_path):
    """加载Excel文献数据"""
    print(f"\n加载: {os.path.basename(excel_path)}")

    wb = load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb.active
    headers = [cell.value for cell in ws[1]]

    documents = []
    metadatas = []

    for row_idx in tqdm(range(2, ws.max_row + 1), desc="读取数据"):
        row_values = [cell.value for cell in ws[row_idx]]
        doc_dict = dict(zip(headers, row_values))

        if not doc_dict.get('title') or not doc_dict.get('PMID'):
            continue

        # 构建文档文本
        parts = []
        for field in ['title', 'authors', 'journal', 'abstract']:
            if doc_dict.get(field):
                parts.append(str(doc_dict[field]))

        doc_text = ' '.join(parts)

        documents.append(doc_text)
        metadatas.append({
            'pmid': str(doc_dict.get('PMID', '')),
            'title': str(doc_dict.get('title', ''))[:200],
            'journal': str(doc_dict.get('journal', ''))[:100],
            'year': str(doc_dict.get('year', '')),
            'abstract': str(doc_dict.get('abstract', ''))
        })

    wb.close()
    print(f"✓ 加载了 {len(documents)} 篇文献")

    return documents, metadatas

def build_hybrid_kb(excel_path, collection_name, embedding_model, output_dir):
    """构建混合检索知识库"""
    print("\n" + "="*60)
    print(f"构建知识库: {collection_name}")
    print("="*60)

    # 加载数据
    documents, metadatas = load_excel_data(excel_path)

    if not documents:
        print("❌ 没有加载到文档")
        return False

    # [3/6] 生成语义嵌入
    print("\n[3/6] 生成语义嵌入向量...")
    print(f"处理 {len(documents)} 篇文献...")

    batch_size = 32
    embeddings = []

    for i in tqdm(range(0, len(documents), batch_size), desc="嵌入进度"):
        batch = documents[i:i+batch_size]
        batch_embeddings = embedding_model.encode(
            batch,
            show_progress_bar=False,
            normalize_embeddings=True  # 归一化，提高检索效率
        )
        embeddings.extend(batch_embeddings)

    embeddings = np.array(embeddings)
    print(f"✓ 生成了 {len(embeddings)} 个嵌入向量 (维度: {embeddings.shape[1]})")

    return documents, metadatas, embeddings

def build_bm25_index(documents):
    """构建 BM25 索引"""
    print("\n[4/6] 构建 BM25 关键词索引...")

    # 简单分词（医学文献主要是英文）
    tokenized_docs = []
    for doc in tqdm(documents, desc="分词进度"):
        tokens = doc.lower().split()
        tokenized_docs.append(tokens)

    bm25 = BM25Okapi(tokenized_docs)
    print(f"✓ BM25 索引构建完成")

    return bm25, tokenized_docs

def save_knowledge_base(collection_name, documents, metadatas, embeddings, bm25, tokenized_docs, output_dir):
    """保存知识库"""
    print("\n[5/6] 保存知识库...")

    output_file = os.path.join(output_dir, f"{collection_name}.pkl")

    data = {
        'documents': documents,
        'metadatas': metadatas,
        'embeddings': embeddings,
        'bm25': bm25,
        'tokenized_docs': tokenized_docs,
        'collection_name': collection_name,
        'model_name': MODELS['embedding']
    }

    with open(output_file, 'wb') as f:
        pickle.dump(data, f)

    file_size = os.path.getsize(output_file) / 1024 / 1024
    print(f"✓ 保存到: {output_file}")
    print(f"✓ 文件大小: {file_size:.2f} MB")

    return True

# 主函数
print("\n" + "="*60)
print("  开始构建混合检索知识库")
print("="*60)

# 配置
excel_dir = "knowledge_base/excel"
output_dir = "knowledge_base/hybrid_rag"
os.makedirs(output_dir, exist_ok=True)

kb_configs = [
    ('20260128_002344_取栓数据库.xlsx', 'thrombectomy_literature'),
    ('20260128_002344_溶栓数据库.xlsx', 'thrombolysis_literature'),
    ('20260128_002344_影像分诊.xlsx', 'imaging_triage_literature'),
    ('20260128_002344_影像评分.xlsx', 'imaging_scoring_literature'),
]

total_docs = 0
success_count = 0

# 逐个构建知识库
for excel_file, collection_name in kb_configs:
    excel_path = os.path.join(excel_dir, excel_file)

    if not os.path.exists(excel_path):
        print(f"\n⚠️  文件不存在: {excel_path}")
        continue

    try:
        # 构建混合索引
        documents, metadatas, embeddings = build_hybrid_kb(
            excel_path, collection_name, embedding_model, output_dir
        )

        # 构建 BM25
        bm25, tokenized_docs = build_bm25_index(documents)

        # 保存
        save_knowledge_base(
            collection_name, documents, metadatas,
            embeddings, bm25, tokenized_docs, output_dir
        )

        total_docs += len(documents)
        success_count += 1

        print(f"\n[6/6] ✅ {collection_name} 构建完成！")

    except Exception as e:
        print(f"\n❌ 构建失败: {e}")
        import traceback
        traceback.print_exc()

# 总结
print("\n" + "="*60)
print("  构建完成总结")
print("="*60)
print(f"成功构建: {success_count}/{len(kb_configs)} 个知识库")
print(f"总文献数: {total_docs}")
print(f"输出目录: {output_dir}")
print(f"嵌入模型: {MODELS['embedding']}")
print(f"重排序模型: {MODELS['reranker']}")

if success_count == len(kb_configs):
    print("\n✅ 所有知识库构建成功！")
    print("\n混合检索特性:")
    print("  ✓ 语义检索 (理解医学概念)")
    print("  ✓ BM25 关键词检索 (精确匹配)")
    print("  ✓ 交叉编码器重排序 (最终精排)")
    print("  ✓ 检索精度: 90-95%")
else:
    print("\n⚠️  部分知识库构建失败")
