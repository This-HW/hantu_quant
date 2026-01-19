#!/usr/bin/env python3
"""
Phase 1, 2 모듈 리팩토링 테스트
새로운 아키텍처(인터페이스 기반, 플러그인)에 대한 테스트
"""

import pytest
import os
import sys
from datetime import datetime
from unittest.mock import patch

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces.trading import (
    IStockScreener, IWatchlistManager, IPriceAnalyzer, IDailyUpdater,
    ScreeningResult, WatchlistEntry, PriceAttractiveness, TechnicalSignal
)

class TestPhase1Refactoring:
    """Phase 1 리팩토링 테스트"""
    
    def test_stock_screener_interface_implementation(self):
        """StockScreener가 IStockScreener 인터페이스를 올바르게 구현하는지 테스트"""
        try:
            from core.watchlist.stock_screener import StockScreener
            
            # 인스턴스 생성
            screener = StockScreener()
            
            # 인터페이스 구현 확인
            assert isinstance(screener, IStockScreener)
            
            # 필수 메서드 존재 확인
            assert hasattr(screener, 'screen_by_fundamentals')
            assert hasattr(screener, 'screen_by_technical')
            assert hasattr(screener, 'screen_by_momentum')
            assert hasattr(screener, 'comprehensive_screening')
            
            # 플러그인 메타데이터 확인
            try:
                assert hasattr(screener, '_plugin_metadata')
                assert screener._plugin_metadata['name'] == 'stock_screener'
                assert screener._plugin_metadata['version'] == '1.0.0'
            except (AttributeError, KeyError):
                # 플러그인 시스템이 완전히 구축되지 않은 경우
                pass
            
        except ImportError:
            pytest.skip("StockScreener 모듈을 불러올 수 없습니다")
    
    def test_watchlist_manager_interface_implementation(self):
        """WatchlistManager가 IWatchlistManager 인터페이스를 올바르게 구현하는지 테스트"""
        try:
            from core.watchlist.watchlist_manager import WatchlistManager
            
            # 임시 파일 경로로 인스턴스 생성
            test_file = "test_watchlist.json"
            manager = WatchlistManager(test_file)
            
            # 인터페이스 구현 확인
            assert isinstance(manager, IWatchlistManager)
            
            # 필수 메서드 존재 확인
            assert hasattr(manager, 'add_stock')
            assert hasattr(manager, 'remove_stock')
            assert hasattr(manager, 'update_stock')
            assert hasattr(manager, 'get_stock')
            assert hasattr(manager, 'list_stocks')
            assert hasattr(manager, 'get_statistics')
            
            # 플러그인 메타데이터 확인
            assert hasattr(manager, '_plugin_metadata')
            assert manager._plugin_metadata['name'] == 'watchlist_manager'
            
            # 테스트 파일 정리
            if os.path.exists(test_file):
                os.remove(test_file)
                
        except ImportError:
            pytest.skip("WatchlistManager 모듈을 불러올 수 없습니다")
    
    def test_watchlist_entry_operations(self):
        """WatchlistEntry 관련 작업 테스트"""
        try:
            from core.watchlist.watchlist_manager import WatchlistManager
            
            test_file = "test_watchlist_entry.json"
            manager = WatchlistManager(test_file)
            
            # 테스트 데이터 생성
            entry = WatchlistEntry(
                stock_code="005930",
                stock_name="삼성전자",
                added_date=datetime.now(),
                added_reason="기술적 분석 신호",
                target_price=80000.0,
                stop_loss=70000.0,
                sector="반도체",
                screening_score=85.5,
                status="active",
                notes="테스트 종목"
            )
            
            # 종목 추가 테스트
            success = manager.add_stock(entry)
            assert success
            
            # 종목 조회 테스트
            retrieved = manager.get_stock("005930")
            assert retrieved is not None
            assert retrieved.stock_code == "005930"
            assert retrieved.stock_name == "삼성전자"
            
            # 종목 목록 조회 테스트
            stock_list = manager.list_stocks(p_status="active")
            assert len(stock_list) >= 1
            assert any(stock.stock_code == "005930" for stock in stock_list)
            
            # 통계 정보 테스트
            stats = manager.get_statistics()
            assert isinstance(stats, dict)
            assert "total_count" in stats
            assert "active_count" in stats
            
            # 테스트 파일 정리
            if os.path.exists(test_file):
                os.remove(test_file)
                
        except ImportError:
            pytest.skip("WatchlistManager 모듈을 불러올 수 없습니다")

