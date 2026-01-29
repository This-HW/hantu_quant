#!/usr/bin/env python3
"""
Phase 2 DailyUpdater 단위 테스트

P1 요구사항:
- _calculate_composite_score 가중치 검증
- _select_top_n_adaptive 섹터 제한 테스트
- _passes_basic_filters 안전 필터 테스트
"""

import unittest
import sys
import os
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# 테스트 환경 설정: SQLite 인메모리 DB 사용
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = ""  # Redis 비활성화

from core.daily_selection.daily_updater import DailyUpdater
from core.daily_selection.price_analyzer import PriceAttractivenessLegacy


class TestDailyUpdaterCompositeScore(unittest.TestCase):
    """종합 점수 계산 테스트"""

    def setUp(self):
        """테스트 픽스처 설정"""
        self.updater = DailyUpdater()

    def test_composite_score_calculation(self):
        """종합 점수 계산 정확도"""
        stock_data = {
            "technical_score": 80.0,
            "volume_score": 60.0,
            "risk_score": 30.0,
            "confidence": 0.8
        }

        score = self.updater._calculate_composite_score(stock_data)

        # 예상값 계산
        # technical: 80 * 0.35 = 28.0
        # volume: 60 * 0.25 = 15.0
        # risk: (100-30) * 0.25 = 17.5
        # confidence: 0.8 * 100 * 0.15 = 12.0
        # 합계: 72.5
        expected = 72.5
        self.assertAlmostEqual(score, expected, places=2)

    def test_composite_score_weight_validation(self):
        """가중치 합 검증 (P1)"""
        # 올바른 가중치 (1.0)
        stock_data = {
            "technical_score": 50.0,
            "volume_score": 50.0,
            "risk_score": 50.0,
            "confidence": 0.5
        }

        # 예외 발생하지 않아야 함
        try:
            score = self.updater._calculate_composite_score(stock_data)
            self.assertIsInstance(score, float)
        except ValueError:
            self.fail("가중치 합이 1.0인데 ValueError 발생")

    def test_composite_score_with_invalid_weights(self):
        """잘못된 가중치 설정 시 에러 (P1)"""
        # config를 임시로 잘못된 값으로 변경
        original_config = self.updater._config.copy()

        try:
            # 가중치 합이 1.0이 아닌 경우
            self.updater._config["composite_weights"] = {
                "technical": 0.5,
                "volume": 0.5,
                "risk": 0.5,
                "confidence": 0.5  # 합계 2.0
            }

            stock_data = {
                "technical_score": 50.0,
                "volume_score": 50.0,
                "risk_score": 50.0,
                "confidence": 0.5
            }

            with self.assertRaises(ValueError) as context:
                self.updater._calculate_composite_score(stock_data)

            self.assertIn("가중치 합", str(context.exception))

        finally:
            # config 복원
            self.updater._config = original_config

    def test_composite_score_boundary_values(self):
        """경계값 테스트"""
        # 최대값
        stock_data_max = {
            "technical_score": 100.0,
            "volume_score": 100.0,
            "risk_score": 0.0,
            "confidence": 1.0
        }
        score_max = self.updater._calculate_composite_score(stock_data_max)
        self.assertAlmostEqual(score_max, 100.0, places=1)

        # 최소값
        stock_data_min = {
            "technical_score": 0.0,
            "volume_score": 0.0,
            "risk_score": 100.0,
            "confidence": 0.0
        }
        score_min = self.updater._calculate_composite_score(stock_data_min)
        self.assertAlmostEqual(score_min, 0.0, places=1)


