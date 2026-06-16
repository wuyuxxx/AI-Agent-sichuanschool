"""Trie 树高频敏感词拦截引擎 — 第一道防线（Deterministic Gate）"""

from typing import List, Optional


class TrieNode:
    __slots__ = ("children", "is_end", "keyword")

    def __init__(self):
        self.children = {}
        self.is_end = False
        self.keyword: Optional[str] = None


class CrisisTrieFilter:
    """基于 Trie 树的高危敏感词秒级扫描引擎"""

    def __init__(self, keywords: List[str]):
        self.root = TrieNode()
        for kw in keywords:
            self._insert(kw)

    def _insert(self, keyword: str):
        node = self.root
        for ch in keyword:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True
        node.keyword = keyword

    def scan(self, text: str) -> List[str]:
        """扫描文本，返回所有命中的高危词列表"""
        hits = []
        for i in range(len(text)):
            node = self.root
            for j in range(i, len(text)):
                ch = text[j]
                if ch not in node.children:
                    break
                node = node.children[ch]
                if node.is_end:
                    hits.append(node.keyword)
                    break  # 最左匹配，防止嵌套词重复触发
        return hits

    def contains_crisis(self, text: str) -> bool:
        return len(self.scan(text)) > 0
