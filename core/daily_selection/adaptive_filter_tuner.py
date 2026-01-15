#!/usr/bin/env python3
"""
적응형 필터 튜너 (Adaptive Filter Tuner) - DB 기반

실거래 결과를 기반으로 필터 임계값을 동적으로 조정하는 모듈.
학습 데이터가 쌓이면 점진적으로 최적화됨.

주요 기능:
1. 거래 결과 기록 및 분석 (DB 저장)
2. 성공/실패 패턴 학습
3. 필터 임계값 동적 조정
4. 시장 레짐별 최적 임계값 탐색
"""

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


def _get_db_session():
    """DB 세션 lazy import (순환 import 방지)"""
    try:
        from core.database.unified_db import get_session
        return get_session
    except ImportError:
        logger.warning("unified_db를 import할 수 없습니다")
        return None


def _get_feedback_data_model():
    """FeedbackData 모델 lazy import"""
    try:
        from core.database.models import FeedbackData
        return FeedbackData
    except ImportError:
        logger.warning("FeedbackData 모델을 import할 수 없습니다")
        return None


def _safe_percentile(values: List[float], percentile: int) -> float:
    """numpy 없이 백분위수 계산"""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * percentile / 100
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_values) else f
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


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

    def to_factor_scores_json(self) -> str:
        """factor_scores를 JSON 문자열로 변환"""
        return json.dumps({
            "total_score": self.total_score,
            "technical_score": self.technical_score,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "volume_score": self.volume_score,
            "composite_score": self.composite_score,
            "market_condition": self.market_condition
        })

    @classmethod
    def from_db_model(cls, model) -> 'TradeResult':
        """DB 모델에서 TradeResult 생성"""
        factor_scores = {}
        if model.factor_scores:
            try:
                factor_scores = json.loads(model.factor_scores)
            except Exception:
                pass

        return cls(
            stock_code=model.stock_code,
            stock_name="",
            entry_date=model.prediction_date.isoformat() if isinstance(model.prediction_date, date) else str(model.prediction_date),
            exit_date=model.feedback_date.isoformat() if model.feedback_date else None,
            entry_price=0,
            exit_price=0,
            profit_rate=model.actual_return_7d,
            is_success=model.actual_class == 1 if model.actual_class is not None else None,
            total_score=factor_scores.get("total_score", 0),
            technical_score=factor_scores.get("technical_score", 0),
            risk_score=factor_scores.get("risk_score", 0),
            confidence=model.predicted_probability or 0,
            volume_score=factor_scores.get("volume_score", 0),
            composite_score=factor_scores.get("composite_score", 0),
            market_condition=factor_scores.get("market_condition", "neutral")
        )


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
    """적응형 필터 튜너 (DB 기반)

    학습 데이터가 쌓이면 점진적으로 필터 임계값을 최적화.
    """

    # 최소 학습 데이터 수
    MIN_TRADES_FOR_LEARNING = 20

    # 학습률 (얼마나 빠르게 조정할지)
    LEARNING_RATE = 0.1

    # 안전 마진 (급격한 변화 방지)
    SAFETY_MARGIN = 0.2

    def __init__(self):
        # 메모리 캐시 (빠른 조회용)
        self._trade_cache: List[TradeResult] = []
        self._cache_loaded = False

        logger.info("AdaptiveFilterTuner 초기화 (DB 기반)")

    @property
    def trade_history(self) -> List[TradeResult]:
        """하위 호환성을 위한 프로퍼티"""
        self._ensure_cache_loaded()
        return self._trade_cache

    def _ensure_cache_loaded(self):
        """캐시 로드 확인"""
        if self._cache_loaded:
            return

        try:
            get_session = _get_db_session()
            FeedbackData = _get_feedback_data_model()

            if get_session is None or FeedbackData is None:
                logger.warning("DB 연결 불가 - 메모리 캐시만 사용")
                self._cache_loaded = True
                return

            # 최근 90일간 거래 기록 로드
            cutoff_date = date.today() - timedelta(days=90)

            with get_session() as session:
                records = session.query(FeedbackData).filter(
                    FeedbackData.prediction_date >= cutoff_date,
                    FeedbackData.is_processed == 1  # 처리 완료된 것만
                ).all()

                for record in records:
                    trade = TradeResult.from_db_model(record)
                    self._trade_cache.append(trade)

                logger.info(f"DB에서 거래 기록 {len(self._trade_cache)}건 로드")

        except Exception as e:
            logger.error(f"캐시 로드 실패: {e}", exc_info=True)

        self._cache_loaded = True

    def record_trade(self, trade: TradeResult):
        """거래 결과 기록 (DB + 캐시)"""
        # 1. DB에 저장
        db_saved = self._save_to_db(trade)

        # 2. 캐시에 추가
        self._trade_cache.append(trade)

        profit_str = f"{trade.profit_rate:.2%}" if trade.profit_rate else "N/A"
        logger.info(f"거래 기록 추가: {trade.stock_code} - 수익률: {profit_str}, DB저장: {'✓' if db_saved else '✗'}")

    def _save_to_db(self, trade: TradeResult) -> bool:
        """DB에 거래 결과 저장"""
        try:
            get_session = _get_db_session()
            FeedbackData = _get_feedback_data_model()

            if get_session is None or FeedbackData is None:
                return False

            # prediction_id 생성
            prediction_id = f"{trade.stock_code}_{trade.entry_date}"

            # 날짜 변환
            if isinstance(trade.entry_date, str):
                prediction_date = datetime.strptime(trade.entry_date, "%Y-%m-%d").date()
            else:
                prediction_date = trade.entry_date

            with get_session() as session:
                # 기존 기록 확인
                existing = session.query(FeedbackData).filter_by(
                    prediction_id=prediction_id
                ).first()

                if existing:
                    # 업데이트
                    existing.actual_return_7d = trade.profit_rate
                    existing.actual_class = 1 if trade.is_success else 0
                    existing.feedback_date = date.today()
                    existing.is_processed = 1
                    existing.factor_scores = trade.to_factor_scores_json()
                    existing.updated_at = datetime.now()
                else:
                    # 신규 생성
                    new_record = FeedbackData(
                        prediction_id=prediction_id,
                        stock_code=trade.stock_code,
                        prediction_date=prediction_date,
                        predicted_probability=trade.confidence,
                        predicted_class=1 if trade.is_success else 0,
                        model_name="adaptive_filter",
                        actual_return_7d=trade.profit_rate,
                        actual_class=1 if trade.is_success else 0,
                        feedback_date=date.today(),
                        is_processed=1,
                        factor_scores=trade.to_factor_scores_json()
                    )
                    session.add(new_record)

                return True

        except Exception as e:
            logger.error(f"DB 저장 실패: {e}", exc_info=True)
            return False

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
        profit_rate = (exit_price - entry_price) / entry_price if entry_price > 0 else 0
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
        self._ensure_cache_loaded()
        completed_trades = [t for t in self._trade_cache if t.exit_date is not None]
        return len(completed_trades) >= self.MIN_TRADES_FOR_LEARNING

    def get_optimal_thresholds(self, market_condition: str = "neutral") -> Optional[FilterThresholds]:
        """최적 임계값 계산

        성공 거래와 실패 거래의 특성을 분석하여 최적 임계값 도출.

        Args:
            market_condition: 시장 상황

        Returns:
            최적 임계값 (학습 데이터 부족 시 None)
        """
        self._ensure_cache_loaded()

        if not self.can_learn():
            logger.info(
                f"학습 데이터 부족 ({len(self._trade_cache)}/{self.MIN_TRADES_FOR_LEARNING}). "
                f"기본 임계값 사용."
            )
            return None

        # 완료된 거래만 필터링
        completed = [t for t in self._trade_cache if t.exit_date is not None]

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
            return _safe_percentile(values, percentile)

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
        self._ensure_cache_loaded()
        completed = [t for t in self._trade_cache if t.exit_date is not None]

        if market_condition:
            completed = [t for t in completed if t.market_condition == market_condition]

        if not completed:
            return 0.0

        wins = len([t for t in completed if t.is_success])
        return wins / len(completed)

    def get_performance_stats(self) -> Dict:
        """성과 통계 조회"""
        self._ensure_cache_loaded()
        completed = [t for t in self._trade_cache if t.exit_date is not None]

        if not completed:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "avg_profit": 0.0,
                "max_profit": 0.0,
                "max_loss": 0.0,
                "learning_ready": False,
                "db_connected": _get_db_session() is not None
            }

        profits = [t.profit_rate for t in completed if t.profit_rate is not None]

        return {
            "total_trades": len(completed),
            "win_rate": self.get_win_rate(),
            "avg_profit": sum(profits) / len(profits) if profits else 0.0,
            "max_profit": max(profits) if profits else 0.0,
            "max_loss": min(profits) if profits else 0.0,
            "learning_ready": self.can_learn(),
            "db_connected": _get_db_session() is not None,
            "by_market_condition": self._get_stats_by_condition()
        }

    def _get_stats_by_condition(self) -> Dict:
        """시장 상황별 통계"""
        completed = [t for t in self._trade_cache if t.exit_date is not None]

        stats = {}
        conditions = set(t.market_condition for t in completed)

        for condition in conditions:
            condition_trades = [t for t in completed if t.market_condition == condition]
            if condition_trades:
                profits = [t.profit_rate for t in condition_trades if t.profit_rate is not None]
                stats[condition] = {
                    "count": len(condition_trades),
                    "win_rate": self.get_win_rate(condition),
                    "avg_profit": sum(profits) / len(profits) if profits else 0.0
                }

        return stats

    def suggest_filter_adjustment(self) -> Dict:
        """필터 조정 제안

        현재 성과를 기반으로 필터 조정 방향 제안.

        Returns:
            조정 제안 딕셔너리
        """
        self._ensure_cache_loaded()

        if not self.can_learn():
            return {
                "status": "insufficient_data",
                "message": f"학습에 {self.MIN_TRADES_FOR_LEARNING}건 이상 필요 "
                          f"(현재: {len(self._trade_cache)}건)",
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
            "total_trades": len(self._trade_cache),
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
