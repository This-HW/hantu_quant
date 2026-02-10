"""
단위 테스트: ScreeningValidator (Dexter 패턴 검증기)

테스트 대상:
- 단일 종목 데이터 검증 (필수 필드, 타입, 범위, 논리 일관성)
- 전체 스크리닝 결과 검증
- 데이터 품질 점수 계산
"""

import pytest
from datetime import datetime
from core.watchlist.validator import ScreeningValidator, ValidationResult, DataQualityChecker


class TestScreeningValidator:
    """ScreeningValidator 단위 테스트"""

    @pytest.fixture
    def validator(self):
        """검증기 인스턴스"""
        return ScreeningValidator()

    @pytest.fixture
    def valid_stock_data(self):
        """정상적인 종목 데이터"""
        return {
            'code': '005930',
            'name': '삼성전자',
            'price': 70000,
            'volume': 1000000,
            'market_cap': 400000000000000,
            'per': 15.0,
            'pbr': 1.2,
            'roe': 12.0,
            'eps': 4666.67,
            'debt_ratio': 50.0,
        }

    @pytest.fixture
    def invalid_stock_data(self):
        """비정상적인 종목 데이터"""
        return {
            'code': '000000',
            'name': '테스트종목',
            'price': -1000,  # 비정상 가격
            'volume': -500,  # 비정상 거래량
            'market_cap': 1000,  # 가격보다 작은 시가총액
            'per': 1500,  # 극단적 PER
            'roe': 250,  # 극단적 ROE
        }

    # ===== 테스트 1: 정상 데이터 검증 =====
    def test_validate_stock_data_success(self, validator, valid_stock_data):
        """
        정상 데이터 검증 성공

        Given: 모든 필드가 정상인 종목 데이터
        When: validate_stock_data() 호출
        Then: is_valid=True, 높은 품질 점수 반환
        """
        result = validator.validate_stock_data('005930', valid_stock_data)

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.score >= 0.6  # 최소 품질 점수 통과
        assert len(result.issues) == 0  # 문제 없음
        assert result.metadata['stock_code'] == '005930'

    # ===== 테스트 2: 필드 누락 검증 =====
    def test_validate_stock_data_missing_fields(self, validator):
        """
        필수 필드 누락 시 검증 실패

        Given: 필수 필드(name, price, volume, market_cap) 중 일부 누락
        When: validate_stock_data() 호출
        Then: is_valid=False, issues에 누락 필드 기록
        """
        incomplete_data = {
            'code': '000001',
            'name': '테스트',
            # 'price': 누락
            'volume': 100000,
            # 'market_cap': 누락
        }

        result = validator.validate_stock_data('000001', incomplete_data)

        assert result.is_valid is False
        assert len(result.issues) > 0
        assert any('누락' in issue for issue in result.issues)
        # 5개 카테고리 중 1개만 0.0이면 평균 0.8 (4/5)
        assert result.score < 0.85  # 품질 점수 낮음

    # ===== 테스트 3: 값 범위 검증 =====
    def test_validate_value_ranges(self, validator, invalid_stock_data):
        """
        비정상 값 범위 검증

        Given: 가격/거래량이 음수, 극단적 재무 비율
        When: validate_stock_data() 호출
        Then: is_valid=False, issues/warnings에 범위 문제 기록
        """
        result = validator.validate_stock_data('000000', invalid_stock_data)

        assert result.is_valid is False
        assert len(result.issues) > 0 or len(result.warnings) > 0

        # 비정상 가격 issue 확인
        assert any('비정상 가격' in issue for issue in result.issues)
        # 비정상 거래량 issue 확인
        assert any('비정상 거래량' in issue for issue in result.issues)

    # ===== 테스트 4: 논리적 일관성 검증 =====
    def test_validate_logical_consistency(self, validator):
        """
        논리적 일관성 검증

        Given: 시가총액 < 가격 (논리적 모순)
        When: validate_stock_data() 호출
        Then: issues에 일관성 문제 기록
        """
        inconsistent_data = {
            'code': '000002',
            'name': '불일치종목',
            'price': 10000,
            'volume': 100000,
            'market_cap': 5000,  # 가격보다 작음 (논리적 모순)
            'per': 15.0,
            'pbr': 1.2,
            'roe': 10.0,
        }

        result = validator.validate_stock_data('000002', inconsistent_data)

        assert result.is_valid is False
        assert any('시가총액' in issue for issue in result.issues)

    # ===== 테스트 5: 전체 결과 검증 =====
    def test_validate_screening_results(self, validator, valid_stock_data):
        """
        전체 스크리닝 결과 검증

        Given: 여러 종목의 스크리닝 결과 리스트
        When: validate_screening_results() 호출
        Then: 검증 통과된 종목만 반환, 전체 ValidationResult 제공
        """
        results = [
            valid_stock_data.copy(),
            {
                'code': '000001',
                'name': '불량종목',
                'price': -100,  # 비정상
                'volume': 100,
                'market_cap': 1000,
                'per': 10,
            },
            valid_stock_data.copy(),
        ]

        validated_results, overall_validation = validator.validate_screening_results(results)

        # 검증 통과한 종목만 반환 (정상 2개, 불량 1개 제외)
        assert len(validated_results) == 2

        # 전체 검증 결과
        assert isinstance(overall_validation, ValidationResult)
        assert overall_validation.metadata['stats']['total'] == 3
        assert overall_validation.metadata['stats']['valid'] == 2
        assert overall_validation.metadata['stats']['invalid'] == 1

    # ===== 테스트 6: 빈 결과 검증 =====
    def test_validate_empty_results(self, validator):
        """
        빈 스크리닝 결과 검증

        Given: 빈 결과 리스트
        When: validate_screening_results() 호출
        Then: is_valid=False, 적절한 에러 메시지
        """
        validated_results, overall_validation = validator.validate_screening_results([])

        assert len(validated_results) == 0
        assert overall_validation.is_valid is False
        assert "비어있음" in overall_validation.issues[0]

    # ===== 테스트 7: 데이터 타입 검증 =====
    def test_validate_data_types(self, validator):
        """
        데이터 타입 검증

        Given: 숫자 필드에 문자열 등 잘못된 타입
        When: validate_stock_data() 호출
        Then: issues에 타입 에러 기록
        """
        wrong_type_data = {
            'code': '000003',
            'name': '타입오류',
            'price': 'not_a_number',  # 잘못된 타입
            'volume': 100000,
            'market_cap': 1000000,
        }

        result = validator.validate_stock_data('000003', wrong_type_data)

        assert result.is_valid is False
        assert any('숫자가 아님' in issue for issue in result.issues)

    # ===== 테스트 8: 경고 vs 에러 구분 =====
    def test_warnings_vs_errors(self, validator):
        """
        경고(Warning)와 에러(Issue) 구분

        Given: 극단적이지만 유효한 값 (예: 매우 높은 가격)
        When: validate_stock_data() 호출
        Then: is_valid=True, warnings에만 기록
        """
        high_price_data = {
            'code': '000004',
            'name': '고가종목',
            'price': 1200000,  # 매우 높은 가격 (경고 대상)
            'volume': 100000,
            'market_cap': 100000000000,
            'per': 20,
            'pbr': 1.5,
            'roe': 15,
        }

        result = validator.validate_stock_data('000004', high_price_data)

        # 경고는 있지만 검증은 통과
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any('매우 높은 가격' in warn for warn in result.warnings)

    # ===== 테스트 9: 컨텍스트 기반 검증 (선택) =====
    def test_validate_with_context(self, validator, valid_stock_data):
        """
        컨텍스트 기반 검증

        Given: 이전 스크리닝 결과와 현재 결과
        When: validate_screening_results(context 포함) 호출
        Then: 컨텍스트 기반 경고 생성
        """
        current_results = [valid_stock_data.copy()]

        # 이전 결과 (완전히 다른 종목)
        context = {
            'previous_results': [
                {'code': '999999', 'name': '다른종목'}
            ],
            'market_index_change': 0.05  # 5% 시장 변동
        }

        validated_results, overall_validation = validator.validate_screening_results(
            current_results, context=context
        )

        # 컨텍스트 기반 경고 확인
        assert len(overall_validation.warnings) > 0
        assert overall_validation.metadata['context_used'] is True


