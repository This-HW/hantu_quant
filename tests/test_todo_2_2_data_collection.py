#!/usr/bin/env python3
"""
TODO 2.2 데이터 수집 및 전처리 시스템 테스트
"""

import unittest
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces.learning import LearningData
from core.learning.data.collector import LearningDataCollector
from core.learning.data.preprocessor import LearningDataPreprocessor
from core.learning.data.backfill import LearningDataBackfill
from core.learning.config.settings import LearningConfig


class TestTodo22DataCollection(unittest.TestCase):
    """TODO 2.2 데이터 수집 및 전처리 시스템 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.test_dir = tempfile.mkdtemp()
        self.config = LearningConfig()
        self.config.data.data_dir = self.test_dir
        
        # 테스트 데이터 준비
        self._setup_test_data()
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def _setup_test_data(self):
        """테스트 데이터 설정"""
        # 테스트용 watchlist 데이터
        self.watchlist_dir = Path(self.test_dir) / "watchlist"
        self.watchlist_dir.mkdir(parents=True, exist_ok=True)
        
        self.daily_selection_dir = Path(self.test_dir) / "daily_selection"
        self.daily_selection_dir.mkdir(parents=True, exist_ok=True)
        
        # 샘플 Phase 1 데이터
        self.phase1_sample = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "sector": "반도체",
            "overall_score": 75.5,
            "fundamental_score": 80.0,
            "technical_score": 70.0,
            "momentum_score": 76.0,
            "overall_passed": True,
            "details": {
                "fundamental": {"roe": 15.5, "per": 12.0},
                "technical": {"rsi": 55.0, "macd": "buy"},
                "momentum": {"price_momentum_1m": 8.5}
            }
        }
        
        # 샘플 Phase 2 데이터
        self.phase2_sample = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "price_attractiveness": 82.0,
            "technical_score": 78.0,
            "volume_score": 85.0,
            "pattern_score": 72.0,
            "entry_price": 68000,
            "target_price": 75000,
            "stop_loss": 62000,
            "risk_score": 25.0,
            "confidence": 0.85,
            "selection_reason": "기술적 돌파 + 높은 거래량"
        }
    
    def test_data_collector_initialization(self):
        """데이터 수집기 초기화 테스트"""
        collector = LearningDataCollector()
        
        self.assertIsNotNone(collector._config)
        self.assertIsNotNone(collector._storage)
        self.assertIsNotNone(collector._logger)
        self.assertTrue(collector._project_root.exists())
    
    def test_collect_phase1_results(self):
        """Phase 1 결과 수집 테스트"""
        collector = LearningDataCollector()
        
        # 테스트 디렉토리로 경로 변경
        collector._watchlist_dir = self.watchlist_dir
        
        # 테스트 데이터 생성
        test_date = "2024-01-15"
        test_file = self.watchlist_dir / f"screening_results_{test_date}.json"
        
        test_data = {
            "timestamp": datetime.now().isoformat(),
            "results": [self.phase1_sample]
        }
        
        with open(test_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        
        # 수집 테스트
        results = collector.collect_phase1_results(test_date)
        
        self.assertGreater(len(results), 0)
        
        # 예상 데이터 확인
        found_sample = False
        for result in results:
            if result.get("stock_code") == "005930" and result.get("overall_score") == 75.5:
                found_sample = True
                break
        
        self.assertTrue(found_sample, "테스트 데이터를 찾을 수 없습니다")
    
    def test_collect_phase2_results(self):
        """Phase 2 결과 수집 테스트"""
        collector = LearningDataCollector()
        
        # 테스트 디렉토리로 경로 변경
        collector._daily_selection_dir = self.daily_selection_dir
        
        # 테스트 데이터 생성
        test_date = "2024-01-15"
        test_file = self.daily_selection_dir / f"daily_selection_{test_date}.json"
        
        test_data = {
            "timestamp": datetime.now().isoformat(),
            "data": {
                "selected_stocks": [self.phase2_sample]
            }
        }
        
        with open(test_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        
        # 수집 테스트
        results = collector.collect_phase2_results(test_date)
        
        self.assertGreater(len(results), 0)
        
        # 예상 데이터 확인
        found_sample = False
        for result in results:
            if result.get("stock_code") == "005930" and result.get("price_attractiveness") == 82.0:
                found_sample = True
                break
        
        self.assertTrue(found_sample, "테스트 데이터를 찾을 수 없습니다")
    
    def test_collect_actual_performance(self):
        """실제 성과 데이터 수집 테스트"""
        collector = LearningDataCollector()
        
        stock_codes = ["005930", "000660"]
        start_date = "2024-01-15"
        end_date = "2024-01-22"
        
        # 성과 데이터 수집
        performance_data = collector.collect_actual_performance(stock_codes, start_date, end_date)
        
        self.assertEqual(len(performance_data), 2)
        self.assertIn("005930", performance_data)
        self.assertIn("000660", performance_data)
        
        # 각 종목 성과 데이터 검증
        for stock_code, perf_data in performance_data.items():
            self.assertIn("7d_return", perf_data)
            self.assertIn("volatility", perf_data)
            self.assertIn("max_drawdown", perf_data)
            self.assertIsInstance(perf_data["7d_return"], float)
    
    def test_validate_data_quality(self):
        """데이터 품질 검증 테스트"""
        collector = LearningDataCollector()
        
        # 테스트 데이터 생성
        test_data = [
            LearningData(
                stock_code="005930",
                stock_name="삼성전자",
                date="2024-01-15",
                phase1_data=self.phase1_sample,
                phase2_data=self.phase2_sample,
                actual_performance={"7d_return": 0.05, "volatility": 0.25},
                market_condition="bull_market"
            ),
            LearningData(
                stock_code="",  # 잘못된 데이터
                stock_name="",
                date="2024-01-15",
                phase1_data={},
                phase2_data={},
                actual_performance=None,
                market_condition="neutral"
            )
        ]
        
        # 품질 검증
        quality_report = collector.validate_data_quality(test_data)
        
        self.assertEqual(quality_report["total_records"], 2)
        self.assertEqual(quality_report["valid_records"], 1)
        self.assertEqual(quality_report["invalid_records"], 1)
        self.assertEqual(quality_report["quality_score"], 0.5)
    
    def test_data_preprocessor_initialization(self):
        """데이터 전처리기 초기화 테스트"""
        preprocessor = LearningDataPreprocessor()
        
        self.assertIsNotNone(preprocessor._config)
        self.assertIsNotNone(preprocessor._storage)
        self.assertIsNotNone(preprocessor._logger)
        self.assertIsInstance(preprocessor._scalers, dict)
        self.assertIsInstance(preprocessor._imputers, dict)
    
    def test_data_preprocessing(self):
        """데이터 전처리 테스트"""
        preprocessor = LearningDataPreprocessor()
        
        # 테스트 데이터 생성 (일부 결측치 포함)
        test_data = [
            LearningData(
                stock_code="005930",
                stock_name="삼성전자",
                date="2024-01-15",
                phase1_data=self.phase1_sample,
                phase2_data=self.phase2_sample,
                actual_performance={"7d_return": 0.05, "volatility": 0.25},
                market_condition="bull_market"
            ),
            LearningData(
                stock_code="000660",
                stock_name=" SK하이닉스 ",  # 공백 포함
                date="2024-01-15",
                phase1_data={},  # 빈 데이터
                phase2_data={"price_attractiveness": 65.0},
                actual_performance=None,
                market_condition="NEUTRAL"  # 대문자
            )
        ]
        
        # 전처리 실행
        processed_data = preprocessor.preprocess_learning_data(test_data)
        
        # 결과 검증
        self.assertEqual(len(processed_data), 2)
        
        # 첫 번째 데이터 (정상)
        self.assertEqual(processed_data[0].stock_code, "005930")
        self.assertEqual(processed_data[0].stock_name, "삼성전자")
        
        # 두 번째 데이터 (전처리됨)
        self.assertEqual(processed_data[1].stock_code, "000660")
        self.assertEqual(processed_data[1].stock_name, "SK하이닉스")  # 공백 제거
        self.assertEqual(processed_data[1].market_condition, "neutral")  # 소문자 변환
    
    def test_backfill_system_initialization(self):
        """백필 시스템 초기화 테스트"""
        backfill = LearningDataBackfill()
        
        self.assertIsNotNone(backfill._config)
        self.assertIsNotNone(backfill._storage)
        self.assertIsNotNone(backfill._collector)
        self.assertIsNotNone(backfill._preprocessor)
        self.assertFalse(backfill._backfill_status["is_running"])
    
    def test_backfill_plan_creation(self):
        """백필 계획 수립 테스트"""
        backfill = LearningDataBackfill()
        
        start_date = "2024-01-15"
        end_date = "2024-01-19"  # 평일 5일
        stock_codes = ["005930", "000660"]
        
        # 계획 수립
        plan = backfill._create_backfill_plan(start_date, end_date, stock_codes)
        
        self.assertEqual(plan["start_date"], start_date)
        self.assertEqual(plan["end_date"], end_date)
        self.assertEqual(len(plan["stock_codes"]), 2)
        self.assertEqual(plan["total_dates"], 5)  # 주말 제외
        self.assertEqual(plan["total_combinations"], 10)  # 5일 × 2종목
    
    def test_backfill_time_estimation(self):
        """백필 시간 추정 테스트"""
        backfill = LearningDataBackfill()
        
        start_date = "2024-01-15"
        end_date = "2024-01-19"
        stock_codes = ["005930", "000660"]
        
        # 시간 추정
        estimation = backfill.estimate_backfill_time(start_date, end_date, stock_codes)
        
        self.assertIn("total_dates", estimation)
        self.assertIn("total_combinations", estimation)
        self.assertIn("estimated_seconds", estimation)
        self.assertIn("estimated_minutes", estimation)
        self.assertIn("estimated_hours", estimation)
        self.assertIn("completion_time", estimation)
        
        self.assertEqual(estimation["total_dates"], 5)
        self.assertEqual(estimation["total_combinations"], 10)
        self.assertGreater(estimation["estimated_seconds"], 0)
    
    def test_backfill_status_management(self):
        """백필 상태 관리 테스트"""
        backfill = LearningDataBackfill()
        
        # 초기 상태 확인
        initial_status = backfill.get_backfill_status()
        self.assertFalse(initial_status["is_running"])
        self.assertEqual(initial_status["progress"], 0.0)
        
        # 상태 업데이트 시뮬레이션
        with backfill._lock:
            backfill._backfill_status["is_running"] = True
            backfill._backfill_status["progress"] = 0.5
            backfill._backfill_status["current_date"] = "2024-01-15"
        
        # 업데이트된 상태 확인
        updated_status = backfill.get_backfill_status()
        self.assertTrue(updated_status["is_running"])
        self.assertEqual(updated_status["progress"], 0.5)
        self.assertEqual(updated_status["current_date"], "2024-01-15")
    
    def test_end_to_end_data_flow(self):
        """종단 간 데이터 플로우 테스트"""
        # 1. 데이터 수집
        collector = LearningDataCollector()
        
        # 테스트 디렉토리로 경로 변경
        collector._watchlist_dir = self.watchlist_dir
        collector._daily_selection_dir = self.daily_selection_dir
        
        # 테스트 데이터 생성
        test_date = "2024-01-15"
        self._create_test_files(test_date)
        
        # Phase 1, 2 결과 수집
        phase1_results = collector.collect_phase1_results(test_date)
        phase2_results = collector.collect_phase2_results(test_date)
        
        # 성과 데이터 수집
        performance_data = collector.collect_actual_performance(["005930"], test_date, test_date)
        
        # 데이터 병합
        merged_data = collector._merge_data(phase1_results, phase2_results, performance_data, test_date)
        
        # 2. 데이터 전처리
        preprocessor = LearningDataPreprocessor()
        processed_data = preprocessor.preprocess_learning_data(merged_data)
        
        # 3. 데이터 품질 검증
        quality_report = collector.validate_data_quality(processed_data)
        
        # 결과 검증
        self.assertGreater(len(processed_data), 0)
        self.assertGreater(quality_report["quality_score"], 0.0)
        
        # 데이터 구조 검증
        for data in processed_data:
            self.assertIsInstance(data, LearningData)
            self.assertTrue(data.stock_code)
            self.assertTrue(data.stock_name)
            self.assertTrue(data.date)
    
    def _create_test_files(self, test_date: str):
        """테스트 파일 생성"""
        import json
        
        # Phase 1 파일 생성
        phase1_file = self.watchlist_dir / f"screening_results_{test_date}.json"
        phase1_data = {
            "timestamp": datetime.now().isoformat(),
            "results": [self.phase1_sample]
        }
        
        with open(phase1_file, 'w', encoding='utf-8') as f:
            json.dump(phase1_data, f, ensure_ascii=False, indent=2)
        
        # Phase 2 파일 생성
        phase2_file = self.daily_selection_dir / f"daily_selection_{test_date}.json"
        phase2_data = {
            "timestamp": datetime.now().isoformat(),
            "data": {
                "selected_stocks": [self.phase2_sample]
            }
        }
        
        with open(phase2_file, 'w', encoding='utf-8') as f:
            json.dump(phase2_data, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    unittest.main() 