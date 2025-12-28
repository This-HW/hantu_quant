"""
실패 분석 모듈

실패 거래를 심층 분석하여 개선점을 도출합니다.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import numpy as np

from .trade_logger import TradeLog

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """실패 유형"""
    TREND_AGAINST = "trend_against"      # 추세 역행 진입
    EARLY_ENTRY = "early_entry"          # 너무 이른 진입
    LATE_ENTRY = "late_entry"            # 너무 늦은 진입
    BAD_TIMING = "bad_timing"            # 시장 타이밍 실패
    STOP_TOO_TIGHT = "stop_too_tight"    # 손절 너무 타이트
    STOP_TOO_WIDE = "stop_too_wide"      # 손절 너무 넓음
    WEAK_SIGNAL = "weak_signal"          # 약한 신호에 진입
    LOW_AGREEMENT = "low_agreement"      # 신호 일치 부족
    MARKET_MOVED = "market_moved"        # 시장 급변
    OTHER = "other"                      # 기타


@dataclass
class FailureTypeAnalysis:
    """실패 유형별 분석"""
    failure_type: FailureType
    count: int = 0
    avg_loss: float = 0.0
    common_indicators: Dict[str, float] = field(default_factory=dict)
    common_conditions: List[str] = field(default_factory=list)
    potential_win_rate_gain: float = 0.0
    prevention_suggestion: str = ""

    def to_dict(self) -> Dict:
        return {
            'failure_type': self.failure_type.value,
            'count': self.count,
            'avg_loss': self.avg_loss,
            'common_indicators': self.common_indicators,
            'common_conditions': self.common_conditions,
            'potential_win_rate_gain': self.potential_win_rate_gain,
            'prevention_suggestion': self.prevention_suggestion,
        }


@dataclass
class Improvement:
    """개선 제안"""
    priority: str  # high, medium, low
    category: str  # entry_filter, signal_filter, risk_filter
    action: str
    description: str
    expected_impact: str
    implementation: str = ""

    def to_dict(self) -> Dict:
        return {
            'priority': self.priority,
            'category': self.category,
            'action': self.action,
            'description': self.description,
            'expected_impact': self.expected_impact,
            'implementation': self.implementation,
        }


@dataclass
class CommonMistake:
    """공통 실수 패턴"""
    pattern: str
    frequency: int
    impact: float  # 총 손실액
    description: str
    trades: List[str] = field(default_factory=list)  # 해당 거래 ID 리스트

    def to_dict(self) -> Dict:
        return {
            'pattern': self.pattern,
            'frequency': self.frequency,
            'impact': self.impact,
            'description': self.description,
            'sample_trades': self.trades[:5],  # 상위 5개만
        }


@dataclass
class FailureAnalysis:
    """실패 분석 결과"""
    total_losers: int = 0
    total_loss: float = 0.0
    failure_distribution: Dict[str, int] = field(default_factory=dict)
    type_analyses: Dict[str, FailureTypeAnalysis] = field(default_factory=dict)
    common_mistakes: List[CommonMistake] = field(default_factory=list)
    improvement_suggestions: List[Improvement] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'total_losers': self.total_losers,
            'total_loss': self.total_loss,
            'failure_distribution': self.failure_distribution,
            'type_analyses': {k: v.to_dict() for k, v in self.type_analyses.items()},
            'common_mistakes': [m.to_dict() for m in self.common_mistakes],
            'improvement_suggestions': [i.to_dict() for i in self.improvement_suggestions],
        }


class FailureAnalyzer:
    """
    실패 거래 분석기

    실패 거래를 심층 분석하여 개선점을 도출합니다.
    """

    def __init__(self, min_samples: int = 5):
        """
        Args:
            min_samples: 분석에 필요한 최소 샘플 수
        """
        self.min_samples = min_samples

    def analyze_failures(self, losers: List[TradeLog]) -> FailureAnalysis:
        """
        실패 거래 분석

        Args:
            losers: 손실 거래 리스트

        Returns:
            FailureAnalysis: 분석 결과
        """
        if not losers:
            return FailureAnalysis()

        # 실패 유형 분류
        classified = self._classify_failures(losers)

        # 실패 분포
        failure_distribution = {k: len(v) for k, v in classified.items()}

        # 각 유형별 분석
        type_analyses = {}
        for failure_type, trades in classified.items():
            if len(trades) >= self.min_samples:
                type_analyses[failure_type] = self._analyze_failure_type(
                    FailureType(failure_type), trades
                )

        # 공통 실수 패턴 식별
        common_mistakes = self._find_common_mistakes(losers)

        # 개선점 도출
        improvements = self._generate_improvements(type_analyses, losers)

        return FailureAnalysis(
            total_losers=len(losers),
            total_loss=sum(t.pnl for t in losers),
            failure_distribution=failure_distribution,
            type_analyses=type_analyses,
            common_mistakes=common_mistakes,
            improvement_suggestions=improvements,
        )

    def _classify_failures(
        self,
        losers: List[TradeLog]
    ) -> Dict[str, List[TradeLog]]:
        """
        실패 유형 분류

        Args:
            losers: 손실 거래 리스트

        Returns:
            Dict: 유형별 거래 리스트
        """
        classified = defaultdict(list)

        for trade in losers:
            ctx = trade.entry_context
            exit_ctx = trade.exit_context

            # 1. 추세 역행 체크
            if ctx.daily_trend != ctx.weekly_trend:
                classified[FailureType.TREND_AGAINST.value].append(trade)
                continue

            # 2. 약한 신호 체크
            if ctx.signal_confidence < 0.6:
                classified[FailureType.WEAK_SIGNAL.value].append(trade)
                continue

            # 3. 신호 일치 부족
            if ctx.agreement_count < 2:
                classified[FailureType.LOW_AGREEMENT.value].append(trade)
                continue

            # 4. 손절 타이밍 분석
            if exit_ctx.exit_reason == "stop_loss":
                # 손절 후 반등했다면 손절이 너무 타이트
                if exit_ctx.max_loss_during < trade.pnl_pct * 1.2:
                    classified[FailureType.STOP_TOO_TIGHT.value].append(trade)
                else:
                    classified[FailureType.MARKET_MOVED.value].append(trade)
                continue

            # 5. 시장 타이밍 분석
            if ctx.market_regime == "high_vol":
                classified[FailureType.BAD_TIMING.value].append(trade)
                continue

            # 6. 진입 타이밍 분석
            if trade.labels.entry_optimal == "early":
                classified[FailureType.EARLY_ENTRY.value].append(trade)
                continue

            if trade.labels.entry_optimal == "late":
                classified[FailureType.LATE_ENTRY.value].append(trade)
                continue

            # 기타
            classified[FailureType.OTHER.value].append(trade)

        return dict(classified)

    def _analyze_failure_type(
        self,
        failure_type: FailureType,
        trades: List[TradeLog]
    ) -> FailureTypeAnalysis:
        """
        특정 실패 유형 분석

        Args:
            failure_type: 실패 유형
            trades: 해당 유형 거래 리스트

        Returns:
            FailureTypeAnalysis: 분석 결과
        """
        avg_loss = np.mean([t.pnl_pct for t in trades])

        # 공통 지표값 분석
        common_indicators = {
            'avg_rsi': np.mean([t.entry_context.rsi for t in trades]),
            'avg_agreement': np.mean([t.entry_context.agreement_count for t in trades]),
            'avg_confidence': np.mean([t.entry_context.signal_confidence for t in trades]),
            'avg_volume_ratio': np.mean([t.entry_context.volume_ratio for t in trades]),
        }

        # 공통 조건 식별
        common_conditions = self._identify_common_conditions(trades)

        # 잠재적 승률 개선
        # 해당 유형을 필터링했다면 얻을 수 있는 승률 개선
        potential_gain = len(trades) / (len(trades) + 1)  # 단순화된 계산

        # 예방 제안
        prevention = self._get_prevention_suggestion(failure_type)

        return FailureTypeAnalysis(
            failure_type=failure_type,
            count=len(trades),
            avg_loss=avg_loss,
            common_indicators=common_indicators,
            common_conditions=common_conditions,
            potential_win_rate_gain=potential_gain,
            prevention_suggestion=prevention,
        )

    def _identify_common_conditions(
        self,
        trades: List[TradeLog]
    ) -> List[str]:
        """공통 조건 식별"""
        conditions = []

        # RSI 범위
        rsi_values = [t.entry_context.rsi for t in trades]
        avg_rsi = np.mean(rsi_values)
        if avg_rsi > 70:
            conditions.append("과매수 구간 진입 (RSI > 70)")
        elif avg_rsi < 30:
            conditions.append("과매도 구간 진입 (RSI < 30)")

        # 신호 강도
        conf_values = [t.entry_context.signal_confidence for t in trades]
        if np.mean(conf_values) < 0.6:
            conditions.append("낮은 신호 신뢰도 (< 60%)")

        # MTF 불일치
        mtf_mismatch = sum(
            1 for t in trades
            if t.entry_context.daily_trend != t.entry_context.weekly_trend
        )
        if mtf_mismatch / len(trades) > 0.5:
            conditions.append("MTF 추세 불일치")

        # 거래량
        vol_values = [t.entry_context.volume_ratio for t in trades]
        if np.mean(vol_values) < 0.8:
            conditions.append("낮은 거래량")
        elif np.mean(vol_values) > 2.0:
            conditions.append("급등 거래량")

        return conditions

    def _get_prevention_suggestion(self, failure_type: FailureType) -> str:
        """실패 유형별 예방 제안"""
        suggestions = {
            FailureType.TREND_AGAINST: "MTF 정렬 필터 추가: 일/주봉 추세 일치 시에만 진입",
            FailureType.WEAK_SIGNAL: "최소 신뢰도 임계값 상향: 60% → 70%",
            FailureType.LOW_AGREEMENT: "최소 신호 일치 수 상향: 2개 → 3개",
            FailureType.STOP_TOO_TIGHT: "ATR 기반 손절폭 확대 (1.5x → 2.0x ATR)",
            FailureType.STOP_TOO_WIDE: "손절폭 축소 또는 트레일링 스탑 적용",
            FailureType.MARKET_MOVED: "시장 급변 시 포지션 축소 또는 헤지",
            FailureType.BAD_TIMING: "고변동성 장에서 진입 제한",
            FailureType.EARLY_ENTRY: "추세 확인 후 진입 (브레이크아웃 확인)",
            FailureType.LATE_ENTRY: "조기 진입 또는 눌림목 대기",
            FailureType.OTHER: "추가 분석 필요",
        }
        return suggestions.get(failure_type, "")

    def _find_common_mistakes(
        self,
        losers: List[TradeLog]
    ) -> List[CommonMistake]:
        """공통 실수 패턴 식별"""
        mistakes = []

        # 1. 연속 손실 패턴
        consecutive_losses = self._find_consecutive_losses(losers)
        if consecutive_losses:
            mistakes.append(CommonMistake(
                pattern="consecutive_losses",
                frequency=len(consecutive_losses),
                impact=sum(t.pnl for t in consecutive_losses),
                description="연속 손실 발생 - 감정적 거래 가능성",
                trades=[t.trade_id for t in consecutive_losses[:5]],
            ))

        # 2. 같은 종목 반복 손실
        stock_losses = defaultdict(list)
        for t in losers:
            stock_losses[t.stock_code].append(t)

        for stock, trades in stock_losses.items():
            if len(trades) >= 3:
                mistakes.append(CommonMistake(
                    pattern="repeated_stock_loss",
                    frequency=len(trades),
                    impact=sum(t.pnl for t in trades),
                    description=f"{stock} 종목 반복 손실 - 해당 종목 분석 필요",
                    trades=[t.trade_id for t in trades[:5]],
                ))

        # 3. 특정 시간대 손실 집중
        hour_losses = defaultdict(list)
        for t in losers:
            hour = t.timestamp.hour
            hour_losses[hour].append(t)

        for hour, trades in hour_losses.items():
            if len(trades) >= 5 and len(trades) / len(losers) > 0.3:
                mistakes.append(CommonMistake(
                    pattern="time_concentration",
                    frequency=len(trades),
                    impact=sum(t.pnl for t in trades),
                    description=f"{hour}시대 손실 집중 ({len(trades)/len(losers):.0%})",
                    trades=[t.trade_id for t in trades[:5]],
                ))

        # 4. 큰 손실 패턴
        big_losers = [t for t in losers if t.labels.is_big_loser]
        if len(big_losers) >= 3:
            mistakes.append(CommonMistake(
                pattern="big_losses",
                frequency=len(big_losers),
                impact=sum(t.pnl for t in big_losers),
                description="대형 손실 발생 - 손절 기준 검토 필요",
                trades=[t.trade_id for t in big_losers[:5]],
            ))

        return sorted(mistakes, key=lambda x: abs(x.impact), reverse=True)

    def _find_consecutive_losses(
        self,
        losers: List[TradeLog]
    ) -> List[TradeLog]:
        """연속 손실 거래 찾기"""
        # 시간순 정렬
        sorted_losers = sorted(losers, key=lambda t: t.timestamp)

        consecutive = []
        current_streak = []

        for trade in sorted_losers:
            if not current_streak:
                current_streak.append(trade)
            else:
                # 이전 거래와 시간 차이가 1일 이내면 연속으로 판단
                time_diff = trade.timestamp - current_streak[-1].timestamp
                if time_diff.days <= 1:
                    current_streak.append(trade)
                else:
                    if len(current_streak) >= 3:
                        consecutive.extend(current_streak)
                    current_streak = [trade]

        if len(current_streak) >= 3:
            consecutive.extend(current_streak)

        return consecutive

    def _generate_improvements(
        self,
        type_analyses: Dict[str, FailureTypeAnalysis],
        losers: List[TradeLog]
    ) -> List[Improvement]:
        """개선점 도출"""
        improvements = []

        # 가장 빈번한 실패 유형부터 처리
        sorted_types = sorted(
            type_analyses.items(),
            key=lambda x: x[1].count,
            reverse=True
        )

        for failure_type, analysis in sorted_types[:5]:  # 상위 5개만
            if analysis.count < self.min_samples:
                continue

            improvement = self._create_improvement(
                FailureType(failure_type), analysis, len(losers)
            )
            if improvement:
                improvements.append(improvement)

        return sorted(
            improvements,
            key=lambda x: (
                0 if x.priority == 'high' else
                1 if x.priority == 'medium' else 2
            )
        )

    def _create_improvement(
        self,
        failure_type: FailureType,
        analysis: FailureTypeAnalysis,
        total_losers: int
    ) -> Optional[Improvement]:
        """개선 제안 생성"""
        impact_ratio = analysis.count / total_losers

        # 영향도가 낮으면 건너뛰기
        if impact_ratio < 0.1:
            return None

        priority = "high" if impact_ratio > 0.3 else "medium" if impact_ratio > 0.15 else "low"

        improvement_map = {
            FailureType.TREND_AGAINST: {
                'category': 'entry_filter',
                'action': 'ADD_MTF_ALIGNMENT_CHECK',
                'description': "MTF 정렬 필터 추가: 일/주봉 추세 일치 시에만 진입",
                'implementation': """
