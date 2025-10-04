#!/usr/bin/env python3
"""
Phase 1: 감시 리스트 구축 테스트
"""

import unittest
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.watchlist.stock_screener import StockScreener
from core.watchlist.watchlist_manager import WatchlistManager, WatchlistStock
from core.watchlist.evaluation_engine import EvaluationEngine, EvaluationWeights, MarketCondition

class TestStockScreener(unittest.TestCase):
    """StockScreener 테스트 클래스"""
    
    def setUp(self):
        """테스트 설정"""
        self.screener = StockScreener()
        self.test_stock_data = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "sector": "반도체",
            "market_cap": 450000000000000,
            "current_price": 56800,
            # 재무 데이터
            "roe": 18.5,
            "per": 12.3,
            "pbr": 1.1,
            "debt_ratio": 45.2,
            "revenue_growth": 15.8,
            "operating_margin": 12.3,
            # 기술적 데이터
            "ma_20": 55000,
            "ma_60": 54000,
            "ma_120": 53000,
            "rsi": 45.2,
            "volume_ratio": 1.8,
            "price_momentum_1m": 5.2,
            "volatility": 0.25,
            # 모멘텀 데이터
            "relative_strength": 0.1,
            "price_momentum_3m": 8.3,
            "price_momentum_6m": 15.7,
            "volume_momentum": 0.2,
            "sector_momentum": 0.05
        }
    
    def test_screen_by_fundamentals(self):
        """재무제표 기반 스크리닝 테스트"""
        passed, score, details = self.screener.screen_by_fundamentals(self.test_stock_data)
        
        self.assertIsInstance(passed, bool)
        self.assertIsInstance(score, float)
        self.assertIsInstance(details, dict)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        
        # 세부 결과 검증
        self.assertIn("roe", details)
        self.assertIn("per", details)
        self.assertIn("pbr", details)
        self.assertIn("debt_ratio", details)
        self.assertIn("revenue_growth", details)
        self.assertIn("operating_margin", details)
    
    def test_screen_by_technical(self):
        """기술적 분석 기반 스크리닝 테스트"""
        passed, score, details = self.screener.screen_by_technical(self.test_stock_data)
        
        self.assertIsInstance(passed, bool)
        self.assertIsInstance(score, float)
        self.assertIsInstance(details, dict)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        
        # 세부 결과 검증
        self.assertIn("ma_trend", details)
        self.assertIn("rsi", details)
        self.assertIn("volume_ratio", details)
        self.assertIn("momentum_1m", details)
        self.assertIn("volatility", details)
    
    def test_screen_by_momentum(self):
        """모멘텀 기반 스크리닝 테스트"""
        passed, score, details = self.screener.screen_by_momentum(self.test_stock_data)
        
        self.assertIsInstance(passed, bool)
        self.assertIsInstance(score, float)
        self.assertIsInstance(details, dict)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        
        # 세부 결과 검증
        self.assertIn("relative_strength", details)
        self.assertIn("price_momentum", details)
        self.assertIn("volume_momentum", details)
        self.assertIn("sector_momentum", details)
    
    def test_comprehensive_screening(self):
        """종합 스크리닝 테스트"""
        test_stock_list = ["005930", "000660", "035420"]
        
        with patch.object(self.screener, '_fetch_stock_data', return_value=self.test_stock_data):
            results = self.screener.comprehensive_screening(test_stock_list)
            
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), len(test_stock_list))
            
            for result in results:
                # ScreeningResult 객체의 속성 확인
                self.assertIsNotNone(getattr(result, "stock_code", None))
                self.assertIsNotNone(getattr(result, "overall_passed", None))
                self.assertIsNotNone(getattr(result, "overall_score", None))
                self.assertIsNotNone(getattr(result, "fundamental", None))
                self.assertIsNotNone(getattr(result, "technical", None))
                self.assertIsNotNone(getattr(result, "momentum", None))
    
    def test_save_screening_results(self):
        """스크리닝 결과 저장 테스트"""
        test_results = [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "overall_passed": True,
                "overall_score": 75.5
            }
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, "watchlist"), exist_ok=True)
            test_file = os.path.join(temp_dir, "watchlist", "test_results.json")
            
            success = self.screener.save_screening_results(test_results, test_file)
            
            self.assertTrue(success)
            self.assertTrue(os.path.exists(test_file))

