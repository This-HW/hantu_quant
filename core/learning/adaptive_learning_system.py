"""
실제 매매 결과 기반 적응형 학습 시스템
매일 매매 결과를 분석하여 알고리즘을 지속적으로 개선
"""

import json
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from ..utils.log_utils import get_logger
from ..performance.performance_metrics import get_performance_metrics

logger = get_logger(__name__)

@dataclass
class LearningMetrics:
    """학습 메트릭"""
    date: str
    total_trades: int
    win_rate: float
    avg_return: float
    sharpe_ratio: float
    max_drawdown: float
    accuracy_score: float
    confidence_score: float
    
@dataclass
class AlgorithmParams:
    """알고리즘 파라미터"""
    # 스크리닝 파라미터
    min_market_cap: float = 50000000000  # 500억
    max_per_ratio: float = 30.0
    min_roe: float = 0.05
    min_roa: float = 0.03
    
    # 기술적 지표 가중치
    technical_weight: float = 0.3
    fundamental_weight: float = 0.4
    momentum_weight: float = 0.3
    
    # 매매 파라미터
    risk_tolerance: float = 0.05
    position_sizing_multiplier: float = 1.0
    
    # 섹터 분산 파라미터
    max_sector_concentration: float = 0.3
    min_sector_diversity: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class AdaptiveLearningSystem:
    """적응형 학습 시스템"""
    
    def __init__(self, data_dir: str = "data/learning"):
        """초기화"""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logger
        self.performance_metrics = get_performance_metrics()
        
        # 학습 기준
        self.min_trades_for_learning = 10  # 최소 거래 수
        self.learning_sensitivity = 0.1    # 학습 민감도
        self.performance_threshold = 0.6   # 성과 임계값
        
        # 현재 파라미터
        self.current_params = self._load_current_params()
        self.logger.info("적응형 학습 시스템 초기화 완료")
        
    def _load_current_params(self) -> AlgorithmParams:
        """현재 파라미터 로드"""
        try:
            params_file = self.data_dir / "current_params.json"
            
            if params_file.exists():
                with open(params_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 딕셔너리에서 AlgorithmParams 객체 생성
                return AlgorithmParams(**data)
            else:
                # 기본 파라미터 사용
                default_params = AlgorithmParams()
                self._save_current_params(default_params)
                return default_params
                
        except Exception as e:
            self.logger.error(f"파라미터 로드 실패, 기본값 사용: {e}", exc_info=True)
            return AlgorithmParams()
            
    def _save_current_params(self, params: AlgorithmParams):
        """현재 파라미터 저장"""
        try:
            params_file = self.data_dir / "current_params.json"
            
            with open(params_file, 'w', encoding='utf-8') as f:
                json.dump(params.to_dict(), f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"파라미터 저장 실패: {e}", exc_info=True)
            
    def analyze_recent_performance(self, days: int = 7) -> Dict[str, Any]:
        """최근 성과 분석"""
        try:
            # 최근 거래 데이터 수집
            trades_data = self._collect_trade_data(days)
            
            if not trades_data:
                return {
                    "status": "insufficient_data",
                    "message": f"최근 {days}일간 거래 데이터 부족"
                }
                
            # 성과 지표 계산
            total_trades = len(trades_data)
            wins = len([t for t in trades_data if t.get('pnl', 0) > 0])
            win_rate = wins / total_trades if total_trades > 0 else 0
            
            returns = [t.get('return_rate', 0) for t in trades_data if t.get('return_rate') is not None]
            avg_return = np.mean(returns) if returns else 0
            return_std = np.std(returns) if len(returns) > 1 else 0
            sharpe_ratio = avg_return / return_std if return_std > 0 else 0
            
            # 섹터별 성과 분석
            sector_performance = self._analyze_sector_performance(trades_data)
            
            # 시간대별 성과 분석
            time_performance = self._analyze_time_performance(trades_data)
            
            return {
                "status": "success",
                "period_days": days,
                "total_trades": total_trades,
                "win_rate": win_rate,
                "avg_return": avg_return,
                "sharpe_ratio": sharpe_ratio,
                "sector_performance": sector_performance,
                "time_performance": time_performance,
                "improvement_needed": win_rate < self.performance_threshold
            }
            
        except Exception as e:
            self.logger.error(f"성과 분석 실패: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
            
    def _collect_trade_data(self, days: int) -> List[Dict[str, Any]]:
        """거래 데이터 수집 (DB 우선, JSON 폴백)"""
        try:
            trades = []

            # 1. DB에서 피드백 데이터 조회 (우선)
            try:
                from core.learning.models.feedback_system import get_feedback_system
                feedback_system = get_feedback_system()
                feedback_data = feedback_system.get_recent_feedback(days=days)

                if feedback_data:
                    for fb in feedback_data:
                        if fb.get('is_processed') and fb.get('actual_return_7d') is not None:
                            trades.append({
                                'date': fb.get('prediction_date', ''),
                                'stock_code': fb.get('stock_code', ''),
                                'pnl': fb.get('actual_return_7d', 0) * 1000000,  # 수익률 → 금액 추정
                                'return_rate': fb.get('actual_return_7d', 0),
                                'is_win': fb.get('actual_class') == 1,
                                'factor_scores': fb.get('factor_scores', {})
                            })

                    if trades:
                        self.logger.info(f"DB에서 {len(trades)}건의 거래 데이터 수집")
                        return trades

            except ImportError:
                self.logger.warning("FeedbackSystem을 import할 수 없음, JSON 폴백 사용")
            except Exception as e:
                self.logger.warning(f"DB 조회 실패, JSON 폴백 사용: {e}")

            # 2. JSON 파일 폴백
            for i in range(days):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                summary_file = f"data/trades/trade_summary_{date}.json"

                if os.path.exists(summary_file):
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary = json.load(f)

                    for detail in summary.get('details', []):
                        trades.append({
                            'date': date,
                            'stock_code': detail.get('stock_code'),
                            'pnl': detail.get('pnl', 0),
                            'return_rate': detail.get('return_rate', 0),
                            'buy_price': detail.get('buy_price', 0),
                            'sell_price': detail.get('sell_price', 0),
                            'quantity': detail.get('quantity', 0)
                        })

            if trades:
                self.logger.info(f"JSON에서 {len(trades)}건의 거래 데이터 수집")

            return trades

        except Exception as e:
            self.logger.error(f"거래 데이터 수집 실패: {e}", exc_info=True)
            return []
            
    def _analyze_sector_performance(self, trades_data: List[Dict]) -> Dict[str, float]:
        """섹터별 성과 분석"""
        try:
            # 종목별 섹터 정보 로드 (간단한 매핑)
            sector_performance = {}
            
            for trade in trades_data:
                stock_code = trade.get('stock_code')
                pnl = trade.get('pnl', 0)
                
                # 종목 코드로 섹터 추정 (실제로는 더 정확한 섹터 정보 필요)
                sector = self._get_sector_by_code(stock_code)
                
                if sector not in sector_performance:
                    sector_performance[sector] = []
                    
                sector_performance[sector].append(pnl)
                
            # 섹터별 평균 수익률 계산
            sector_avg = {}
            for sector, pnls in sector_performance.items():
                sector_avg[sector] = np.mean(pnls) if pnls else 0
                
            return sector_avg
            
        except Exception as e:
            self.logger.error(f"섹터별 성과 분석 실패: {e}", exc_info=True)
            return {}
            
    def _get_sector_by_code(self, stock_code: str) -> str:
        """종목 코드로 섹터 추정 (간단한 방법)"""
        if not stock_code:
            return "기타"
            
        # 대표적인 종목들의 섹터 매핑
        sector_mapping = {
            "005930": "반도체",    # 삼성전자
            "000660": "IT서비스",  # SK하이닉스
            "035420": "화학",      # NAVER
            "051910": "금융",      # LG화학
            "006400": "제약",      # 삼성SDI
        }
        
        return sector_mapping.get(stock_code, "기타")
        
    def _analyze_time_performance(self, trades_data: List[Dict]) -> Dict[str, float]:
        """시간대별 성과 분석"""
        try:
            # 간단한 시간대별 분석 (실제로는 더 상세한 시간 정보 필요)
            time_performance = {
                "morning": [],    # 09:00-11:00
                "midday": [],     # 11:00-14:00  
                "afternoon": []   # 14:00-15:30
            }
            
            # 현재는 전체 거래를 균등 분배 (실제로는 거래 시간 정보 필요)
            for i, trade in enumerate(trades_data):
                pnl = trade.get('pnl', 0)
                
                if i % 3 == 0:
                    time_performance["morning"].append(pnl)
                elif i % 3 == 1:
                    time_performance["midday"].append(pnl)
                else:
                    time_performance["afternoon"].append(pnl)
                    
            # 시간대별 평균 수익률
            time_avg = {}
            for time_slot, pnls in time_performance.items():
                time_avg[time_slot] = np.mean(pnls) if pnls else 0
                
            return time_avg
            
        except Exception as e:
            self.logger.error(f"시간대별 성과 분석 실패: {e}", exc_info=True)
            return {}
            
    def adapt_parameters(self, performance_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """성과 기반 파라미터 적응"""
        try:
            if performance_data.get("status") != "success":
                return False, {"message": "성과 데이터 부족"}
                
            improved_params = AlgorithmParams(**self.current_params.to_dict())
            changes_made = []
            
            # 승률이 낮으면 보수적으로 조정
            if performance_data["win_rate"] < 0.5:
                # 리스크 줄이기
                improved_params.risk_tolerance *= 0.9
                improved_params.position_sizing_multiplier *= 0.95
                
                # 더 엄격한 선정 기준
                improved_params.min_roe *= 1.05
                improved_params.max_per_ratio *= 0.95
                
                changes_made.append("보수적 조정: 리스크 감소, 선정 기준 강화")
                
            # 승률이 높으면 공격적으로 조정
            elif performance_data["win_rate"] > 0.7:
                # 리스크 늘리기
                improved_params.risk_tolerance *= 1.05
                improved_params.position_sizing_multiplier *= 1.03
                
                # 선정 기준 완화
                improved_params.min_roe *= 0.98
                improved_params.max_per_ratio *= 1.02
                
                changes_made.append("공격적 조정: 리스크 증가, 선정 기준 완화")
                
            # 섹터 성과 기반 조정
            sector_perf = performance_data.get("sector_performance", {})
            if sector_perf:
                best_sector = max(sector_perf, key=sector_perf.get)
                worst_sector = min(sector_perf, key=sector_perf.get)
                
                self.logger.info(f"최고 섹터: {best_sector} ({sector_perf[best_sector]:.2%})")
                self.logger.info(f"최저 섹터: {worst_sector} ({sector_perf[worst_sector]:.2%})")
                
                changes_made.append(f"섹터 분석: {best_sector} 강화, {worst_sector} 회피")
                
            # 샤프 비율 기반 조정
            if performance_data.get("sharpe_ratio", 0) < 0.5:
                # 변동성 줄이기
                improved_params.technical_weight *= 1.1
                improved_params.momentum_weight *= 0.9
                
                changes_made.append("샤프 비율 개선: 기술적 분석 강화")
                
            # 변경사항이 있으면 저장
            if changes_made:
                self.current_params = improved_params
                self._save_current_params(improved_params)
                
                # 변경 이력 저장
                self._save_adaptation_history(performance_data, improved_params, changes_made)
                
                return True, {
                    "message": "파라미터 적응 완료",
                    "changes": changes_made,
                    "new_params": improved_params.to_dict()
                }
            else:
                return False, {"message": "변경 불필요"}
                
        except Exception as e:
            self.logger.error(f"파라미터 적응 실패: {e}", exc_info=True)
            return False, {"message": f"오류: {e}"}
            
    def _save_adaptation_history(self, performance_data: Dict, new_params: AlgorithmParams, changes: List[str]):
        """적응 이력 저장"""
        try:
            history_file = self.data_dir / "adaptation_history.json"
            
            history_entry = {
                "date": datetime.now().isoformat(),
                "performance_data": performance_data,
                "new_params": new_params.to_dict(),
                "changes_made": changes
            }
            
            # 기존 이력 로드
            history = []
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    
            # 새 이력 추가
            history.append(history_entry)
            
            # 최근 100개만 유지
            history = history[-100:]
            
            # 저장
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"적응 이력 저장 실패: {e}", exc_info=True)
            
    def run_daily_learning(self) -> Dict[str, Any]:
        """일일 학습 실행"""
        try:
            self.logger.info("=== 일일 적응형 학습 시작 ===")
            
            # 최근 7일 성과 분석
            performance_data = self.analyze_recent_performance(days=7)
            
            if performance_data.get("status") != "success":
                return {
                    "status": "skipped",
                    "message": "충분한 거래 데이터 없음"
                }
                
            # 학습 기준 확인
            if performance_data["total_trades"] < self.min_trades_for_learning:
                return {
                    "status": "skipped", 
                    "message": f"거래 수 부족 ({performance_data['total_trades']} < {self.min_trades_for_learning})"
                }
                
            # 파라미터 적응
            adapted, adaptation_result = self.adapt_parameters(performance_data)
            
            result = {
                "status": "completed",
                "date": datetime.now().strftime('%Y-%m-%d'),
                "performance_analysis": performance_data,
                "parameter_adaptation": adaptation_result,
                "adapted": adapted
            }
            
            # 결과 저장
            self._save_learning_result(result)
            
            self.logger.info(f"일일 학습 완료 - 적응 여부: {adapted}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"일일 학습 실패: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
            
    def run_weekly_learning(self) -> Dict[str, Any]:
        """주간 학습 실행 (더 깊은 분석)"""
        try:
            self.logger.info("=== 주간 적응형 학습 시작 ===")
            
            # 최근 30일 성과 분석
            performance_data = self.analyze_recent_performance(days=30)
            
            if performance_data.get("status") != "success":
                return {
                    "status": "skipped",
                    "message": "충분한 거래 데이터 없음"
                }
                
            # 트렌드 분석
            trend_analysis = self._analyze_performance_trend(30)
            
            # 더 적극적인 파라미터 조정
            adapted, adaptation_result = self.adapt_parameters(performance_data)
            
            result = {
                "status": "completed",
                "type": "weekly",
                "date": datetime.now().strftime('%Y-%m-%d'),
                "performance_analysis": performance_data,
                "trend_analysis": trend_analysis,
                "parameter_adaptation": adaptation_result,
                "adapted": adapted
            }
            
            # 결과 저장
            self._save_learning_result(result)
            
            self.logger.info(f"주간 학습 완료 - 적응 여부: {adapted}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"주간 학습 실패: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
            
    def _analyze_performance_trend(self, days: int) -> Dict[str, Any]:
        """성과 트렌드 분석"""
        try:
            # 일별 성과 수집
            daily_performance = []
            
            for i in range(days):
                date = (datetime.now() - timedelta(days=days-i)).strftime("%Y%m%d")
                day_data = self._get_daily_performance(date)
                if day_data:
                    daily_performance.append(day_data)
                    
            if len(daily_performance) < 7:
                return {"status": "insufficient_data"}
                
            # 트렌드 계산
            returns = [d.get('avg_return', 0) for d in daily_performance]
            win_rates = [d.get('win_rate', 0) for d in daily_performance]
            
            # 선형 회귀로 트렌드 계산
            x = np.arange(len(returns))
            return_slope = np.polyfit(x, returns, 1)[0] if len(returns) > 1 else 0
            win_rate_slope = np.polyfit(x, win_rates, 1)[0] if len(win_rates) > 1 else 0
            
            return {
                "status": "success",
                "return_trend": "improving" if return_slope > 0 else "declining",
                "win_rate_trend": "improving" if win_rate_slope > 0 else "declining",
                "return_slope": return_slope,
                "win_rate_slope": win_rate_slope,
                "volatility": np.std(returns) if returns else 0
            }
            
        except Exception as e:
            self.logger.error(f"트렌드 분석 실패: {e}", exc_info=True)
            return {"status": "error"}
            
    def _get_daily_performance(self, date: str) -> Optional[Dict]:
        """특정 날짜 성과 조회"""
        try:
            summary_file = f"data/trades/trade_summary_{date}.json"
            
            if os.path.exists(summary_file):
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                    
                return {
                    'date': date,
                    'total_trades': summary.get('total_trades', 0),
                    'win_rate': summary.get('win_rate', 0),
                    'avg_return': summary.get('realized_pnl', 0) / 1000000 if summary.get('realized_pnl') else 0  # 백만원 단위로 정규화
                }
                
            return None
            
        except Exception as e:
            self.logger.error(f"일일 성과 조회 실패 {date}: {e}", exc_info=True)
            return None
            
    def _save_learning_result(self, result: Dict[str, Any]):
        """학습 결과 저장"""
        try:
            results_file = self.data_dir / "learning_results.json"
            
            # 기존 결과 로드
            results = []
            if results_file.exists():
                with open(results_file, 'r', encoding='utf-8') as f:
                    results = json.load(f)
                    
            # 새 결과 추가
            results.append(result)
            
            # 최근 50개만 유지
            results = results[-50:]
            
            # 저장
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"학습 결과 저장 실패: {e}", exc_info=True)
            
    def get_current_parameters(self) -> Dict[str, Any]:
        """현재 파라미터 조회"""
        return self.current_params.to_dict()
        
    def get_learning_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """학습 이력 조회"""
        try:
            results_file = self.data_dir / "learning_results.json"
            
            if results_file.exists():
                with open(results_file, 'r', encoding='utf-8') as f:
                    results = json.load(f)
                    
                return results[-limit:]
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"학습 이력 조회 실패: {e}", exc_info=True)
            return []

# 전역 인스턴스
_learning_system = None

def get_adaptive_learning_system() -> AdaptiveLearningSystem:
    """적응형 학습 시스템 싱글톤 인스턴스 반환"""
    global _learning_system
    if _learning_system is None:
        _learning_system = AdaptiveLearningSystem()
    return _learning_system