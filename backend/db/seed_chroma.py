"""ChromaDB 双隔离向量库 — seed 脚本"""

import os
import re
import logging
from typing import List, Dict, Any

from chromadb import PersistentClient
from chromadb.config import Settings

from backend.core.embedding import LocalEmbedding

logger = logging.getLogger(__name__)

_CHROMA_SETTINGS = Settings(anonymized_telemetry=False)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)


def _parse_policy_entries(text: str) -> List[Dict[str, Any]]:
    """解析政策文档中的结构化条目"""
    entries = []
    blocks = re.split(r"(?=\[ID: POLICY_\d+\])", text)
    for block in blocks:
        block = block.strip()
        if not block or not block.startswith("[ID: POLICY_"):
            continue

        entry: Dict[str, Any] = {"metadata": {}}

        # 提取 ID
        id_match = re.search(r"\[ID: (POLICY_\d+)\]", block)
        if id_match:
            entry["id"] = id_match.group(1)

        # 提取章节
        section_match = re.search(r"\[所属章节: (.+?)\]", block)
        if section_match:
            entry["metadata"]["section"] = section_match.group(1)

        # 提取关键词
        kw_match = re.search(r"\[核心关键词: (.+?)\]", block)
        if kw_match:
            entry["metadata"]["keywords"] = kw_match.group(1)

        # 提取年级
        grade_match = re.search(r"\[适用年级: (.+?)\]", block)
        if grade_match:
            entry["metadata"]["grade"] = grade_match.group(1)

        # 提取刚性等级
        rigid_match = re.search(r"\[刚性等级: (.+?)\]", block)
        if rigid_match:
            entry["metadata"]["rigid_level"] = rigid_match.group(1)

        # 提取条款原文
        text_match = re.search(r"【条款原文】\n(.+?)(?=【高频|$)", block, re.DOTALL)
        if text_match:
            entry["text"] = text_match.group(1).strip()
        else:
            entry["text"] = block

        entry.setdefault("id", f"policy_{len(entries)}")
        entry.setdefault("metadata", {})
        entry["metadata"]["source"] = "学生手册"
        entry.setdefault("text", block)

        entries.append(entry)

    return entries


def _parse_mental_entries(text: str) -> List[Dict[str, Any]]:
    """解析心理文档中的结构化条目"""
    entries = []
    blocks = re.split(r"(?=\[ID: (CLINICAL|MENTAL|PSY)_)", text)
    for block in blocks:
        block = block.strip()
        if not block or not block.startswith("[ID:"):
            continue

        entry: Dict[str, Any] = {"metadata": {}}

        id_match = re.search(r"\[ID: (.+?)\]", block)
        if id_match:
            entry["id"] = id_match.group(1)

        cat_match = re.search(r"\[业务分类: (.+?)\]", block)
        if cat_match:
            entry["metadata"]["category"] = cat_match.group(1)

        safety_match = re.search(r"\[安全控制级别: (.+?)\]", block)
        if safety_match:
            entry["metadata"]["safety_level"] = safety_match.group(1)

        entry["text"] = block
        entry.setdefault("id", f"mental_{len(entries)}")
        entry["metadata"]["source"] = "DSM-5CCMD心理危机分级干预指南"

        entries.append(entry)

    return entries


def seed_policy_chroma(policy_path: str, source_file: str):
    """读取政策源文件，注入 policy_chroma"""
    client = PersistentClient(path=policy_path, settings=_CHROMA_SETTINGS)
    try:
        collection = client.get_collection("policy")
        # 清空重建
        client.delete_collection("policy")
    except Exception:
        pass
    embedding_fn = LocalEmbedding()
    collection = client.create_collection("policy", embedding_function=embedding_fn,
                                          metadata={"hnsw:space": "cosine"})

    with open(source_file, "r", encoding="utf-8") as f:
        content = f.read()

    entries = _parse_policy_entries(content)
    if not entries:
        logger.warning("政策文档解析失败，将整个文件作为单条注入")
        entries = [{"id": "policy_0", "text": content, "metadata": {"source": "学生手册"}}]

    ids = [e["id"] for e in entries]
    documents = [e["text"] for e in entries]
    metadatas = [e["metadata"] for e in entries]

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    logger.info(f"✅ policy_chroma 注入完成: {len(entries)} 条")


def seed_mental_chroma(mental_path: str, source_file: str):
    """读取心理源文件，注入 mental_chroma"""
    client = PersistentClient(path=mental_path, settings=_CHROMA_SETTINGS)
    try:
        collection = client.get_collection("mental")
        client.delete_collection("mental")
    except Exception:
        pass
    embedding_fn = LocalEmbedding()
    collection = client.create_collection("mental", embedding_function=embedding_fn,
                                          metadata={"hnsw:space": "cosine"})

    with open(source_file, "r", encoding="utf-8") as f:
        content = f.read()

    entries = _parse_mental_entries(content)
    if not entries:
        logger.warning("心理文档解析失败，将整个文件作为单条注入")
        entries = [{"id": "mental_0", "text": content, "metadata": {"source": "DSM-5CCMD心理危机分级干预指南"}}]

    ids = [e["id"] for e in entries]
    documents = [e["text"] for e in entries]
    metadatas = [e["metadata"] for e in entries]

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    logger.info(f"✅ mental_chroma 注入完成: {len(entries)} 条")


def seed_all():
    """注入所有向量库"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # D:/Agent/pywork/
    parent_dir = os.path.dirname(base_dir)  # D:/Agent/
    policy_src = os.path.join(parent_dir, "student_manual_rag.txt")
    mental_src = os.path.join(parent_dir, "clinical_grade_mental_safety_v2.txt")
    policy_chroma_path = os.path.join(base_dir, "policy_chroma")
    mental_chroma_path = os.path.join(base_dir, "mental_chroma")

    if os.path.exists(policy_src):
        seed_policy_chroma(policy_chroma_path, policy_src)
    else:
        logger.warning(f"政策源文件不存在: {policy_src}")

    if os.path.exists(mental_src):
        seed_mental_chroma(mental_chroma_path, mental_src)
    else:
        logger.warning(f"心理源文件不存在: {mental_src}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    seed_all()