class TestWatchlistManager(unittest.TestCase):
    """WatchlistManager 테스트 클래스"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_data_file = os.path.join(self.temp_dir, "test_watchlist.json")
        self.manager = WatchlistManager(self.test_data_file)
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    def test_add_stock(self):
        """종목 추가 테스트"""
        success = self.manager.add_stock_legacy(
            p_stock_code="005930",
            p_stock_name="삼성전자",
            p_added_reason="테스트 추가",
            p_target_price=70000,
            p_stop_loss=50000,
            p_sector="반도체",
            p_screening_score=85.5,
            p_notes="테스트 메모"
        )
        
        self.assertTrue(success)
        
        # 추가된 종목 확인
        stock = self.manager.get_stock("005930")
        self.assertIsNotNone(stock)
        self.assertEqual(stock.stock_code, "005930")
        self.assertEqual(stock.stock_name, "삼성전자")
        self.assertEqual(stock.target_price, 70000)
        self.assertEqual(stock.stop_loss, 50000)
        self.assertEqual(stock.screening_score, 85.5)
    
    def test_duplicate_add_stock(self):
        """중복 종목 추가 테스트"""
        # 첫 번째 추가
        success1 = self.manager.add_stock_legacy(
            p_stock_code="005930",
            p_stock_name="삼성전자",
            p_added_reason="첫 번째 추가",
            p_target_price=70000,
            p_stop_loss=50000,
            p_sector="반도체",
            p_screening_score=85.5
        )
        self.assertTrue(success1)
        
        # 중복 추가 시도
        success2 = self.manager.add_stock_legacy(
            p_stock_code="005930",
            p_stock_name="삼성전자",
            p_added_reason="중복 추가",
            p_target_price=75000,
            p_stop_loss=55000,
            p_sector="반도체",
            p_screening_score=90.0
        )
        self.assertFalse(success2)
    
    def test_update_stock(self):
        """종목 수정 테스트"""
        # 종목 추가
        self.manager.add_stock_legacy(
            p_stock_code="005930",
            p_stock_name="삼성전자",
            p_added_reason="테스트 추가",
            p_target_price=70000,
            p_stop_loss=50000,
            p_sector="반도체",
            p_screening_score=85.5
        )
        
        # 종목 수정
        success = self.manager.update_stock("005930", {
            "target_price": 75000,
            "stop_loss": 55000,
            "notes": "수정된 메모"
        })
        
        self.assertTrue(success)
        
        # 수정 확인
        stock = self.manager.get_stock("005930")
        self.assertEqual(stock.target_price, 75000)
        self.assertEqual(stock.stop_loss, 55000)
        self.assertEqual(stock.notes, "수정된 메모")
    
    def test_remove_stock(self):
        """종목 제거 테스트"""
        # 종목 추가
        self.manager.add_stock_legacy(
            p_stock_code="005930",
            p_stock_name="삼성전자",
            p_added_reason="테스트 추가",
            p_target_price=70000,
            p_stop_loss=50000,
            p_sector="반도체",
            p_screening_score=85.5
        )
        
        # 종목 제거 (상태 변경)
        success = self.manager.remove_stock("005930", p_permanent=False)
        self.assertTrue(success)
        
        stock = self.manager.get_stock("005930")
        self.assertEqual(stock.status, "removed")
        
        # 영구 삭제
        success = self.manager.remove_stock("005930", p_permanent=True)
        self.assertTrue(success)
        
        stock = self.manager.get_stock("005930")
        self.assertIsNone(stock)
    
    def test_list_stocks(self):
        """종목 목록 조회 테스트"""
        # 여러 종목 추가
        test_stocks = [
            ("005930", "삼성전자", "반도체", 85.5),
            ("000660", "SK하이닉스", "반도체", 75.2),
            ("035420", "NAVER", "인터넷", 90.1)
        ]
        
        for code, name, sector, score in test_stocks:
            self.manager.add_stock_legacy(
                p_stock_code=code,
                p_stock_name=name,
                p_added_reason="테스트 추가",
                p_target_price=70000,
                p_stop_loss=50000,
                p_sector=sector,
                p_screening_score=score
            )
        
        # 전체 목록 조회
        all_stocks = self.manager.list_stocks()
        self.assertEqual(len(all_stocks), 3)
        
        # 섹터별 필터링
        semiconductor_stocks = self.manager.list_stocks(p_sector="반도체")
        self.assertEqual(len(semiconductor_stocks), 2)
        
        # 점수 정렬 확인
        sorted_stocks = self.manager.list_stocks(p_sort_by="screening_score", p_ascending=False)
        # 정렬이 제대로 되었는지 확인 (내림차순)
        for i in range(len(sorted_stocks) - 1):
            self.assertGreaterEqual(sorted_stocks[i].screening_score, sorted_stocks[i + 1].screening_score)
        
        # 가장 높은 점수 확인 (90.1점인 NAVER)
        highest_score_stock = max(sorted_stocks, key=lambda x: x.screening_score)
        self.assertEqual(highest_score_stock.stock_code, "035420")
        self.assertEqual(highest_score_stock.screening_score, 90.1)
    
    def test_get_statistics(self):
        """통계 정보 조회 테스트"""
        # 여러 종목 추가
        test_stocks = [
            ("005930", "삼성전자", "반도체", 85.5),
            ("000660", "SK하이닉스", "반도체", 75.2),
            ("035420", "NAVER", "인터넷", 90.1),
            ("035720", "카카오", "인터넷", 65.8)
        ]
        
        for code, name, sector, score in test_stocks:
            self.manager.add_stock_legacy(
                p_stock_code=code,
                p_stock_name=name,
                p_added_reason="테스트 추가",
                p_target_price=70000,
                p_stop_loss=50000,
                p_sector=sector,
                p_screening_score=score
            )
        
        stats = self.manager.get_statistics()
        
        self.assertEqual(stats["total_count"], 4)
        self.assertEqual(stats["active_count"], 4)
        self.assertEqual(stats["sector_distribution"]["반도체"], 2)
        self.assertEqual(stats["sector_distribution"]["인터넷"], 2)
        self.assertGreater(stats["average_score"], 0)
        self.assertEqual(len(stats["top_stocks"]), 4)
    
    def test_validate_data(self):
        """데이터 무결성 검증 테스트"""
        # 정상 데이터 추가
        self.manager.add_stock_legacy(
            p_stock_code="005930",
            p_stock_name="삼성전자",
            p_added_reason="테스트 추가",
            p_target_price=70000,
            p_stop_loss=50000,
            p_sector="반도체",
            p_screening_score=85.5
        )
        
        # 데이터 검증
        is_valid, errors = self.manager.validate_data()
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

class TestEvaluationEngine(unittest.TestCase):
    """EvaluationEngine 테스트 클래스"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
        self.engine = EvaluationEngine(self.config_file)
        
        self.test_stock_data = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "sector": "반도체",
            "current_price": 56800,
            # 재무 데이터
            "roe": 18.5,
            "per": 12.3,
            "pbr": 1.1,
            "debt_ratio": 45.2,
            "revenue_growth": 15.8,
            "operating_margin": 12.3,
            # 기술적 데이터
            "ma_20": 55000,
            "ma_60": 54000,
            "ma_120": 53000,
            "rsi": 45.2,
            "volume_ratio": 1.8,
            "price_momentum_1m": 5.2,
            "volatility": 0.25,
            # 모멘텀 데이터
            "relative_strength": 0.1,
            "price_momentum_3m": 8.3,
            "price_momentum_6m": 15.7,
            "volume_momentum": 0.2,
            "sector_momentum": 0.05
        }
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    def test_calculate_comprehensive_score(self):
        """종합 점수 계산 테스트"""
        score, details = self.engine.calculate_comprehensive_score(self.test_stock_data)
        
        self.assertIsInstance(score, float)
        self.assertIsInstance(details, dict)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        
        # 세부 점수 검증
        self.assertIn("comprehensive_score", details)
        self.assertIn("fundamental_score", details)
        self.assertIn("technical_score", details)
        self.assertIn("momentum_score", details)
        self.assertIn("sector_score", details)
        self.assertIn("weights_used", details)
    
    def test_compare_with_sector(self):
        """섹터 비교 테스트"""
        comparison = self.engine.compare_with_sector(self.test_stock_data)
        
        self.assertIsInstance(comparison, dict)
        self.assertIn("sector", comparison)
        self.assertIn("vs_sector_average", comparison)
        self.assertIn("recommendation", comparison)
        
        # 섹터 평균 대비 비교 검증
        vs_sector = comparison["vs_sector_average"]
        for metric in ["roe", "per", "pbr", "debt_ratio", "revenue_growth"]:
            if metric in vs_sector:
                self.assertIn("stock_value", vs_sector[metric])
                self.assertIn("sector_average", vs_sector[metric])
                self.assertIn("ratio", vs_sector[metric])
    
    def test_set_weights(self):
        """가중치 설정 테스트"""
        new_weights = EvaluationWeights(
            fundamental=0.5,
            technical=0.25,
            momentum=0.15,
            sector=0.1
        )
        
        success = self.engine.set_weights(new_weights)
        self.assertTrue(success)
        
        # 잘못된 가중치 (합계가 1.0이 아님)
        invalid_weights = EvaluationWeights(
            fundamental=0.6,
            technical=0.3,
            momentum=0.2,
            sector=0.1
        )
        
        success = self.engine.set_weights(invalid_weights)
        self.assertFalse(success)
    
    def test_update_market_condition(self):
        """시장 상황 업데이트 테스트"""
        market_condition = MarketCondition(
            volatility_index=30.0,
            market_trend="상승",
            interest_rate=3.5,
            economic_indicator="양호"
        )
        
        # 예외 없이 실행되는지 확인
        self.engine.update_market_condition(market_condition)
        
        # 시장 상황이 반영된 점수 계산
        score1, _ = self.engine.calculate_comprehensive_score(self.test_stock_data)
        
        # 다른 시장 상황으로 변경
        market_condition.market_trend = "하락"
        market_condition.volatility_index = 40.0
        self.engine.update_market_condition(market_condition)
        
        score2, _ = self.engine.calculate_comprehensive_score(self.test_stock_data)
        
        # 점수가 변경되었는지 확인 (시장 상황 반영)
        self.assertNotEqual(score1, score2)

