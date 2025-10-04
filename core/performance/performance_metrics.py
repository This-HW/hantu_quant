"""
실시간 성과 지표 계산 모듈
실제 거래 데이터를 기반으로 성과 지표를 계산
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import numpy as np

from ..utils.log_utils import get_logger
from ..api.kis_api import KISAPI
from ..trading.trade_journal import TradeJournal

logger = get_logger(__name__)


class PerformanceMetrics:
    """실시간 성과 지표 계산 클래스"""
    
    def __init__(self):
        """초기화"""
        self.api = None
        self.logger = logger
        
    def _get_api(self) -> Optional[KISAPI]:
        """API 인스턴스 가져오기"""
        if self.api is None:
            try:
                self.api = KISAPI()
            except Exception as e:
                self.logger.error(f"API 초기화 실패: {e}")
        return self.api
        
    def get_daily_performance(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """당일 성과 계산 (실현손익 + 평가손익)
        
        Returns:
            Dict containing:
            - realized_pnl: 당일 매도 실현손익
            - realized_return: 당일 매도 수익률
            - unrealized_pnl: 보유 종목 평가손익
            - unrealized_return: 보유 종목 평가수익률
            - total_pnl: 총 손익
            - total_return: 총 수익률
            - win_rate: 승률
            - trade_count: 거래 횟수
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
            
        result = {
            "date": date_str,
            "realized_pnl": 0.0,
            "realized_return": 0.0,
            "unrealized_pnl": 0.0,
            "unrealized_return": 0.0,
            "total_pnl": 0.0,
            "total_return": 0.0,
            "win_rate": 0.0,
            "trade_count": 0,
            "holding_count": 0
        }
        
        # 1. 실현손익 계산 (매매일지에서)
        realized_data = self._get_realized_performance(date_str)
        result.update(realized_data)
        
        # 2. 평가손익 계산 (현재 보유 종목)
        unrealized_data = self._get_unrealized_performance()
        result.update(unrealized_data)
        
        # 3. 총합 계산
        result["total_pnl"] = result["realized_pnl"] + result["unrealized_pnl"]
        
        # 총 수익률 계산 (투자금 대비)
        total_investment = self._get_total_investment()
        if total_investment > 0:
            result["total_return"] = result["total_pnl"] / total_investment
        
        return result
        
    def _get_realized_performance(self, date_str: str) -> Dict[str, Any]:
        """실현손익 계산 (매매일지 기반)"""
        try:
            # 매매일지 요약 파일 읽기
            summary_path = f"data/trades/trade_summary_{date_str}.json"
            if os.path.exists(summary_path):
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                    
                # 실현 수익률 계산
                realized_return = 0.0
                if summary.get("details"):
                    returns = []
                    for trade in summary["details"]:
                        buy_price = trade.get("buy_price", 0)
                        sell_price = trade.get("sell_price", 0)
                        if buy_price > 0:
                            returns.append((sell_price - buy_price) / buy_price)
                    if returns:
                        realized_return = np.mean(returns)
                        
                return {
                    "realized_pnl": summary.get("realized_pnl", 0.0),
                    "realized_return": realized_return,
                    "win_rate": summary.get("win_rate", 0.0),
                    "trade_count": summary.get("total_trades", 0)
                }
            else:
                # 매매일지가 없으면 TradeJournal로 직접 계산
                journal = TradeJournal()
                summary = journal.compute_daily_summary()
                
                realized_return = 0.0
                if summary.get("details"):
                    returns = []
                    for trade in summary["details"]:
                        buy_price = trade.get("buy_price", 0)
                        sell_price = trade.get("sell_price", 0)
                        if buy_price > 0:
                            returns.append((sell_price - buy_price) / buy_price)
                    if returns:
                        realized_return = np.mean(returns)
                        
                return {
                    "realized_pnl": summary.get("realized_pnl", 0.0),
                    "realized_return": realized_return,
                    "win_rate": summary.get("win_rate", 0.0),
                    "trade_count": summary.get("total_trades", 0)
                }
                
        except Exception as e:
            self.logger.error(f"실현손익 계산 실패: {e}")
            return {
                "realized_pnl": 0.0,
                "realized_return": 0.0,
                "win_rate": 0.0,
                "trade_count": 0
            }
            
    def _get_unrealized_performance(self) -> Dict[str, Any]:
        """평가손익 계산 (보유 종목 기반)"""
        try:
            api = self._get_api()
            if not api:
                return {
                    "unrealized_pnl": 0.0,
                    "unrealized_return": 0.0,
                    "holding_count": 0
                }
                
            # 잔고 조회
            balance = api.get_balance()
            if not balance or not balance.get("positions"):
                return {
                    "unrealized_pnl": 0.0,
                    "unrealized_return": 0.0,
                    "holding_count": 0
                }
                
            total_pnl = 0.0
            total_investment = 0.0
            holding_count = 0
            
            for stock_code, position in balance["positions"].items():
                quantity = position.get("quantity", 0)
                avg_price = position.get("avg_price", 0)
                current_price = position.get("current_price", 0)
                
                if quantity > 0 and avg_price > 0:
                    investment = avg_price * quantity
                    current_value = current_price * quantity
                    pnl = current_value - investment
                    
                    total_pnl += pnl
                    total_investment += investment
                    holding_count += 1
                    
            unrealized_return = 0.0
            if total_investment > 0:
                unrealized_return = total_pnl / total_investment
                
            return {
                "unrealized_pnl": total_pnl,
                "unrealized_return": unrealized_return,
                "holding_count": holding_count
            }
            
        except Exception as e:
            self.logger.error(f"평가손익 계산 실패: {e}")
            return {
                "unrealized_pnl": 0.0,
                "unrealized_return": 0.0,
                "holding_count": 0
            }
            
    def _get_total_investment(self) -> float:
        """총 투자금액 계산"""
        try:
            api = self._get_api()
            if not api:
                return 0.0
                
            balance = api.get_balance()
            if not balance:
                return 0.0
                
            # 예수금 + 평가금액
            deposit = balance.get("deposit", 0)
            total_eval = balance.get("total_eval_amount", 0)
            
            return deposit + total_eval
            
        except Exception as e:
            self.logger.error(f"총 투자금액 계산 실패: {e}")
            return 0.0
            
    def get_historical_performance(self, days: int = 30) -> Dict[str, Any]:
        """과거 성과 통계 계산
        
        Args:
            days: 분석할 과거 일수
            
        Returns:
            Dict containing historical performance metrics
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        total_realized_pnl = 0.0
        total_trades = 0
        winning_trades = 0
        daily_returns = []
        
        # 각 날짜별로 매매 요약 파일 읽기
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y%m%d")
            summary_path = f"data/trades/trade_summary_{date_str}.json"
            
            if os.path.exists(summary_path):
                try:
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        summary = json.load(f)
                        
                    total_realized_pnl += summary.get("realized_pnl", 0.0)
                    total_trades += summary.get("total_trades", 0)
                    
                    # 승률 계산을 위한 데이터
                    if summary.get("details"):
                        for trade in summary["details"]:
                            if trade.get("pnl", 0) > 0:
                                winning_trades += 1
                                
                    # 일별 수익률
                    if summary.get("details"):
                        for trade in summary["details"]:
                            buy_price = trade.get("buy_price", 0)
                            sell_price = trade.get("sell_price", 0)
                            if buy_price > 0:
                                daily_returns.append((sell_price - buy_price) / buy_price)
                                
                except Exception as e:
                    self.logger.error(f"요약 파일 읽기 실패 {date_str}: {e}")
                    
            current_date += timedelta(days=1)
            
        # 통계 계산
        avg_return = np.mean(daily_returns) if daily_returns else 0.0
        win_rate = (winning_trades / total_trades) if total_trades > 0 else 0.0
        
        # 샤프 비율 계산 (연간화)
        if daily_returns and len(daily_returns) > 1:
            returns_std = np.std(daily_returns)
            if returns_std > 0:
                sharpe_ratio = (avg_return * 252) / (returns_std * np.sqrt(252))
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0
            
        return {
            "period_days": days,
            "total_realized_pnl": total_realized_pnl,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "avg_return": avg_return,
            "sharpe_ratio": sharpe_ratio,
            "accuracy": win_rate  # 정확도를 승률로 사용
        }
        
    def get_screening_statistics(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """스크리닝 통계 가져오기"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
            
        try:
            # 스크리닝 결과 파일 읽기
            screening_file = f"data/watchlist/screening_{date_str}.json"
            if os.path.exists(screening_file):
                with open(screening_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                stocks = data.get("stocks", [])
                total_count = len(stocks)
                
                # 평균 점수 계산
                scores = [s.get("total_score", 0) for s in stocks]
                avg_score = np.mean(scores) if scores else 0.0
                
                # 섹터별 통계
                sectors = {}
                for stock in stocks:
                    sector = stock.get("sector", "기타")
                    sectors[sector] = sectors.get(sector, 0) + 1
                    
                return {
                    "total_count": total_count,
                    "avg_score": avg_score,
                    "sectors": sectors
                }
            else:
                return {
                    "total_count": 0,
                    "avg_score": 0.0,
                    "sectors": {}
                }
                
        except Exception as e:
            self.logger.error(f"스크리닝 통계 계산 실패: {e}")
            return {
                "total_count": 0,
                "avg_score": 0.0,
                "sectors": {}
            }


# 싱글톤 인스턴스
_metrics_instance = None

def get_performance_metrics() -> PerformanceMetrics:
    """성과 지표 계산기 싱글톤 인스턴스 반환"""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = PerformanceMetrics()
    return _metrics_instance