class TestDataQualityChecker:
    """DataQualityChecker 단위 테스트"""

    @pytest.fixture
    def checker(self):
        """품질 체커 인스턴스"""
        return DataQualityChecker()

    # ===== 테스트 1: API 응답 검증 =====
    def test_check_api_response_success(self, checker):
        """
        정상 API 응답 검증

        Given: 모든 필수 필드 포함된 API 응답
        When: check_api_response() 호출
        Then: True 반환
        """
        response = {
            'stock_code': '005930',
            'price': 70000,
            'volume': 1000000,
        }
        expected_fields = ['stock_code', 'price', 'volume']

        assert checker.check_api_response(response, expected_fields) is True

    # ===== 테스트 2: API 응답 필드 누락 =====
    def test_check_api_response_missing_fields(self, checker):
        """
        필드 누락된 API 응답

        Given: 필수 필드 일부 누락
        When: check_api_response() 호출
        Then: False 반환
        """
        response = {
            'stock_code': '005930',
            # 'price': 누락
        }
        expected_fields = ['stock_code', 'price', 'volume']

        assert checker.check_api_response(response, expected_fields) is False

    # ===== 테스트 3: 가격 데이터 검증 =====
    def test_check_price_data_success(self, checker):
        """
        정상 가격 데이터 검증

        Given: 충분한 가격 데이터 (20일 이상)
        When: check_price_data() 호출
        Then: True 반환
        """
        price_data = [
            {'date': f'2024-01-{i:02d}', 'close': 10000 + i * 100}
            for i in range(1, 31)
        ]

        assert checker.check_price_data(price_data) is True

    # ===== 테스트 4: 가격 데이터 부족 =====
    def test_check_price_data_insufficient(self, checker):
        """
        가격 데이터 부족

        Given: 20일 미만의 데이터
        When: check_price_data() 호출
        Then: False 반환
        """
        price_data = [
            {'date': f'2024-01-{i:02d}', 'close': 10000}
            for i in range(1, 10)  # 10개만
        ]

        assert checker.check_price_data(price_data) is False

    # ===== 테스트 5: 급격한 가격 변동 =====
    def test_check_price_data_sudden_change(self, checker):
        """
        급격한 가격 변동 감지

        Given: 연속된 날짜에 30% 이상 가격 변동
        When: check_price_data() 호출
        Then: 경고 로그 생성, True 반환 (상한가/하한가 가능성)
        """
        price_data = [
            {'date': '2024-01-01', 'close': 10000},
            {'date': '2024-01-02', 'close': 14000},  # 40% 상승
        ] + [
            {'date': f'2024-01-{i:02d}', 'close': 14000}
            for i in range(3, 25)
        ]

        # 경고만 하고 통과
        result = checker.check_price_data(price_data)
        assert result is True  # 통과