class TestIntegration(unittest.TestCase):
    """통합 테스트 클래스"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.watchlist_file = os.path.join(self.temp_dir, "watchlist.json")
        self.config_file = os.path.join(self.temp_dir, "config.json")
        
        self.screener = StockScreener()
        self.manager = WatchlistManager(self.watchlist_file)
        self.engine = EvaluationEngine(self.config_file)
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    def test_full_workflow(self):
        """전체 워크플로우 테스트"""
        # 1. 스크리닝 실행
        test_stocks = ["005930", "000660"]
        
        with patch.object(self.screener, '_fetch_stock_data') as mock_fetch:
            mock_fetch.return_value = {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "sector": "반도체",
                "roe": 18.5,
                "per": 12.3,
                "pbr": 1.1,
                "debt_ratio": 45.2,
                "revenue_growth": 15.8,
                "operating_margin": 12.3,
                "current_price": 56800,
                "ma_20": 55000,
                "ma_60": 54000,
                "ma_120": 53000,
                "rsi": 45.2,
                "volume_ratio": 1.8,
                "price_momentum_1m": 5.2,
                "volatility": 0.25,
                "relative_strength": 0.1,
                "price_momentum_3m": 8.3,
                "price_momentum_6m": 15.7,
                "volume_momentum": 0.2,
                "sector_momentum": 0.05
            }
            
            screening_results = self.screener.comprehensive_screening(test_stocks)
            
            self.assertEqual(len(screening_results), 2)
            
            # 2. 통과한 종목을 감시 리스트에 추가
            for result in screening_results:
                if getattr(result, "overall_passed", False):
                    success = self.manager.add_stock_legacy(
                        p_stock_code=getattr(result, "stock_code", ""),
                        p_stock_name=getattr(result, "stock_name", ""),
                        p_added_reason="스크리닝 통과",
                        p_target_price=70000,
                        p_stop_loss=50000,
                        p_sector=getattr(result, "sector", "기타"),
                        p_screening_score=getattr(result, "overall_score", 0.0)
                    )
                    self.assertTrue(success)
            
            # 3. 감시 리스트 조회
            watchlist_stocks = self.manager.list_stocks()
            self.assertGreaterEqual(len(watchlist_stocks), 0)
            
            # 4. 평가 엔진으로 재평가
            for stock in watchlist_stocks:
                stock_data = mock_fetch.return_value
                stock_data["stock_code"] = stock.stock_code
                
                score, details = self.engine.calculate_comprehensive_score(stock_data)
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 100.0)

if __name__ == '__main__':
    # 테스트 실행
    unittest.main(verbosity=2) 