"""
백테스트 결과 검증 시스템

백테스트 결과의 품질을 평가하고 실전 적용 가능성을 검증
"""

import numpy as np
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from ...utils.logging import get_logger
from .backtest_engine import BacktestResult

logger = get_logger(__name__)

class ValidationStatus(Enum):
    """검증 상태"""
    PASSED = "passed"           # 검증 통과
    FAILED = "failed"           # 검증 실패
    WARNING = "warning"         # 경고 (조건부 통과)
    PENDING = "pending"         # 검증 대기

class ValidationLevel(Enum):
    """검증 수준"""
    STRICT = "strict"           # 엄격한 기준
    MODERATE = "moderate"       # 보통 기준
    LENIENT = "lenient"         # 관대한 기준

@dataclass
class ValidationCriteria:
    """검증 기준"""
    # 수익성 기준
    min_total_return: float = 0.10          # 최소 총 수익률 (10%)
    min_annual_return: float = 0.15         # 최소 연간 수익률 (15%)
    min_sharpe_ratio: float = 1.0           # 최소 샤프 비율
    min_calmar_ratio: float = 0.5           # 최소 칼마 비율
    
    # 리스크 기준
    max_drawdown: float = 0.20              # 최대 낙폭 (20%)
    max_volatility: float = 0.25            # 최대 변동성 (25%)
    max_consecutive_losses: int = 10        # 최대 연속 손실 횟수
    
    # 거래 기준
    min_win_rate: float = 0.40              # 최소 승률 (40%)
    min_profit_factor: float = 1.2          # 최소 수익 팩터
    min_trades: int = 50                    # 최소 거래 횟수
    max_avg_trade_duration: int = 30        # 최대 평균 거래 기간 (일)
    
    # 안정성 기준
    min_monthly_positive_ratio: float = 0.6 # 최소 월별 양수 수익률 비율 (60%)
    max_single_trade_impact: float = 0.05   # 최대 단일 거래 영향 (5%)
    min_diversification_score: float = 0.7  # 최소 다양화 점수
    
    # 통계적 유의성
    min_t_statistic: float = 2.0            # 최소 t-통계량
    max_p_value: float = 0.05               # 최대 p-값
    
    # 기타
    validation_level: ValidationLevel = ValidationLevel.MODERATE
    allow_warnings: bool = True             # 경고 허용 여부
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        result = asdict(self)
        result['validation_level'] = self.validation_level.value
        return result
    
    @classmethod
    def create_strict_criteria(cls) -> 'ValidationCriteria':
        """엄격한 검증 기준 생성"""
        return cls(
            min_total_return=0.15,
            min_annual_return=0.20,
            min_sharpe_ratio=1.5,
            min_calmar_ratio=0.8,
            max_drawdown=0.15,
            max_volatility=0.20,
            max_consecutive_losses=7,
            min_win_rate=0.50,
            min_profit_factor=1.5,
            min_trades=100,
            min_monthly_positive_ratio=0.7,
            validation_level=ValidationLevel.STRICT,
            allow_warnings=False
        )
    
    @classmethod
    def create_lenient_criteria(cls) -> 'ValidationCriteria':
        """관대한 검증 기준 생성"""
        return cls(
            min_total_return=0.05,
            min_annual_return=0.08,
            min_sharpe_ratio=0.5,
            min_calmar_ratio=0.3,
            max_drawdown=0.30,
            max_volatility=0.35,
            max_consecutive_losses=15,
            min_win_rate=0.35,
            min_profit_factor=1.0,
            min_trades=30,
            min_monthly_positive_ratio=0.5,
            validation_level=ValidationLevel.LENIENT,
            allow_warnings=True
        )

@dataclass
class ValidationCheck:
    """개별 검증 항목"""
    name: str                               # 검증 항목명
    description: str                        # 설명
    expected_value: Any                     # 기대값
    actual_value: Any                       # 실제값
    operator: str                           # 연산자 (>=, <=, ==)
    passed: bool                            # 통과 여부
    score: float                            # 점수 (0.0-1.0)
    weight: float = 1.0                     # 가중치
    is_critical: bool = False               # 필수 항목 여부
    message: str = ""                       # 메시지

