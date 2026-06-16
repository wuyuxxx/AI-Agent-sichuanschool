"""情感极性滑动监控与灰度降级 — 第三道防线"""

import logging
from typing import List, Dict, Any
from dataclasses import dataclass

from backend.config import AffectiveConfig

logger = logging.getLogger(__name__)


@dataclass
class AffectiveReport:
    """情感审计报告"""
    avg_score: float
    slope: float  # 线性回归斜率，负值表示恶化
    is_deteriorating: bool
    needs_degradation: bool  # 是否触发灰度降级
    needs_alert: bool  # 是否触发后台预警


class AffectiveGuardrail:
    """
    情感极性滑动监控器
    对会话历史进行情感动态审计，检测负向情感恶化趋势
    """

    def __init__(self, cfg: AffectiveConfig):
        self.cfg = cfg

    def analyze(self, history: List[Dict[str, Any]]) -> AffectiveReport:
        """
        对最近 N 轮用户消息进行情感分析。
        使用简易词典评分（生产环境可替换为深度学习模型）。
        """
        scores = []
        for msg in history:
            text = msg.get("content", "")
            score = self._polarity_score(text)
            scores.append(score)

        if len(scores) < 2:
            return AffectiveReport(
                avg_score=sum(scores) / max(len(scores), 1),
                slope=0.0,
                is_deteriorating=False,
                needs_degradation=False,
                needs_alert=False,
            )

        avg_score = sum(scores) / len(scores)

        # 简单线性回归计算斜率
        n = len(scores)
        x_mean = (n - 1) / 2
        y_mean = avg_score
        num = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(scores))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0.0

        is_deteriorating = slope < self.cfg.threshold
        needs_degradation = is_deteriorating
        needs_alert = any(s < self.cfg.alert_negative_score for s in scores[-2:])

        return AffectiveReport(
            avg_score=avg_score,
            slope=slope,
            is_deteriorating=is_deteriorating,
            needs_degradation=needs_degradation,
            needs_alert=needs_alert,
        )

    @staticmethod
    def _polarity_score(text: str) -> float:
        """简易情感极性打分（-1 ~ 1），负值表示负面"""
        positive_words = {
            "开心", "高兴", "谢谢", "好", "不错", "喜欢", "满意",
            "太好了", "没问题", "理解了", "懂了", "可以",
        }
        negative_words = {
            "难过", "伤心", "痛苦", "焦虑", "害怕", "孤独", "绝望",
            "失眠", "烦躁", "累", "没意思", "无聊", "压力", "难受",
            "讨厌", "恶心", "烦", "崩溃", "受不了", "没用", "差",
        }

        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)
        total = pos_count + neg_count
        if total == 0:
            return 0.0
        # 归一化到 [-1, 1]
        raw = (pos_count - neg_count) / total
        return max(-1.0, min(1.0, raw))
