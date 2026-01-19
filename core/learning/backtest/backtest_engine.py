"""
백테스트 실행 엔진

기존 hantu_backtest 모듈과 통합하여 자동화된 백테스트 실행을 제공
"""

import numpy as np
import pandas as pd
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
import uuid

from ...utils.logging import get_logger

logger = get_logger(__name__)

class BacktestStatus(Enum):
    """백테스트 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class BacktestConfig:
    """백테스트 설정"""
    start_date: str = "2023-01-01"          # 백테스트 시작일
    end_date: str = "2024-01-01"            # 백테스트 종료일
    initial_capital: float = 10000000       # 초기 자본 (1천만원)
    commission: float = 0.0015              # 수수료 (0.15%)
    slippage: float = 0.0001                # 슬리피지 (0.01%)
    max_positions: int = 20                 # 최대 포지션 수
    timeout_seconds: int = 300              # 타임아웃 (5분)
    parallel_execution: bool = True         # 병렬 실행 여부
    use_dummy_data: bool = True             # 더미 데이터 사용 여부
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return asdict(self)

@dataclass
class BacktestResult:
    """백테스트 결과"""
    backtest_id: str
    strategy_name: str
    parameters: Dict[str, Any]
    config: BacktestConfig
    status: BacktestStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_time: Optional[float] = None
    
    # 성과 지표
    total_return: Optional[float] = None
    annual_return: Optional[float] = None
    volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    calmar_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    total_trades: Optional[int] = None
    winning_trades: Optional[int] = None
    losing_trades: Optional[int] = None
    average_win: Optional[float] = None
    average_loss: Optional[float] = None
    largest_win: Optional[float] = None
    largest_loss: Optional[float] = None
    consecutive_wins: Optional[int] = None
    consecutive_losses: Optional[int] = None
    
    # 월별/년별 수익률
    monthly_returns: Optional[List[float]] = field(default_factory=list)
    yearly_returns: Optional[List[float]] = field(default_factory=list)
    
    # 포트폴리오 데이터
    equity_curve: Optional[List[float]] = field(default_factory=list)
    positions_history: Optional[List[Dict]] = field(default_factory=list)
    trades_history: Optional[List[Dict]] = field(default_factory=list)
    
    # 추가 정보
    error_message: Optional[str] = None
    log_file: Optional[str] = None
    result_file: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환 (JSON 직렬화 가능)"""
        result_dict = asdict(self)
        
        # Enum과 datetime 처리
        result_dict['status'] = self.status.value
        result_dict['start_time'] = self.start_time.isoformat()
        if self.end_time:
            result_dict['end_time'] = self.end_time.isoformat()
        
        # BacktestConfig 처리
        result_dict['config'] = self.config.to_dict()
        
        return result_dict

