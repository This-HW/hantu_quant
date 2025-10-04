#!/usr/bin/env python3
"""
Phase 2 종합 테스트
가격 매력도 분석, 일일 업데이트, 선정 기준 관리, CLI 워크플로우 통합 테스트
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.daily_selection.price_analyzer import PriceAnalyzer, PriceAttractiveness, TechnicalIndicators
from core.daily_selection.daily_updater import DailyUpdater, FilteringCriteria, DailySelection
from core.daily_selection.selection_criteria import SelectionCriteriaManager, MarketCondition, SelectionCriteria
from workflows.phase2_daily_selection import Phase2CLI
from core.watchlist.watchlist_manager import WatchlistManager, WatchlistStock

class TestTechnicalIndicators(unittest.TestCase):
    """기술적 지표 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.indicators = TechnicalIndicators()
        self.sample_prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109]
        self.sample_highs = [p * 1.02 for p in self.sample_prices]
        self.sample_lows = [p * 0.98 for p in self.sample_prices]
        self.sample_volumes = [1000000 + i * 10000 for i in range(len(self.sample_prices))]
    
    def test_bollinger_bands_calculation(self):
        """볼린저 밴드 계산 테스트"""
        upper, middle, lower = self.indicators.calculate_bollinger_bands(self.sample_prices)
        
        self.assertGreater(upper, middle)
        self.assertGreater(middle, lower)
        self.assertIsInstance(float(upper), float)
        self.assertIsInstance(float(middle), float)
        self.assertIsInstance(float(lower), float)
    
    def test_macd_calculation(self):
        """MACD 계산 테스트"""
        macd, signal, histogram = self.indicators.calculate_macd(self.sample_prices)
        
        self.assertIsInstance(macd, float)
        self.assertIsInstance(signal, float)
        self.assertIsInstance(histogram, float)
        self.assertAlmostEqual(histogram, macd - signal, places=5)
    
    def test_rsi_calculation(self):
        """RSI 계산 테스트"""
        rsi = self.indicators.calculate_rsi(self.sample_prices)
        
        self.assertIsInstance(rsi, float)
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
    
    def test_stochastic_calculation(self):
        """스토캐스틱 계산 테스트"""
        k, d = self.indicators.calculate_stochastic(
            self.sample_highs, self.sample_lows, self.sample_prices
        )
        
        self.assertIsInstance(k, float)
        self.assertIsInstance(d, float)
        self.assertGreaterEqual(k, 0)
        self.assertLessEqual(k, 100)
        self.assertGreaterEqual(d, 0)
        self.assertLessEqual(d, 100)
    
    def test_cci_calculation(self):
        """CCI 계산 테스트"""
        cci = self.indicators.calculate_cci(
            self.sample_highs, self.sample_lows, self.sample_prices
        )
        
        self.assertIsInstance(cci, float)
    
    def test_empty_data_handling(self):
        """빈 데이터 처리 테스트"""
        empty_prices = []
        
        upper, middle, lower = self.indicators.calculate_bollinger_bands(empty_prices)
        self.assertEqual(upper, 0.0)
        self.assertEqual(middle, 0.0)
        self.assertEqual(lower, 0.0)
        
        rsi = self.indicators.calculate_rsi(empty_prices)
        self.assertEqual(rsi, 50.0)