class TestDailyUpdaterAdaptiveSelection(unittest.TestCase):
    """시장 적응형 선정 테스트"""

    def setUp(self):
        """테스트 픽스처 설정"""
        self.updater = DailyUpdater()

    def test_adaptive_selection_bullish(self):
        """상승장 선정 개수 테스트"""
        candidates = self._create_mock_candidates(20)
        selected = self.updater._select_top_n_adaptive(candidates, "bullish")

        # config에서 목표 개수 확인
        expected = self.updater._config["adaptive_selection"]["bullish"]
        self.assertEqual(len(selected), expected)

    def test_adaptive_selection_neutral(self):
        """중립장 선정 개수 테스트"""
        candidates = self._create_mock_candidates(20)
        selected = self.updater._select_top_n_adaptive(candidates, "neutral")

        expected = self.updater._config["adaptive_selection"]["neutral"]
        self.assertEqual(len(selected), expected)

    def test_adaptive_selection_bearish(self):
        """하락장 선정 개수 테스트"""
        candidates = self._create_mock_candidates(20)
        selected = self.updater._select_top_n_adaptive(candidates, "bearish")

        expected = self.updater._config["adaptive_selection"]["bearish"]
        self.assertEqual(len(selected), expected)

    def test_sector_diversification(self):
        """섹터 다각화 제한 테스트 (P1)"""
        # 같은 섹터 종목 10개 생성
        candidates = []
        for i in range(10):
            candidates.append({
                "stock_code": f"00000{i}",
                "stock_name": f"종목{i}",
                "technical_score": 90.0 - i,  # 점수 순서
                "volume_score": 80.0,
                "risk_score": 20.0,
                "confidence": 0.8,
                "sector": "IT",  # 모두 같은 섹터
                "market_cap": 1000000000.0
            })

        selected = self.updater._select_top_n_adaptive(candidates, "bullish")

        # 섹터당 최대 개수 확인
        max_per_sector = self.updater._config["diversification"]["max_stocks_per_sector"]
        it_count = sum(1 for s in selected if s.get("sector") == "IT")
        self.assertLessEqual(it_count, max_per_sector)

    def test_sector_diversification_multiple_sectors(self):
        """여러 섹터 분산 테스트 (P1)"""
        candidates = []

        # IT 섹터 5개
        for i in range(5):
            candidates.append({
                "stock_code": f"IT{i:04d}",
                "stock_name": f"IT종목{i}",
                "technical_score": 90.0,
                "volume_score": 80.0,
                "risk_score": 20.0,
                "confidence": 0.8,
                "sector": "IT",
                "market_cap": 1000000000.0
            })

        # 금융 섹터 5개
        for i in range(5):
            candidates.append({
                "stock_code": f"FIN{i:04d}",
                "stock_name": f"금융종목{i}",
                "technical_score": 85.0,
                "volume_score": 75.0,
                "risk_score": 25.0,
                "confidence": 0.75,
                "sector": "금융",
                "market_cap": 1000000000.0
            })

        selected = self.updater._select_top_n_adaptive(candidates, "bullish")

        # 각 섹터 개수 확인
        max_per_sector = self.updater._config["diversification"]["max_stocks_per_sector"]
        it_count = sum(1 for s in selected if s.get("sector") == "IT")
        fin_count = sum(1 for s in selected if s.get("sector") == "금융")

        self.assertLessEqual(it_count, max_per_sector)
        self.assertLessEqual(fin_count, max_per_sector)
        self.assertGreater(it_count + fin_count, 0)

    def test_empty_candidates(self):
        """빈 후보 리스트 테스트"""
        selected = self.updater._select_top_n_adaptive([], "neutral")
        self.assertEqual(len(selected), 0)

    def test_fewer_candidates_than_target(self):
        """목표보다 적은 후보 테스트"""
        candidates = self._create_mock_candidates(3)
        selected = self.updater._select_top_n_adaptive(candidates, "bullish")

        # 목표는 12개지만 후보가 3개만 있으므로 3개 선정
        self.assertEqual(len(selected), 3)

    def _create_mock_candidates(self, count: int) -> list:
        """모의 후보 종목 생성"""
        candidates = []
        sectors = ["IT", "금융", "제조", "서비스", "에너지"]

        for i in range(count):
            candidates.append({
                "stock_code": f"{i:06d}",
                "stock_name": f"종목{i}",
                "technical_score": 90.0 - (i * 2),
                "volume_score": 80.0,
                "risk_score": 20.0 + (i * 1),
                "confidence": 0.8,
                "sector": sectors[i % len(sectors)],
                "market_cap": 1000000000.0
            })

        return candidates


