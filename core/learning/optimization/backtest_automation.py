"""
백테스트 자동화 시스템

전략 변경 시 자동으로 백테스트를 실행하고 검증하는 시스템
"""

import numpy as np
import pandas as pd
import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import subprocess

from ...utils.logging import get_logger
from .parameter_manager import ParameterManager, ParameterSet

logger = get_logger(__name__)

class BacktestStatus(Enum):
    """백테스트 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ValidationStatus(Enum):
    """검증 상태"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"

@dataclass
class BacktestConfig:
    """백테스트 설정"""
    start_date: str = "2023-01-01"      # 백테스트 시작일
    end_date: str = "2024-01-01"        # 백테스트 종료일
    initial_capital: float = 10000000   # 초기 자본 (1천만원)
    commission: float = 0.0015          # 수수료 (0.15%)
    max_positions: int = 20             # 최대 포지션 수
    timeout_seconds: int = 300          # 타임아웃 (5분)
    parallel_execution: bool = True     # 병렬 실행 여부

@dataclass
class ValidationCriteria:
    """검증 기준"""
    min_sharpe_ratio: float = 1.0       # 최소 샤프 비율
    min_annual_return: float = 0.15     # 최소 연간 수익률 (15%)
    max_drawdown: float = 0.20          # 최대 낙폭 (20%)
    min_win_rate: float = 0.40          # 최소 승률 (40%)
    min_profit_factor: float = 1.2      # 최소 수익 팩터
    min_trades: int = 50                # 최소 거래 횟수
    max_consecutive_losses: int = 10    # 최대 연속 손실 횟수

@dataclass
class BacktestResult:
    """백테스트 결과"""
    backtest_id: str
    strategy_name: str
    parameters: Dict[str, Any]
    status: BacktestStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_time: Optional[float] = None
    
    # 성과 지표
    total_return: Optional[float] = None
    annual_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
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
    
    # 추가 정보
    error_message: Optional[str] = None
    log_file: Optional[str] = None
    result_file: Optional[str] = None

@dataclass
class ValidationResult:
    """검증 결과"""
    validation_id: str
    backtest_result: BacktestResult
    criteria: ValidationCriteria
    status: ValidationStatus
    validation_time: datetime
    passed_checks: List[str]
    failed_checks: List[str]
    warnings: List[str]
    overall_score: float
    recommendation: str