class TestPriceAnalyzer(unittest.TestCase):
    """가격 분석기 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.analyzer = PriceAnalyzer()
        self.sample_stock_data = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "current_price": 56800,
            "sector": "반도체",
            "market_cap": 450000000000000,
            "volatility": 0.25,
            "sector_momentum": 0.05
        }
    
    def test_price_attractiveness_analysis(self):
        """가격 매력도 분석 테스트"""
        result = self.analyzer.analyze_price_attractiveness(self.sample_stock_data)
        
        self.assertIsInstance(result, PriceAttractiveness)
        self.assertEqual(result.stock_code, "005930")
        self.assertEqual(result.stock_name, "삼성전자")
        self.assertGreater(result.total_score, 0)
        self.assertLessEqual(result.total_score, 100)
        self.assertGreater(result.target_price, result.entry_price)
        self.assertLess(result.stop_loss, result.entry_price)
        self.assertGreaterEqual(result.confidence, 0)
        self.assertLessEqual(result.confidence, 1)
    
    def test_multiple_stocks_analysis(self):
        """여러 종목 일괄 분석 테스트"""
        stock_list = [
            self.sample_stock_data,
            {
                "stock_code": "000660",
                "stock_name": "SK하이닉스",
                "current_price": 89000,
                "sector": "반도체",
                "market_cap": 65000000000000,
                "volatility": 0.30,
                "sector_momentum": 0.03
            }
        ]
        
        results = self.analyzer.analyze_multiple_stocks(stock_list)
        
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], PriceAttractiveness)
        self.assertIsInstance(results[1], PriceAttractiveness)
        self.assertEqual(results[0].stock_code, "005930")
        self.assertEqual(results[1].stock_code, "000660")
    
    def test_analysis_result_serialization(self):
        """분석 결과 직렬화 테스트"""
        result = self.analyzer.analyze_price_attractiveness(self.sample_stock_data)
        result_dict = result.to_dict()
        
        self.assertIsInstance(result_dict, dict)
        self.assertIn("stock_code", result_dict)
        self.assertIn("total_score", result_dict)
        self.assertIn("technical_signals", result_dict)
    
    def test_save_analysis_results(self):
        """분석 결과 저장 테스트"""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.analyzer.analyze_price_attractiveness(self.sample_stock_data)
            file_path = os.path.join(temp_dir, "test_analysis.json")
            
            success = self.analyzer.save_analysis_results([result], file_path)
            
            self.assertTrue(success)
            self.assertTrue(os.path.exists(file_path))
            
            with open(file_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            self.assertIn("results", saved_data)
            self.assertEqual(len(saved_data["results"]), 1)
            self.assertEqual(saved_data["results"][0]["stock_code"], "005930")

class TestDailyUpdater(unittest.TestCase):
    """일일 업데이터 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.watchlist_file = os.path.join(self.temp_dir, "watchlist.json")
        self.output_dir = os.path.join(self.temp_dir, "daily_selection")
        
        # 테스트용 감시 리스트 생성
        self._create_test_watchlist()
        
        self.updater = DailyUpdater(self.watchlist_file, self.output_dir)
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    def _create_test_watchlist(self):
        """테스트용 감시 리스트 생성"""
        # WatchlistManager 형식에 맞는 데이터 구조 생성
        os.makedirs(os.path.dirname(self.watchlist_file), exist_ok=True)
        
        # WatchlistManager를 사용하여 종목 추가
        watchlist_manager = WatchlistManager(self.watchlist_file)
        
        # 테스트 종목들 추가
        test_stocks = [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "sector": "반도체",
                "market_cap": 450000000000000,
                "current_price": 56800,
                "pe_ratio": 12.5,
                "pb_ratio": 0.8,
                "roe": 18.5,
                "debt_ratio": 25.3,
                "dividend_yield": 2.1,
                "volume_avg": 15000000,
                "beta": 1.2,
                "momentum_score": 75.5,
                "volatility": 0.25,
                "liquidity_score": 85.0,
                "technical_score": 72.3,
                "fundamental_score": 68.9,
                "relative_strength": 1.15,
                "analyst_rating": 4.2,
                "target_price": 65000,
                "notes": "테스트용 종목"
            },
            {
                "stock_code": "000660",
                "stock_name": "SK하이닉스",
                "sector": "반도체",
                "market_cap": 65000000000000,
                "current_price": 89000,
                "pe_ratio": 15.2,
                "pb_ratio": 1.1,
                "roe": 15.3,
                "debt_ratio": 32.1,
                "dividend_yield": 1.8,
                "volume_avg": 8000000,
                "beta": 1.5,
                "momentum_score": 68.2,
                "volatility": 0.30,
                "liquidity_score": 78.5,
                "technical_score": 65.8,
                "fundamental_score": 62.4,
                "relative_strength": 1.08,
                "analyst_rating": 3.8,
                "target_price": 95000,
                "notes": "테스트용 종목"
            }
        ]
        
        for stock_data in test_stocks:
            watchlist_manager.add_stock_legacy(
                p_stock_code=stock_data["stock_code"],
                p_stock_name=stock_data["stock_name"],
                p_added_reason="테스트용 종목",
                p_target_price=stock_data["target_price"],
                p_stop_loss=stock_data["current_price"] * 0.9,  # 10% 손절
                p_sector=stock_data["sector"],
                p_screening_score=stock_data["fundamental_score"],
                p_notes=stock_data["notes"]
            )
    
    def test_daily_update_execution(self):
        """일일 업데이트 실행 테스트"""
        success = self.updater.run_daily_update(p_force_run=True)
        
        self.assertTrue(success)
        
        # 결과 파일 확인
        latest_file = os.path.join(self.output_dir, "latest_selection.json")
        self.assertTrue(os.path.exists(latest_file))
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            latest_data = json.load(f)
        
        self.assertIn("data", latest_data)
        self.assertIn("selected_stocks", latest_data["data"])
        self.assertIn("metadata", latest_data)
    
    def test_filtering_criteria_adjustment(self):
        """필터링 기준 조정 테스트"""
        # 상승장 기준 조정
        self.updater._adjust_criteria_by_market("bull_market")
        self.assertEqual(self.updater._v_criteria.price_attractiveness, 65.0)
        self.assertEqual(self.updater._v_criteria.total_limit, 20)
        
        # 하락장 기준 조정
        self.updater._adjust_criteria_by_market("bear_market")
        self.assertEqual(self.updater._v_criteria.price_attractiveness, 80.0)
        self.assertEqual(self.updater._v_criteria.total_limit, 10)
    
    def test_latest_selection_retrieval(self):
        """최신 선정 결과 조회 테스트"""
        # 업데이트 실행
        self.updater.run_daily_update(p_force_run=True)
        
        # 최신 결과 조회
        latest = self.updater.get_latest_selection()
        
        self.assertIsNotNone(latest)
        self.assertIn("market_date", latest)
        self.assertIn("data", latest)
    
    def test_selection_history_retrieval(self):
        """선정 이력 조회 테스트"""
        # 업데이트 실행
        self.updater.run_daily_update(p_force_run=True)
        
        # 이력 조회
        history = self.updater.get_selection_history(7)
        
        self.assertIsInstance(history, list)
        self.assertGreaterEqual(len(history), 1)
    
    def test_scheduler_lifecycle(self):
        """스케줄러 생명주기 테스트"""
        # 스케줄러 시작
        self.updater.start_scheduler()
        self.assertTrue(self.updater._v_scheduler_running)
        
        # 스케줄러 중지
        self.updater.stop_scheduler()
        self.assertFalse(self.updater._v_scheduler_running)