class TestPhase2Refactoring:
    """Phase 2 리팩토링 테스트"""
    
    def test_price_analyzer_interface_implementation(self):
        """PriceAnalyzer가 IPriceAnalyzer 인터페이스를 올바르게 구현하는지 테스트"""
        try:
            from core.daily_selection.price_analyzer import PriceAnalyzer
            
            # 인스턴스 생성
            analyzer = PriceAnalyzer()
            
            # 인터페이스 구현 확인
            assert isinstance(analyzer, IPriceAnalyzer)
            
            # 필수 메서드 존재 확인
            assert hasattr(analyzer, 'analyze_price_attractiveness')
            assert hasattr(analyzer, 'analyze_multiple_stocks')
            assert hasattr(analyzer, 'analyze_technical_indicators')
            assert hasattr(analyzer, 'analyze_volume_pattern')
            assert hasattr(analyzer, 'detect_patterns')
            
            # 플러그인 메타데이터 확인
            assert hasattr(analyzer, '_plugin_metadata')
            assert analyzer._plugin_metadata['name'] == 'price_analyzer'
            
        except ImportError:
            pytest.skip("PriceAnalyzer 모듈을 불러올 수 없습니다")
    
    def test_daily_updater_interface_implementation(self):
        """DailyUpdater가 IDailyUpdater 인터페이스를 올바르게 구현하는지 테스트"""
        try:
            from core.daily_selection.daily_updater import DailyUpdater
            
            # 인스턴스 생성
            updater = DailyUpdater()
            
            # 인터페이스 구현 확인
            assert isinstance(updater, IDailyUpdater)
            
            # 필수 메서드 존재 확인
            assert hasattr(updater, 'run_daily_update')
            assert hasattr(updater, 'analyze_market_condition')
            assert hasattr(updater, 'filter_and_select_stocks')
            assert hasattr(updater, 'create_daily_trading_list')
            assert hasattr(updater, 'start_scheduler')
            assert hasattr(updater, 'stop_scheduler')
            
            # 플러그인 메타데이터 확인
            assert hasattr(updater, '_plugin_metadata')
            assert updater._plugin_metadata['name'] == 'daily_updater'
            
        except ImportError:
            pytest.skip("DailyUpdater 모듈을 불러올 수 없습니다")
    
    def test_price_attractiveness_analysis(self):
        """가격 매력도 분석 기능 테스트"""
        try:
            from core.daily_selection.price_analyzer import PriceAnalyzer
            
            analyzer = PriceAnalyzer()
            
            # 테스트 데이터
            stock_data = {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "current_price": 75000.0,
                "sector": "반도체",
                "volume": 1000000,
                "ma_20": 74000.0,
                "ma_60": 73000.0,
                "ma_120": 72000.0,
                "rsi": 55.0,
                "volume_ratio": 1.5
            }
            
            # 가격 매력도 분석 테스트
            result = analyzer.analyze_price_attractiveness(stock_data)
            
            # 결과 타입 확인
            assert isinstance(result, PriceAttractiveness)
            assert result.stock_code == "005930"
            assert result.stock_name == "삼성전자"
            assert isinstance(result.total_score, (int, float))
            assert isinstance(result.technical_signals, list)
            
            # 점수 범위 확인
            assert 0 <= result.total_score <= 100
            assert 0 <= result.technical_score <= 100
            assert 0 <= result.volume_score <= 100
            assert 0 <= result.pattern_score <= 100
            
        except ImportError:
            pytest.skip("PriceAnalyzer 모듈을 불러올 수 없습니다")

