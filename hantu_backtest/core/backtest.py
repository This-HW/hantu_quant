"""
Backtesting engine for Hantu Quant trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from pathlib import Path
import logging
import json
from decimal import Decimal

from .metrics import calculate_metrics
from .portfolio import Portfolio
from ..strategies.base import BacktestStrategy
from ..visualization.backtest import BacktestVisualizer

logger = logging.getLogger(__name__)


class Backtest:
    """백테스팅 엔진"""

    def __init__(
        self,
        strategy: BacktestStrategy,
        start_date: str,
        end_date: str,
        initial_capital: float = 100_000_000,
        commission: float = 0.00015,  # 0.015%
        slippage: float = 0.0001,
    ):  # 0.01%
        """
        Args:
            strategy: 백테스팅할 전략
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            initial_capital: 초기 자본금
            commission: 수수료율
            slippage: 슬리피지
        """
        self.strategy = strategy
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

        self.portfolio = Portfolio(initial_capital)
        self.trades: List[Dict] = []
        self.equity_curve: pd.Series = None

        # 데이터 저장 경로
        self.data_dir = Path(__file__).parent.parent / "data"
        self.results_dir = self.data_dir / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # 시각화 도구
        self.visualizer = BacktestVisualizer()

    def run(self) -> Dict[str, Any]:
        """백테스트 실행

        Returns:
            Dict[str, Any]: 백테스트 결과
                - returns: 수익률 정보
                - positions: 포지션 정보
                - trades: 거래 내역
        """
        try:
            logger.info(f"[{self.strategy.name}] 백테스트 시작")

            # 데이터 로드
            data = self.strategy.load_data(self.start_date, self.end_date)
            if data.empty:
                raise ValueError("데이터가 비어있습니다.")

            # 포트폴리오 초기화
            self.strategy.initialize_portfolio(self.initial_capital)

            # 매매 신호 생성
            signals = self.strategy.generate_signals(data)
            if signals.empty:
                logger.warning("매매 신호가 없습니다.")
                return {"returns": {"total_return": 0.0}, "positions": {}, "trades": []}

            # 거래 실행 및 포트폴리오 업데이트
            trades = []
            equity_curve = pd.Series(index=data.index, dtype=float)
            test_code = "TEST"  # 테스트용 종목 코드

            # 초기 포트폴리오 가치 설정
            equity_curve.iloc[0] = self.initial_capital

            for i, date in enumerate(data.index):
                current_data = data.loc[date]
                signal = signals.loc[date, "signal"] if date in signals.index else 0

                if signal == 1:  # 매수 신호
                    quantity = int(
                        self.initial_capital * 0.1 / current_data["close"]
                    )  # 자본의 10% 투자
                    if quantity > 0:
                        self.strategy.execute_trade(
                            code=test_code,
                            action="buy",
                            price=Decimal(str(current_data["close"])),
                            quantity=quantity,
                        )
                        trades.append(
                            {
                                "date": date,
                                "type": "buy",
                                "price": float(current_data["close"]),
                                "quantity": quantity,
                            }
                        )

                elif signal == -1:  # 매도 신호
                    position = self.strategy.portfolio.get_position(test_code)
                    if position and position.quantity > 0:
                        self.strategy.execute_trade(
                            code=test_code,
                            action="sell",
                            price=Decimal(str(current_data["close"])),
                            quantity=position.quantity,
                        )
                        trades.append(
                            {
                                "date": date,
                                "type": "sell",
                                "price": float(current_data["close"]),
                                "quantity": position.quantity,
                            }
                        )

                # 포트폴리오 가치 계산 (간단한 방법)
                if i > 0:
                    equity_curve.iloc[i] = equity_curve.iloc[i - 1]  # 이전 값 복사
                else:
                    equity_curve.iloc[i] = self.initial_capital

            # 성과 지표 계산 (간단한 방법)
            final_value = (
                equity_curve.iloc[-1] if len(equity_curve) > 0 else self.initial_capital
            )
            total_return = (
                (final_value - self.initial_capital) / self.initial_capital
            ) * 100

            # 간단한 연간 수익률 계산
            days = len(equity_curve)
            annual_return = total_return * (365 / days) if days > 0 else 0

            metrics = {
                "total_return": total_return,
                "annual_return": annual_return,
                "daily_returns_mean": 0.0,
                "daily_returns_std": 1.0,
                "sharpe_ratio": 0.0,
            }

            # 최종 포지션 정보 수집
            positions = {}
            for code, position in self.strategy.portfolio.positions.items():
                positions[code] = {
                    "quantity": position.quantity,
                    "avg_price": float(position.avg_price),
                }

            logger.info(f"[{self.strategy.name}] 백테스트 완료")
            return {
                "returns": {
                    "total_return": metrics["total_return"],
                    "annual_return": metrics["annual_return"],
                    "daily_returns_mean": metrics["daily_returns_mean"],
                    "daily_returns_std": metrics["daily_returns_std"],
                    "sharpe_ratio": metrics["sharpe_ratio"],
                },
                "positions": positions,
                "trades": trades,
            }

        except Exception as e:
            logger.error(f"[run] 백테스트 실행 중 오류 발생: {str(e)}")
            raise

    def _execute_trade(self, signal: Dict, data: pd.DataFrame) -> Optional[Dict]:
        """주문 실행"""
        try:
            code = signal["code"]
            order_type = signal["type"]  # 'buy' or 'sell'
            quantity = signal["quantity"]
            price = data.loc[code, "close"]

            # 슬리피지 적용
            if order_type == "buy":
                price *= 1 + self.slippage
            else:
                price *= 1 - self.slippage

            # 수수료 계산
            commission = price * quantity * self.commission

            # 포트폴리오 업데이트
            if order_type == "buy":
                if not self.portfolio.can_buy(price, quantity, commission):
                    return None
                self.portfolio.buy(code, quantity, price, commission)
            else:
                if not self.portfolio.can_sell(code, quantity):
                    return None
                self.portfolio.sell(code, quantity, price, commission)

            # 거래 기록
            trade = {
                "datetime": data.index[0],
                "code": code,
                "type": order_type,
                "quantity": quantity,
                "price": price,
                "commission": commission,
                "total": price * quantity + commission,
            }

            logger.debug(f"[_execute_trade] 거래 실행 - {trade}")
            return trade

        except Exception as e:
            logger.error(f"[_execute_trade] 거래 실행 중 오류 발생: {str(e)}")
            return None

    def _update_equity_curve(self, date: pd.Timestamp):
        """자본금 곡선 업데이트"""
        if self.equity_curve is None:
            self.equity_curve = pd.Series(dtype=float)
        self.equity_curve[date] = self.portfolio.total_value

    def _visualize_results(self):
        """백테스트 결과 시각화"""
        try:
            # 수익률 계산
            returns = self.equity_curve.pct_change().dropna()

            # 1. 자본금 곡선
            self.visualizer.plot_equity_curve(self.equity_curve)

            # 2. 수익률 분포
            self.visualizer.plot_returns_distribution(returns)

            # 3. Drawdown
            self.visualizer.plot_drawdown(self.equity_curve)

            # 4. 월별 수익률
            self.visualizer.plot_monthly_returns(returns)

            # 5. 거래 분석
            self.visualizer.plot_trade_analysis(self.trades)

        except Exception as e:
            logger.error(f"[_visualize_results] 결과 시각화 중 오류 발생: {str(e)}")

    def _save_results(self, metrics: Dict):
        """백테스트 결과 저장"""
        try:
            # 결과 파일명 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_results_{self.strategy.name}_{timestamp}.json"
            filepath = self.results_dir / filename

            # 결과 저장
            results = {
                "strategy": self.strategy.name,
                "period": {
                    "start": self.start_date.strftime("%Y-%m-%d"),
                    "end": self.end_date.strftime("%Y-%m-%d"),
                },
                "parameters": {
                    "initial_capital": self.initial_capital,
                    "commission": self.commission,
                    "slippage": self.slippage,
                },
                "metrics": metrics,
                "trades": self.trades,
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            logger.info(f"[_save_results] 백테스트 결과 저장 완료: {filepath}")

        except Exception as e:
            logger.error(f"[_save_results] 결과 저장 중 오류 발생: {str(e)}")
