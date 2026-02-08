#!/usr/bin/env python3
"""
백테스트 성과 분석 모듈
Sharpe, Sortino, Calmar, Information Ratio 등 성과 지표 계산
"""

import numpy as np
from typing import Dict, List
from core.utils.log_utils import get_logger
from core.backtesting.models import Trade

logger = get_logger(__name__)


class PerformanceAnalyzer:
    """백테스트 성과 분석기"""

    def __init__(self):
        """초기화"""
        self.logger = logger

    def calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.02
    ) -> float:
        """샤프 비율 계산

        샤프 비율 = (평균 수익률 - 무위험 수익률) / 수익률 표준편차 * √252

        Args:
            returns: 일별 수익률 리스트
            risk_free_rate: 무위험 이자율 (연율, 기본값: 2%)

        Returns:
            float: 샤프 비율
        """
        try:
            if not returns or len(returns) < 2:
                self.logger.warning("샤프 비율 계산을 위한 데이터 부족")
                return 0.0

            returns_array = np.array(returns)
            avg_return = np.mean(returns_array)
            std_return = np.std(returns_array, ddof=1)  # 표본 표준편차

            if std_return == 0:
                self.logger.warning("표준편차가 0으로 샤프 비율 계산 불가")
                return 0.0

            # 일일 무위험 수익률 (연율 / 252 영업일)
            daily_rf = risk_free_rate / 252

            # 샤프 비율 (연율화)
            sharpe = (avg_return - daily_rf) / std_return * np.sqrt(252)

            self.logger.debug(f"Sharpe Ratio: {sharpe:.2f}")
            return float(sharpe)

        except Exception as e:
            self.logger.error(f"샤프 비율 계산 중 오류: {e}", exc_info=True)
            return 0.0

    def calculate_sortino_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.02
    ) -> float:
        """소르티노 비율 계산

        소르티노 비율 = (평균 수익률 - 무위험 수익률) / 하방 편차 * √252
        하방 편차: 음수 수익률만 사용한 표준편차

        Args:
            returns: 일별 수익률 리스트
            risk_free_rate: 무위험 이자율 (연율, 기본값: 2%)

        Returns:
            float: 소르티노 비율
        """
        try:
            if not returns or len(returns) < 2:
                self.logger.warning("소르티노 비율 계산을 위한 데이터 부족")
                return 0.0

            returns_array = np.array(returns)
            avg_return = np.mean(returns_array)

            # 하방 편차 계산 (음수 수익률만)
            downside_returns = returns_array[returns_array < 0]

            if len(downside_returns) == 0:
                self.logger.warning("하방 수익률 없음: 소르티노 비율 무한대로 설정")
                return float('inf')

            downside_std = np.std(downside_returns, ddof=1)

            if downside_std == 0:
                self.logger.warning("하방 표준편차가 0으로 소르티노 비율 계산 불가")
                return 0.0

            # 일일 무위험 수익률
            daily_rf = risk_free_rate / 252

            # 소르티노 비율 (연율화)
            sortino = (avg_return - daily_rf) / downside_std * np.sqrt(252)

            self.logger.debug(f"Sortino Ratio: {sortino:.2f}")
            return float(sortino)

        except Exception as e:
            self.logger.error(f"소르티노 비율 계산 중 오류: {e}", exc_info=True)
            return 0.0

    def calculate_calmar_ratio(
        self,
        returns: List[float],
        max_drawdown: float
    ) -> float:
        """칼마 비율 계산

        칼마 비율 = 연율화 수익률 / |최대 손실폭|

        Args:
            returns: 일별 수익률 리스트
            max_drawdown: 최대 손실폭 (음수)

        Returns:
            float: 칼마 비율
        """
        try:
            if not returns:
                self.logger.warning("칼마 비율 계산을 위한 데이터 부족")
                return 0.0

            if max_drawdown == 0:
                self.logger.warning("최대 손실폭이 0으로 칼마 비율 계산 불가")
                return 0.0

            returns_array = np.array(returns)
            avg_return = np.mean(returns_array)

            # 연율화 수익률
            annualized_return = avg_return * 252

            # 칼마 비율
            calmar = annualized_return / abs(max_drawdown)

            self.logger.debug(f"Calmar Ratio: {calmar:.2f}")
            return float(calmar)

        except Exception as e:
            self.logger.error(f"칼마 비율 계산 중 오류: {e}", exc_info=True)
            return 0.0

    def calculate_information_ratio(
        self,
        returns: List[float],
        benchmark_returns: List[float]
    ) -> float:
        """정보 비율 계산

        정보 비율 = (전략 수익률 - 벤치마크 수익률) / Tracking Error
        Tracking Error = std(전략 수익률 - 벤치마크 수익률)

        Args:
            returns: 전략 수익률 리스트
            benchmark_returns: 벤치마크 수익률 리스트

        Returns:
            float: 정보 비율
        """
        try:
            if not returns or not benchmark_returns:
                self.logger.warning("정보 비율 계산을 위한 데이터 부족")
                return 0.0

            if len(returns) != len(benchmark_returns):
                self.logger.warning("전략과 벤치마크 수익률 길이 불일치")
                return 0.0

            returns_array = np.array(returns)
            benchmark_array = np.array(benchmark_returns)

            # 초과 수익률 (Active Return)
            active_returns = returns_array - benchmark_array
            avg_active_return = np.mean(active_returns)

            # Tracking Error
            tracking_error = np.std(active_returns, ddof=1)

            if tracking_error == 0:
                self.logger.warning("Tracking Error가 0으로 정보 비율 계산 불가")
                return 0.0

            # 정보 비율 (연율화)
            information_ratio = avg_active_return / tracking_error * np.sqrt(252)

            self.logger.debug(f"Information Ratio: {information_ratio:.2f}")
            return float(information_ratio)

        except Exception as e:
            self.logger.error(f"정보 비율 계산 중 오류: {e}", exc_info=True)
            return 0.0

    def analyze_trade_distribution(self, trades: List[Trade]) -> Dict:
        """거래 분포 분석

        승률, 평균 수익/손실, Profit Factor, 평균 보유일 등을 분석합니다.

        Args:
            trades: 거래 내역 리스트

        Returns:
            Dict: 거래 분포 분석 결과
                - win_rate: 승률
                - avg_profit: 평균 수익 (이익 거래만)
                - avg_loss: 평균 손실 (손실 거래만)
                - profit_factor: Profit Factor (총이익 / 총손실)
                - avg_holding_days: 평균 보유일
                - max_consecutive_wins: 최대 연속 승
                - max_consecutive_losses: 최대 연속 패
        """
        try:
            if not trades:
                self.logger.warning("거래 데이터가 없습니다")
                return self._empty_distribution()

            # 완료된 거래만 분석 (return_pct가 None이 아닌 것)
            completed_trades = [t for t in trades if t.return_pct is not None]

            if not completed_trades:
                self.logger.warning("완료된 거래가 없습니다")
                return self._empty_distribution()

            # 승/패 분류
            winning_trades = [t for t in completed_trades if t.return_pct > 0]
            losing_trades = [t for t in completed_trades if t.return_pct < 0]

            total_count = len(completed_trades)
            win_count = len(winning_trades)
            loss_count = len(losing_trades)

            # 승률
            win_rate = win_count / total_count if total_count > 0 else 0.0

            # 평균 수익/손실
            avg_profit = np.mean([t.return_pct for t in winning_trades]) if winning_trades else 0.0
            avg_loss = np.mean([t.return_pct for t in losing_trades]) if losing_trades else 0.0

            # Profit Factor
            total_profit = sum([t.return_pct for t in winning_trades])
            total_loss = abs(sum([t.return_pct for t in losing_trades]))
            profit_factor = total_profit / total_loss if total_loss > 0 else 0.0

            # 평균 보유일
            holding_days_list = [t.holding_days for t in completed_trades if t.holding_days is not None]
            avg_holding_days = np.mean(holding_days_list) if holding_days_list else 0.0

            # 연속 승/패
            consecutive_wins = []
            consecutive_losses = []
            current_streak = 0
            is_winning_streak = None

            for trade in completed_trades:
                is_win = trade.return_pct > 0

                if is_winning_streak is None:
                    is_winning_streak = is_win
                    current_streak = 1
                elif is_winning_streak == is_win:
                    current_streak += 1
                else:
                    if is_winning_streak:
                        consecutive_wins.append(current_streak)
                    else:
                        consecutive_losses.append(current_streak)
                    is_winning_streak = is_win
                    current_streak = 1

            # 마지막 스트릭 추가
            if current_streak > 0:
                if is_winning_streak:
                    consecutive_wins.append(current_streak)
                else:
                    consecutive_losses.append(current_streak)

            max_consecutive_wins = max(consecutive_wins) if consecutive_wins else 0
            max_consecutive_losses = max(consecutive_losses) if consecutive_losses else 0

            result = {
                'total_trades': total_count,
                'winning_trades': win_count,
                'losing_trades': loss_count,
                'win_rate': win_rate,
                'avg_profit': avg_profit,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'avg_holding_days': avg_holding_days,
                'max_consecutive_wins': max_consecutive_wins,
                'max_consecutive_losses': max_consecutive_losses
            }

            self.logger.debug(
                f"거래 분포 분석 완료: 승률 {win_rate:.1%}, "
                f"Profit Factor {profit_factor:.2f}, "
                f"평균 보유일 {avg_holding_days:.1f}일"
            )

            return result

        except Exception as e:
            self.logger.error(f"거래 분포 분석 중 오류: {e}", exc_info=True)
            return self._empty_distribution()

    def _empty_distribution(self) -> Dict:
        """빈 거래 분포 결과"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'avg_profit': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'avg_holding_days': 0.0,
            'max_consecutive_wins': 0,
            'max_consecutive_losses': 0
        }