class TestDataClasses:
    """새로운 데이터 클래스들 테스트"""
    
    def test_technical_signal_creation(self):
        """TechnicalSignal 데이터 클래스 테스트"""
        signal = TechnicalSignal(
            signal_type="rsi",
            signal_name="oversold_recovery",
            strength=75.0,
            confidence=0.8,
            description="RSI 과매도 구간에서 반등 신호",
            timestamp=datetime.now()
        )
        
        assert signal.signal_type == "rsi"
        assert signal.signal_name == "oversold_recovery"
        assert signal.strength == 75.0
        assert signal.confidence == 0.8
        assert isinstance(signal.timestamp, datetime)
    
    def test_screening_result_creation(self):
        """ScreeningResult 데이터 클래스 테스트"""
        result = ScreeningResult(
            stock_code="005930",
            stock_name="삼성전자",
            passed=True,
            score=82.5,
            details={"fundamental": {"roe": 15.2}},
            signals=["기본분석_통과", "기술분석_통과"],
            timestamp=datetime.now()
        )
        
        assert result.stock_code == "005930"
        assert result.passed is True
        assert result.score == 82.5
        assert "기본분석_통과" in result.signals
        assert isinstance(result.details, dict)
    
    def test_price_attractiveness_creation(self):
        """PriceAttractiveness 데이터 클래스 테스트"""
        signals = [
            TechnicalSignal(
                signal_type="macd",
                signal_name="bullish_cross",
                strength=70.0,
                confidence=0.75,
                description="MACD 골든크로스",
                timestamp=datetime.now()
            )
        ]
        
        attractiveness = PriceAttractiveness(
            stock_code="005930",
            stock_name="삼성전자",
            analysis_date=datetime.now(),
            current_price=75000.0,
            total_score=78.5,
            technical_score=80.0,
            volume_score=75.0,
            pattern_score=80.0,
            technical_signals=signals,
            entry_price=74500.0,
            target_price=82000.0,
            stop_loss=70000.0,
            expected_return=10.0,
            risk_score=25.0,
            confidence=0.78,
            selection_reason="기술적 신호 양호",
            market_condition="neutral",
            sector_momentum=5.2,
            sector="반도체"
        )
        
        assert attractiveness.stock_code == "005930"
        assert attractiveness.total_score == 78.5
        assert len(attractiveness.technical_signals) == 1
        assert attractiveness.expected_return == 10.0

class TestIntegration:
    """통합 테스트"""
    
    def test_phase1_phase2_integration(self):
        """Phase 1과 Phase 2 모듈 간 통합 테스트"""
        try:
            from core.watchlist.watchlist_manager import WatchlistManager
            from core.daily_selection.price_analyzer import PriceAnalyzer
            
            # 임시 파일
            test_file = "test_integration.json"
            
            # Phase 1: 감시 리스트 생성
            manager = WatchlistManager(test_file)
            entry = WatchlistEntry(
                stock_code="005930",
                stock_name="삼성전자",
                added_date=datetime.now(),
                added_reason="통합 테스트",
                target_price=80000.0,
                stop_loss=70000.0,
                sector="반도체",
                screening_score=85.0,
                status="active",
                notes=""
            )
            
            success = manager.add_stock(entry)
            assert success
            
            # Phase 2: 가격 분석
            analyzer = PriceAnalyzer()
            stock_data = {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "current_price": 75000.0,
                "sector": "반도체"
            }
            
            result = analyzer.analyze_price_attractiveness(stock_data)
            assert isinstance(result, PriceAttractiveness)
            assert result.stock_code == "005930"
            
            # 정리
            if os.path.exists(test_file):
                os.remove(test_file)
                
        except ImportError:
            pytest.skip("필요한 모듈을 불러올 수 없습니다")
    
    @patch('core.daily_selection.daily_updater.schedule')
    def test_daily_updater_scheduler(self, mock_schedule):
        """DailyUpdater 스케줄러 기능 테스트"""
        try:
            from core.daily_selection.daily_updater import DailyUpdater
            
            updater = DailyUpdater()
            
            # 스케줄러 시작 테스트
            updater.start_scheduler()
            assert updater._scheduler_running is True
            
            # 스케줄러 중지 테스트
            updater.stop_scheduler()
            assert updater._scheduler_running is False
            
        except ImportError:
            pytest.skip("DailyUpdater 모듈을 불러올 수 없습니다")

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 