class BacktestEngine:
    """백테스트 엔진"""
    
    def __init__(self, backtest_script_path: str = "hantu_backtest/main.py",
                 data_dir: str = "data/backtest_automation"):
        """
        초기화
        
        Args:
            backtest_script_path: 백테스트 스크립트 경로
            data_dir: 백테스트 데이터 저장 디렉토리
        """
        self._logger = logger
        self._backtest_script_path = backtest_script_path
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 실행 중인 백테스트 관리
        self._running_backtests = {}
        self._backtest_history = []
        
        self._logger.info("백테스트 엔진 초기화 완료")
    
    def run_backtest(self, strategy_name: str, parameters: Dict[str, Any],
                    config: BacktestConfig = None) -> BacktestResult:
        """
        백테스트 실행
        
        Args:
            strategy_name: 전략명
            parameters: 전략 파라미터
            config: 백테스트 설정
        
        Returns:
            BacktestResult: 백테스트 결과
        """
        if config is None:
            config = BacktestConfig()
        
        # 백테스트 ID 생성
        backtest_id = f"{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 백테스트 결과 객체 생성
        result = BacktestResult(
            backtest_id=backtest_id,
            strategy_name=strategy_name,
            parameters=parameters,
            status=BacktestStatus.PENDING,
            start_time=datetime.now()
        )
        
        try:
            self._logger.info(f"백테스트 시작: {backtest_id}")
            result.status = BacktestStatus.RUNNING
            self._running_backtests[backtest_id] = result
            
            # 파라미터 파일 생성
            param_file = self._create_parameter_file(backtest_id, parameters, config)
            
            # 백테스트 실행
            if self._backtest_script_path.endswith('.py'):
                success, output, error = self._run_python_backtest(param_file, config)
            else:
                success, output, error = self._run_external_backtest(param_file, config)
            
            # 결과 처리
            result.end_time = datetime.now()
            result.execution_time = (result.end_time - result.start_time).total_seconds()
            
            if success:
                # 결과 파일 파싱
                self._parse_backtest_results(result, output)
                result.status = BacktestStatus.COMPLETED
                self._logger.info(f"백테스트 완료: {backtest_id} - 수익률: {result.total_return:.2%}")
            else:
                result.status = BacktestStatus.FAILED
                result.error_message = error
                self._logger.error(f"백테스트 실패: {backtest_id} - {error}")
            
        except Exception as e:
            result.status = BacktestStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.now()
            result.execution_time = (result.end_time - result.start_time).total_seconds()
            self._logger.error(f"백테스트 예외 발생: {backtest_id} - {e}")
        
        finally:
            # 실행 중 목록에서 제거
            if backtest_id in self._running_backtests:
                del self._running_backtests[backtest_id]
            
            # 히스토리에 추가
            self._backtest_history.append(result)
            
            # 결과 저장
            self._save_backtest_result(result)
        
        return result
    
    def _create_parameter_file(self, backtest_id: str, parameters: Dict[str, Any],
                              config: BacktestConfig) -> str:
        """파라미터 파일 생성"""
        param_data = {
            "backtest_id": backtest_id,
            "parameters": parameters,
            "config": asdict(config),
            "timestamp": datetime.now().isoformat()
        }
        
        param_file = os.path.join(self._data_dir, f"{backtest_id}_params.json")
        with open(param_file, 'w', encoding='utf-8') as f:
            json.dump(param_data, f, ensure_ascii=False, indent=2, default=str)
        
        return param_file
    
    def _run_python_backtest(self, param_file: str, config: BacktestConfig) -> Tuple[bool, str, str]:
        """Python 백테스트 실행"""
        try:
            cmd = [
                "python", self._backtest_script_path,
                "--config", param_file,
                "--output-dir", self._data_dir
            ]
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds
            )
            
            success = process.returncode == 0
            output = process.stdout
            error = process.stderr
            
            return success, output, error
            
        except subprocess.TimeoutExpired:
            return False, "", "백테스트 타임아웃"
        except Exception as e:
            return False, "", f"백테스트 실행 실패: {e}"
    
    def _run_external_backtest(self, param_file: str, config: BacktestConfig) -> Tuple[bool, str, str]:
        """외부 백테스트 도구 실행"""
        try:
            cmd = [
                self._backtest_script_path,
                "--config", param_file,
                "--output-dir", self._data_dir
            ]
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds
            )
            
            success = process.returncode == 0
            output = process.stdout
            error = process.stderr
            
            return success, output, error
            
        except subprocess.TimeoutExpired:
            return False, "", "백테스트 타임아웃"
        except Exception as e:
            return False, "", f"백테스트 실행 실패: {e}"
    
    def _parse_backtest_results(self, result: BacktestResult, output: str):
        """백테스트 결과 파싱"""
        try:
            # 결과 파일 경로 생성
            result_file = os.path.join(self._data_dir, f"{result.backtest_id}_results.json")
            
            if os.path.exists(result_file):
                # JSON 결과 파일에서 로드
                with open(result_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 성과 지표 추출
                result.total_return = data.get('total_return', 0.0)
                result.annual_return = data.get('annual_return', 0.0)
                result.sharpe_ratio = data.get('sharpe_ratio', 0.0)
                result.max_drawdown = data.get('max_drawdown', 0.0)
                result.win_rate = data.get('win_rate', 0.0)
                result.profit_factor = data.get('profit_factor', 1.0)
                result.total_trades = data.get('total_trades', 0)
                result.winning_trades = data.get('winning_trades', 0)
                result.losing_trades = data.get('losing_trades', 0)
                result.average_win = data.get('average_win', 0.0)
                result.average_loss = data.get('average_loss', 0.0)
                result.largest_win = data.get('largest_win', 0.0)
                result.largest_loss = data.get('largest_loss', 0.0)
                result.consecutive_wins = data.get('consecutive_wins', 0)
                result.consecutive_losses = data.get('consecutive_losses', 0)
                
                result.result_file = result_file
                
            else:
                # 출력에서 간단한 파싱 시도
                self._parse_output_text(result, output)
                
        except Exception as e:
            self._logger.error(f"백테스트 결과 파싱 실패: {e}")
            # 기본값 설정
            result.total_return = 0.0
            result.annual_return = 0.0
            result.sharpe_ratio = 0.0
    
    def _parse_output_text(self, result: BacktestResult, output: str):
        """텍스트 출력에서 결과 파싱"""
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip().lower()
            
            if 'total return' in line or '총수익률' in line:
                try:
                    value = float(line.split(':')[-1].strip().replace('%', '')) / 100
                    result.total_return = value
                except:
                    pass
            
            elif 'sharpe' in line or '샤프' in line:
                try:
                    value = float(line.split(':')[-1].strip())
                    result.sharpe_ratio = value
                except:
                    pass
            
            elif 'drawdown' in line or '낙폭' in line:
                try:
                    value = abs(float(line.split(':')[-1].strip().replace('%', ''))) / 100
                    result.max_drawdown = value
                except:
                    pass
        
        # 연간 수익률 추정 (간단한 계산)
        if result.total_return:
            result.annual_return = result.total_return  # 1년 가정
    
    def get_backtest_status(self, backtest_id: str) -> Optional[BacktestStatus]:
        """백테스트 상태 조회"""
        if backtest_id in self._running_backtests:
            return self._running_backtests[backtest_id].status
        
        for result in self._backtest_history:
            if result.backtest_id == backtest_id:
                return result.status
        
        return None
    
    def cancel_backtest(self, backtest_id: str) -> bool:
        """백테스트 취소"""
        if backtest_id in self._running_backtests:
            self._running_backtests[backtest_id].status = BacktestStatus.CANCELLED
            # 실제 프로세스 종료는 구현 복잡성으로 인해 생략
            self._logger.info(f"백테스트 취소 요청: {backtest_id}")
            return True
        
        return False
    
    def _save_backtest_result(self, result: BacktestResult):
        """백테스트 결과 저장"""
        try:
            result_file = os.path.join(self._data_dir, f"{result.backtest_id}_backtest.json")
            
            # datetime 객체 처리
            result_dict = asdict(result)
            result_dict['start_time'] = result.start_time.isoformat()
            if result.end_time:
                result_dict['end_time'] = result.end_time.isoformat()
            result_dict['status'] = result.status.value
            
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result_dict, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            self._logger.error(f"백테스트 결과 저장 실패: {e}")

class ValidationSystem:
    """검증 시스템"""
    
    def __init__(self, criteria: ValidationCriteria = None):
        """
        초기화
        
        Args:
            criteria: 검증 기준
        """
        self._logger = logger
        self._criteria = criteria or ValidationCriteria()
        self._validation_history = []
        
        self._logger.info("검증 시스템 초기화 완료")
    
    def validate_backtest(self, backtest_result: BacktestResult) -> ValidationResult:
        """
        백테스트 결과 검증
        
        Args:
            backtest_result: 백테스트 결과
        
        Returns:
            ValidationResult: 검증 결과
        """
        validation_id = f"val_{backtest_result.backtest_id}_{datetime.now().strftime('%H%M%S')}"
        
        passed_checks = []
        failed_checks = []
        warnings = []
        
        # 각 기준별 검증
        checks = [
            ("샤프 비율", backtest_result.sharpe_ratio, self._criteria.min_sharpe_ratio, ">="),
            ("연간 수익률", backtest_result.annual_return, self._criteria.min_annual_return, ">="),
            ("최대 낙폭", backtest_result.max_drawdown, self._criteria.max_drawdown, "<="),
            ("승률", backtest_result.win_rate, self._criteria.min_win_rate, ">="),
            ("수익 팩터", backtest_result.profit_factor, self._criteria.min_profit_factor, ">="),
            ("거래 횟수", backtest_result.total_trades, self._criteria.min_trades, ">="),
            ("최대 연속 손실", backtest_result.consecutive_losses, self._criteria.max_consecutive_losses, "<=")
        ]
        
        for check_name, actual, expected, operator in checks:
            if actual is None:
                warnings.append(f"{check_name} 데이터 없음")
                continue
            
            if operator == ">=" and actual >= expected:
                passed_checks.append(f"{check_name}: {actual:.3f} >= {expected:.3f}")
            elif operator == "<=" and actual <= expected:
                passed_checks.append(f"{check_name}: {actual:.3f} <= {expected:.3f}")
            else:
                failed_checks.append(f"{check_name}: {actual:.3f} (기준: {operator} {expected:.3f})")
        
        # 전체 점수 계산
        total_checks = len(checks)
        passed_count = len(passed_checks)
        overall_score = passed_count / total_checks if total_checks > 0 else 0.0
        
        # 검증 상태 결정
        if len(failed_checks) == 0:
            status = ValidationStatus.PASSED
        elif overall_score >= 0.7:  # 70% 이상 통과
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.FAILED
        
        # 추천사항 생성
        recommendation = self._generate_recommendation(
            backtest_result, passed_checks, failed_checks, warnings, overall_score
        )
        
        # 검증 결과 생성
        validation_result = ValidationResult(
            validation_id=validation_id,
            backtest_result=backtest_result,
            criteria=self._criteria,
            status=status,
            validation_time=datetime.now(),
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            warnings=warnings,
            overall_score=overall_score,
            recommendation=recommendation
        )
        
        # 히스토리에 추가
        self._validation_history.append(validation_result)
        
        self._logger.info(f"검증 완료: {validation_id} - {status.value} (점수: {overall_score:.1%})")
        return validation_result
    
    def _generate_recommendation(self, backtest_result: BacktestResult,
                               passed_checks: List[str], failed_checks: List[str],
                               warnings: List[str], overall_score: float) -> str:
        """추천사항 생성"""
        recommendations = []
        
        if overall_score >= 0.9:
            recommendations.append("✅ 우수한 성과! 실전 적용을 검토해보세요.")
        elif overall_score >= 0.7:
            recommendations.append("⚠️ 양호한 성과이지만 일부 개선이 필요합니다.")
        else:
            recommendations.append("❌ 기준 미달. 전략 재검토가 필요합니다.")
        
        # 구체적인 개선사항
        if backtest_result.sharpe_ratio and backtest_result.sharpe_ratio < self._criteria.min_sharpe_ratio:
            recommendations.append("• 샤프 비율 개선: 리스크 대비 수익률을 높여야 합니다.")
        
        if backtest_result.max_drawdown and backtest_result.max_drawdown > self._criteria.max_drawdown:
            recommendations.append("• 낙폭 관리: 손절 전략을 강화하세요.")
        
        if backtest_result.win_rate and backtest_result.win_rate < self._criteria.min_win_rate:
            recommendations.append("• 승률 개선: 진입 조건을 더 엄격하게 설정하세요.")
        
        if backtest_result.total_trades and backtest_result.total_trades < self._criteria.min_trades:
            recommendations.append("• 거래 빈도: 더 많은 기회를 포착할 수 있는 전략이 필요합니다.")
        
        return "\n".join(recommendations)

class AutomationManager:
    """자동화 관리자"""
    
    def __init__(self, backtest_engine: BacktestEngine,
                 validation_system: ValidationSystem,
                 parameter_manager: ParameterManager):
        """
        초기화
        
        Args:
            backtest_engine: 백테스트 엔진
            validation_system: 검증 시스템
            parameter_manager: 파라미터 관리자
        """
        self._logger = logger
        self._backtest_engine = backtest_engine
        self._validation_system = validation_system
        self._parameter_manager = parameter_manager
        
        # 자동화 설정
        self._automation_enabled = False
        self._automation_thread = None
        self._stop_automation = threading.Event()
        
        # 자동화 규칙
        self._automation_rules = []
        
        self._logger.info("자동화 관리자 초기화 완료")
    
    def add_automation_rule(self, strategy_name: str, trigger_condition: str,
                           auto_validate: bool = True, auto_apply: bool = False):
        """자동화 규칙 추가"""
        rule = {
            'strategy_name': strategy_name,
            'trigger_condition': trigger_condition,
            'auto_validate': auto_validate,
            'auto_apply': auto_apply,
            'created_at': datetime.now()
        }
        
        self._automation_rules.append(rule)
        self._logger.info(f"자동화 규칙 추가: {strategy_name} - {trigger_condition}")
    
    def start_automation(self):
        """자동화 시작"""
        if self._automation_enabled:
            self._logger.warning("자동화가 이미 실행 중입니다")
            return
        
        self._automation_enabled = True
        self._stop_automation.clear()
        self._automation_thread = threading.Thread(target=self._automation_loop)
        self._automation_thread.start()
        
        self._logger.info("백테스트 자동화 시작")
    
    def stop_automation(self):
        """자동화 중지"""
        if not self._automation_enabled:
            return
        
        self._automation_enabled = False
        self._stop_automation.set()
        
        if self._automation_thread:
            self._automation_thread.join()
        
        self._logger.info("백테스트 자동화 중지")
    
    def _automation_loop(self):
        """자동화 루프"""
        while self._automation_enabled and not self._stop_automation.is_set():
            try:
                # 새로운 파라미터 세트 확인
                self._check_for_new_parameters()
                
                # 일정 시간 대기
                self._stop_automation.wait(60)  # 1분 대기
                
            except Exception as e:
                self._logger.error(f"자동화 루프 오류: {e}")
                time.sleep(60)
    
    def _check_for_new_parameters(self):
        """새로운 파라미터 세트 확인"""
        # 최근 추가된 파라미터 세트들을 확인하고 백테스트 실행
        # 실제 구현에서는 파라미터 매니저의 변경 이벤트를 구독하는 방식이 더 효율적
        pass
    
    def run_automated_backtest(self, strategy_name: str, parameter_set: ParameterSet) -> Dict[str, Any]:
        """자동 백테스트 실행"""
        try:
            # 백테스트 실행
            backtest_result = self._backtest_engine.run_backtest(
                strategy_name, parameter_set.parameters
            )
            
            # 검증 실행
            validation_result = self._validation_system.validate_backtest(backtest_result)
            
            # 결과 요약
            automation_result = {
                'strategy_name': strategy_name,
                'parameter_set_id': id(parameter_set),
                'backtest_result': backtest_result,
                'validation_result': validation_result,
                'automation_time': datetime.now(),
                'auto_approved': validation_result.status == ValidationStatus.PASSED
            }
            
            # 자동 승인 조건 확인
            if automation_result['auto_approved']:
                self._logger.info(f"자동 승인: {strategy_name} - 검증 통과")
                # 실제로는 파라미터를 프로덕션에 적용하는 로직 추가
            
            return automation_result
            
        except Exception as e:
            self._logger.error(f"자동 백테스트 실행 실패: {e}")
            return {
                'error': str(e),
                'automation_time': datetime.now()
            }
    
    def get_automation_summary(self) -> Dict[str, Any]:
        """자동화 요약 정보"""
        return {
            'automation_enabled': self._automation_enabled,
            'total_rules': len(self._automation_rules),
            'active_rules': len([r for r in self._automation_rules if r.get('enabled', True)]),
            'running_backtests': len(self._backtest_engine._running_backtests),
            'recent_validations': len(self._validation_system._validation_history[-10:])
        }

# 전역 인스턴스들
_backtest_engine = None
_validation_system = None
_automation_manager = None

def get_backtest_automation_system(parameter_manager: ParameterManager = None):
    """백테스트 자동화 시스템 반환"""
    global _backtest_engine, _validation_system, _automation_manager
    
    if _backtest_engine is None:
        _backtest_engine = BacktestEngine()
    
    if _validation_system is None:
        _validation_system = ValidationSystem()
    
    if _automation_manager is None and parameter_manager:
        _automation_manager = AutomationManager(
            _backtest_engine, _validation_system, parameter_manager
        )
    
    return {
        'backtest_engine': _backtest_engine,
        'validation_system': _validation_system,
        'automation_manager': _automation_manager
    } 