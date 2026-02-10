"""
스크리닝 결과 검증 모듈 (Dexter 패턴 적용)

Dexter의 자가 검증 메커니즘을 참고하여 구현:
- 데이터 품질 검증
- 이상치 탐지
- 논리적 일관성 검사
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    score: float  # 0.0 ~ 1.0 (품질 점수)
    issues: List[str]  # 발견된 문제들
    warnings: List[str]  # 경고 사항들
    metadata: Dict  # 추가 정보


class ScreeningValidator:
    """스크리닝 결과 검증기 (Dexter 스타일)"""

    def __init__(self):
        self.logger = get_logger(__name__)

        # 검증 임계값
        self.thresholds = {
            'min_quality_score': 0.6,  # 최소 품질 점수
            'max_missing_fields': 3,   # 최대 누락 필드 수
            'max_outlier_ratio': 0.2,  # 최대 이상치 비율
        }

    def validate_stock_data(self, stock_code: str, data: Dict) -> ValidationResult:
        """
        단일 종목 데이터 검증

        Args:
            stock_code: 종목 코드
            data: 종목 데이터

        Returns:
            ValidationResult: 검증 결과
        """
        # None/타입 입력 방어
        if data is None or not isinstance(data, dict):
            return ValidationResult(
                is_valid=False,
                score=0.0,
                issues=["입력 데이터가 None"],
                warnings=[],
                metadata={
                    'stock_code': stock_code,
                    'validated_at': datetime.now().isoformat(),
                }
            )

        issues = []
        warnings = []
        scores = []

        # 1. 필수 필드 검증
        required_fields = ['name', 'price', 'volume', 'market_cap']
        missing_fields = [f for f in required_fields if f not in data or data[f] is None]

        if missing_fields:
            issues.append(f"필수 필드 누락: {missing_fields}")
            scores.append(0.0)
        else:
            scores.append(1.0)

        # 2. 데이터 타입 검증
        type_score = self._validate_data_types(data, issues, warnings)
        scores.append(type_score)

        # 3. 값 범위 검증
        range_score = self._validate_value_ranges(data, issues, warnings)
        scores.append(range_score)

        # 4. 논리적 일관성 검증
        consistency_score = self._validate_logical_consistency(data, issues, warnings)
        scores.append(consistency_score)

        # 5. 이상치 검증
        outlier_score = self._validate_outliers(data, warnings)
        scores.append(outlier_score)

        # 종합 점수 계산
        final_score = np.mean(scores) if scores else 0.0
        is_valid = final_score >= self.thresholds['min_quality_score'] and len(issues) == 0

        if not is_valid:
            self.logger.warning(
                f"종목 {stock_code} 검증 실패 (점수: {final_score:.2f})",
                extra={'issues': issues, 'warnings': warnings}
            )

        return ValidationResult(
            is_valid=is_valid,
            score=final_score,
            issues=issues,
            warnings=warnings,
            metadata={
                'stock_code': stock_code,
                'validated_at': datetime.now().isoformat(),
                'scores': {
                    'fields': scores[0] if len(scores) > 0 else 0.0,
                    'types': scores[1] if len(scores) > 1 else 0.0,
                    'ranges': scores[2] if len(scores) > 2 else 0.0,
                    'consistency': scores[3] if len(scores) > 3 else 0.0,
                    'outliers': scores[4] if len(scores) > 4 else 0.0,
                }
            }
        )

    def validate_screening_results(
        self,
        results: List[Dict],
        context: Optional[Dict] = None
    ) -> Tuple[List[Dict], ValidationResult]:
        """
        전체 스크리닝 결과 검증 (Dexter의 컨텍스트 관리 패턴)

        Args:
            results: 스크리닝 결과 리스트
            context: 검증 컨텍스트 (이전 결과, 시장 상황 등)

        Returns:
            Tuple[List[Dict], ValidationResult]: (검증된 결과, 전체 검증 결과)
        """
        if not results:
            return [], ValidationResult(
                is_valid=False,
                score=0.0,
                issues=["스크리닝 결과가 비어있음"],
                warnings=[],
                metadata={'total_count': 0}
            )

        validated_results = []
        validation_stats = {
            'total': len(results),
            'valid': 0,
            'invalid': 0,
            'quality_scores': [],
        }

        all_issues = []
        all_warnings = []

        # 각 종목 검증
        for item in results:
            stock_code = item.get('code', 'unknown')
            validation = self.validate_stock_data(stock_code, item)

            if validation.is_valid:
                validated_results.append(item)
                validation_stats['valid'] += 1
            else:
                validation_stats['invalid'] += 1
                all_issues.extend([f"[{stock_code}] {issue}" for issue in validation.issues])

            validation_stats['quality_scores'].append(validation.score)
            all_warnings.extend([f"[{stock_code}] {warn}" for warn in validation.warnings])

        # 전체 통계 계산
        avg_quality = np.mean(validation_stats['quality_scores'])
        valid_ratio = validation_stats['valid'] / validation_stats['total']

        # 컨텍스트 기반 검증 (선택적)
        if context:
            context_validation = self._validate_with_context(validated_results, context)
            all_warnings.extend(context_validation)

        # 최종 판정
        is_valid = (
            valid_ratio >= (1.0 - self.thresholds['max_outlier_ratio']) and
            avg_quality >= self.thresholds['min_quality_score']
        )

        if not is_valid:
            self.logger.error(
                f"스크리닝 결과 검증 실패: 유효 비율 {valid_ratio:.1%}, 평균 품질 {avg_quality:.2f}",
                extra={'stats': validation_stats, 'issues': all_issues[:10]}  # 상위 10개만
            )
        else:
            self.logger.info(
                f"스크리닝 결과 검증 성공: {validation_stats['valid']}/{validation_stats['total']} 종목"
            )

        return validated_results, ValidationResult(
            is_valid=is_valid,
            score=avg_quality,
            issues=all_issues,
            warnings=all_warnings,
            metadata={
                'stats': validation_stats,
                'valid_ratio': valid_ratio,
                'context_used': context is not None,
            }
        )

    def _validate_data_types(self, data: Dict, issues: List[str], warnings: List[str]) -> float:
        """데이터 타입 검증"""
        score = 1.0

        # 숫자 필드 검증
        numeric_fields = ['price', 'volume', 'market_cap', 'per', 'pbr', 'roe']
        for field in numeric_fields:
            if field in data and data[field] is not None:
                if not isinstance(data[field], (int, float)):
                    issues.append(f"{field}이(가) 숫자가 아님: {type(data[field])}")
                    score -= 0.2

        return max(score, 0.0)

    def _validate_value_ranges(self, data: Dict, issues: List[str], warnings: List[str]) -> float:
        """값 범위 검증"""
        score = 1.0

        # 가격 검증
        if 'price' in data and data['price'] is not None:
            price = data['price']
            if price <= 0:
                issues.append(f"비정상 가격: {price}")
                score -= 0.3
            elif price > 1_000_000:  # 100만원 초과
                warnings.append(f"매우 높은 가격: {price:,}원")
                score -= 0.1

        # 거래량 검증
        if 'volume' in data and data['volume'] is not None:
            volume = data['volume']
            if volume < 0:
                issues.append(f"비정상 거래량: {volume}")
                score -= 0.3

        # 재무 비율 검증
        if 'roe' in data and data['roe'] is not None:
            roe = data['roe']
            if roe < -100 or roe > 200:
                warnings.append(f"극단적 ROE: {roe}%")
                score -= 0.1

        if 'per' in data and data['per'] is not None:
            per = data['per']
            if per < 0 or per > 1000:
                warnings.append(f"극단적 PER: {per}")
                score -= 0.1

        return max(score, 0.0)

    def _validate_logical_consistency(
        self,
        data: Dict,
        issues: List[str],
        warnings: List[str]
    ) -> float:
        """논리적 일관성 검증"""
        score = 1.0

        # 시가총액 vs 가격 일관성
        if all(k in data and data[k] is not None for k in ['market_cap', 'price']):
            # 시가총액이 가격보다 작으면 비정상
            if data['market_cap'] < data['price']:
                issues.append(
                    f"시가총액({data['market_cap']}) < 가격({data['price']})"
                )
                score -= 0.3

        # PER과 EPS 일관성 (있는 경우)
        if all(k in data and data[k] is not None for k in ['per', 'eps', 'price']):
            # PER = 가격 / EPS
            calculated_per = data['price'] / data['eps'] if data['eps'] != 0 else None
            if calculated_per and data['per'] != 0 and abs(calculated_per - data['per']) / data['per'] > 0.1:
                warnings.append(
                    f"PER 불일치: 보고값 {data['per']}, 계산값 {calculated_per:.2f}"
                )
                score -= 0.1

        return max(score, 0.0)

    def _validate_outliers(self, data: Dict, warnings: List[str]) -> float:
        """이상치 검증 (통계적 방법)"""
        score = 1.0

        # 개별 종목에 대한 이상치 검증은 전체 분포 필요
        # 여기서는 극단값만 체크

        if 'volume' in data and data['volume'] is not None:
            if data['volume'] == 0:
                warnings.append("거래량 0 (거래 정지 가능성)")
                score -= 0.1

        return max(score, 0.0)

    def _validate_with_context(self, results: List[Dict], context: Dict) -> List[str]:
        """
        컨텍스트 기반 검증 (Dexter의 컨텍스트 관리 패턴)

        Args:
            results: 검증된 결과
            context: 검증 컨텍스트 (예: 이전 스크리닝 결과, 시장 지수 등)

        Returns:
            List[str]: 컨텍스트 기반 경고 목록
        """
        warnings = []

        # 이전 결과와 비교
        if 'previous_results' in context:
            prev_codes = set(item.get('code', item.get('stock_code', '')) for item in context['previous_results'])
            curr_codes = set(item.get('code', item.get('stock_code', '')) for item in results)

            # 완전히 다른 결과면 경고
            overlap_ratio = len(prev_codes & curr_codes) / len(prev_codes) if prev_codes else 0
            if overlap_ratio < 0.3:
                warnings.append(
                    f"이전 스크리닝과 겹치는 종목 {overlap_ratio:.1%}만 (급격한 변화 감지)"
                )

        # 시장 상황과 비교
        if 'market_index_change' in context:
            market_change = context['market_index_change']
            if abs(market_change) > 0.03:  # 3% 이상 변동
                warnings.append(
                    f"시장 급변동 감지 ({market_change:+.1%}) - 결과 신뢰도 낮을 수 있음"
                )

        return warnings


class DataQualityChecker:
    """데이터 품질 체크 (API 응답 검증)"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def check_api_response(self, response: Dict, expected_fields: List[str]) -> bool:
        """
        API 응답 품질 체크

        Args:
            response: API 응답
            expected_fields: 기대되는 필드 목록

        Returns:
            bool: 품질 통과 여부
        """
        if not response:
            self.logger.error("API 응답이 비어있음")
            return False

        # 필수 필드 체크
        missing = [f for f in expected_fields if f not in response]
        if missing:
            self.logger.warning(f"응답에 필드 누락: {missing}")
            return False

        # None 값 체크
        none_fields = [f for f in expected_fields if response.get(f) is None]
        if none_fields:
            self.logger.warning(f"응답 필드가 None: {none_fields}")
            return False

        return True

    def check_price_data(self, price_data: List[Dict]) -> bool:
        """
        가격 데이터 품질 체크

        Args:
            price_data: 가격 데이터 리스트

        Returns:
            bool: 품질 통과 여부
        """
        if not price_data:
            self.logger.error("가격 데이터가 비어있음")
            return False

        # 최소 데이터 수 체크 (최소 20일)
        if len(price_data) < 20:
            self.logger.warning(f"가격 데이터 부족: {len(price_data)}개")
            return False

        # 가격 연속성 체크 (갭이 너무 크면 의심)
        prices = [item.get('close', 0) for item in price_data if item.get('close')]
        if not prices:
            self.logger.error("유효한 종가 데이터 없음")
            return False

        # 연속된 가격 변동률 체크
        for i in range(1, len(prices)):
            change_ratio = abs(prices[i] - prices[i-1]) / prices[i-1] if prices[i-1] != 0 else 0
            if change_ratio > 0.3:  # 30% 이상 변동
                self.logger.warning(
                    f"급격한 가격 변동 감지: {prices[i-1]} -> {prices[i]} ({change_ratio:.1%})"
                )
                # 경고만 하고 통과 (상한가/하한가 가능)

        return True