# ===== 엣지 케이스 테스트 =====
class TestValidatorEdgeCases:
    """검증기 엣지 케이스 테스트"""

    @pytest.fixture
    def validator(self):
        return ScreeningValidator()

    def test_none_values(self, validator):
        """
        None 값 처리

        Given: 필드 값이 None
        When: validate_stock_data() 호출
        Then: 필드 누락으로 처리
        """
        data = {
            'code': '000005',
            'name': None,  # None 값
            'price': None,
            'volume': 100000,
            'market_cap': 1000000,
        }

        result = validator.validate_stock_data('000005', data)

        assert result.is_valid is False
        assert any('누락' in issue for issue in result.issues)

    def test_zero_values(self, validator):
        """
        0 값 처리

        Given: 거래량이 0 (거래 정지 가능)
        When: validate_stock_data() 호출
        Then: warnings에 기록
        """
        data = {
            'code': '000006',
            'name': '거래정지',
            'price': 10000,
            'volume': 0,  # 거래 정지
            'market_cap': 1000000,
        }

        result = validator.validate_stock_data('000006', data)

        # 경고로 처리
        assert any('거래량 0' in warn for warn in result.warnings)

    def test_extreme_values(self, validator):
        """
        극단값 처리

        Given: ROE 200%, PER 1000 등 극단값
        When: validate_stock_data() 호출
        Then: warnings에 기록
        """
        data = {
            'code': '000007',
            'name': '극단종목',
            'price': 10000,
            'volume': 100000,
            'market_cap': 1000000,
            'roe': 250,  # 극단적 ROE
            'per': 1500,  # 극단적 PER
        }

        result = validator.validate_stock_data('000007', data)

        assert len(result.warnings) > 0
        assert any('극단적 ROE' in warn for warn in result.warnings)
        assert any('극단적 PER' in warn for warn in result.warnings)