class TestSelectionCriteriaManager(unittest.TestCase):
    """선정 기준 관리자 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SelectionCriteriaManager(self.temp_dir)
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    def test_default_criteria_creation(self):
        """기본 기준 생성 테스트"""
        criteria = self.manager.get_criteria(MarketCondition.BULL_MARKET)
        
        self.assertIsInstance(criteria, SelectionCriteria)
        self.assertEqual(criteria.market_condition, MarketCondition.BULL_MARKET)
        self.assertGreater(criteria.max_stocks, 0)
        self.assertGreater(criteria.price_attractiveness.optimal_value, 0)
    
    def test_criteria_update(self):
        """기준 업데이트 테스트"""
        # 기본 기준 조회
        original_criteria = self.manager.get_criteria(MarketCondition.SIDEWAYS)
        original_max_stocks = original_criteria.max_stocks
        
        # 기준 수정
        modified_criteria = original_criteria
        modified_criteria.max_stocks = 25
        
        # 업데이트
        self.manager.update_criteria(MarketCondition.SIDEWAYS, modified_criteria)
        
        # 확인
        updated_criteria = self.manager.get_criteria(MarketCondition.SIDEWAYS)
        self.assertEqual(updated_criteria.max_stocks, 25)
        self.assertNotEqual(updated_criteria.max_stocks, original_max_stocks)
    
    def test_custom_criteria_creation(self):
        """사용자 정의 기준 생성 테스트"""
        custom_criteria = self.manager.create_custom_criteria(
            "테스트_기준",
            "테스트용 사용자 정의 기준",
            MarketCondition.VOLATILE,
            {
                "max_stocks": 8,
                "max_sector_stocks": 2
            }
        )
        
        self.assertEqual(custom_criteria.name, "테스트_기준")
        self.assertEqual(custom_criteria.max_stocks, 8)
        self.assertEqual(custom_criteria.max_sector_stocks, 2)
        self.assertEqual(custom_criteria.market_condition, MarketCondition.VOLATILE)
    
    def test_criteria_serialization(self):
        """기준 직렬화 테스트"""
        criteria = self.manager.get_criteria(MarketCondition.BULL_MARKET)
        
        # 딕셔너리 변환
        criteria_dict = criteria.to_dict()
        self.assertIsInstance(criteria_dict, dict)
        self.assertIn("name", criteria_dict)
        self.assertIn("market_condition", criteria_dict)
        
        # 딕셔너리에서 복원
        restored_criteria = SelectionCriteria.from_dict(criteria_dict)
        self.assertEqual(restored_criteria.name, criteria.name)
        self.assertEqual(restored_criteria.market_condition, criteria.market_condition)
    
    def test_criteria_performance_evaluation(self):
        """기준 성과 평가 테스트"""
        historical_data = [{"date": "2024-01-01", "return": 0.05}] * 100
        
        performance = self.manager.evaluate_criteria_performance(
            MarketCondition.BULL_MARKET, historical_data
        )
        
        self.assertGreaterEqual(performance.win_rate, 0)
        self.assertLessEqual(performance.win_rate, 1)
        self.assertIsInstance(performance.total_trades, int)
        self.assertIsInstance(performance.avg_return, float)
    
    def test_criteria_summary(self):
        """기준 요약 테스트"""
        summary = self.manager.get_criteria_summary()
        
        self.assertIn("total_criteria", summary)
        self.assertIn("market_conditions", summary)
        self.assertIn("criteria_details", summary)
        self.assertGreater(summary["total_criteria"], 0)

class TestPhase2CLI(unittest.TestCase):
    """Phase 2 CLI 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.cli = Phase2CLI()
        
        # 테스트용 감시 리스트 생성
        self._create_test_watchlist()
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    def _create_test_watchlist(self):
        """테스트용 감시 리스트 생성"""
        watchlist_file = "data/watchlist/watchlist.json"
        os.makedirs(os.path.dirname(watchlist_file), exist_ok=True)
        
        # WatchlistManager를 사용하여 종목 추가
        watchlist_manager = WatchlistManager(watchlist_file)
        
        stock_data = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "sector": "반도체",
            "market_cap": 450000000000000,
            "current_price": 56800,
            "pe_ratio": 12.5,
            "pb_ratio": 0.8,
            "roe": 18.5,
            "debt_ratio": 25.3,
            "dividend_yield": 2.1,
            "volume_avg": 15000000,
            "beta": 1.2,
            "momentum_score": 75.5,
            "volatility": 0.25,
            "liquidity_score": 85.0,
            "technical_score": 72.3,
            "fundamental_score": 68.9,
            "relative_strength": 1.15,
            "analyst_rating": 4.2,
            "target_price": 65000,
            "notes": "테스트용 종목"
        }
        
        watchlist_manager.add_stock_legacy(
            p_stock_code=stock_data["stock_code"],
            p_stock_name=stock_data["stock_name"],
            p_added_reason="테스트용 종목",
            p_target_price=stock_data["target_price"],
            p_stop_loss=stock_data["current_price"] * 0.9,  # 10% 손절
            p_sector=stock_data["sector"],
            p_screening_score=stock_data["fundamental_score"],
            p_notes=stock_data["notes"]
        )
    
    def test_single_stock_analysis(self):
        """단일 종목 분석 테스트"""
        result = self.cli._analyze_single_stock("005930")
        
        self.assertIsInstance(result, PriceAttractiveness)
        self.assertEqual(result.stock_code, "005930")
        self.assertEqual(result.stock_name, "삼성전자")
    
    def test_all_stocks_analysis(self):
        """전체 종목 분석 테스트"""
        results = self.cli._analyze_all_stocks()
        
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        self.assertIsInstance(results[0], PriceAttractiveness)
    
    def test_historical_data_retrieval(self):
        """과거 데이터 조회 테스트"""
        historical_data = self.cli._get_historical_data()
        
        self.assertIsInstance(historical_data, list)
        self.assertGreater(len(historical_data), 0)
    
    def test_performance_data_collection(self):
        """성과 데이터 수집 테스트"""
        performance_data = self.cli._collect_performance_data(30)
        
        self.assertIsInstance(performance_data, dict)
        self.assertIn("period", performance_data)
        self.assertIn("total_trades", performance_data)
        self.assertIn("win_rate", performance_data)
    
    def test_scheduler_status_retrieval(self):
        """스케줄러 상태 조회 테스트"""
        status = self.cli._get_scheduler_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn("running", status)
        self.assertIn("status", status)