class BacktestEngine:
    """백테스트 실행 엔진"""
    
    def __init__(self, 
                 hantu_backtest_path: str = "hantu_backtest",
                 data_dir: str = "data/backtest_automation",
                 results_dir: str = "data/backtest_results"):
        """
        초기화
        
        Args:
            hantu_backtest_path: hantu_backtest 모듈 경로
            data_dir: 백테스트 설정 데이터 저장 디렉토리
            results_dir: 백테스트 결과 저장 디렉토리
        """
        self._logger = logger
        self._hantu_backtest_path = hantu_backtest_path
        self._data_dir = Path(data_dir)
        self._results_dir = Path(results_dir)
        
        # 디렉토리 생성
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._results_dir.mkdir(parents=True, exist_ok=True)
        
        # 실행 중인 백테스트 관리
        self._running_backtests: Dict[str, BacktestResult] = {}
        self._backtest_history: List[BacktestResult] = []
        
        # 통계
        self._total_backtests = 0
        self._successful_backtests = 0
        self._failed_backtests = 0
        
        self._logger.info("백테스트 엔진 초기화 완료")
    
    def run_backtest(self, 
                    strategy_name: str, 
                    parameters: Dict[str, Any],
                    config: Optional[BacktestConfig] = None) -> BacktestResult:
        """
        백테스트 실행
        
        Args:
            strategy_name: 전략명 (예: "momentum", "mean_reversion")
            parameters: 전략 파라미터
            config: 백테스트 설정
        
        Returns:
            BacktestResult: 백테스트 결과
        """
        if config is None:
            config = BacktestConfig()
        
        # 백테스트 ID 생성
        backtest_id = f"{strategy_name}_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 백테스트 결과 객체 생성
        result = BacktestResult(
            backtest_id=backtest_id,
            strategy_name=strategy_name,
            parameters=parameters,
            config=config,
            status=BacktestStatus.PENDING,
            start_time=datetime.now()
        )
        
        try:
            self._logger.info(f"백테스트 시작: {backtest_id} [{strategy_name}]")
            self._total_backtests += 1
            
            result.status = BacktestStatus.RUNNING
            self._running_backtests[backtest_id] = result
            
            # 백테스트 실행
            if config.use_dummy_data:
                success, metrics, error = self._run_dummy_backtest(strategy_name, parameters, config)
            else:
                success, metrics, error = self._run_hantu_backtest(strategy_name, parameters, config)
            
            # 결과 처리
            result.end_time = datetime.now()
            result.execution_time = (result.end_time - result.start_time).total_seconds()
            
            if success and metrics:
                self._populate_result_metrics(result, metrics)
                result.status = BacktestStatus.COMPLETED
                self._successful_backtests += 1
                
                self._logger.info(
                    f"백테스트 완료: {backtest_id} - "
                    f"수익률: {result.total_return:.2%}, "
                    f"샤프비율: {result.sharpe_ratio:.2f}"
                )
            else:
                result.status = BacktestStatus.FAILED
                result.error_message = error
                self._failed_backtests += 1
                self._logger.error(f"백테스트 실패: {backtest_id} - {error}", exc_info=True)
            
        except Exception as e:
            result.status = BacktestStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.now()
            result.execution_time = (result.end_time - result.start_time).total_seconds()
            self._failed_backtests += 1
            self._logger.error(f"백테스트 예외 발생: {backtest_id} - {e}", exc_info=True)
        
        finally:
            # 실행 중 목록에서 제거
            if backtest_id in self._running_backtests:
                del self._running_backtests[backtest_id]
            
            # 히스토리에 추가
            self._backtest_history.append(result)
            
            # 결과 저장
            self._save_backtest_result(result)
        
        return result
    
    def _run_hantu_backtest(self, 
                           strategy_name: str, 
                           parameters: Dict[str, Any],
                           config: BacktestConfig) -> Tuple[bool, Optional[Dict], str]:
        """hantu_backtest 모듈을 사용한 백테스트 실행"""
        try:
            # hantu_backtest 모듈 임포트
            sys.path.insert(0, str(Path.cwd()))
            
            from hantu_backtest.core.backtest import Backtest
            from hantu_backtest.strategies.momentum import MomentumStrategy
            
            # 전략 초기화
            if strategy_name.lower() == "momentum":
                strategy = MomentumStrategy(
                    rsi_period=parameters.get('rsi_period', 14),
                    rsi_lower=parameters.get('rsi_lower', 30),
                    rsi_upper=parameters.get('rsi_upper', 70),
                    ma_short=parameters.get('ma_short', 5),
                    ma_long=parameters.get('ma_long', 20)
                )
            else:
                return False, None, f"지원하지 않는 전략: {strategy_name}"
            
            # 백테스트 실행
            backtest = Backtest(
                strategy=strategy,
                start_date=config.start_date,
                end_date=config.end_date,
                initial_capital=config.initial_capital,
                commission=config.commission,
                slippage=config.slippage
            )
            
            results = backtest.run()
            
            if results and 'returns' in results:
                metrics = results['returns']
                metrics.update({
                    'trades': results.get('trades', []),
                    'positions': results.get('positions', {}),
                    'total_trades': len(results.get('trades', [])),
                    'equity_curve': results.get('equity_curve', [])
                })
                return True, metrics, ""
            else:
                return False, None, "백테스트 결과가 비어있습니다"
                
        except ImportError as e:
            return False, None, f"hantu_backtest 모듈 임포트 실패: {e}"
        except Exception as e:
            return False, None, f"hantu_backtest 실행 실패: {e}"
    
    def _run_dummy_backtest(self, 
                           strategy_name: str, 
                           parameters: Dict[str, Any],
                           config: BacktestConfig) -> Tuple[bool, Optional[Dict], str]:
        """더미 데이터를 사용한 백테스트 시뮬레이션"""
        try:
            # 시드 설정 (일관된 결과를 위해)
            np.random.seed(hash(str(parameters)) % 2**32)
            
            # 기간 계산
            start_date = pd.to_datetime(config.start_date)
            end_date = pd.to_datetime(config.end_date)
            days = (end_date - start_date).days
            
            # 전략별 성과 시뮬레이션
            if strategy_name.lower() == "momentum":
                base_return = 0.12  # 12% 연간 수익률
                volatility = 0.18   # 18% 변동성
                sharpe_base = 0.67
            elif strategy_name.lower() == "mean_reversion":
                base_return = 0.08  # 8% 연간 수익률
                volatility = 0.15   # 15% 변동성
                sharpe_base = 0.53
            else:
                base_return = 0.06  # 6% 연간 수익률
                volatility = 0.20   # 20% 변동성
                sharpe_base = 0.30
            
            # 파라미터 영향 계산
            param_effect = self._calculate_parameter_effect(parameters, strategy_name)
            
            # 최종 성과 지표 계산
            annual_return = base_return * (1 + param_effect)
            actual_volatility = volatility * (1 + param_effect * 0.5)
            sharpe_ratio = sharpe_base * (1 + param_effect * 0.3)
            
            # 일별 수익률 시뮬레이션
            daily_returns = np.random.normal(
                annual_return / 252, 
                actual_volatility / np.sqrt(252), 
                days
            )
            
            # 트렌드 효과 추가
            trend = np.linspace(0, param_effect * 0.1, days)
            daily_returns += trend
            
            # 누적 수익률과 equity curve
            cumulative_returns = np.cumprod(1 + daily_returns)
            total_return = cumulative_returns[-1] - 1
            equity_curve = (config.initial_capital * cumulative_returns).tolist()
            
            # 최대 낙폭 계산
            peak = np.maximum.accumulate(cumulative_returns)
            drawdown = (cumulative_returns - peak) / peak
            max_drawdown = abs(drawdown.min())
            
            # 거래 통계 시뮬레이션
            total_trades = int(np.random.uniform(50, 200) * (1 + param_effect * 0.2))
            win_rate = np.clip(np.random.uniform(0.45, 0.65) * (1 + param_effect * 0.1), 0.3, 0.8)
            winning_trades = int(total_trades * win_rate)
            losing_trades = total_trades - winning_trades
            
            average_win = np.random.uniform(0.03, 0.08) * (1 + param_effect * 0.2)
            average_loss = -np.random.uniform(0.02, 0.05) * (1 - param_effect * 0.1)
            profit_factor = abs(average_win * winning_trades / (average_loss * losing_trades)) if losing_trades > 0 else 3.0
            
            # 월별 수익률 계산
            monthly_returns = []
            for i in range(0, days, 30):
                end_idx = min(i + 30, days)
                if i < days:
                    period_return = cumulative_returns[end_idx-1] / (cumulative_returns[i] if i > 0 else 1) - 1
                    monthly_returns.append(period_return)
            
            # 거래 히스토리 생성
            trades_history = []
            for i in range(total_trades):
                is_win = i < winning_trades
                trade = {
                    'trade_id': i + 1,
                    'symbol': f'STOCK_{i % 20:03d}',
                    'entry_date': (start_date + timedelta(days=int(i * days / total_trades))).isoformat(),
                    'exit_date': (start_date + timedelta(days=int((i + 1) * days / total_trades))).isoformat(),
                    'position_size': np.random.randint(100, 1000) * 100,
                    'entry_price': np.random.uniform(10000, 100000),
                    'exit_price': 0,
                    'pnl': average_win if is_win else average_loss,
                    'pnl_percent': (average_win if is_win else average_loss) * 100,
                    'holding_days': np.random.randint(1, 30)
                }
                trade['exit_price'] = trade['entry_price'] * (1 + trade['pnl'])
                trades_history.append(trade)
            
            # 결과 딕셔너리 생성
            metrics = {
                'total_return': total_return,
                'annual_return': annual_return,
                'volatility': actual_volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'calmar_ratio': annual_return / max_drawdown if max_drawdown > 0 else 0,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'average_win': average_win,
                'average_loss': average_loss,
                'largest_win': average_win * 2.5,
                'largest_loss': average_loss * 2.0,
                'consecutive_wins': np.random.randint(3, 8),
                'consecutive_losses': np.random.randint(2, 6),
                'monthly_returns': monthly_returns,
                'yearly_returns': [total_return],  # 1년 가정
                'equity_curve': equity_curve,
                'trades_history': trades_history,
                'positions_history': []
            }
            
            return True, metrics, ""
            
        except Exception as e:
            return False, None, f"더미 백테스트 실행 실패: {e}"
    
    def _calculate_parameter_effect(self, parameters: Dict[str, Any], strategy_name: str) -> float:
        """파라미터가 성과에 미치는 영향 계산"""
        effect = 0.0
        
        if strategy_name.lower() == "momentum":
            # RSI 파라미터 효과
            rsi_period = parameters.get('rsi_period', 14)
            if 10 <= rsi_period <= 20:
                effect += 0.1
            
            rsi_lower = parameters.get('rsi_lower', 30)
            rsi_upper = parameters.get('rsi_upper', 70)
            rsi_spread = rsi_upper - rsi_lower
            if 30 <= rsi_spread <= 50:
                effect += 0.05
            
            # 이동평균 파라미터 효과
            ma_short = parameters.get('ma_short', 5)
            ma_long = parameters.get('ma_long', 20)
            ma_ratio = ma_long / ma_short if ma_short > 0 else 1
            if 3 <= ma_ratio <= 5:
                effect += 0.08
        
        # 랜덤 노이즈 추가
        effect += np.random.uniform(-0.05, 0.05)
        
        return np.clip(effect, -0.3, 0.3)  # -30% ~ +30% 제한
    
    def _populate_result_metrics(self, result: BacktestResult, metrics: Dict[str, Any]):
        """결과 객체에 메트릭 데이터 채우기"""
        result.total_return = metrics.get('total_return', 0.0)
        result.annual_return = metrics.get('annual_return', 0.0)
        result.volatility = metrics.get('volatility', 0.0)
        result.sharpe_ratio = metrics.get('sharpe_ratio', 0.0)
        result.max_drawdown = metrics.get('max_drawdown', 0.0)
        result.calmar_ratio = metrics.get('calmar_ratio', 0.0)
        result.win_rate = metrics.get('win_rate', 0.0)
        result.profit_factor = metrics.get('profit_factor', 1.0)
        result.total_trades = metrics.get('total_trades', 0)
        result.winning_trades = metrics.get('winning_trades', 0)
        result.losing_trades = metrics.get('losing_trades', 0)
        result.average_win = metrics.get('average_win', 0.0)
        result.average_loss = metrics.get('average_loss', 0.0)
        result.largest_win = metrics.get('largest_win', 0.0)
        result.largest_loss = metrics.get('largest_loss', 0.0)
        result.consecutive_wins = metrics.get('consecutive_wins', 0)
        result.consecutive_losses = metrics.get('consecutive_losses', 0)
        result.monthly_returns = metrics.get('monthly_returns', [])
        result.yearly_returns = metrics.get('yearly_returns', [])
        result.equity_curve = metrics.get('equity_curve', [])
        result.positions_history = metrics.get('positions_history', [])
        result.trades_history = metrics.get('trades_history', [])
    
    def _save_backtest_result(self, result: BacktestResult):
        """백테스트 결과 저장"""
        try:
            result_file = self._results_dir / f"{result.backtest_id}.json"
            
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2, default=str)
            
            result.result_file = str(result_file)
            self._logger.debug(f"백테스트 결과 저장: {result_file}")
                
        except Exception as e:
            self._logger.error(f"백테스트 결과 저장 실패: {e}", exc_info=True)
    
    def get_backtest_status(self, backtest_id: str) -> Optional[BacktestStatus]:
        """백테스트 상태 조회"""
        if backtest_id in self._running_backtests:
            return self._running_backtests[backtest_id].status
        
        for result in self._backtest_history:
            if result.backtest_id == backtest_id:
                return result.status
        
        return None
    
    def get_backtest_result(self, backtest_id: str) -> Optional[BacktestResult]:
        """백테스트 결과 조회"""
        # 실행 중인 백테스트 확인
        if backtest_id in self._running_backtests:
            return self._running_backtests[backtest_id]
        
        # 히스토리에서 검색
        for result in self._backtest_history:
            if result.backtest_id == backtest_id:
                return result
        
        # 파일에서 로드 시도
        try:
            result_file = self._results_dir / f"{backtest_id}.json"
            if result_file.exists():
                with open(result_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # BacktestResult 객체로 복원
                return self._dict_to_backtest_result(data)
        except Exception as e:
            self._logger.error(f"백테스트 결과 로드 실패 [{backtest_id}]: {e}", exc_info=True)
        
        return None
    
    def _dict_to_backtest_result(self, data: Dict[str, Any]) -> BacktestResult:
        """딕셔너리에서 BacktestResult 객체로 변환"""
        # datetime 변환
        data['start_time'] = datetime.fromisoformat(data['start_time'])
        if data.get('end_time'):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        
        # Enum 변환
        data['status'] = BacktestStatus(data['status'])
        
        # BacktestConfig 변환
        config_data = data.pop('config')
        data['config'] = BacktestConfig(**config_data)
        
        return BacktestResult(**data)
    
    def cancel_backtest(self, backtest_id: str) -> bool:
        """백테스트 취소"""
        if backtest_id in self._running_backtests:
            result = self._running_backtests[backtest_id]
            result.status = BacktestStatus.CANCELLED
            result.end_time = datetime.now()
            result.execution_time = (result.end_time - result.start_time).total_seconds()
            
            # 히스토리로 이동
            del self._running_backtests[backtest_id]
            self._backtest_history.append(result)
            
            self._logger.info(f"백테스트 취소: {backtest_id}")
            return True
        
        return False
    
    def get_running_backtests(self) -> List[BacktestResult]:
        """실행 중인 백테스트 목록"""
        return list(self._running_backtests.values())
    
    def get_backtest_history(self, limit: int = 50) -> List[BacktestResult]:
        """백테스트 히스토리"""
        return self._backtest_history[-limit:]
    
    def get_engine_statistics(self) -> Dict[str, Any]:
        """엔진 통계 정보"""
        return {
            'total_backtests': self._total_backtests,
            'successful_backtests': self._successful_backtests,
            'failed_backtests': self._failed_backtests,
            'success_rate': self._successful_backtests / self._total_backtests if self._total_backtests > 0 else 0,
            'running_backtests': len(self._running_backtests),
            'history_size': len(self._backtest_history),
            'data_directory': str(self._data_dir),
            'results_directory': str(self._results_dir)
        }
    
    def cleanup_old_results(self, days_old: int = 30):
        """오래된 결과 파일 정리"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            removed_count = 0
            
            for result_file in self._results_dir.glob("*.json"):
                if result_file.stat().st_mtime < cutoff_date.timestamp():
                    result_file.unlink()
                    removed_count += 1
            
            self._logger.info(f"오래된 백테스트 결과 {removed_count}개 파일 정리 완료")
            return removed_count
            
        except Exception as e:
            self._logger.error(f"결과 파일 정리 실패: {e}", exc_info=True)
            return 0 