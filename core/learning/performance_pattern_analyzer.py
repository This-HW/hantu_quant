"""
성과 패턴 분석 모듈

거래 성과 패턴을 분석하여 승/패 조건을 식별합니다.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import Counter
import numpy as np

from .trade_logger import TradeLog, EntryContext

logger = logging.getLogger(__name__)


@dataclass
class WinningConditions:
    """승리 거래 조건"""
    rsi_range: Tuple[float, float] = (30.0, 70.0)
    min_agreement: int = 2
    best_regime: str = "range"
    mtf_alignment_rate: float = 0.0
    best_source_combo: List[str] = field(default_factory=list)

    # 통계
    total_winners: int = 0
    avg_profit: float = 0.0
    avg_holding_days: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'rsi_range': self.rsi_range,
            'min_agreement': self.min_agreement,
            'best_regime': self.best_regime,
            'mtf_alignment_rate': self.mtf_alignment_rate,
            'best_source_combo': self.best_source_combo,
            'total_winners': self.total_winners,
            'avg_profit': self.avg_profit,
            'avg_holding_days': self.avg_holding_days,
        }


@dataclass
class LosingConditions:
    """패배 거래 조건"""
    common_rsi_range: Tuple[float, float] = (0.0, 100.0)
    low_agreement_rate: float = 0.0
    trend_against_rate: float = 0.0
    worst_regime: str = ""
    weak_signal_rate: float = 0.0

    # 통계
    total_losers: int = 0
    avg_loss: float = 0.0
    avg_holding_days: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'common_rsi_range': self.common_rsi_range,
            'low_agreement_rate': self.low_agreement_rate,
            'trend_against_rate': self.trend_against_rate,
            'worst_regime': self.worst_regime,
            'weak_signal_rate': self.weak_signal_rate,
            'total_losers': self.total_losers,
            'avg_loss': self.avg_loss,
            'avg_holding_days': self.avg_holding_days,
        }


@dataclass
class OptimalRange:
    """지표 최적 범위"""
    indicator: str
    ranges: List[Tuple[float, float]] = field(default_factory=list)
    win_rate: float = 0.0
    sample_size: int = 0

    def to_dict(self) -> Dict:
        return {
            'indicator': self.indicator,
            'ranges': self.ranges,
            'win_rate': self.win_rate,
            'sample_size': self.sample_size,
        }


@dataclass
class PerformanceByCategory:
    """카테고리별 성과"""
    category: str
    values: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'category': self.category,
            'values': self.values,
        }


@dataclass
class PatternAnalysis:
    """패턴 분석 결과"""
    winning_conditions: WinningConditions = field(default_factory=WinningConditions)
    losing_conditions: LosingConditions = field(default_factory=LosingConditions)
    optimal_indicator_ranges: Dict[str, OptimalRange] = field(default_factory=dict)
    performance_by_regime: Dict[str, Dict[str, float]] = field(default_factory=dict)
    performance_by_source: Dict[str, Dict[str, float]] = field(default_factory=dict)
    performance_by_time: Dict[str, Dict[str, float]] = field(default_factory=dict)
    performance_by_holding: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'winning_conditions': self.winning_conditions.to_dict(),
            'losing_conditions': self.losing_conditions.to_dict(),
            'optimal_indicator_ranges': {
                k: v.to_dict() for k, v in self.optimal_indicator_ranges.items()
            },
            'performance_by_regime': self.performance_by_regime,
            'performance_by_source': self.performance_by_source,
            'performance_by_time': self.performance_by_time,
            'performance_by_holding': self.performance_by_holding,
        }


class PerformancePatternAnalyzer:
    """
    성과 패턴 분석기

    거래 성과 패턴을 분석하여 승/패 조건을 식별합니다.
    """

    def __init__(self, min_samples: int = 20):
        """
        Args:
            min_samples: 분석에 필요한 최소 샘플 수
        """
        self.min_samples = min_samples

    def analyze_patterns(self, trade_logs: List[TradeLog]) -> PatternAnalysis:
        """
        거래 패턴 종합 분석

        Args:
            trade_logs: 거래 로그 리스트

        Returns:
            PatternAnalysis: 분석 결과
        """
        if not trade_logs:
            return PatternAnalysis()

        winners = [t for t in trade_logs if t.labels.is_winner]
        losers = [t for t in trade_logs if not t.labels.is_winner]

        return PatternAnalysis(
            winning_conditions=self._analyze_winning_conditions(winners),
            losing_conditions=self._analyze_losing_conditions(losers),
            optimal_indicator_ranges=self._find_optimal_ranges(trade_logs),
            performance_by_regime=self._analyze_by_regime(trade_logs),
            performance_by_source=self._analyze_by_source(trade_logs),
            performance_by_time=self._analyze_by_time(trade_logs),
            performance_by_holding=self._analyze_by_holding_period(trade_logs),
        )

    def _analyze_winning_conditions(
        self,
        winners: List[TradeLog]
    ) -> WinningConditions:
        """승리 거래 조건 분석"""
        if not winners:
            return WinningConditions()

        # RSI 분포
        rsi_values = [t.entry_context.rsi for t in winners]
        rsi_mean = np.mean(rsi_values)
        rsi_std = np.std(rsi_values)

        # 신호 일치 수
        agreement_counts = [t.entry_context.agreement_count for t in winners]
        avg_agreement = np.mean(agreement_counts)

        # 시장 레짐 분포
        regime_dist = Counter([t.entry_context.market_regime for t in winners])
        best_regime = regime_dist.most_common(1)[0][0] if regime_dist else "range"

        # MTF 정렬률
        aligned_count = sum(
            1 for t in winners
            if t.entry_context.daily_trend == t.entry_context.weekly_trend
        )
        alignment_rate = aligned_count / len(winners)

        # 신호 소스 조합
        source_dist = Counter([
            tuple(sorted(t.entry_context.signal_source)) for t in winners
        ])
        best_combo = list(source_dist.most_common(1)[0][0]) if source_dist else []

        return WinningConditions(
            rsi_range=(max(0, rsi_mean - rsi_std), min(100, rsi_mean + rsi_std)),
            min_agreement=int(avg_agreement),
            best_regime=best_regime,
            mtf_alignment_rate=alignment_rate,
            best_source_combo=best_combo,
            total_winners=len(winners),
            avg_profit=np.mean([t.pnl_pct for t in winners]),
            avg_holding_days=np.mean([t.holding_days for t in winners]),
        )

    def _analyze_losing_conditions(
        self,
        losers: List[TradeLog]
    ) -> LosingConditions:
        """패배 거래 조건 분석"""
        if not losers:
            return LosingConditions()

        # RSI 분포
        rsi_values = [t.entry_context.rsi for t in losers]
        rsi_mean = np.mean(rsi_values)
        rsi_std = np.std(rsi_values)

        # 낮은 신호 일치율
        low_agreement = sum(
            1 for t in losers if t.entry_context.agreement_count < 2
        )
        low_agreement_rate = low_agreement / len(losers)

        # 추세 역행률
        trend_against = sum(
            1 for t in losers
            if t.entry_context.daily_trend != t.entry_context.weekly_trend
        )
        trend_against_rate = trend_against / len(losers)

        # 최악의 레짐
        regime_dist = Counter([t.entry_context.market_regime for t in losers])
        worst_regime = regime_dist.most_common(1)[0][0] if regime_dist else ""

        # 약한 신호율
        weak_signal = sum(
            1 for t in losers if t.entry_context.signal_confidence < 0.6
        )
        weak_signal_rate = weak_signal / len(losers)

        return LosingConditions(
            common_rsi_range=(max(0, rsi_mean - rsi_std), min(100, rsi_mean + rsi_std)),
            low_agreement_rate=low_agreement_rate,
            trend_against_rate=trend_against_rate,
            worst_regime=worst_regime,
            weak_signal_rate=weak_signal_rate,
            total_losers=len(losers),
            avg_loss=np.mean([t.pnl_pct for t in losers]),
            avg_holding_days=np.mean([t.holding_days for t in losers]),
        )

    def _find_optimal_ranges(
        self,
        trade_logs: List[TradeLog]
    ) -> Dict[str, OptimalRange]:
        """지표별 최적 범위 탐색"""
        indicators = ['rsi', 'macd', 'bb_position', 'volume_ratio']
        optimal_ranges = {}

        for indicator in indicators:
            values = [
                (getattr(t.entry_context, indicator), t.labels.is_winner)
                for t in trade_logs
                if hasattr(t.entry_context, indicator)
            ]

            if len(values) < self.min_samples:
                continue

            # 구간별 승률 계산
            sorted_values = sorted(values, key=lambda x: x[0])
            n_bins = min(10, len(sorted_values) // 5)

            if n_bins < 2:
                continue

            bin_size = len(sorted_values) // n_bins
            good_ranges = []
            total_good_samples = 0
            total_win_rate = 0.0

            for i in range(n_bins):
                start_idx = i * bin_size
                end_idx = (i + 1) * bin_size if i < n_bins - 1 else len(sorted_values)
                bin_data = sorted_values[start_idx:end_idx]

                if not bin_data:
                    continue

                win_count = sum(1 for _, is_win in bin_data if is_win)
                win_rate = win_count / len(bin_data)

                if win_rate >= 0.6:  # 60% 이상 승률
                    min_val = bin_data[0][0]
                    max_val = bin_data[-1][0]
                    good_ranges.append((min_val, max_val))
                    total_good_samples += len(bin_data)
                    total_win_rate += win_rate * len(bin_data)

            if good_ranges:
                optimal_ranges[indicator] = OptimalRange(
                    indicator=indicator,
                    ranges=good_ranges,
                    win_rate=total_win_rate / total_good_samples if total_good_samples > 0 else 0.0,
                    sample_size=total_good_samples,
                )

        return optimal_ranges

    def _analyze_by_regime(
        self,
        trade_logs: List[TradeLog]
    ) -> Dict[str, Dict[str, float]]:
        """시장 레짐별 성과 분석"""
        by_regime: Dict[str, List[TradeLog]] = {}

        for t in trade_logs:
            regime = t.entry_context.market_regime
            if regime not in by_regime:
                by_regime[regime] = []
            by_regime[regime].append(t)

        result = {}
        for regime, trades in by_regime.items():
            if len(trades) < 5:
                continue

            winners = [t for t in trades if t.labels.is_winner]
            result[regime] = {
                'count': len(trades),
                'win_rate': len(winners) / len(trades),
                'avg_pnl': np.mean([t.pnl_pct for t in trades]),
                'avg_winner': np.mean([t.pnl_pct for t in winners]) if winners else 0.0,
            }

        return result

    def _analyze_by_source(
        self,
        trade_logs: List[TradeLog]
    ) -> Dict[str, Dict[str, float]]:
        """신호 소스별 성과 분석"""
        by_source: Dict[str, List[TradeLog]] = {}

        for t in trade_logs:
            for source in t.entry_context.signal_source:
                if source not in by_source:
                    by_source[source] = []
                by_source[source].append(t)

        result = {}
        for source, trades in by_source.items():
            if len(trades) < 5:
                continue

            winners = [t for t in trades if t.labels.is_winner]
            result[source] = {
                'count': len(trades),
                'win_rate': len(winners) / len(trades),
                'avg_pnl': np.mean([t.pnl_pct for t in trades]),
                'contribution': sum(t.pnl for t in trades),
            }

        return result

    def _analyze_by_time(
        self,
        trade_logs: List[TradeLog]
    ) -> Dict[str, Dict[str, float]]:
        """시간대별 성과 분석"""
        by_weekday: Dict[int, List[TradeLog]] = {}
        by_month: Dict[int, List[TradeLog]] = {}

        for t in trade_logs:
            weekday = t.timestamp.weekday()
            month = t.timestamp.month

            if weekday not in by_weekday:
                by_weekday[weekday] = []
            by_weekday[weekday].append(t)

            if month not in by_month:
                by_month[month] = []
            by_month[month].append(t)

        result = {}

        # 요일별
        weekday_names = ['월', '화', '수', '목', '금', '토', '일']
        for weekday, trades in by_weekday.items():
            if len(trades) < 5:
                continue
            winners = [t for t in trades if t.labels.is_winner]
            result[f"weekday_{weekday_names[weekday]}"] = {
                'count': len(trades),
                'win_rate': len(winners) / len(trades),
                'avg_pnl': np.mean([t.pnl_pct for t in trades]),
            }

        # 월별
        for month, trades in by_month.items():
            if len(trades) < 5:
                continue
            winners = [t for t in trades if t.labels.is_winner]
            result[f"month_{month:02d}"] = {
                'count': len(trades),
                'win_rate': len(winners) / len(trades),
                'avg_pnl': np.mean([t.pnl_pct for t in trades]),
            }

        return result

    def _analyze_by_holding_period(
        self,
        trade_logs: List[TradeLog]
    ) -> Dict[str, Dict[str, float]]:
        """보유 기간별 성과 분석"""
        periods = [
            ('1d', 0, 1),
            ('2-3d', 2, 3),
            ('4-5d', 4, 5),
            ('1w', 6, 10),
            ('2w', 11, 15),
            ('2w+', 16, 999),
        ]

        result = {}
        for name, min_days, max_days in periods:
            trades = [
                t for t in trade_logs
                if min_days <= t.holding_days <= max_days
            ]

            if len(trades) < 5:
                continue

            winners = [t for t in trades if t.labels.is_winner]
            result[name] = {
                'count': len(trades),
                'win_rate': len(winners) / len(trades),
                'avg_pnl': np.mean([t.pnl_pct for t in trades]),
                'avg_holding': np.mean([t.holding_days for t in trades]),
            }

        return result

    def get_recommendations(
        self,
        analysis: PatternAnalysis
    ) -> List[Dict[str, Any]]:
        """
        분석 결과 기반 권고사항 생성

        Args:
            analysis: 패턴 분석 결과

        Returns:
            List[Dict]: 권고사항 리스트
        """
        recommendations = []

        # 1. RSI 범위 권고
        win_cond = analysis.winning_conditions
        lose_cond = analysis.losing_conditions

        if win_cond.total_winners > 0:
            recommendations.append({
                'category': 'entry_filter',
                'priority': 'high',
                'title': 'RSI 최적 범위',
                'description': f"RSI {win_cond.rsi_range[0]:.0f}-{win_cond.rsi_range[1]:.0f} 범위에서 진입 시 승률 높음",
                'action': f"RSI 필터를 {win_cond.rsi_range[0]:.0f}-{win_cond.rsi_range[1]:.0f}로 설정",
            })

        # 2. 신호 일치 권고
        if win_cond.min_agreement >= 2:
            recommendations.append({
                'category': 'signal_filter',
                'priority': 'high',
                'title': '최소 신호 일치',
                'description': f"최소 {win_cond.min_agreement}개 이상 신호 일치 시 승률 높음",
                'action': f"min_agreement = {win_cond.min_agreement} 설정",
            })

        # 3. MTF 정렬 권고
        if win_cond.mtf_alignment_rate > 0.7:
            recommendations.append({
                'category': 'entry_filter',
                'priority': 'high',
                'title': 'MTF 정렬 필터',
                'description': f"승리 거래의 {win_cond.mtf_alignment_rate:.0%}가 MTF 정렬 상태에서 발생",
                'action': "daily_trend == weekly_trend 조건 추가",
            })

        # 4. 추세 역행 경고
        if lose_cond.trend_against_rate > 0.4:
            recommendations.append({
                'category': 'risk_filter',
                'priority': 'high',
                'title': '추세 역행 필터',
                'description': f"패배 거래의 {lose_cond.trend_against_rate:.0%}가 추세 역행 상태",
                'action': "추세 역행 시 진입 금지",
            })

        # 5. 약한 신호 경고
        if lose_cond.weak_signal_rate > 0.5:
            recommendations.append({
                'category': 'signal_filter',
                'priority': 'medium',
                'title': '신호 강도 필터',
                'description': f"패배 거래의 {lose_cond.weak_signal_rate:.0%}가 약한 신호",
                'action': "signal_confidence >= 0.6 조건 강화",
            })

        # 6. 최적 레짐 권고
        if win_cond.best_regime:
            regime_perf = analysis.performance_by_regime.get(win_cond.best_regime, {})
            if regime_perf.get('win_rate', 0) > 0.6:
                recommendations.append({
                    'category': 'market_filter',
                    'priority': 'medium',
                    'title': f'최적 시장 레짐: {win_cond.best_regime}',
                    'description': f"{win_cond.best_regime} 레짐에서 승률 {regime_perf['win_rate']:.0%}",
                    'action': f"{win_cond.best_regime} 레짐에서 포지션 확대",
                })

        # 7. 지표별 최적 범위 권고
        for indicator, opt_range in analysis.optimal_indicator_ranges.items():
            if opt_range.win_rate > 0.65 and opt_range.sample_size >= self.min_samples:
                range_str = ", ".join(
                    f"{r[0]:.2f}-{r[1]:.2f}" for r in opt_range.ranges
                )
                recommendations.append({
                    'category': 'indicator_filter',
                    'priority': 'medium',
                    'title': f'{indicator} 최적 범위',
                    'description': f"범위 {range_str}에서 승률 {opt_range.win_rate:.0%}",
                    'action': f"{indicator} 필터 범위 설정",
                })

        return recommendations

    def compare_periods(
        self,
        logs1: List[TradeLog],
        logs2: List[TradeLog],
        period1_name: str = "기간1",
        period2_name: str = "기간2"
    ) -> Dict[str, Any]:
        """
        두 기간 성과 비교

        Args:
            logs1: 첫 번째 기간 로그
            logs2: 두 번째 기간 로그
            period1_name: 첫 번째 기간 이름
            period2_name: 두 번째 기간 이름

        Returns:
            Dict: 비교 결과
        """
        def calc_stats(logs: List[TradeLog]) -> Dict[str, float]:
            if not logs:
                return {'count': 0, 'win_rate': 0, 'avg_pnl': 0, 'total_pnl': 0}

            winners = [t for t in logs if t.labels.is_winner]
            return {
                'count': len(logs),
                'win_rate': len(winners) / len(logs),
                'avg_pnl': np.mean([t.pnl_pct for t in logs]),
                'total_pnl': sum(t.pnl for t in logs),
            }

        stats1 = calc_stats(logs1)
        stats2 = calc_stats(logs2)

        return {
            period1_name: stats1,
            period2_name: stats2,
            'comparison': {
                'count_change': stats2['count'] - stats1['count'],
                'win_rate_change': stats2['win_rate'] - stats1['win_rate'],
                'avg_pnl_change': stats2['avg_pnl'] - stats1['avg_pnl'],
                'total_pnl_change': stats2['total_pnl'] - stats1['total_pnl'],
            }
        }
