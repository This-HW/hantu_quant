#!/usr/bin/env python3
"""
적응형 필터 튜너 (Adaptive Filter Tuner)

실거래 결과를 기반으로 필터 임계값을 동적으로 조정하는 모듈.
학습 데이터가 쌓이면 점진적으로 최적화됨.

주요 기능:
1. 거래 결과 기록 및 분석
2. 성공/실패 패턴 학습
3. 필터 임계값 동적 조정
4. 시장 레짐별 최적 임계값 탐색
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class TradeResult:
    """거래 결과 데이터"""
    stock_code: str
    stock_name: str
    entry_date: str
    exit_date: Optional[str]
    entry_price: float
    exit_price: Optional[float]
    profit_rate: Optional[float]
    is_success: Optional[bool]  # profit_rate > 0

    # 선정 당시 지표
    total_score: float
    technical_score: float
    risk_score: float
    confidence: float
    volume_score: float
    composite_score: float

    # 시장 상황
    market_condition: str


@dataclass
class FilterThresholds:
    """필터 임계값 세트"""
    price_attractiveness: float
    risk_score_max: float
    confidence_min: float
    min_technical_score: float
    liquidity_score: float
    min_composite_score: float


class AdaptiveFilterTuner:
    """적응형 필터 튜너

    학습 데이터가 쌓이면 점진적으로 필터 임계값을 최적화.
    """

    # 최소 학습 데이터 수
    MIN_TRADES_FOR_LEARNING = 20

    # 학습률 (얼마나 빠르게 조정할지)
    LEARNING_RATE = 0.1

    # 안전 마진 (급격한 변화 방지)
    SAFETY_MARGIN = 0.2

    def __init__(self, data_dir: str = "data/learning"):
        self.data_dir = data_dir
        self.trade_history: List[TradeResult] = []

        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)

        # 기존 데이터 로드
        self._load_history()

        logger.info(f"AdaptiveFilterTuner 초기화 - 거래 기록: {len(self.trade_history)}건")

    def _load_history(self):
        """거래 기록 로드"""
        try:
            history_file = os.path.join(self.data_dir, "trade_history.json")
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get("trades", []):
                        self.trade_history.append(TradeResult(**item))
        except Exception as e:
            logger.error(f"거래 기록 로드 실패: {e}", exc_info=True)

    def _save_history(self):
        """거래 기록 저장"""
        try:
            history_file = os.path.join(self.data_dir, "trade_history.json")
            data = {
                "updated_at": datetime.now().isoformat(),
                "total_trades": len(self.trade_history),
                "trades": [asdict(t) for t in self.trade_history]
            }
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"거래 기록 저장 실패: {e}", exc_info=True)

    def record_trade(self, trade: TradeResult):
        """거래 결과 기록"""
        self.trade_history.append(trade)
        self._save_history()
        logger.info(f"거래 기록 추가: {trade.stock_code} - 수익률: {trade.profit_rate:.2%}")

    def record_trade_result(
        self,
        stock_code: str,
        stock_name: str,
        entry_date: str,
        exit_date: str,
        entry_price: float,
        exit_price: float,
        selection_metrics: Dict,
        market_condition: str
    ):
        """거래 결과 기록 (간편 버전)"""
        profit_rate = (exit_price - entry_price) / entry_price
        is_success = profit_rate > 0

        trade = TradeResult(
            stock_code=stock_code,
            stock_name=stock_name,
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            profit_rate=profit_rate,
            is_success=is_success,
            total_score=selection_metrics.get("total_score", 0),
            technical_score=selection_metrics.get("technical_score", 0),
            risk_score=selection_metrics.get("risk_score", 0),
            confidence=selection_metrics.get("confidence", 0),
            volume_score=selection_metrics.get("volume_score", 0),
            composite_score=selection_metrics.get("composite_score", 0),
            market_condition=market_condition
        )

        self.record_trade(trade)

    def can_learn(self) -> bool:
        """학습 가능 여부 확인"""
        completed_trades = [t for t in self.trade_history if t.exit_date is not None]
        return len(completed_trades) >= self.MIN_TRADES_FOR_LEARNING

    def get_optimal_thresholds(self, market_condition: str = "neutral") -> Optional[FilterThresholds]:
        """최적 임계값 계산

        성공 거래와 실패 거래의 특성을 분석하여 최적 임계값 도출.

        Args:
            market_condition: 시장 상황

        Returns:
            최적 임계값 (학습 데이터 부족 시 None)
        """
        if not self.can_learn():
            logger.info(
                f"학습 데이터 부족 ({len(self.trade_history)}/{self.MIN_TRADES_FOR_LEARNING}). "
                f"기본 임계값 사용."
            )
            return None

        # 완료된 거래만 필터링
        completed = [t for t in self.trade_history if t.exit_date is not None]

        # 시장 상황별 필터링 (데이터가 충분하면)
        condition_trades = [t for t in completed if t.market_condition == market_condition]
        if len(condition_trades) < self.MIN_TRADES_FOR_LEARNING // 2:
            # 시장별 데이터 부족 시 전체 데이터 사용
            condition_trades = completed

        # 성공/실패 분리
        successful = [t for t in condition_trades if t.is_success]
        failed = [t for t in condition_trades if not t.is_success]

        if not successful:
            logger.warning("성공 거래 없음. 기본 임계값 사용.")
            return None

        # 성공 거래의 특성 분석 (하위 25% 분위수 = 최소 기준)
        def get_percentile(trades: List[TradeResult], attr: str, percentile: int) -> float:
            values = [getattr(t, attr) for t in trades if getattr(t, attr) is not None]
            if not values:
                return 0.0
            return float(np.percentile(values, percentile))

        # 성공 거래의 하위 25% = 최소 기준선
        optimal = FilterThresholds(
            price_attractiveness=get_percentile(successful, "total_score", 25),
            risk_score_max=get_percentile(successful, "risk_score", 75),  # 리스크는 상위 75%
            confidence_min=get_percentile(successful, "confidence", 25),
            min_technical_score=get_percentile(successful, "technical_score", 25),
            liquidity_score=get_percentile(successful, "volume_score", 25),
            min_composite_score=get_percentile(successful, "composite_score", 25) / 100
        )

        logger.info(
            f"학습 기반 임계값 계산 완료 - "
            f"성공 {len(successful)}건, 실패 {len(failed)}건 분석 | "
            f"매력도>{optimal.price_attractiveness:.1f}, "
            f"신뢰도>{optimal.confidence_min:.2f}"
        )

        return optimal

    def get_win_rate(self, market_condition: Optional[str] = None) -> float:
        """승률 계산"""
        completed = [t for t in self.trade_history if t.exit_date is not None]

        if market_condition:
            completed = [t for t in completed if t.market_condition == market_condition]

        if not completed:
            return 0.0

        wins = len([t for t in completed if t.is_success])
        return wins / len(completed)

    def get_performance_stats(self) -> Dict:
        """성과 통계 조회"""
        completed = [t for t in self.trade_history if t.exit_date is not None]

        if not completed:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "avg_profit": 0.0,
                "max_profit": 0.0,
                "max_loss": 0.0,
                "learning_ready": False
            }

        profits = [t.profit_rate for t in completed if t.profit_rate is not None]

        return {
            "total_trades": len(completed),
            "win_rate": self.get_win_rate(),
            "avg_profit": np.mean(profits) if profits else 0.0,
            "max_profit": max(profits) if profits else 0.0,
            "max_loss": min(profits) if profits else 0.0,
            "learning_ready": self.can_learn(),
            "by_market_condition": self._get_stats_by_condition()
        }

    def _get_stats_by_condition(self) -> Dict:
        """시장 상황별 통계"""
        completed = [t for t in self.trade_history if t.exit_date is not None]

        stats = {}
        conditions = set(t.market_condition for t in completed)

        for condition in conditions:
            condition_trades = [t for t in completed if t.market_condition == condition]
            if condition_trades:
                profits = [t.profit_rate for t in condition_trades if t.profit_rate is not None]
                stats[condition] = {
                    "count": len(condition_trades),
                    "win_rate": self.get_win_rate(condition),
                    "avg_profit": np.mean(profits) if profits else 0.0
                }

        return stats

    def suggest_filter_adjustment(self) -> Dict:
        """필터 조정 제안

        현재 성과를 기반으로 필터 조정 방향 제안.

        Returns:
            조정 제안 딕셔너리
        """
        if not self.can_learn():
            return {
                "status": "insufficient_data",
                "message": f"학습에 {self.MIN_TRADES_FOR_LEARNING}건 이상 필요 "
                          f"(현재: {len(self.trade_history)}건)",
                "suggestions": []
            }

        win_rate = self.get_win_rate()
        suggestions = []

        if win_rate < 0.45:
            # 승률이 낮으면 기준 강화
            suggestions.append({
                "type": "tighten",
                "reason": f"낮은 승률 ({win_rate:.1%})",
                "action": "min_composite_score를 5% 상향"
            })
        elif win_rate > 0.65:
            # 승률이 높으면 기준 완화 가능
            suggestions.append({
                "type": "loosen",
                "reason": f"높은 승률 ({win_rate:.1%})",
                "action": "min_composite_score를 3% 하향하여 기회 확대"
            })

        # 시장 상황별 분석
        stats = self._get_stats_by_condition()
        for condition, data in stats.items():
            if data["win_rate"] < 0.40:
                suggestions.append({
                    "type": "tighten",
                    "market": condition,
                    "reason": f"{condition}에서 낮은 승률 ({data['win_rate']:.1%})",
                    "action": f"{condition} 프리셋의 min_composite_score 상향"
                })

        return {
            "status": "ready",
            "win_rate": win_rate,
            "total_trades": len(self.trade_history),
            "suggestions": suggestions
        }


# 싱글톤 인스턴스
_tuner_instance: Optional[AdaptiveFilterTuner] = None


def get_adaptive_filter_tuner() -> AdaptiveFilterTuner:
    """AdaptiveFilterTuner 싱글톤 인스턴스 반환"""
    global _tuner_instance
    if _tuner_instance is None:
        _tuner_instance = AdaptiveFilterTuner()
    return _tuner_instance