if daily_trend != weekly_trend:
    return Signal(type=HOLD, reason='MTF_NOT_ALIGNED')
""",
            },
            FailureType.WEAK_SIGNAL: {
                'category': 'signal_filter',
                'action': 'INCREASE_CONFIDENCE_THRESHOLD',
                'description': "최소 신뢰도 임계값 상향: 60% → 70%",
                'implementation': "self.min_confidence = 0.70",
            },
            FailureType.LOW_AGREEMENT: {
                'category': 'signal_filter',
                'action': 'REQUIRE_MORE_AGREEMENT',
                'description': "최소 신호 일치 수 상향",
                'implementation': "self.min_agreement = 3",
            },
            FailureType.STOP_TOO_TIGHT: {
                'category': 'risk_management',
                'action': 'WIDEN_STOP_LOSS',
                'description': "ATR 기반 손절폭 확대",
                'implementation': "stop_loss = entry_price - 2.0 * atr",
            },
            FailureType.BAD_TIMING: {
                'category': 'market_filter',
                'action': 'AVOID_HIGH_VOL',
                'description': "고변동성 장에서 진입 제한",
                'implementation': """
if market_regime == 'high_vol':
    position_size *= 0.5  # 포지션 축소
""",
            },
        }

        config = improvement_map.get(failure_type)
        if not config:
            return None

        return Improvement(
            priority=priority,
            category=config['category'],
            action=config['action'],
            description=config['description'],
            expected_impact=f"약 {analysis.count}건 손실 회피 가능 ({impact_ratio:.0%})",
            implementation=config.get('implementation', ''),
        )

    def get_summary(self, analysis: FailureAnalysis) -> str:
        """
        분석 결과 요약 생성

        Args:
            analysis: 분석 결과

        Returns:
            str: 요약 텍스트
        """
        lines = [
            "=" * 50,
            "실패 거래 분석 요약",
            "=" * 50,
            f"총 손실 거래: {analysis.total_losers}건",
            f"총 손실액: {analysis.total_loss:,.0f}원",
            "",
            "실패 유형 분포:",
        ]

        for ftype, count in sorted(
            analysis.failure_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            pct = count / analysis.total_losers * 100 if analysis.total_losers > 0 else 0
            lines.append(f"  - {ftype}: {count}건 ({pct:.1f}%)")

        if analysis.common_mistakes:
            lines.append("")
            lines.append("주요 실수 패턴:")
            for mistake in analysis.common_mistakes[:3]:
                lines.append(f"  - {mistake.description}")
                lines.append(f"    빈도: {mistake.frequency}건, 손실: {mistake.impact:,.0f}원")

        if analysis.improvement_suggestions:
            lines.append("")
            lines.append("개선 제안:")
            for imp in analysis.improvement_suggestions[:3]:
                lines.append(f"  [{imp.priority.upper()}] {imp.description}")
                lines.append(f"    예상 효과: {imp.expected_impact}")

        lines.append("=" * 50)

        return "\n".join(lines)
