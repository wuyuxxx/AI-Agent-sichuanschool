"""高级混合检索 RAG 流水线（Hybrid Search + RRF + Confidence Guardrail）"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from backend.config import RAGConfig, ChromaConfig
from backend.core.embedding import LocalEmbedding

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    多路混合检索流水线：
    - 向量检索（ChromaDB semantic search）
    - BM25 关键字检索
    - RRF 融合排序
    - 置信度阈值拦截
    """

    def __init__(self, rag_cfg: RAGConfig, chroma_cfg: ChromaConfig):
        self.cfg = rag_cfg
        self.chroma_cfg = chroma_cfg
        self._policy_collection = None
        self._mental_collection = None
        self._embedding_fn = LocalEmbedding()
        from chromadb import PersistentClient
        from chromadb.config import Settings
        # ChromaDB 模块已加载，此时抑制其遥测日志才生效
        logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
        _settings = Settings(anonymized_telemetry=False)
        self._policy_client = PersistentClient(path=chroma_cfg.policy_path, settings=_settings)
        self._mental_client = PersistentClient(path=chroma_cfg.mental_path, settings=_settings)

    def _get_collection(self, client, name: str):
        """惰性加载 collection"""
        try:
            return client.get_collection(name, embedding_function=self._embedding_fn)
        except Exception:
            return client.create_collection(name, embedding_function=self._embedding_fn,
                                            metadata={"hnsw:space": "cosine"})

    @property
    def policy_collection(self):
        if self._policy_collection is None:
            self._policy_collection = self._get_collection(self._policy_client, "policy")
        return self._policy_collection

    @property
    def mental_collection(self):
        if self._mental_collection is None:
            self._mental_collection = self._get_collection(self._mental_client, "mental")
        return self._mental_collection

    # ----------------------------------------------------------------
    # BM25 简易实现（轻量无依赖）
    # ----------------------------------------------------------------
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[\w一-鿿]+", text)

    def _bm25_score(self, query_tokens: List[str], doc_tokens: List[str],
                    avg_dl: float, N: int, df: Dict[str, int]) -> float:
        k1, b = self.cfg.bm25_k1, self.cfg.bm25_b
        dl = len(doc_tokens)
        score = 0.0
        for qt in query_tokens:
            if qt not in df or df[qt] == 0:
                continue
            idf = np.log((N - df[qt] + 0.5) / (df[qt] + 0.5) + 1.0)
            tf = doc_tokens.count(qt)
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
        return score

    def _bm25_search(self, query: str, docs: List[Dict[str, Any]]) -> List[Tuple[int, float]]:
        """BM25 检索，返回 (doc_index, score) 列表"""
        qtokens = self._tokenize(query)
        if not qtokens:
            return []

        doc_tokens_list = [self._tokenize(d["text"]) for d in docs]
        N = len(docs)
        avg_dl = np.mean([len(t) for t in doc_tokens_list]) if N > 0 else 1.0

        # 文档频率
        df: Dict[str, int] = {}
        for dt in doc_tokens_list:
            for t in set(dt):
                df[t] = df.get(t, 0) + 1

        scores = []
        for i, dt in enumerate(doc_tokens_list):
            s = self._bm25_score(qtokens, dt, avg_dl, N, df)
            if s > 0:
                scores.append((i, s))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:self.cfg.top_k]

    # ----------------------------------------------------------------
    # RRF 融合
    # ----------------------------------------------------------------
    @staticmethod
    def _rrf_fusion(vector_results: List[Tuple[int, float]],
                    bm25_results: List[Tuple[int, float]], k: int = 60) -> List[Tuple[int, float]]:
        """Reciprocal Rank Fusion"""
        scores: Dict[int, float] = {}

        for rank, (doc_id, _) in enumerate(vector_results):
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)

        for rank, (doc_id, _) in enumerate(bm25_results):
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked

    # ----------------------------------------------------------------
    # 主检索入口
    # ----------------------------------------------------------------
    async def hybrid_search(self, query: str, collection_type: str = "policy",
                            metadata_filter: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """
        多路混合检索主入口

        Args:
            query: 检索查询
            collection_type: "policy" | "mental"
            metadata_filter: 可选的元数据过滤条件

        Returns:
            带有置信度分数的检索结果列表
        """
        collection = self.policy_collection if collection_type == "policy" else self.mental_collection

        # 1. 向量检索
        where = metadata_filter or {}
        try:
            vector_results = collection.query(
                query_texts=[query],
                n_results=self.cfg.top_k * 2,
                where=where if where else None,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning(f"向量检索失败: {e}")
            vector_results = {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        # 构建文档列表
        docs = []
        vec_scores = []
        for i, doc in enumerate(vector_results.get("documents", [[]])[0] or []):
            metadata = (vector_results.get("metadatas", [[]])[0] or [{}])[i] if i < len(vector_results.get("metadatas", [[]])[0] or []) else {}
            distance = (vector_results.get("distances", [[]])[0] or [1.0])[i] if i < len(vector_results.get("distances", [[]])[0] or []) else 1.0
            similarity = 1.0 - distance  # ChromDB distance → similarity
            doc_id = len(docs)
            docs.append({"id": doc_id, "text": doc, "metadata": metadata, "similarity": similarity})
            vec_scores.append((doc_id, similarity))

        if not docs:
            return []

        # 2. BM25 检索
        bm25_scores = self._bm25_search(query, docs)

        # 3. RRF 融合
        if bm25_scores:
            fused = self._rrf_fusion(vec_scores, bm25_scores, self.cfg.rrf_k)
        else:
            fused = vec_scores

        # 4. 置信度过滤
        results = []
        for doc_id, rrf_score in fused:
            doc = docs[doc_id]
            similarity = doc["similarity"]
            if similarity < self.cfg.confidence_threshold:
                logger.info(f"切片 ID={doc_id} 相似度 {similarity:.4f} 低于阈值 {self.cfg.confidence_threshold}，已拦截")
                continue
            results.append({
                "text": doc["text"],
                "metadata": doc["metadata"],
                "similarity": similarity,
                "rrf_score": rrf_score,
            })

        return results[:self.cfg.top_k]

    def format_citation(self, results: List[Dict[str, Any]]) -> str:
        """将检索结果格式化为带有引用的上下文"""
        if not results:
            return ""

        parts = []
        for i, r in enumerate(results):
            meta = r.get("metadata", {})
            source = meta.get("source", "未知来源")
            section = meta.get("section", "")
            ref = f"[{i+1}]" + (f"[出处: {source}-{section}]" if section else f"[出处: {source}]")
            parts.append(f"{ref}\n{r['text']}")

        return "\n\n".join(parts)

    def seed_policy_collection(self, entries: List[Dict[str, Any]]):
        """批量注入政策文档到 policy_chroma"""
        ids = []
        documents = []
        metadatas = []
        for entry in entries:
            ids.append(entry["id"])
            documents.append(entry["text"])
            metadatas.append(entry.get("metadata", {}))
        self.policy_collection.add(ids=ids, documents=documents, metadatas=metadatas)
        logger.info(f"已注入 {len(entries)} 条政策文档到 policy_chroma")

    def seed_mental_collection(self, entries: List[Dict[str, Any]]):
        """批量注入心理文档到 mental_chroma"""
        ids = []
        documents = []
        metadatas = []
        for entry in entries:
            ids.append(entry["id"])
            documents.append(entry["text"])
            metadatas.append(entry.get("metadata", {}))
        self.mental_collection.add(ids=ids, documents=documents, metadatas=metadatas)
        logger.info(f"已注入 {len(entries)} 条心理文档到 mental_chroma")