@dataclass
class ValidationResult:
    """검증 결과"""
    validation_id: str
    backtest_result: BacktestResult
    criteria: ValidationCriteria
    status: ValidationStatus
    validation_time: datetime
    
    # 검증 상세 결과
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0
    critical_failures: int = 0
    
    # 점수 및 평가
    overall_score: float = 0.0              # 전체 점수 (0.0-1.0)
    performance_score: float = 0.0          # 성과 점수
    risk_score: float = 0.0                 # 리스크 점수
    reliability_score: float = 0.0          # 신뢰도 점수
    
    # 상세 검증 결과
    validation_checks: List[ValidationCheck] = None
    
    # 추천사항 및 분석
    recommendation: str = ""
    risk_assessment: str = ""
    improvement_suggestions: List[str] = None
    
    # 추가 메타데이터
    validation_duration: Optional[float] = None
    result_file: Optional[str] = None
    
    def __post_init__(self):
        if self.validation_checks is None:
            self.validation_checks = []
        if self.improvement_suggestions is None:
            self.improvement_suggestions = []
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        result_dict = asdict(self)
        
        # Enum 처리
        result_dict['status'] = self.status.value
        result_dict['validation_time'] = self.validation_time.isoformat()
        
        # BacktestResult와 ValidationCriteria는 별도 처리
        result_dict['backtest_result'] = self.backtest_result.to_dict()
        result_dict['criteria'] = self.criteria.to_dict()
        
        return result_dict