class TestPhase2Integration(unittest.TestCase):
    """Phase 2 통합 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.watchlist_file = os.path.join(self.temp_dir, "watchlist.json")
        self.output_dir = os.path.join(self.temp_dir, "daily_selection")
        
        # 테스트용 감시 리스트 생성
        self._create_test_watchlist()
        
        # 컴포넌트 초기화
        self.price_analyzer = PriceAnalyzer()
        self.daily_updater = DailyUpdater(self.watchlist_file, self.output_dir)
        self.criteria_manager = SelectionCriteriaManager(os.path.join(self.temp_dir, "criteria"))
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    def _create_test_watchlist(self):
        """테스트용 감시 리스트 생성"""
        os.makedirs(os.path.dirname(self.watchlist_file), exist_ok=True)
        
        # WatchlistManager를 사용하여 종목 추가
        watchlist_manager = WatchlistManager(self.watchlist_file)
        
        test_stocks = [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "sector": "반도체",
                "market_cap": 450000000000000,
                "current_price": 56800,
                "pe_ratio": 12.5,
                "pb_ratio": 0.8,
                "roe": 18.5,
                "debt_ratio": 25.3,
                "dividend_yield": 2.1,
                "volume_avg": 15000000,
                "beta": 1.2,
                "momentum_score": 75.5,
                "volatility": 0.25,
                "liquidity_score": 85.0,
                "technical_score": 72.3,
                "fundamental_score": 68.9,
                "relative_strength": 1.15,
                "analyst_rating": 4.2,
                "target_price": 65000,
                "notes": "테스트용 종목"
            },
            {
                "stock_code": "000660",
                "stock_name": "SK하이닉스",
                "sector": "반도체",
                "market_cap": 65000000000000,
                "current_price": 89000,
                "pe_ratio": 15.2,
                "pb_ratio": 1.1,
                "roe": 15.3,
                "debt_ratio": 32.1,
                "dividend_yield": 1.8,
                "volume_avg": 8000000,
                "beta": 1.5,
                "momentum_score": 68.2,
                "volatility": 0.30,
                "liquidity_score": 78.5,
                "technical_score": 65.8,
                "fundamental_score": 62.4,
                "relative_strength": 1.08,
                "analyst_rating": 3.8,
                "target_price": 95000,
                "notes": "테스트용 종목"
            },
            {
                "stock_code": "035420",
                "stock_name": "NAVER",
                "sector": "인터넷",
                "market_cap": 30000000000000,
                "current_price": 180000,
                "pe_ratio": 18.7,
                "pb_ratio": 1.3,
                "roe": 12.8,
                "debt_ratio": 15.6,
                "dividend_yield": 0.8,
                "volume_avg": 3000000,
                "beta": 1.1,
                "momentum_score": 62.5,
                "volatility": 0.28,
                "liquidity_score": 75.2,
                "technical_score": 58.9,
                "fundamental_score": 55.7,
                "relative_strength": 0.95,
                "analyst_rating": 3.5,
                "target_price": 190000,
                "notes": "테스트용 종목"
            }
        ]
        
        for stock_data in test_stocks:
            watchlist_manager.add_stock_legacy(
                p_stock_code=stock_data["stock_code"],
                p_stock_name=stock_data["stock_name"],
                p_added_reason="테스트용 종목",
                p_target_price=stock_data["target_price"],
                p_stop_loss=stock_data["current_price"] * 0.9,  # 10% 손절
                p_sector=stock_data["sector"],
                p_screening_score=stock_data["fundamental_score"],
                p_notes=stock_data["notes"]
            )
    
    def test_full_workflow_integration(self):
        """전체 워크플로우 통합 테스트"""
        # 1. 기준 설정
        criteria = self.criteria_manager.get_criteria(MarketCondition.BULL_MARKET)
        self.assertIsNotNone(criteria)
        
        # 2. 가격 분석 실행
        stock_data = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "current_price": 56800,
            "sector": "반도체",
            "market_cap": 450000000000000,
            "volatility": 0.25,
            "sector_momentum": 0.05
        }
        
        analysis_result = self.price_analyzer.analyze_price_attractiveness(stock_data)
        self.assertIsInstance(analysis_result, PriceAttractiveness)
        
        # 3. 일일 업데이트 실행
        update_success = self.daily_updater.run_daily_update(p_force_run=True)
        self.assertTrue(update_success)
        
        # 4. 결과 확인
        latest_selection = self.daily_updater.get_latest_selection()
        self.assertIsNotNone(latest_selection)
        self.assertIn("data", latest_selection)
        self.assertIn("selected_stocks", latest_selection["data"])
    
    def test_market_condition_adaptation(self):
        """시장 상황별 적응 테스트"""
        # 다양한 시장 상황에서 기준 조회
        bull_criteria = self.criteria_manager.get_criteria(MarketCondition.BULL_MARKET)
        bear_criteria = self.criteria_manager.get_criteria(MarketCondition.BEAR_MARKET)
        
        # 상승장과 하락장 기준이 다른지 확인
        self.assertNotEqual(bull_criteria.max_stocks, bear_criteria.max_stocks)
        self.assertNotEqual(
            bull_criteria.price_attractiveness.min_value,
            bear_criteria.price_attractiveness.min_value
        )
    
    def test_data_persistence(self):
        """데이터 지속성 테스트"""
        # 일일 업데이트 실행
        self.daily_updater.run_daily_update(p_force_run=True)
        
        # 파일 존재 확인
        latest_file = os.path.join(self.output_dir, "latest_selection.json")
        self.assertTrue(os.path.exists(latest_file))
        
        # 데이터 읽기 확인
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertIn("timestamp", data)
        self.assertIn("market_date", data)
        self.assertIn("data", data)
    
    def test_error_handling(self):
        """오류 처리 테스트"""
        # 잘못된 종목 데이터로 분석 시도
        invalid_stock_data = {
            "stock_code": "INVALID",
            "stock_name": "잘못된종목",
            "current_price": -1000,  # 음수 가격
            "sector": "",
            "market_cap": 0,
            "volatility": -0.5,  # 음수 변동성
            "sector_momentum": 10.0  # 비현실적인 모멘텀
        }
        
        # 분석이 실패하지 않고 기본값을 반환하는지 확인
        result = self.price_analyzer.analyze_price_attractiveness(invalid_stock_data)
        self.assertIsInstance(result, PriceAttractiveness)
        self.assertEqual(result.stock_code, "INVALID")
    
    def test_performance_monitoring(self):
        """성과 모니터링 테스트"""
        # 일일 업데이트 실행
        self.daily_updater.run_daily_update(p_force_run=True)
        
        # 성과 데이터 확인
        latest_result = self.daily_updater.get_latest_selection()
        metadata = latest_result.get("metadata", {})
        
        self.assertIn("total_selected", metadata)
        self.assertIn("selection_rate", metadata)
        self.assertIn("avg_attractiveness", metadata)
        self.assertIn("sector_distribution", metadata)
    
    def test_concurrent_operations(self):
        """동시 작업 테스트"""
        import threading
        
        results = []
        errors = []
        
        def analyze_stock(stock_code):
            try:
                stock_data = {
                    "stock_code": stock_code,
                    "stock_name": f"테스트{stock_code}",
                    "current_price": 50000,
                    "sector": "테스트",
                    "market_cap": 1000000000000,
                    "volatility": 0.25,
                    "sector_momentum": 0.05
                }
                result = self.price_analyzer.analyze_price_attractiveness(stock_data)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # 여러 스레드에서 동시 분석
        threads = []
        for i in range(5):
            thread = threading.Thread(target=analyze_stock, args=(f"TEST{i:03d}",))
            threads.append(thread)
            thread.start()
        
        # 모든 스레드 완료 대기
        for thread in threads:
            thread.join()
        
        # 결과 확인
        self.assertEqual(len(results), 5)
        self.assertEqual(len(errors), 0)

def run_phase2_tests():
    """Phase 2 테스트 실행"""
    # 테스트 스위트 생성
    test_suite = unittest.TestSuite()
    
    # 개별 테스트 클래스 추가
    test_classes = [
        TestTechnicalIndicators,
        TestPriceAnalyzer,
        TestDailyUpdater,
        TestSelectionCriteriaManager,
        TestPhase2CLI,
        TestPhase2Integration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 테스트 실행
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 2 종합 테스트 시작")
    print("=" * 60)
    
    success = run_phase2_tests()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 모든 Phase 2 테스트 통과!")
    else:
        print("❌ 일부 Phase 2 테스트 실패")
    print("=" * 60) 