#!/usr/bin/env python3
"""
간단한 백테스트 시스템
일일 선정 데이터의 예상 수익률을 활용한 시뮬레이션
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.backtesting.base_backtester import BaseBacktester
from core.backtesting.models import Trade

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class SimpleBacktester(BaseBacktester):
    """간단한 백테스터 (예상 수익률 기반 시뮬레이션)"""

    def __init__(self, initial_capital: float = 100000000, random_seed: Optional[int] = None):
        """
        Args:
            initial_capital: 초기 자본금 (기본: 1억원)
            random_seed: 난수 시드 (재현성 확보용)
        """
        super().__init__(initial_capital)

        # ✅ MF-5 수정: 난수 시드 고정 (재현성 확보)
        self.random_state = np.random.RandomState(random_seed)

    def _get_strategy_name(self) -> str:
        """전략명 반환"""
        return "Simple Expected Return Strategy"

    def _load_historical_selections(self, start_date: str, end_date: str) -> List[Dict]:
        """과거 일일 선정 데이터 로드 (필드 정규화 포함)

        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)

        Returns:
            List[Dict]: 선정 데이터 목록
        """
        # 부모 클래스에서 기본 로드
        selections = super()._load_historical_selections(start_date, end_date)

        # 필드 정규화 (SimpleBacktester 전용)
        for stock in selections:
            # entry_price 없으면 current_price 사용
            if 'entry_price' not in stock:
                stock['entry_price'] = stock.get('current_price', 0)

            # expected_return 없으면 target_price로부터 계산
            if 'expected_return' not in stock:
                entry = stock['entry_price']
                target = stock.get('target_price', entry)
                if entry > 0:
                    stock['expected_return'] = (target - entry) / entry * 100
                else:
                    stock['expected_return'] = 0

        return selections

    def backtest_selection_strategy(
        self,
        start_date: str,
        end_date: str,
        selection_criteria: Dict,
        trading_config: Dict,
        strategy_name: str = "Default"
    ):
        """선정 전략 백테스트 (레거시 API)

        일일 선정 데이터의 expected_return을 실제 수익률로 가정
        (현실성을 위해 50-70% 달성률 적용)

        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            selection_criteria: 선정 기준 (미사용)
            trading_config: 매매 설정

        Returns:
            BacktestResult: 백테스트 결과
        """
        # 부모 클래스의 backtest() 메서드 호출
        return self.backtest(
            start_date=start_date,
            end_date=end_date,
            achievement_rate=trading_config.get('achievement_rate', 0.6),
            max_holding_days=trading_config.get('max_holding_days', 10)
        )


    def _simulate_trading(
        self,
        selections: List[Dict],
        achievement_rate: float = 0.6,
        max_holding_days: int = 10,
        **kwargs
    ) -> List[Trade]:
        """매매 시뮬레이션 (현실적 버전)

        Args:
            selections: 일일 선정 종목 리스트
            achievement_rate: 예상 수익률 달성률 (0.5 = 50%)
            max_holding_days: 최대 보유 기간
            **kwargs: 추가 파라미터 (미사용)

        Returns:
            List[Trade]: 거래 목록
        """
        trades = []

        # 날짜별 그룹화
        by_date = {}
        for sel in selections:
            date = sel.get('selection_date', '2025-01-01')
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(sel)

        # 날짜별로 최대 5종목만 선택
        for date, daily_stocks in sorted(by_date.items()):
            # 상위 5종목만 (confidence 또는 total_score 기준)
            daily_stocks.sort(key=lambda x: x.get('confidence', 0) or x.get('total_score', 0), reverse=True)
            selected = daily_stocks[:5]

            for sel in selected:
                # 예상 수익률 조회
                expected_return = sel.get('expected_return', 0) / 100  # 퍼센트 → 소수

                # 실제 수익률 = 예상 수익률 × 달성률 × 랜덤 노이즈
                # 노이즈: -1.0~1.5 범위 (손실 가능성 포함)
                # ✅ MF-5 수정: RandomState 사용 (재현성 보장)
                noise = self.random_state.uniform(-1.0, 1.5)
                actual_return = expected_return * achievement_rate * noise

                # 거래 비용 반영
                entry_price = sel.get('entry_price', 0)
                if entry_price <= 0:
                    continue

                quantity = 100  # 고정 수량

                # 비용 반영 전 청산가
                gross_exit_price = entry_price * (1 + actual_return)

                # 순손익 계산 (비용 반영)
                net_pnl = self.trading_costs.calculate_net_pnl(
                    buy_price=entry_price,
                    sell_price=gross_exit_price,
                    quantity=quantity
                )

                # 실제 수익률 (비용 반영 후)
                buy_cost = self.trading_costs.calculate_buy_cost(entry_price, quantity)
                net_return = net_pnl / buy_cost if buy_cost > 0 else 0

                # 청산 사유 판단
                if net_return >= 0.10:  # 10% 이상 익절
                    exit_reason = "take_profit"
                elif net_return <= -0.05:  # -5% 이하 손절
                    exit_reason = "stop_loss"
                else:
                    exit_reason = "time_limit"

                # 보유 기간 (랜덤 3~10일)
                # ✅ MF-5 수정: RandomState 사용 (재현성 보장)
                holding_days = self.random_state.randint(3, max_holding_days + 1)

                # Trade 생성
                entry_date = sel.get('selection_date', '2025-01-01')
                exit_date = (datetime.strptime(entry_date, "%Y-%m-%d") +
                            timedelta(days=holding_days)).strftime("%Y-%m-%d")

                trade = Trade(
                    stock_code=sel.get('stock_code', 'UNKNOWN'),
                    stock_name=sel.get('stock_name', 'Unknown'),
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_date=exit_date,
                    exit_price=gross_exit_price,
                    quantity=quantity,
                    return_pct=net_return,
                    holding_days=holding_days,
                    exit_reason=exit_reason
                )

                trades.append(trade)

        return trades
