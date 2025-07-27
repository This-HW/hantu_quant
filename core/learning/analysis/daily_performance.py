"""
일일 성과 분석 시스템

선정 종목의 실제 성과를 추적하고 다양한 성과 지표를 계산하여
AI 학습을 위한 데이터를 제공하는 시스템
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
import json
import os

from ...utils.logging import get_logger

# KIS API 클라이언트 (선택적 import)
try:
    from ...api.kis_api import KISApiClient
except ImportError:
    KISApiClient = None

logger = get_logger(__name__)

@dataclass
class PerformanceMetrics:
    """성과 지표"""
    date: datetime
    stock_code: str
    stock_name: str
    entry_price: float
    current_price: float
    return_rate: float                # 수익률
    cumulative_return: float          # 누적 수익률
    volatility: float                 # 변동성
    max_drawdown: float              # 최대 손실
    sharpe_ratio: float              # 샤프 비율
    win_rate: float                  # 승률
    profit_loss_ratio: float         # 손익비
    hold_days: int                   # 보유 일수
    selection_reason: str            # 선정 이유
    phase: str                       # Phase 1 or 2
    prediction_accuracy: float       # 예측 정확도

@dataclass
class DailySelection:
    """일일 선정 정보"""
    date: datetime
    stock_code: str
    stock_name: str
    entry_price: float
    selection_reason: str
    confidence_score: float
    phase: str
    target_return: float
    stop_loss: float

class DailyPerformanceAnalyzer:
    """일일 성과 분석기"""
    
    def __init__(self, data_dir: str = "data/performance"):
        """
        초기화
        
        Args:
            data_dir: 성과 데이터 저장 디렉토리
        """
        self._logger = logger
        self._data_dir = data_dir
        self._selections_file = os.path.join(data_dir, "daily_selections.json")
        self._performance_file = os.path.join(data_dir, "performance_metrics.json")
        self._api_client = None
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 기존 데이터 로드
        self._selections = self._load_selections()
        self._performance_history = self._load_performance_history()
        
        self._logger.info("일일 성과 분석기 초기화 완료")
    
    def _get_api_client(self) -> Optional[Any]:
        """API 클라이언트 가져오기"""
        if self._api_client is None and KISApiClient is not None:
            try:
                self._api_client = KISApiClient()
            except Exception as e:
                self._logger.warning(f"API 클라이언트 초기화 실패: {e}")
                return None
        return self._api_client
    
    def _load_selections(self) -> List[DailySelection]:
        """일일 선정 기록 로드"""
        try:
            if os.path.exists(self._selections_file):
                with open(self._selections_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                selections = []
                for item in data:
                    selection = DailySelection(
                        date=datetime.fromisoformat(item['date']),
                        stock_code=item['stock_code'],
                        stock_name=item['stock_name'],
                        entry_price=item['entry_price'],
                        selection_reason=item['selection_reason'],
                        confidence_score=item['confidence_score'],
                        phase=item['phase'],
                        target_return=item['target_return'],
                        stop_loss=item['stop_loss']
                    )
                    selections.append(selection)
                
                return selections
            return []
        except Exception as e:
            self._logger.error(f"선정 기록 로드 실패: {e}")
            return []
    
    def _save_selections(self):
        """일일 선정 기록 저장"""
        try:
            data = []
            for selection in self._selections:
                item = asdict(selection)
                item['date'] = selection.date.isoformat()
                data.append(item)
            
            with open(self._selections_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self._logger.error(f"선정 기록 저장 실패: {e}")
    
    def _load_performance_history(self) -> List[PerformanceMetrics]:
        """성과 이력 로드"""
        try:
            if os.path.exists(self._performance_file):
                with open(self._performance_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                metrics = []
                for item in data:
                    metric = PerformanceMetrics(
                        date=datetime.fromisoformat(item['date']),
                        stock_code=item['stock_code'],
                        stock_name=item['stock_name'],
                        entry_price=item['entry_price'],
                        current_price=item['current_price'],
                        return_rate=item['return_rate'],
                        cumulative_return=item['cumulative_return'],
                        volatility=item['volatility'],
                        max_drawdown=item['max_drawdown'],
                        sharpe_ratio=item['sharpe_ratio'],
                        win_rate=item['win_rate'],
                        profit_loss_ratio=item['profit_loss_ratio'],
                        hold_days=item['hold_days'],
                        selection_reason=item['selection_reason'],
                        phase=item['phase'],
                        prediction_accuracy=item['prediction_accuracy']
                    )
                    metrics.append(metric)
                
                return metrics
            return []
        except Exception as e:
            self._logger.error(f"성과 이력 로드 실패: {e}")
            return []
    
    def _save_performance_history(self):
        """성과 이력 저장"""
        try:
            data = []
            for metric in self._performance_history:
                item = asdict(metric)
                item['date'] = metric.date.isoformat()
                data.append(item)
            
            with open(self._performance_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self._logger.error(f"성과 이력 저장 실패: {e}")
    
    def add_daily_selection(self, stock_code: str, stock_name: str, entry_price: float,
                          selection_reason: str, confidence_score: float, phase: str,
                          target_return: float = 0.1, stop_loss: float = -0.05) -> bool:
        """일일 선정 종목 추가"""
        try:
            selection = DailySelection(
                date=datetime.now(),
                stock_code=stock_code,
                stock_name=stock_name,
                entry_price=entry_price,
                selection_reason=selection_reason,
                confidence_score=confidence_score,
                phase=phase,
                target_return=target_return,
                stop_loss=stop_loss
            )
            
            self._selections.append(selection)
            self._save_selections()
            
            self._logger.info(f"일일 선정 추가: {stock_code} ({stock_name}), Phase {phase}")
            return True
            
        except Exception as e:
            self._logger.error(f"일일 선정 추가 실패: {e}")
            return False
    
    def update_daily_performance(self, date: Optional[datetime] = None) -> List[PerformanceMetrics]:
        """일일 성과 업데이트"""
        if date is None:
            date = datetime.now()
        
        updated_metrics = []
        api_client = self._get_api_client()
        
        # 현재 보유 중인 종목들 대상
        active_selections = [s for s in self._selections 
                           if (date - s.date).days <= 30]  # 30일 이내 선정 종목
        
        for selection in active_selections:
            try:
                # 현재 가격 조회
                current_price = self._get_current_price(selection.stock_code, api_client)
                if current_price is None:
                    continue
                
                # 성과 지표 계산
                metrics = self._calculate_performance_metrics(selection, current_price, date)
                updated_metrics.append(metrics)
                
                # 기존 데이터 업데이트 또는 추가
                self._update_performance_record(metrics)
                
            except Exception as e:
                self._logger.error(f"성과 업데이트 실패 {selection.stock_code}: {e}")
        
        # 저장
        self._save_performance_history()
        
        self._logger.info(f"일일 성과 업데이트 완료: {len(updated_metrics)}개 종목")
        return updated_metrics
    
    def _get_current_price(self, stock_code: str, api_client: Optional[Any]) -> Optional[float]:
        """현재 가격 조회"""
        if api_client is None:
            # API 없을 시 모의 데이터 (실제로는 API에서 가져와야 함)
            return None
            
        try:
            # KIS API를 통한 현재가 조회
            price_data = api_client.get_current_price(stock_code)
            if price_data and 'current_price' in price_data:
                return float(price_data['current_price'])
            return None
            
        except Exception as e:
            self._logger.error(f"현재가 조회 실패 {stock_code}: {e}")
            return None
    
    def _calculate_performance_metrics(self, selection: DailySelection, 
                                     current_price: float, date: datetime) -> PerformanceMetrics:
        """성과 지표 계산"""
        # 기본 수익률 계산
        return_rate = (current_price - selection.entry_price) / selection.entry_price
        
        # 보유 일수
        hold_days = (date - selection.date).days + 1
        
        # 이전 성과 데이터에서 가격 히스토리 추출
        price_history = self._get_price_history(selection.stock_code, selection.date, date)
        
        # 변동성 계산 (일일 수익률의 표준편차)
        volatility = self._calculate_volatility(price_history)
        
        # 최대 손실 계산
        max_drawdown = self._calculate_max_drawdown(price_history, selection.entry_price)
        
        # 샤프 비율 계산 (위험 조정 수익률)
        sharpe_ratio = self._calculate_sharpe_ratio(return_rate, volatility, hold_days)
        
        # 누적 수익률 (복리 효과 고려)
        cumulative_return = (1 + return_rate) ** (252 / max(hold_days, 1)) - 1  # 연간화
        
        # 예측 정확도 (타겟 대비)
        prediction_accuracy = self._calculate_prediction_accuracy(
            return_rate, selection.target_return, selection.stop_loss
        )
        
        # 승률과 손익비는 전체 이력에서 계산
        win_rate, profit_loss_ratio = self._calculate_win_loss_metrics(selection.phase)
        
        return PerformanceMetrics(
            date=date,
            stock_code=selection.stock_code,
            stock_name=selection.stock_name,
            entry_price=selection.entry_price,
            current_price=current_price,
            return_rate=return_rate,
            cumulative_return=cumulative_return,
            volatility=volatility,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            profit_loss_ratio=profit_loss_ratio,
            hold_days=hold_days,
            selection_reason=selection.selection_reason,
            phase=selection.phase,
            prediction_accuracy=prediction_accuracy
        )
    
    def _get_price_history(self, stock_code: str, start_date: datetime, 
                          end_date: datetime) -> List[float]:
        """가격 히스토리 조회 (모의 데이터)"""
        # 실제로는 API나 데이터베이스에서 가져와야 함
        days = (end_date - start_date).days + 1
        
        # 모의 가격 데이터 생성 (실제로는 외부 데이터 소스 사용)
        base_price = 50000  # 임시 기준 가격
        prices = []
        for i in range(days):
            # 랜덤워크 모의 생성
            change = np.random.normal(0, 0.02)  # 일일 2% 변동성
            price = base_price * (1 + change * i / days)
            prices.append(price)
        
        return prices
    
    def _calculate_volatility(self, price_history: List[float]) -> float:
        """변동성 계산"""
        if len(price_history) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(price_history)):
            ret = (price_history[i] - price_history[i-1]) / price_history[i-1]
            returns.append(ret)
        
        return np.std(returns) * np.sqrt(252)  # 연간화
    
    def _calculate_max_drawdown(self, price_history: List[float], entry_price: float) -> float:
        """최대 손실 계산"""
        if not price_history:
            return 0.0
        
        peak_price = entry_price
        max_dd = 0.0
        
        for price in price_history:
            if price > peak_price:
                peak_price = price
            
            drawdown = (price - peak_price) / peak_price
            if drawdown < max_dd:
                max_dd = drawdown
        
        return max_dd
    
    def _calculate_sharpe_ratio(self, return_rate: float, volatility: float, 
                               hold_days: int) -> float:
        """샤프 비율 계산"""
        if volatility == 0 or hold_days == 0:
            return 0.0
        
        # 연간화된 수익률
        annualized_return = (1 + return_rate) ** (252 / hold_days) - 1
        
        # 무위험 수익률 (3% 가정)
        risk_free_rate = 0.03
        
        return (annualized_return - risk_free_rate) / volatility
    
    def _calculate_prediction_accuracy(self, actual_return: float, 
                                     target_return: float, stop_loss: float) -> float:
        """예측 정확도 계산"""
        if actual_return >= target_return:
            return 1.0  # 목표 달성
        elif actual_return <= stop_loss:
            return 0.0  # 손절매
        else:
            # 부분적 달성도
            if target_return > 0:
                return max(0, actual_return / target_return)
            else:
                return 0.5  # 중립
    
    def _calculate_win_loss_metrics(self, phase: str) -> Tuple[float, float]:
        """승률과 손익비 계산"""
        phase_metrics = [m for m in self._performance_history if m.phase == phase]
        
        if not phase_metrics:
            return 0.0, 0.0
        
        # 승률 계산
        wins = len([m for m in phase_metrics if m.return_rate > 0])
        win_rate = wins / len(phase_metrics)
        
        # 손익비 계산
        profit_trades = [m for m in phase_metrics if m.return_rate > 0]
        loss_trades = [m for m in phase_metrics if m.return_rate < 0]
        
        if not loss_trades:
            profit_loss_ratio = float('inf') if profit_trades else 0.0
        else:
            avg_profit = float(np.mean([m.return_rate for m in profit_trades])) if profit_trades else 0.0
            avg_loss = abs(float(np.mean([m.return_rate for m in loss_trades])))
            profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0.0
        
        return win_rate, profit_loss_ratio
    
    def _update_performance_record(self, new_metrics: PerformanceMetrics):
        """성과 기록 업데이트"""
        # 기존 같은 날짜, 같은 종목 데이터 제거
        self._performance_history = [
            m for m in self._performance_history 
            if not (m.stock_code == new_metrics.stock_code and 
                   m.date.date() == new_metrics.date.date())
        ]
        
        # 새 데이터 추가
        self._performance_history.append(new_metrics)
        
        # 날짜순 정렬
        self._performance_history.sort(key=lambda x: x.date)
    
    def get_performance_summary(self, days: int = 30, phase: Optional[str] = None) -> Dict[str, Any]:
        """성과 요약 정보"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 기간 내 데이터 필터링
        filtered_metrics = [
            m for m in self._performance_history
            if start_date <= m.date <= end_date
        ]
        
        # Phase 필터링
        if phase:
            filtered_metrics = [m for m in filtered_metrics if m.phase == phase]
        
        if not filtered_metrics:
            return {
                'period_days': days,
                'total_trades': 0,
                'avg_return': 0.0,
                'win_rate': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'prediction_accuracy': 0.0
            }
        
        # 통계 계산
        total_trades = len(filtered_metrics)
        avg_return = np.mean([m.return_rate for m in filtered_metrics])
        win_rate = len([m for m in filtered_metrics if m.return_rate > 0]) / total_trades
        avg_sharpe = np.mean([m.sharpe_ratio for m in filtered_metrics])
        worst_drawdown = min([m.max_drawdown for m in filtered_metrics])
        avg_accuracy = np.mean([m.prediction_accuracy for m in filtered_metrics])
        
        return {
            'period_days': days,
            'total_trades': total_trades,
            'avg_return': avg_return,
            'win_rate': win_rate,
            'sharpe_ratio': avg_sharpe,
            'max_drawdown': worst_drawdown,
            'prediction_accuracy': avg_accuracy,
            'best_performer': max(filtered_metrics, key=lambda x: x.return_rate),
            'worst_performer': min(filtered_metrics, key=lambda x: x.return_rate)
        }
    
    def get_detailed_analysis(self, stock_code: Optional[str] = None, 
                            days: int = 30) -> Dict[str, Any]:
        """상세 분석 정보"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 데이터 필터링
        filtered_metrics = [
            m for m in self._performance_history
            if start_date <= m.date <= end_date
        ]
        
        if stock_code:
            filtered_metrics = [m for m in filtered_metrics if m.stock_code == stock_code]
        
        if not filtered_metrics:
            return {'error': '분석할 데이터가 없습니다'}
        
        # Phase별 분석
        phase1_metrics = [m for m in filtered_metrics if m.phase == 'Phase 1']
        phase2_metrics = [m for m in filtered_metrics if m.phase == 'Phase 2']
        
        analysis = {
            'overall': self._analyze_metrics_group(filtered_metrics),
            'phase1': self._analyze_metrics_group(phase1_metrics),
            'phase2': self._analyze_metrics_group(phase2_metrics),
            'comparison': self._compare_phases(phase1_metrics, phase2_metrics)
        }
        
        return analysis
    
    def _analyze_metrics_group(self, metrics: List[PerformanceMetrics]) -> Dict[str, Any]:
        """메트릭 그룹 분석"""
        if not metrics:
            return {'count': 0}
        
        returns = [m.return_rate for m in metrics]
        
        return {
            'count': len(metrics),
            'avg_return': np.mean(returns),
            'median_return': np.median(returns),
            'std_return': np.std(returns),
            'min_return': min(returns),
            'max_return': max(returns),
            'win_rate': len([r for r in returns if r > 0]) / len(returns),
            'avg_hold_days': np.mean([m.hold_days for m in metrics]),
            'avg_prediction_accuracy': np.mean([m.prediction_accuracy for m in metrics])
        }
    
    def _compare_phases(self, phase1_metrics: List[PerformanceMetrics], 
                       phase2_metrics: List[PerformanceMetrics]) -> Dict[str, Any]:
        """Phase 간 비교"""
        if not phase1_metrics or not phase2_metrics:
            return {'comparison_available': False}
        
        p1_returns = [m.return_rate for m in phase1_metrics]
        p2_returns = [m.return_rate for m in phase2_metrics]
        
        return {
            'comparison_available': True,
            'return_improvement': np.mean(p2_returns) - np.mean(p1_returns),
            'accuracy_improvement': (
                np.mean([m.prediction_accuracy for m in phase2_metrics]) -
                np.mean([m.prediction_accuracy for m in phase1_metrics])
            ),
            'phase1_better_count': len([r for r in p1_returns if r > np.mean(p2_returns)]),
            'phase2_better_count': len([r for r in p2_returns if r > np.mean(p1_returns)])
        }
    
    def generate_daily_report(self, date: Optional[datetime] = None) -> str:
        """일일 리포트 생성"""
        if date is None:
            date = datetime.now()
        
        # 해당 날짜 성과 데이터
        daily_metrics = [
            m for m in self._performance_history
            if m.date.date() == date.date()
        ]
        
        if not daily_metrics:
            return f"# {date.strftime('%Y-%m-%d')} 일일 성과 리포트\n\n분석할 데이터가 없습니다."
        
        # 리포트 생성
        report = [
            f"# {date.strftime('%Y-%m-%d')} 일일 성과 리포트",
            "",
            f"**분석 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**분석 종목 수**: {len(daily_metrics)}개",
            "",
            "## 📊 전체 성과",
        ]
        
        # 전체 통계
        total_return = sum([m.return_rate for m in daily_metrics])
        avg_return = total_return / len(daily_metrics)
        wins = len([m for m in daily_metrics if m.return_rate > 0])
        win_rate = wins / len(daily_metrics)
        
        report.extend([
            f"- **평균 수익률**: {avg_return:.2%}",
            f"- **승률**: {win_rate:.2%} ({wins}/{len(daily_metrics)})",
            f"- **최고 수익률**: {max([m.return_rate for m in daily_metrics]):.2%}",
            f"- **최저 수익률**: {min([m.return_rate for m in daily_metrics]):.2%}",
            ""
        ])
        
        # Phase별 성과
        phase1_metrics = [m for m in daily_metrics if m.phase == 'Phase 1']
        phase2_metrics = [m for m in daily_metrics if m.phase == 'Phase 2']
        
        if phase1_metrics:
            p1_avg = np.mean([m.return_rate for m in phase1_metrics])
            report.extend([
                "## 🎯 Phase 1 성과",
                f"- **종목 수**: {len(phase1_metrics)}개",
                f"- **평균 수익률**: {p1_avg:.2%}",
                ""
            ])
        
        if phase2_metrics:
            p2_avg = np.mean([m.return_rate for m in phase2_metrics])
            report.extend([
                "## 🚀 Phase 2 성과",
                f"- **종목 수**: {len(phase2_metrics)}개", 
                f"- **평균 수익률**: {p2_avg:.2%}",
                ""
            ])
        
        # 개별 종목 성과
        report.extend([
            "## 📋 개별 종목 성과",
            "| 종목코드 | 종목명 | 수익률 | Phase | 예측정확도 |",
            "|---------|-------|-------|-------|----------|"
        ])
        
        # 수익률 순으로 정렬
        sorted_metrics = sorted(daily_metrics, key=lambda x: x.return_rate, reverse=True)
        
        for metric in sorted_metrics:
            report.append(
                f"| {metric.stock_code} | {metric.stock_name} | "
                f"{metric.return_rate:.2%} | {metric.phase} | {metric.prediction_accuracy:.1%} |"
            )
        
        return "\n".join(report)

# 전역 인스턴스
_performance_analyzer = None

def get_performance_analyzer() -> DailyPerformanceAnalyzer:
    """성과 분석기 싱글톤 인스턴스 반환"""
    global _performance_analyzer
    if _performance_analyzer is None:
        _performance_analyzer = DailyPerformanceAnalyzer()
    return _performance_analyzer 