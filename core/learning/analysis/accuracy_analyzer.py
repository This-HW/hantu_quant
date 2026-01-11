"""
Phase 4: AI 학습 시스템 - 정확도 분석 시스템

시스템의 선정 정확도를 다양한 관점에서 분석
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import sqlite3
from dataclasses import dataclass
import json

from core.utils.log_utils import get_logger

logger = get_logger(__name__)

@dataclass
class AccuracyMetrics:
    """정확도 지표 클래스"""
    period: str  # 분석 기간
    
    # 기본 정확도 지표
    total_predictions: int
    correct_predictions: int
    accuracy: float
    
    # 수익률 기준 정확도
    positive_return_count: int
    positive_accuracy: float
    
    # 강한 수익 기준 정확도 (5% 이상)
    strong_positive_count: int
    strong_positive_accuracy: float
    
    # 평균 성과
    avg_return_1d: float
    avg_return_7d: float
    avg_return_30d: float
    
    # 리스크 조정 지표
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    
    # 섹터별 정확도
    sector_accuracy: Optional[Dict[str, float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'period': self.period,
            'total_predictions': self.total_predictions,
            'correct_predictions': self.correct_predictions,
            'accuracy': self.accuracy,
            'positive_return_count': self.positive_return_count,
            'positive_accuracy': self.positive_accuracy,
            'strong_positive_count': self.strong_positive_count,
            'strong_positive_accuracy': self.strong_positive_accuracy,
            'avg_return_1d': self.avg_return_1d,
            'avg_return_7d': self.avg_return_7d,
            'avg_return_30d': self.avg_return_30d,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'sector_accuracy': self.sector_accuracy or {}
        }

class AccuracyAnalyzer:
    """정확도 분석 시스템"""

    def __init__(self, db_path: str = "data/performance.db",
                 use_unified_db: bool = True):
        """초기화

        Args:
            db_path: 성과 데이터베이스 경로 (SQLite 폴백용)
            use_unified_db: 통합 DB 사용 여부 (기본값: True)
        """
        self._logger = logger
        self._db_path = db_path
        self._unified_db_available = False

        # 통합 DB 초기화 시도
        if use_unified_db:
            try:
                from core.database.unified_db import get_db, ensure_tables_exist
                ensure_tables_exist()
                self._unified_db_available = True
                self._logger.info("AccuracyAnalyzer: 통합 DB 사용")
            except Exception as e:
                self._logger.warning(f"통합 DB 초기화 실패, SQLite 폴백 사용: {e}")
                self._unified_db_available = False

        # 정확도 기준 설정
        self._accuracy_thresholds = {
            'positive': 0.0,      # 양수 수익률
            'good': 0.03,         # 3% 이상 수익
            'excellent': 0.05,    # 5% 이상 수익
            'outstanding': 0.10   # 10% 이상 수익
        }

        self._logger.info("AccuracyAnalyzer 초기화 완료")
    
    def analyze_accuracy(self, start_date: str, end_date: str, 
                        return_period: str = '7d') -> AccuracyMetrics:
        """정확도 분석 실행
        
        Args:
            start_date: 분석 시작 날짜 (YYYY-MM-DD)
            end_date: 분석 종료 날짜 (YYYY-MM-DD)
            return_period: 수익률 기준 기간 ('1d', '7d', '30d')
            
        Returns:
            AccuracyMetrics: 정확도 지표
        """
        try:
            self._logger.info(f"정확도 분석 시작: {start_date} ~ {end_date}, 기준: {return_period}")
            
            # 성과 데이터 조회
            performance_data = self._get_performance_data(start_date, end_date, return_period)
            
            if not performance_data:
                self._logger.warning("분석할 성과 데이터가 없습니다")
                return self._create_empty_metrics(f"{start_date} ~ {end_date}")
            
            # 기본 지표 계산
            total_predictions = len(performance_data)
            returns = [p[f'return_{return_period}'] for p in performance_data if p[f'return_{return_period}'] is not None]
            
            if not returns:
                self._logger.warning("유효한 수익률 데이터가 없습니다")
                return self._create_empty_metrics(f"{start_date} ~ {end_date}")
            
            # 양수 수익률 정확도
            positive_returns = [r for r in returns if r > self._accuracy_thresholds['positive']]
            positive_accuracy = len(positive_returns) / len(returns)
            
            # 강한 양수 수익률 정확도 (5% 이상)
            strong_positive_returns = [r for r in returns if r > self._accuracy_thresholds['excellent']]
            strong_positive_accuracy = len(strong_positive_returns) / len(returns)
            
            # 평균 수익률 계산
            avg_return_1d = self._calculate_avg_return(performance_data, '1d')
            avg_return_7d = self._calculate_avg_return(performance_data, '7d')
            avg_return_30d = self._calculate_avg_return(performance_data, '30d')
            
            # 리스크 조정 지표 계산
            sharpe_ratio = self._calculate_sharpe_ratio(returns)
            max_drawdown = self._calculate_portfolio_max_drawdown(performance_data)
            
            # 섹터별 정확도 계산
            sector_accuracy = self._calculate_sector_accuracy(performance_data, return_period)
            
            # 전체 정확도 (양수 수익률 기준)
            overall_accuracy = positive_accuracy
            
            metrics = AccuracyMetrics(
                period=f"{start_date} ~ {end_date}",
                total_predictions=total_predictions,
                correct_predictions=len(positive_returns),
                accuracy=overall_accuracy,
                positive_return_count=len(positive_returns),
                positive_accuracy=positive_accuracy,
                strong_positive_count=len(strong_positive_returns),
                strong_positive_accuracy=strong_positive_accuracy,
                avg_return_1d=avg_return_1d,
                avg_return_7d=avg_return_7d,
                avg_return_30d=avg_return_30d,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                sector_accuracy=sector_accuracy
            )
            
            self._logger.info(f"정확도 분석 완료: 전체 정확도 {overall_accuracy:.1%}")
            return metrics
            
        except Exception as e:
            self._logger.error(f"정확도 분석 오류: {e}", exc_info=True)
            return self._create_empty_metrics(f"{start_date} ~ {end_date}")
    
    def _get_performance_data(self, start_date: str, end_date: str, return_period: str) -> List[Dict]:
        """성과 데이터 조회"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                
                query = f"""
                    SELECT date, stock_code, stock_name, selection_price, selection_score,
                           return_1d, return_7d, return_30d, volatility_7d, max_drawdown_7d,
                           sector, market_cap
                    FROM daily_performance 
                    WHERE date BETWEEN ? AND ? 
                    AND return_{return_period} IS NOT NULL
                    ORDER BY date, stock_code
                """
                
                cursor.execute(query, (start_date, end_date))
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            self._logger.error(f"성과 데이터 조회 오류: {e}", exc_info=True)
            return []
    
    def _calculate_avg_return(self, performance_data: List[Dict], period: str) -> float:
        """평균 수익률 계산"""
        try:
            returns = [p[f'return_{period}'] for p in performance_data if p[f'return_{period}'] is not None]
            return np.mean(returns) if returns else 0.0
        except Exception as e:
            self._logger.error(f"평균 수익률 계산 오류: {e}", exc_info=True)
            return 0.0
    
    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.03) -> Optional[float]:
        """샤프 비율 계산
        
        Args:
            returns: 수익률 리스트
            risk_free_rate: 무위험 수익률 (연 3%)
            
        Returns:
            Optional[float]: 샤프 비율
        """
        try:
            if len(returns) < 2:
                return None
            
            returns_array = np.array(returns)
            
            # 연환산 수익률 및 변동성
            avg_return = np.mean(returns_array)
            volatility = np.std(returns_array)
            
            if volatility == 0:
                return None
            
            # 샤프 비율 계산 (무위험 수익률 일간 환산)
            daily_risk_free = risk_free_rate / 252
            sharpe = (avg_return - daily_risk_free) / volatility
            
            return float(sharpe)
            
        except Exception as e:
            self._logger.error(f"샤프 비율 계산 오류: {e}", exc_info=True)
            return None
    
    def _calculate_portfolio_max_drawdown(self, performance_data: List[Dict]) -> Optional[float]:
        """포트폴리오 최대 낙폭 계산"""
        try:
            if not performance_data:
                return None
            
            # 날짜별 평균 수익률 계산
            daily_returns = {}
            for p in performance_data:
                date = p['date']
                return_7d = p['return_7d']
                
                if return_7d is not None:
                    if date not in daily_returns:
                        daily_returns[date] = []
                    daily_returns[date].append(return_7d)
            
            # 날짜별 평균 수익률
            sorted_dates = sorted(daily_returns.keys())
            avg_returns = [np.mean(daily_returns[date]) for date in sorted_dates]
            
            if not avg_returns:
                return None
            
            # 누적 수익률 계산
            cumulative_returns = np.cumprod(1 + np.array(avg_returns))
            
            # 최대 낙폭 계산
            peak = cumulative_returns[0]
            max_drawdown = 0.0
            
            for value in cumulative_returns:
                if value > peak:
                    peak = value
                
                drawdown = (peak - value) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            return float(max_drawdown)
            
        except Exception as e:
            self._logger.error(f"포트폴리오 최대 낙폭 계산 오류: {e}", exc_info=True)
            return None
    
    def _calculate_sector_accuracy(self, performance_data: List[Dict], return_period: str) -> Dict[str, float]:
        """섹터별 정확도 계산"""
        try:
            sector_data = {}
            
            for p in performance_data:
                sector = p.get('sector', '기타')
                return_value = p[f'return_{return_period}']
                
                if return_value is not None:
                    if sector not in sector_data:
                        sector_data[sector] = []
                    sector_data[sector].append(return_value)
            
            sector_accuracy = {}
            for sector, returns in sector_data.items():
                if returns:
                    positive_count = sum(1 for r in returns if r > 0)
                    accuracy = positive_count / len(returns)
                    sector_accuracy[sector] = accuracy
            
            return sector_accuracy
            
        except Exception as e:
            self._logger.error(f"섹터별 정확도 계산 오류: {e}", exc_info=True)
            return {}
    
    def _create_empty_metrics(self, period: str) -> AccuracyMetrics:
        """빈 정확도 지표 생성"""
        return AccuracyMetrics(
            period=period,
            total_predictions=0,
            correct_predictions=0,
            accuracy=0.0,
            positive_return_count=0,
            positive_accuracy=0.0,
            strong_positive_count=0,
            strong_positive_accuracy=0.0,
            avg_return_1d=0.0,
            avg_return_7d=0.0,
            avg_return_30d=0.0
        )
    
    def compare_periods(self, periods: List[Tuple[str, str]], 
                       return_period: str = '7d') -> Dict[str, AccuracyMetrics]:
        """여러 기간 정확도 비교
        
        Args:
            periods: 분석할 기간들 [(start_date, end_date), ...]
            return_period: 수익률 기준 기간
            
        Returns:
            Dict[str, AccuracyMetrics]: 기간별 정확도 지표
        """
        try:
            results = {}
            
            for start_date, end_date in periods:
                period_key = f"{start_date}~{end_date}"
                metrics = self.analyze_accuracy(start_date, end_date, return_period)
                results[period_key] = metrics
            
            return results
            
        except Exception as e:
            self._logger.error(f"기간 비교 분석 오류: {e}", exc_info=True)
            return {}
    
    def get_accuracy_trend(self, start_date: str, end_date: str, 
                          window_days: int = 30) -> List[Dict[str, Any]]:
        """정확도 추세 분석
        
        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜  
            window_days: 분석 윈도우 크기 (일)
            
        Returns:
            List[Dict[str, Any]]: 시계열 정확도 데이터
        """
        try:
            trend_data = []
            
            current_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            
            while current_date <= end_datetime:
                window_start = current_date
                window_end = current_date + timedelta(days=window_days)
                
                if window_end > end_datetime:
                    window_end = end_datetime
                
                # 해당 윈도우의 정확도 계산
                metrics = self.analyze_accuracy(
                    window_start.strftime('%Y-%m-%d'),
                    window_end.strftime('%Y-%m-%d')
                )
                
                trend_data.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'window_start': window_start.strftime('%Y-%m-%d'),
                    'window_end': window_end.strftime('%Y-%m-%d'),
                    'accuracy': metrics.accuracy,
                    'total_predictions': metrics.total_predictions,
                    'avg_return_7d': metrics.avg_return_7d
                })
                
                # 다음 윈도우로 이동 (일주일 단위)
                current_date += timedelta(days=7)
            
            return trend_data
            
        except Exception as e:
            self._logger.error(f"정확도 추세 분석 오류: {e}", exc_info=True)
            return []
    
    def save_accuracy_report(self, metrics: AccuracyMetrics, filepath: str) -> bool:
        """정확도 리포트 저장
        
        Args:
            metrics: 정확도 지표
            filepath: 저장 경로
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            report_data = {
                'accuracy_metrics': metrics.to_dict(),
                'generated_at': datetime.now().isoformat(),
                'analysis_summary': {
                    'total_selections': metrics.total_predictions,
                    'success_rate': f"{metrics.accuracy:.1%}",
                    'strong_success_rate': f"{metrics.strong_positive_accuracy:.1%}",
                    'average_7d_return': f"{metrics.avg_return_7d:.2%}",
                    'risk_adjusted_return': f"{metrics.sharpe_ratio:.3f}" if metrics.sharpe_ratio else "N/A"
                }
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"정확도 리포트 저장 완료: {filepath}")
            return True
            
        except Exception as e:
            self._logger.error(f"정확도 리포트 저장 오류: {e}", exc_info=True)
            return False 