class TestDailyUpdaterSafetyFilter(unittest.TestCase):
    """안전 필터 테스트"""

    def setUp(self):
        """테스트 픽스처 설정"""
        self.updater = DailyUpdater()

    def test_passes_basic_filters_success(self):
        """안전 필터 통과 테스트"""
        result = PriceAttractivenessLegacy(
            stock_code="000000",
            stock_name="테스트",
            analysis_date="2026-01-29",
            current_price=10000.0,
            total_score=70.0,
            technical_score=80.0,
            volume_score=60.0,
            pattern_score=70.0,
            technical_signals=[],
            risk_score=30.0,  # < 60 (통과)
            entry_price=10000.0,
            target_price=12000.0,
            stop_loss=9000.0,
            expected_return=0.2,
            confidence=0.8,
            selection_reason="테스트",
            market_condition="neutral",
            sector_momentum=0.5
        )

        self.assertTrue(self.updater._passes_basic_filters(result))

    def test_passes_basic_filters_high_risk(self):
        """리스크 점수 초과 테스트"""
        result = PriceAttractivenessLegacy(
            stock_code="000001",
            stock_name="고위험",
            analysis_date="2026-01-29",
            current_price=10000.0,
            total_score=70.0,
            technical_score=80.0,
            volume_score=60.0,
            pattern_score=70.0,
            technical_signals=[],
            risk_score=65.0,  # > 60 (실패)
            entry_price=10000.0,
            target_price=12000.0,
            stop_loss=9000.0,
            expected_return=0.2,
            confidence=0.8,
            selection_reason="테스트",
            market_condition="neutral",
            sector_momentum=0.5
        )

        self.assertFalse(self.updater._passes_basic_filters(result))

    def test_passes_basic_filters_low_volume(self):
        """거래량 점수 미달 테스트"""
        result = PriceAttractivenessLegacy(
            stock_code="000002",
            stock_name="저거래량",
            analysis_date="2026-01-29",
            current_price=10000.0,
            total_score=70.0,
            technical_score=80.0,
            volume_score=3.0,  # < 5 (실패)
            pattern_score=70.0,
            technical_signals=[],
            risk_score=30.0,
            entry_price=10000.0,
            target_price=12000.0,
            stop_loss=9000.0,
            expected_return=0.2,
            confidence=0.8,
            selection_reason="테스트",
            market_condition="neutral",
            sector_momentum=0.5
        )

        self.assertFalse(self.updater._passes_basic_filters(result))

    def test_passes_basic_filters_boundary(self):
        """경계값 테스트"""
        # 리스크 점수 정확히 60 (통과)
        result_risk_boundary = PriceAttractivenessLegacy(
            stock_code="000003",
            stock_name="경계값",
            analysis_date="2026-01-29",
            current_price=10000.0,
            total_score=70.0,
            technical_score=80.0,
            volume_score=10.0,
            pattern_score=70.0,
            technical_signals=[],
            risk_score=60.0,  # = 60 (통과, > 조건이므로)
            entry_price=10000.0,
            target_price=12000.0,
            stop_loss=9000.0,
            expected_return=0.2,
            confidence=0.8,
            selection_reason="테스트",
            market_condition="neutral",
            sector_momentum=0.5
        )
        self.assertTrue(self.updater._passes_basic_filters(result_risk_boundary))

        # 거래량 점수 정확히 5 (통과)
        result_volume_boundary = PriceAttractivenessLegacy(
            stock_code="000004",
            stock_name="경계값",
            analysis_date="2026-01-29",
            current_price=10000.0,
            total_score=70.0,
            technical_score=80.0,
            volume_score=5.0,  # = 5 (통과, < 조건이므로)
            pattern_score=70.0,
            technical_signals=[],
            risk_score=30.0,
            entry_price=10000.0,
            target_price=12000.0,
            stop_loss=9000.0,
            expected_return=0.2,
            confidence=0.8,
            selection_reason="테스트",
            market_condition="neutral",
            sector_momentum=0.5
        )
        self.assertTrue(self.updater._passes_basic_filters(result_volume_boundary))


if __name__ == "__main__":
    unittest.main()