class ValidationSystem:
    """백테스트 검증 시스템"""
    
    def __init__(self, 
                 default_criteria: Optional[ValidationCriteria] = None,
                 results_dir: str = "data/validation_results"):
        """
        초기화
        
        Args:
            default_criteria: 기본 검증 기준
            results_dir: 검증 결과 저장 디렉토리
        """
        self._logger = logger
        self._default_criteria = default_criteria or ValidationCriteria()
        self._results_dir = Path(results_dir)
        
        # 디렉토리 생성
        self._results_dir.mkdir(parents=True, exist_ok=True)
        
        # 검증 히스토리
        self._validation_history: List[ValidationResult] = []
        
        # 통계
        self._total_validations = 0
        self._passed_validations = 0
        self._failed_validations = 0
        self._warning_validations = 0
        
        self._logger.info("백테스트 검증 시스템 초기화 완료")
    
    def validate_backtest(self, 
                         backtest_result: BacktestResult,
                         criteria: Optional[ValidationCriteria] = None) -> ValidationResult:
        """
        백테스트 결과 검증
        
        Args:
            backtest_result: 백테스트 결과
            criteria: 검증 기준 (None이면 기본 기준 사용)
        
        Returns:
            ValidationResult: 검증 결과
        """
        if criteria is None:
            criteria = self._default_criteria
        
        start_time = datetime.now()
        validation_id = f"val_{backtest_result.backtest_id}_{start_time.strftime('%H%M%S')}"
        
        self._logger.info(f"백테스트 검증 시작: {validation_id}")
        self._total_validations += 1
        
        # 검증 결과 객체 생성
        validation_result = ValidationResult(
            validation_id=validation_id,
            backtest_result=backtest_result,
            criteria=criteria,
            status=ValidationStatus.PENDING,
            validation_time=start_time
        )
        
        try:
            # 개별 검증 수행
            self._perform_validation_checks(validation_result)
            
            # 전체 평가 계산
            self._calculate_overall_assessment(validation_result)
            
            # 추천사항 생성
            self._generate_recommendations(validation_result)
            
            # 최종 상태 결정
            self._determine_final_status(validation_result)
            
            # 검증 완료
            end_time = datetime.now()
            validation_result.validation_duration = (end_time - start_time).total_seconds()
            
            # 통계 업데이트
            if validation_result.status == ValidationStatus.PASSED:
                self._passed_validations += 1
            elif validation_result.status == ValidationStatus.FAILED:
                self._failed_validations += 1
            elif validation_result.status == ValidationStatus.WARNING:
                self._warning_validations += 1
            
            self._logger.info(
                f"백테스트 검증 완료: {validation_id} - "
                f"{validation_result.status.value} (점수: {validation_result.overall_score:.2f})"
            )
            
        except Exception as e:
            validation_result.status = ValidationStatus.FAILED
            validation_result.recommendation = f"검증 중 오류 발생: {e}"
            self._failed_validations += 1
            self._logger.error(f"백테스트 검증 실패: {validation_id} - {e}", exc_info=True)
        
        finally:
            # 히스토리에 추가
            self._validation_history.append(validation_result)
            
            # 결과 저장
            self._save_validation_result(validation_result)
        
        return validation_result
    
    def _perform_validation_checks(self, validation_result: ValidationResult):
        """개별 검증 수행"""
        result = validation_result.backtest_result
        criteria = validation_result.criteria
        checks = []
        
        # 1. 수익성 검증
        checks.extend(self._check_profitability(result, criteria))
        
        # 2. 리스크 검증
        checks.extend(self._check_risk_metrics(result, criteria))
        
        # 3. 거래 품질 검증
        checks.extend(self._check_trading_quality(result, criteria))
        
        # 4. 안정성 검증
        checks.extend(self._check_stability(result, criteria))
        
        # 5. 통계적 유의성 검증
        checks.extend(self._check_statistical_significance(result, criteria))
        
        # 검증 결과 집계
        validation_result.validation_checks = checks
        validation_result.total_checks = len(checks)
        validation_result.passed_checks = sum(1 for c in checks if c.passed)
        validation_result.failed_checks = validation_result.total_checks - validation_result.passed_checks
        validation_result.critical_failures = sum(1 for c in checks if not c.passed and c.is_critical)
    
    def _check_profitability(self, result: BacktestResult, criteria: ValidationCriteria) -> List[ValidationCheck]:
        """수익성 검증"""
        checks = []
        
        # 총 수익률 검증
        checks.append(ValidationCheck(
            name="총 수익률",
            description="백테스트 기간 동안의 총 수익률",
            expected_value=f">= {criteria.min_total_return:.1%}",
            actual_value=f"{result.total_return:.1%}" if result.total_return is not None else "N/A",
            operator=">=",
            passed=result.total_return is not None and result.total_return >= criteria.min_total_return,
            score=min(result.total_return / criteria.min_total_return, 2.0) if result.total_return is not None else 0.0,
            weight=2.0,
            is_critical=True
        ))
        
        # 연간 수익률 검증
        checks.append(ValidationCheck(
            name="연간 수익률",
            description="연간화된 수익률",
            expected_value=f">= {criteria.min_annual_return:.1%}",
            actual_value=f"{result.annual_return:.1%}" if result.annual_return is not None else "N/A",
            operator=">=",
            passed=result.annual_return is not None and result.annual_return >= criteria.min_annual_return,
            score=min(result.annual_return / criteria.min_annual_return, 2.0) if result.annual_return is not None else 0.0,
            weight=2.0,
            is_critical=True
        ))
        
        # 샤프 비율 검증
        checks.append(ValidationCheck(
            name="샤프 비율",
            description="위험 대비 수익률",
            expected_value=f">= {criteria.min_sharpe_ratio:.2f}",
            actual_value=f"{result.sharpe_ratio:.2f}" if result.sharpe_ratio is not None else "N/A",
            operator=">=",
            passed=result.sharpe_ratio is not None and result.sharpe_ratio >= criteria.min_sharpe_ratio,
            score=min(result.sharpe_ratio / criteria.min_sharpe_ratio, 2.0) if result.sharpe_ratio is not None else 0.0,
            weight=1.5,
            is_critical=True
        ))
        
        # 칼마 비율 검증
        if result.calmar_ratio is not None:
            checks.append(ValidationCheck(
                name="칼마 비율",
                description="연간 수익률 대비 최대 낙폭",
                expected_value=f">= {criteria.min_calmar_ratio:.2f}",
                actual_value=f"{result.calmar_ratio:.2f}",
                operator=">=",
                passed=result.calmar_ratio >= criteria.min_calmar_ratio,
                score=min(result.calmar_ratio / criteria.min_calmar_ratio, 2.0),
                weight=1.0
            ))
        
        return checks
    
    def _check_risk_metrics(self, result: BacktestResult, criteria: ValidationCriteria) -> List[ValidationCheck]:
        """리스크 지표 검증"""
        checks = []
        
        # 최대 낙폭 검증
        checks.append(ValidationCheck(
            name="최대 낙폭",
            description="포트폴리오 최대 손실폭",
            expected_value=f"<= {criteria.max_drawdown:.1%}",
            actual_value=f"{result.max_drawdown:.1%}" if result.max_drawdown is not None else "N/A",
            operator="<=",
            passed=result.max_drawdown is not None and result.max_drawdown <= criteria.max_drawdown,
            score=max(0, 1 - (result.max_drawdown / criteria.max_drawdown)) if result.max_drawdown is not None else 0.0,
            weight=2.0,
            is_critical=True
        ))
        
        # 변동성 검증
        if result.volatility is not None:
            checks.append(ValidationCheck(
                name="변동성",
                description="연간화된 변동성",
                expected_value=f"<= {criteria.max_volatility:.1%}",
                actual_value=f"{result.volatility:.1%}",
                operator="<=",
                passed=result.volatility <= criteria.max_volatility,
                score=max(0, 1 - (result.volatility / criteria.max_volatility)),
                weight=1.0
            ))
        
        # 연속 손실 검증
        if result.consecutive_losses is not None:
            checks.append(ValidationCheck(
                name="최대 연속 손실",
                description="연속 손실 거래 횟수",
                expected_value=f"<= {criteria.max_consecutive_losses}",
                actual_value=str(result.consecutive_losses),
                operator="<=",
                passed=result.consecutive_losses <= criteria.max_consecutive_losses,
                score=max(0, 1 - (result.consecutive_losses / criteria.max_consecutive_losses)),
                weight=1.0
            ))
        
        return checks
    
    def _check_trading_quality(self, result: BacktestResult, criteria: ValidationCriteria) -> List[ValidationCheck]:
        """거래 품질 검증"""
        checks = []
        
        # 승률 검증
        checks.append(ValidationCheck(
            name="승률",
            description="전체 거래 중 수익 거래 비율",
            expected_value=f">= {criteria.min_win_rate:.1%}",
            actual_value=f"{result.win_rate:.1%}" if result.win_rate is not None else "N/A",
            operator=">=",
            passed=result.win_rate is not None and result.win_rate >= criteria.min_win_rate,
            score=min(result.win_rate / criteria.min_win_rate, 2.0) if result.win_rate is not None else 0.0,
            weight=1.5
        ))
        
        # 수익 팩터 검증
        checks.append(ValidationCheck(
            name="수익 팩터",
            description="총 수익 대비 총 손실",
            expected_value=f">= {criteria.min_profit_factor:.2f}",
            actual_value=f"{result.profit_factor:.2f}" if result.profit_factor is not None else "N/A",
            operator=">=",
            passed=result.profit_factor is not None and result.profit_factor >= criteria.min_profit_factor,
            score=min(result.profit_factor / criteria.min_profit_factor, 2.0) if result.profit_factor is not None else 0.0,
            weight=1.5
        ))
        
        # 거래 횟수 검증
        checks.append(ValidationCheck(
            name="거래 횟수",
            description="백테스트 기간 동안 총 거래 횟수",
            expected_value=f">= {criteria.min_trades}",
            actual_value=str(result.total_trades) if result.total_trades is not None else "N/A",
            operator=">=",
            passed=result.total_trades is not None and result.total_trades >= criteria.min_trades,
            score=min(result.total_trades / criteria.min_trades, 2.0) if result.total_trades is not None else 0.0,
            weight=1.0
        ))
        
        return checks
    
    def _check_stability(self, result: BacktestResult, criteria: ValidationCriteria) -> List[ValidationCheck]:
        """안정성 검증"""
        checks = []
        
        # 월별 양수 수익률 비율
        if result.monthly_returns:
            positive_months = sum(1 for r in result.monthly_returns if r > 0)
            positive_ratio = positive_months / len(result.monthly_returns)
            
            checks.append(ValidationCheck(
                name="월별 양수 수익률 비율",
                description="월별 수익률 중 양수인 비율",
                expected_value=f">= {criteria.min_monthly_positive_ratio:.1%}",
                actual_value=f"{positive_ratio:.1%}",
                operator=">=",
                passed=positive_ratio >= criteria.min_monthly_positive_ratio,
                score=min(positive_ratio / criteria.min_monthly_positive_ratio, 2.0),
                weight=1.0
            ))
        
        # 단일 거래 영향도 (가장 큰 거래의 영향)
        if result.largest_win is not None and result.total_return is not None:
            single_trade_impact = abs(result.largest_win) / abs(result.total_return) if result.total_return != 0 else 0
            
            checks.append(ValidationCheck(
                name="최대 단일 거래 영향",
                description="가장 큰 거래가 전체 수익에 미치는 영향",
                expected_value=f"<= {criteria.max_single_trade_impact:.1%}",
                actual_value=f"{single_trade_impact:.1%}",
                operator="<=",
                passed=single_trade_impact <= criteria.max_single_trade_impact,
                score=max(0, 1 - (single_trade_impact / criteria.max_single_trade_impact)),
                weight=1.0
            ))
        
        return checks
    
    def _check_statistical_significance(self, result: BacktestResult, criteria: ValidationCriteria) -> List[ValidationCheck]:
        """통계적 유의성 검증"""
        checks = []
        
        # 간단한 t-통계량 계산 (실제로는 더 정교한 계산 필요)
        if result.annual_return is not None and result.volatility is not None and result.total_trades is not None:
            if result.volatility > 0 and result.total_trades > 1:
                t_stat = (result.annual_return * np.sqrt(result.total_trades)) / result.volatility
                
                checks.append(ValidationCheck(
                    name="t-통계량",
                    description="수익률의 통계적 유의성",
                    expected_value=f">= {criteria.min_t_statistic:.2f}",
                    actual_value=f"{t_stat:.2f}",
                    operator=">=",
                    passed=t_stat >= criteria.min_t_statistic,
                    score=min(t_stat / criteria.min_t_statistic, 2.0),
                    weight=1.0
                ))
        
        return checks
    
    def _calculate_overall_assessment(self, validation_result: ValidationResult):
        """전체 평가 계산"""
        checks = validation_result.validation_checks
        
        if not checks:
            return
        
        # 가중 평균 점수 계산
        total_weighted_score = sum(check.score * check.weight for check in checks)
        total_weights = sum(check.weight for check in checks)
        validation_result.overall_score = total_weighted_score / total_weights if total_weights > 0 else 0.0
        
        # 카테고리별 점수 계산
        profitability_checks = [c for c in checks if c.name in ["총 수익률", "연간 수익률", "샤프 비율", "칼마 비율"]]
        risk_checks = [c for c in checks if c.name in ["최대 낙폭", "변동성", "최대 연속 손실"]]
        trading_checks = [c for c in checks if c.name in ["승률", "수익 팩터", "거래 횟수"]]
        
        validation_result.performance_score = self._calculate_category_score(profitability_checks)
        validation_result.risk_score = self._calculate_category_score(risk_checks)
        validation_result.reliability_score = self._calculate_category_score(trading_checks)
    
    def _calculate_category_score(self, checks: List[ValidationCheck]) -> float:
        """카테고리별 점수 계산"""
        if not checks:
            return 0.0
        
        total_weighted_score = sum(check.score * check.weight for check in checks)
        total_weights = sum(check.weight for check in checks)
        return total_weighted_score / total_weights if total_weights > 0 else 0.0
    
    def _generate_recommendations(self, validation_result: ValidationResult):
        """추천사항 생성"""
        result = validation_result.backtest_result
        checks = validation_result.validation_checks
        failed_checks = [c for c in checks if not c.passed]
        critical_failures = [c for c in failed_checks if c.is_critical]
        
        recommendations = []
        
        # 전체 평가
        if validation_result.overall_score >= 0.9:
            recommendations.append("✅ 우수한 백테스트 결과입니다. 실전 적용을 검토해보세요.")
        elif validation_result.overall_score >= 0.7:
            recommendations.append("⚠️ 양호한 결과이지만 일부 개선이 필요합니다.")
        else:
            recommendations.append("❌ 기준 미달입니다. 전략을 재검토하세요.")
        
        # 구체적인 개선사항
        for check in critical_failures:
            if check.name == "총 수익률":
                recommendations.append("• 수익률 개선: 더 강한 신호나 다른 진입/청산 조건을 검토하세요.")
            elif check.name == "최대 낙폭":
                recommendations.append("• 리스크 관리: 손절 전략을 강화하거나 포지션 크기를 줄이세요.")
            elif check.name == "샤프 비율":
                recommendations.append("• 위험 대비 수익: 변동성을 줄이거나 수익률을 높이는 방법을 찾으세요.")
        
        # 리스크 평가
        risk_assessment = []
        if result.max_drawdown and result.max_drawdown > 0.15:
            risk_assessment.append("높은 낙폭 위험")
        if result.consecutive_losses and result.consecutive_losses > 8:
            risk_assessment.append("연속 손실 위험")
        if result.volatility and result.volatility > 0.25:
            risk_assessment.append("높은 변동성")
        
        validation_result.recommendation = "\n".join(recommendations)
        validation_result.risk_assessment = ", ".join(risk_assessment) if risk_assessment else "낮은 리스크"
        validation_result.improvement_suggestions = [r for r in recommendations if r.startswith("•")]
    
    def _determine_final_status(self, validation_result: ValidationResult):
        """최종 상태 결정"""
        criteria = validation_result.criteria
        
        # 필수 항목 실패 시 무조건 실패
        if validation_result.critical_failures > 0:
            validation_result.status = ValidationStatus.FAILED
            return
        
        # 전체 점수 기반 판정
        if validation_result.overall_score >= 0.85:
            validation_result.status = ValidationStatus.PASSED
        elif validation_result.overall_score >= 0.70 and criteria.allow_warnings:
            validation_result.status = ValidationStatus.WARNING
        else:
            validation_result.status = ValidationStatus.FAILED
    
    def _save_validation_result(self, validation_result: ValidationResult):
        """검증 결과 저장"""
        try:
            result_file = self._results_dir / f"{validation_result.validation_id}.json"
            
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(validation_result.to_dict(), f, ensure_ascii=False, indent=2, default=str)
            
            validation_result.result_file = str(result_file)
            self._logger.debug(f"검증 결과 저장: {result_file}")
                
        except Exception as e:
            self._logger.error(f"검증 결과 저장 실패: {e}", exc_info=True)
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """검증 통계 정보"""
        return {
            'total_validations': self._total_validations,
            'passed_validations': self._passed_validations,
            'failed_validations': self._failed_validations,
            'warning_validations': self._warning_validations,
            'pass_rate': self._passed_validations / self._total_validations if self._total_validations > 0 else 0,
            'warning_rate': self._warning_validations / self._total_validations if self._total_validations > 0 else 0,
            'fail_rate': self._failed_validations / self._total_validations if self._total_validations > 0 else 0,
            'recent_validations': len(self._validation_history[-10:]),
            'results_directory': str(self._results_dir)
        }
    
    def get_validation_history(self, limit: int = 50) -> List[ValidationResult]:
        """검증 히스토리"""
        return self._validation_history[-limit:]
    
    def compare_validations(self, validation_ids: List[str]) -> Dict[str, Any]:
        """검증 결과 비교"""
        validations = []
        
        for val_id in validation_ids:
            # 히스토리에서 검색
            for val_result in self._validation_history:
                if val_result.validation_id == val_id:
                    validations.append(val_result)
                    break
        
        if len(validations) < 2:
            return {"error": "비교할 검증 결과가 부족합니다"}
        
        comparison = {
            'validation_count': len(validations),
            'overall_scores': [v.overall_score for v in validations],
            'performance_scores': [v.performance_score for v in validations],
            'risk_scores': [v.risk_score for v in validations],
            'reliability_scores': [v.reliability_score for v in validations],
            'status_distribution': {},
            'best_validation': None,
            'worst_validation': None
        }
        
        # 상태 분포
        for validation in validations:
            status = validation.status.value
            comparison['status_distribution'][status] = comparison['status_distribution'].get(status, 0) + 1
        
        # 최고/최저 검증 결과
        best_validation = max(validations, key=lambda v: v.overall_score)
        worst_validation = min(validations, key=lambda v: v.overall_score)
        
        comparison['best_validation'] = {
            'validation_id': best_validation.validation_id,
            'overall_score': best_validation.overall_score,
            'strategy_name': best_validation.backtest_result.strategy_name
        }
        
        comparison['worst_validation'] = {
            'validation_id': worst_validation.validation_id,
            'overall_score': worst_validation.overall_score,
            'strategy_name': worst_validation.backtest_result.strategy_name
        }
        
        return comparison 