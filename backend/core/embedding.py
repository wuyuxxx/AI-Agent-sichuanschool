"""统一嵌入函数 — 供 seed 和 RAG 流水线共享"""

import hashlib
from typing import List

import numpy as np
from chromadb.api.types import EmbeddingFunction, Embeddings


class LocalEmbedding(EmbeddingFunction):
    """
    轻量本地嵌入函数（无需下载模型）。
    基于字符 n-gram 哈希的特征向量，维度 384（与 all-MiniLM-L6-v2 对齐）。
    生产环境建议替换为 sentence-transformers / ONNX 模型。
    """

    def __init__(self, dim: int = 384):
        self.dim = dim
        self._name = "local_ngram_hash"

    def __call__(self, input: List[str]) -> Embeddings:
        embeddings = []
        for text in input:
            features = np.zeros(self.dim, dtype=np.float32)
            for i in range(len(text)):
                for n in range(1, 4):
                    if i + n <= len(text):
                        gram = text[i:i + n]
                        h = hashlib.md5(gram.encode("utf-8")).digest()
                        idx = int.from_bytes(h[:4], "little") % self.dim
                        features[idx] += 1.0
            norm = np.linalg.norm(features)
            if norm > 0:
                features /= norm
            embeddings.append(features.tolist())
        return embeddings

    def __repr__(self):
        return f"LocalEmbedding(dim={self.dim})"
