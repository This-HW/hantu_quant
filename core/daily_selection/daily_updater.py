#!/usr/bin/env python3
"""
Phase 2: 일일 업데이트 스케줄러
매일 감시 리스트에서 가격이 매력적인 주식을 당일 매매 리스트에 업데이트
"""

import os
import sys
import json
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import threading
import logging

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.watchlist.watchlist_manager import WatchlistManager
from core.daily_selection.price_analyzer import PriceAnalyzer, PriceAttractivenessLegacy
from core.utils.log_utils import get_logger
from core.utils.telegram_notifier import get_telegram_notifier
from core.interfaces.trading import IDailyUpdater, PriceAttractiveness, DailySelection

# 새로운 아키텍처 imports - 사용 가능할 때만 import
try:
    from core.plugins.decorators import plugin
    from core.di.injector import inject
    from core.interfaces.base import ILogger, IConfiguration
    ARCHITECTURE_AVAILABLE = True
except ImportError:
    # 새 아키텍처가 아직 완전히 구축되지 않은 경우 임시 대안
    ARCHITECTURE_AVAILABLE = False
    
    def plugin(**kwargs):
        """임시 플러그인 데코레이터"""
        def decorator(cls):
            cls._plugin_metadata = kwargs
            return cls
        return decorator
    
    def inject(cls):
        """임시 DI 데코레이터"""
        return cls

logger = get_logger(__name__)

@dataclass
class FilteringCriteria:
    """필터링 기준 데이터 클래스 (개선: 점수 기반 통합 필터링)"""
    # 기본 임계값 (완화됨)
    price_attractiveness: float = 38.0      # 가격 매력도 점수 기준 (46 → 38, 완화)
    volume_threshold: float = 1.2           # 평균 거래량 대비 배수 (1.5 → 1.2)
    volatility_range: tuple = (0.05, 0.5)   # 변동성 범위 (5-50%, 확장)
    market_cap_min: float = 5000000000      # 최소 시가총액 (50억원, 완화)
    liquidity_score: float = 8.0            # 유동성 점수 기준 (10 → 8)
    risk_score_max: float = 55.0            # 최대 리스크 점수 (43 → 55, 완화)
    sector_limit: int = 3                   # 섹터별 최대 종목 수
    total_limit: int = 10                   # 전체 최대 종목 수 (목표: 5-10개)
    confidence_min: float = 0.45            # 최소 신뢰도 (0.62 → 0.45, 완화)

    # 기술적 지표 기준 (완화됨)
    min_relative_strength: float = 0.4      # 시장 대비 상위 60% (0.6 → 0.4)
    min_technical_score: float = 30.0       # 기술적 점수 최소값 (40 → 30)

    # 점수 기반 통합 필터링 (신규)
    use_score_based_filter: bool = True     # 점수 기반 필터링 활성화
    min_composite_score: float = 0.55       # 최소 복합 점수 (55% 이상이면 통과)


# 시장 레짐별 필터 프리셋
REGIME_FILTER_PRESETS = {
    "bull_market": {
        "price_attractiveness": 35.0,       # 상승장: 적극적
        "confidence_min": 0.40,
        "risk_score_max": 60.0,
        "min_technical_score": 25.0,
        "total_limit": 10,
        "min_composite_score": 0.50,
        "use_score_based_filter": True,     # 점수 기반 필터링 사용
        "liquidity_score": 6.0,             # 유동성 기준 완화
    },
    "bear_market": {
        "price_attractiveness": 50.0,       # 하락장: 보수적
        "confidence_min": 0.55,
        "risk_score_max": 40.0,
        "min_technical_score": 40.0,
        "total_limit": 5,
        "min_composite_score": 0.65,
        "use_score_based_filter": True,     # 점수 기반 필터링 사용
        "liquidity_score": 12.0,            # 유동성 기준 강화
    },
    "sideways": {
        "price_attractiveness": 40.0,       # 횡보장: 중립
        "confidence_min": 0.45,
        "risk_score_max": 50.0,
        "min_technical_score": 32.0,
        "total_limit": 8,
        "min_composite_score": 0.55,
        "use_score_based_filter": True,     # 점수 기반 필터링 사용
        "liquidity_score": 8.0,
    },
    "volatile": {
        "price_attractiveness": 45.0,       # 변동성장: 신중
        "confidence_min": 0.50,
        "risk_score_max": 45.0,
        "min_technical_score": 35.0,
        "total_limit": 6,
        "min_composite_score": 0.60,
        "use_score_based_filter": True,     # 점수 기반 필터링 사용
        "liquidity_score": 10.0,
    },
    "recovery": {
        "price_attractiveness": 38.0,       # 회복장: 기회 포착
        "confidence_min": 0.42,
        "risk_score_max": 55.0,
        "min_technical_score": 28.0,
        "total_limit": 10,
        "min_composite_score": 0.52,
        "use_score_based_filter": True,     # 점수 기반 필터링 사용
        "liquidity_score": 7.0,
    },
    "neutral": {
        "price_attractiveness": 38.0,       # 기본값
        "confidence_min": 0.45,
        "risk_score_max": 55.0,
        "min_technical_score": 30.0,
        "total_limit": 10,
        "min_composite_score": 0.55,
        "use_score_based_filter": True,     # 점수 기반 필터링 사용
        "liquidity_score": 8.0,
    }
}

@dataclass
class DailySelectionLegacy:
    """일일 선정 종목 데이터 클래스 (기존 호환성용)"""
    stock_code: str
    stock_name: str
    selection_date: str
    selection_reason: str
    price_attractiveness: float
    entry_price: float
    target_price: float
    stop_loss: float
    expected_return: float      # 기대 수익률 필드 추가
    risk_score: float
    volume_score: float
    technical_signals: List[str]
    sector: str
    market_cap: float
    priority: int
    position_size: float        # 포트폴리오 비중
    confidence: float           # 신뢰도 (0-1)
    predicted_class: int = 1    # 예측 분류 (0: 실패예상, 1: 성공예상) - Phase 4 학습용
    model_name: str = "ensemble"  # 예측 모델명

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)
    
    def to_daily_selection(self) -> DailySelection:
        """새로운 DailySelection으로 변환"""
        return DailySelection(
            stock_code=self.stock_code,
            stock_name=self.stock_name,
            selection_date=datetime.fromisoformat(self.selection_date) if isinstance(self.selection_date, str) else self.selection_date,
            selection_reason=self.selection_reason,
            price_attractiveness=self.price_attractiveness,
            entry_price=self.entry_price,
            target_price=self.target_price,
            stop_loss=self.stop_loss,
            risk_score=self.risk_score,
            volume_score=self.volume_score,
            technical_signals=self.technical_signals,
            sector=self.sector,
            market_cap=self.market_cap,
            priority=self.priority,
            position_size=self.position_size,
            confidence=self.confidence
        )

@dataclass
class MarketIndicators:
    """시장 지표 데이터 클래스"""
    kospi: float = 0.0
    kosdaq: float = 0.0
    vix: float = 0.0
    usd_krw: float = 0.0
    interest_rate: float = 0.0
    oil_price: float = 0.0
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)

class MarketConditionAnalyzer:
    """시장 상황 분석 클래스"""
    
    def __init__(self):
        self._market_indicators = MarketIndicators()
    
    def analyze_market_condition(self) -> str:
        """시장 상황 분석"""
        try:
            self._update_market_indicators()
            
            # 임시로 중립 시장 반환 (실제로는 지수 분석 필요)
            return "neutral"
            
        except Exception as e:
            logger.error(f"시장 상황 분석 오류: {e}", exc_info=True)
            return "neutral"
    
    def _update_market_indicators(self):
        """시장 지표 업데이트 (시뮬레이션)"""
        # 실제로는 API에서 데이터를 가져와야 함
        import random
        self._market_indicators.kospi = random.uniform(2400, 2600)
        self._market_indicators.kosdaq = random.uniform(800, 900)
        self._market_indicators.vix = random.uniform(15, 25)
        self._market_indicators.usd_krw = random.uniform(1300, 1350)
    
    def get_market_indicators(self) -> MarketIndicators:
        """시장 지표 조회"""
        return self._market_indicators

@plugin(
    name="daily_updater",
    version="1.0.0", 
    description="일일 업데이트 스케줄러 플러그인",
    author="HantuQuant",
    dependencies=["watchlist_manager", "price_analyzer", "logger"],
    category="daily_selection"
)
class DailyUpdater(IDailyUpdater):
    """일일 업데이트 스케줄러 클래스 - 새로운 아키텍처 적용"""
    
    @inject
    def __init__(self, 
                 p_watchlist_file: str = "data/watchlist/watchlist.json",
                 p_output_dir: str = "data/daily_selection",
                 watchlist_manager=None,
                 price_analyzer=None,
                 logger=None):
        """초기화 메서드"""
        self._watchlist_file = p_watchlist_file
        self._output_dir = p_output_dir
        self._logger = logger or get_logger(__name__)
        
        # 컴포넌트 초기화 (DI 또는 직접 생성)
        self._watchlist_manager = watchlist_manager or WatchlistManager(p_watchlist_file)
        self._price_analyzer = price_analyzer or PriceAnalyzer()
        self._market_analyzer = MarketConditionAnalyzer()

        # KIS API 인스턴스 (공유하여 rate limiting 적용)
        self._kis_api = None  # lazy initialization

        # 적응형 필터 튜너 (학습 기반 임계값 조정)
        self._adaptive_tuner = None  # lazy initialization

        # 필터링 기준 및 상태
        self._filtering_criteria = FilteringCriteria()
        self._scheduler_running = False
        self._scheduler_thread = None

        # 출력 디렉토리 생성
        os.makedirs(self._output_dir, exist_ok=True)

        self._logger.info("DailyUpdater 초기화 완료 (새 아키텍처)")

    def _get_kis_api(self):
        """KIS API 싱글톤 인스턴스 반환 (rate limiting 공유)"""
        if self._kis_api is None:
            from core.api.kis_api import KISAPI
            self._kis_api = KISAPI()
            self._logger.info("KIS API 인스턴스 초기화 완료")
        return self._kis_api

    def run_daily_update(self, p_force_run: bool = False) -> bool:
        """일일 업데이트 실행 (새 인터페이스 구현)"""
        try:
            self._logger.info("일일 업데이트 시작")
            
            # 1. 시장 상황 분석
            _v_market_condition = self.analyze_market_condition()
            
            # 2. 시장 상황에 따른 기준 조정
            self._adjust_criteria_by_market(_v_market_condition)
            
            # 3. 감시 리스트에서 종목 데이터 준비
            _v_watchlist_stocks = self._watchlist_manager.list_stocks(p_status="active")
            _v_stock_data_list = self._prepare_stock_data(_v_watchlist_stocks)
            
            # 4. 가격 매력도 분석 (PriceAttractiveness 직접 사용)
            _v_analysis_results = []
            for _v_stock_data in _v_stock_data_list:
                try:
                    _v_result = self._price_analyzer.analyze_price_attractiveness(_v_stock_data)
                    _v_analysis_results.append(_v_result)
                except Exception as e:
                    self._logger.error(f"종목 {_v_stock_data.get('stock_code')} 분석 오류: {e}", exc_info=True)
                    continue
            
            # 5. 필터링 및 선정 (PriceAttractiveness 직접 사용)
            _v_selected_stocks = self._filter_and_select_stocks(_v_analysis_results)
            
            # 6. 일일 매매 리스트 생성
            _v_market_indicators = self._market_analyzer.get_market_indicators()
            _v_daily_list = self._create_daily_trading_list(_v_selected_stocks, _v_market_condition, _v_market_indicators)
            
            # 7. 결과 저장
            _v_save_success = self._save_daily_list(_v_daily_list)
            
            if _v_save_success:
                self._logger.info(f"일일 업데이트 완료 - 선정 종목: {len(_v_selected_stocks)}개")
                
                # 텔레그램 일일 업데이트 완료 알림 전송
                self._send_daily_update_complete_notification(len(_v_selected_stocks))
                
                return True
            else:
                self._logger.error("일일 리스트 저장 실패")
                return False
                
        except Exception as e:
            import traceback
            self._logger.error(f"일일 업데이트 오류: {e}", exc_info=True)
            self._logger.error(f"상세 에러: {traceback.format_exc()}", exc_info=True)
            return False

    def analyze_market_condition(self) -> str:
        """시장 상황 분석 (새 인터페이스 구현)"""
        return self._market_analyzer.analyze_market_condition()

    def filter_and_select_stocks(self, p_analysis_results: List[PriceAttractiveness]) -> List[PriceAttractiveness]:
        """종목 필터링 및 선정 (새 인터페이스 구현)"""
        # PriceAttractiveness를 기존 형식으로 변환
        _v_legacy_results = []
        for result in p_analysis_results:
            _v_legacy_result = PriceAttractivenessLegacy(
                stock_code=result.stock_code,
                stock_name=result.stock_name,
                analysis_date=result.analysis_date.isoformat() if isinstance(result.analysis_date, datetime) else str(result.analysis_date),
                current_price=result.current_price,
                total_score=result.total_score,
                technical_score=result.technical_score,
                volume_score=result.volume_score,
                pattern_score=result.pattern_score,
                technical_signals=[],  # 간소화
                entry_price=result.entry_price,
                target_price=result.target_price,
                stop_loss=result.stop_loss,
                expected_return=result.expected_return,
                risk_score=result.risk_score,
                confidence=result.confidence,
                selection_reason=result.selection_reason,
                market_condition=result.market_condition,
                sector_momentum=result.sector_momentum,
                sector=result.sector
            )
            _v_legacy_results.append(_v_legacy_result)
        
        # 기존 필터링 로직 사용
        _v_filtered = self._filter_and_select_stocks(_v_legacy_results)
        
        # 결과를 새로운 형식으로 변환
        _v_new_results = []
        for legacy_result in _v_filtered:
            _v_new_result = legacy_result.to_price_attractiveness()
            _v_new_results.append(_v_new_result)
        
        return _v_new_results

    def create_daily_trading_list(self, p_selected_stocks: List[PriceAttractiveness]) -> Dict:
        """일일 매매 리스트 생성 (새 인터페이스 구현)"""
        _v_market_condition = self.analyze_market_condition()
        _v_market_indicators = self._market_analyzer.get_market_indicators()
        
        # PriceAttractiveness를 기존 형식으로 변환
        _v_legacy_stocks = []
        for stock in p_selected_stocks:
            _v_legacy_stock = PriceAttractivenessLegacy(
                stock_code=stock.stock_code,
                stock_name=stock.stock_name,
                analysis_date=stock.analysis_date.isoformat() if isinstance(stock.analysis_date, datetime) else str(stock.analysis_date),
                current_price=stock.current_price,
                total_score=stock.total_score,
                technical_score=stock.technical_score,
                volume_score=stock.volume_score,
                pattern_score=stock.pattern_score,
                technical_signals=[],  # 간소화
                entry_price=stock.entry_price,
                target_price=stock.target_price,
                stop_loss=stock.stop_loss,
                expected_return=stock.expected_return,
                risk_score=stock.risk_score,
                confidence=stock.confidence,
                selection_reason=stock.selection_reason,
                market_condition=stock.market_condition,
                sector_momentum=stock.sector_momentum,
                sector=stock.sector
            )
            _v_legacy_stocks.append(_v_legacy_stock)
        
        return self._create_daily_trading_list(_v_legacy_stocks, _v_market_condition, _v_market_indicators)

    def start_scheduler(self) -> None:
        """스케줄러 시작 (새 인터페이스 구현)"""
        if self._scheduler_running:
            self._logger.warning("스케줄러가 이미 실행 중입니다")
            return
        
        try:
            # 스케줄 설정
            schedule.clear()
            schedule.every().day.at("08:30").do(self.run_daily_update)
            
            self._scheduler_running = True
            self._scheduler_thread = threading.Thread(target=self._run_scheduler_loop, daemon=True)
            self._scheduler_thread.start()
            
            self._logger.info("일일 업데이트 스케줄러 시작")
            
        except Exception as e:
            self._logger.error(f"스케줄러 시작 오류: {e}", exc_info=True)

    def stop_scheduler(self) -> None:
        """스케줄러 중지 (새 인터페이스 구현)"""
        self._scheduler_running = False
        schedule.clear()
        self._logger.info("일일 업데이트 스케줄러 중지")

    def _run_scheduler_loop(self):
        """스케줄러 루프 실행"""
        while self._scheduler_running:
            schedule.run_pending()
            time.sleep(60)  # 1분마다 체크

    def _get_adaptive_tuner(self):
        """적응형 필터 튜너 싱글톤 인스턴스 반환"""
        if self._adaptive_tuner is None:
            try:
                from core.daily_selection.adaptive_filter_tuner import get_adaptive_filter_tuner
                self._adaptive_tuner = get_adaptive_filter_tuner()
                self._logger.info("적응형 필터 튜너 초기화 완료")
            except Exception as e:
                self._logger.warning(f"적응형 필터 튜너 로드 실패: {e}")
                self._adaptive_tuner = None
        return self._adaptive_tuner

    def _adjust_criteria_by_market(self, p_market_condition: str):
        """시장 상황에 따른 필터링 기준 동적 조정

        우선순위:
        1. 학습 기반 최적 임계값 (충분한 데이터가 있을 때)
        2. 시장 레짐별 프리셋 (기본값)

        Args:
            p_market_condition: 시장 상황 (bull_market, bear_market, sideways, volatile, recovery, neutral)
        """
        # 기본 기준으로 초기화
        self._filtering_criteria = FilteringCriteria()

        # 1. 학습 기반 임계값 시도
        learned_thresholds = None
        tuner = self._get_adaptive_tuner()
        if tuner and tuner.can_learn():
            learned_thresholds = tuner.get_optimal_thresholds(p_market_condition)
            if learned_thresholds:
                self._filtering_criteria.price_attractiveness = learned_thresholds.price_attractiveness
                self._filtering_criteria.confidence_min = learned_thresholds.confidence_min
                self._filtering_criteria.risk_score_max = learned_thresholds.risk_score_max
                self._filtering_criteria.min_technical_score = learned_thresholds.min_technical_score
                self._filtering_criteria.liquidity_score = learned_thresholds.liquidity_score
                self._filtering_criteria.min_composite_score = learned_thresholds.min_composite_score

                self._logger.info(
                    f"🧠 학습 기반 임계값 적용 - 시장상황: {p_market_condition} | "
                    f"매력도>{learned_thresholds.price_attractiveness:.1f}, "
                    f"신뢰도>{learned_thresholds.confidence_min:.2f}, "
                    f"리스크<{learned_thresholds.risk_score_max:.1f}"
                )
                return

        # 2. 학습 데이터 부족 시 시장 레짐별 프리셋 적용
        preset = REGIME_FILTER_PRESETS.get(p_market_condition, REGIME_FILTER_PRESETS["neutral"])

        # 프리셋 값 적용 (모든 필드)
        self._filtering_criteria.price_attractiveness = preset["price_attractiveness"]
        self._filtering_criteria.confidence_min = preset["confidence_min"]
        self._filtering_criteria.risk_score_max = preset["risk_score_max"]
        self._filtering_criteria.min_technical_score = preset["min_technical_score"]
        self._filtering_criteria.total_limit = preset["total_limit"]
        self._filtering_criteria.min_composite_score = preset["min_composite_score"]
        self._filtering_criteria.use_score_based_filter = preset.get("use_score_based_filter", True)
        self._filtering_criteria.liquidity_score = preset.get("liquidity_score", 8.0)

        self._logger.info(
            f"📋 프리셋 기반 임계값 적용 - 시장상황: {p_market_condition} | "
            f"매력도>{preset['price_attractiveness']:.0f}, "
            f"신뢰도>{preset['confidence_min']:.2f}, "
            f"리스크<{preset['risk_score_max']:.0f}, "
            f"목표종목: {preset['total_limit']}개, "
            f"점수필터: {'ON' if preset.get('use_score_based_filter', True) else 'OFF'}"
        )
    
    def _prepare_stock_data(self, p_watchlist_stocks: List) -> List[Dict]:
        """감시 리스트 종목을 분석용 데이터로 변환
        
        Args:
            p_watchlist_stocks: 감시 리스트 종목들
            
        Returns:
            분석용 종목 데이터 리스트
        """
        _v_stock_data_list = []

        # 당일 스크리닝 통과 종목만 대상으로 제한
        try:
            from datetime import datetime
            from pathlib import Path
            today_key = datetime.now().strftime("%Y%m%d")
            part_file = Path("data/watchlist") / f"screening_{today_key}.json"
            if part_file.exists():
                import json
                payload = json.loads(part_file.read_text(encoding="utf-8"))
                today_codes = {s.get("stock_code") for s in payload.get("stocks", []) if s.get("stock_code")}
                if today_codes:
                    p_watchlist_stocks = [s for s in p_watchlist_stocks if s.stock_code in today_codes]
        except Exception:
            pass
        
        # API 호출 최적화: 한 번의 호출로 현재가+시가총액 조회
        total_stocks = len(p_watchlist_stocks)
        self._logger.info(f"API 데이터 조회 시작: {total_stocks}개 종목")

        for idx, stock in enumerate(p_watchlist_stocks, 1):
            # 단일 API 호출로 현재가와 시가총액 동시 조회
            stock_info = self._get_stock_info_combined(stock.stock_code)

            _v_stock_data = {
                "stock_code": stock.stock_code,
                "stock_name": stock.stock_name,
                "current_price": stock_info.get("current_price", 0.0),
                "sector": stock.sector,
                "market_cap": stock_info.get("market_cap", 0.0),
                "volatility": self._get_volatility(stock.stock_code),
                "sector_momentum": self._get_sector_momentum(stock.sector)
            }
            _v_stock_data_list.append(_v_stock_data)

            # 진행 상황 로깅 (50개마다)
            if idx % 50 == 0:
                self._logger.info(f"API 데이터 조회 진행: {idx}/{total_stocks}개")

        self._logger.info(f"API 데이터 조회 완료: {total_stocks}개 종목")
        return _v_stock_data_list

    def _get_stock_info_combined(self, p_stock_code: str) -> Dict:
        """종목 정보 통합 조회 (현재가 + 시가총액, 단일 API 호출)"""
        try:
            kis = self._get_kis_api()
            info = kis.get_stock_info(p_stock_code) or {}
            return {
                "current_price": float(info.get("current_price", 0.0)),
                "market_cap": float(info.get("market_cap", 0.0)),
            }
        except Exception as e:
            self._logger.warning(f"종목 정보 조회 실패 ({p_stock_code}): {e}")
            return {"current_price": 0.0, "market_cap": 0.0}
    
    def _get_current_price(self, p_stock_code: str) -> float:
        """현재가 조회 (실데이터: KIS API, 공유 인스턴스 사용)"""
        try:
            kis = self._get_kis_api()
            info = kis.get_current_price(p_stock_code) or {}
            return float(info.get("current_price", 0.0))
        except Exception as e:
            self._logger.warning(f"현재가 조회 실패 ({p_stock_code}): {e}")
            return 0.0

    def _get_market_cap(self, p_stock_code: str) -> float:
        """시가총액 조회 (실데이터: KIS API, 공유 인스턴스 사용)"""
        try:
            kis = self._get_kis_api()
            info = kis.get_stock_info(p_stock_code) or {}
            return float(info.get("market_cap", 0.0))
        except Exception as e:
            self._logger.warning(f"시가총액 조회 실패 ({p_stock_code}): {e}")
            return 0.0
    
    def _get_volatility(self, p_stock_code: str) -> float:
        """변동성 조회 (더미 구현)"""
        # 실제로는 과거 데이터로부터 변동성 계산
        # 5% ~ 50% 범위로 다양화
        volatility = 0.05 + (hash(p_stock_code) % 450) / 1000
        return volatility
    
    def _get_sector_momentum(self, p_sector: str) -> float:
        """섹터 모멘텀 조회 (더미 구현)"""
        # 실제로는 섹터 지수 분석  
        # -20% ~ +20% 범위로 확장
        momentum = (hash(p_sector) % 400 - 200) / 1000
        return momentum
    
    def _filter_and_select_stocks(self, p_analysis_results: List[PriceAttractivenessLegacy]) -> List[PriceAttractivenessLegacy]:
        """분석 결과를 필터링하여 매매 대상 선정 (방안 A + 방안 C 통합)

        Args:
            p_analysis_results: 가격 매력도 분석 결과 리스트

        Returns:
            선정된 종목 리스트
        """
        _v_filtered_stocks = []
        _v_sector_count = {}

        # 점수순으로 정렬
        _v_sorted_results = sorted(p_analysis_results, key=lambda x: x.total_score, reverse=True)

        # [방안 A] 추세 추종 필터 적용
        _v_trend_filtered = self._apply_trend_filter(_v_sorted_results)

        # [방안 C] 멀티 전략 앙상블 적용
        _v_ensemble_filtered = self._apply_multi_strategy_ensemble(_v_trend_filtered)

        for result in _v_ensemble_filtered:
            # 기본 필터링 조건 확인
            if not self._passes_basic_filters(result):
                continue

            # 섹터별 제한 확인
            _v_sector_count[result.sector] = _v_sector_count.get(result.sector, 0)
            if _v_sector_count[result.sector] >= self._filtering_criteria.sector_limit:
                continue

            # 전체 제한: 0이면 제한 없음
            if self._filtering_criteria.total_limit and len(_v_filtered_stocks) >= self._filtering_criteria.total_limit:
                break

            _v_filtered_stocks.append(result)
            _v_sector_count[result.sector] += 1

        self._logger.info(f"필터링 완료: {len(_v_filtered_stocks)}개 종목 선정 (추세 + 멀티전략 필터)")
        return _v_filtered_stocks

    def _apply_trend_filter(self, p_results: List[PriceAttractivenessLegacy]) -> List[PriceAttractivenessLegacy]:
        """추세 추종 필터 적용 (개선: Adaptive Minimum Data)

        데이터 길이에 따라 다른 분석 방식 적용:
        - 60일+: 전체 분석 (ma5, ma20, ma60)
        - 30-59일: 중간 분석 (ma5, ma20만)
        - 20-29일: 간이 분석 (ma5, ma10만)
        - 10-19일: 최소 분석 (ma5만, 모멘텀 중심)

        Args:
            p_results: 분석 결과 리스트

        Returns:
            추세 조건을 통과한 종목 리스트
        """
        try:
            from core.daily_selection.trend_follower import get_trend_follower

            trend_follower = get_trend_follower()
            api = self._get_kis_api()

            # 종목별 가격 데이터 수집 (최소 10일, 최대 60일 시도)
            market_data = {}
            data_stats = {"60+": 0, "30-59": 0, "20-29": 0, "10-19": 0, "<10": 0}

            for result in p_results:
                try:
                    # 60일 데이터 요청 시도
                    df = api.get_stock_history(result.stock_code, period="D", count=60)

                    if df is not None and len(df) >= 10:  # 최소 10일 데이터만 있으면 OK
                        market_data[result.stock_code] = df

                        # 통계 수집
                        data_len = len(df)
                        if data_len >= 60:
                            data_stats["60+"] += 1
                        elif data_len >= 30:
                            data_stats["30-59"] += 1
                        elif data_len >= 20:
                            data_stats["20-29"] += 1
                        else:
                            data_stats["10-19"] += 1
                    else:
                        data_stats["<10"] += 1

                except Exception as e:
                    self._logger.debug(f"종목 {result.stock_code} 가격 데이터 수집 실패: {e}")
                    data_stats["<10"] += 1
                    continue

            # 데이터 통계 로깅
            self._logger.info(
                f"가격 데이터 수집 결과: 60일+={data_stats['60+']}, "
                f"30-59일={data_stats['30-59']}, 20-29일={data_stats['20-29']}, "
                f"10-19일={data_stats['10-19']}, 10일미만(제외)={data_stats['<10']}"
            )

            # 추세 추종 필터 적용
            stocks_dict = [{'stock_code': r.stock_code, 'stock_name': r.stock_name} for r in p_results]
            filtered_codes = {s['stock_code'] for s in trend_follower.filter_stocks(stocks_dict, market_data)}

            # 추세 조건 통과한 종목만 반환
            trend_filtered = [r for r in p_results if r.stock_code in filtered_codes]

            self._logger.info(f"추세 추종 필터: {len(p_results)}개 → {len(trend_filtered)}개")

            return trend_filtered

        except Exception as e:
            self._logger.warning(f"추세 필터 적용 실패 (원본 리스트 사용): {e}")
            return p_results  # 실패 시 원본 리스트 반환

    def _apply_multi_strategy_ensemble(self, p_results: List[PriceAttractivenessLegacy]) -> List[PriceAttractivenessLegacy]:
        """멀티 전략 앙상블 적용 (방안 C 통합)

        Args:
            p_results: 분석 결과 리스트

        Returns:
            앙상블 점수로 재정렬된 종목 리스트
        """
        try:
            from core.strategy.multi_strategy_manager import MultiStrategyManager

            multi_strategy = MultiStrategyManager()
            api = self._get_kis_api()  # 싱글톤 사용하여 rate limiting 공유

            # 시장 지수 데이터 가져오기 (KOSPI)
            market_index_data = api.get_stock_history("0001", period="D", count=60)  # KOSPI 지수

            if market_index_data is None or len(market_index_data) < 20:
                self._logger.warning("시장 지수 데이터 부족 - 멀티 전략 건너뜀")
                return p_results

            # 종목 데이터를 Dict 형식으로 변환
            candidate_stocks = []
            result_map = {}  # stock_code -> PriceAttractivenessLegacy 매핑

            for result in p_results:
                stock_dict = {
                    'stock_code': result.stock_code,
                    'stock_name': result.stock_name,
                    'price_attractiveness': result.total_score,
                    'technical_score': result.technical_score,
                    'risk_score': result.risk_score,
                    'confidence': result.confidence,
                    'volume_score': result.volume_score,
                }
                candidate_stocks.append(stock_dict)
                result_map[result.stock_code] = result

            # 앙상블 방식으로 종목 선정 (최대 30개)
            ensemble_stocks = multi_strategy.get_ensemble_stocks(
                candidate_stocks=candidate_stocks,
                market_index_data=market_index_data,
                max_stocks=min(30, len(candidate_stocks))
            )

            # 선정된 종목들을 원본 객체로 복구하고 앙상블 점수로 정렬
            ensemble_results = []
            for stock in ensemble_stocks:
                code = stock['stock_code']
                original = result_map[code]
                # 앙상블 점수를 기록 (나중에 참고용)
                original.ensemble_score = stock.get('ensemble_score', original.total_score)
                ensemble_results.append(original)

            self._logger.info(f"멀티 전략 앙상블: {len(p_results)}개 → {len(ensemble_results)}개")

            return ensemble_results

        except Exception as e:
            self._logger.warning(f"멀티 전략 앙상블 적용 실패 (원본 리스트 사용): {e}")
            import traceback
            self._logger.debug(traceback.format_exc())
            return p_results  # 실패 시 원본 리스트 반환

    def _passes_basic_filters(self, p_result: PriceAttractivenessLegacy) -> bool:
        """기본 필터링 조건 확인 (개선: 점수 기반 통합 필터링)

        AND 조건 누적 탈락 문제 해결:
        - 기존: 5개 필터 모두 통과 필요 → 누적 탈락률 90%
        - 개선: 각 필터를 점수화하여 복합 점수 55% 이상이면 통과

        Args:
            p_result: 분석 결과

        Returns:
            필터링 통과 여부
        """
        # 점수 기반 통합 필터링 사용 여부 확인
        if self._filtering_criteria.use_score_based_filter:
            return self._score_based_filter(p_result)
        else:
            return self._legacy_and_filter(p_result)

    def _score_based_filter(self, p_result: PriceAttractivenessLegacy) -> bool:
        """점수 기반 통합 필터링 (개선된 방식)

        각 필터 항목을 0-100 점수로 변환 후 가중 합산
        복합 점수가 min_composite_score 이상이면 통과

        Args:
            p_result: 분석 결과

        Returns:
            필터링 통과 여부
        """
        scores = {}
        weights = {
            'price_attractiveness': 0.30,  # 가격 매력도 30%
            'risk': 0.25,                   # 리스크 25%
            'confidence': 0.20,             # 신뢰도 20%
            'technical': 0.15,              # 기술적 점수 15%
            'volume': 0.10,                 # 거래량 10%
        }

        # 1. 가격 매력도 점수화 (0-100)
        # 기준값의 80%면 50점, 100%면 80점, 120%면 100점
        threshold = self._filtering_criteria.price_attractiveness
        ratio = p_result.total_score / max(threshold, 1)
        scores['price_attractiveness'] = min(100, max(0, (ratio - 0.8) * 250))

        # 2. 리스크 점수화 (낮을수록 좋음, 역수)
        # 기준값의 80%면 100점, 100%면 70점, 120%면 40점
        risk_threshold = self._filtering_criteria.risk_score_max
        risk_ratio = p_result.risk_score / max(risk_threshold, 1)
        scores['risk'] = min(100, max(0, (1.4 - risk_ratio) * 100))

        # 3. 신뢰도 점수화 (0-100)
        conf_threshold = self._filtering_criteria.confidence_min
        conf_ratio = p_result.confidence / max(conf_threshold, 0.01)
        scores['confidence'] = min(100, max(0, (conf_ratio - 0.8) * 250))

        # 4. 기술적 점수화 (이미 0-100)
        tech_threshold = self._filtering_criteria.min_technical_score
        tech_ratio = p_result.technical_score / max(tech_threshold, 1)
        scores['technical'] = min(100, max(0, (tech_ratio - 0.8) * 250))

        # 5. 거래량 점수화 (이미 0-100)
        vol_threshold = self._filtering_criteria.liquidity_score
        vol_ratio = p_result.volume_score / max(vol_threshold, 1)
        scores['volume'] = min(100, max(0, (vol_ratio - 0.8) * 250))

        # 가중 합산
        composite_score = sum(scores[k] * weights[k] for k in weights)
        normalized_score = composite_score / 100  # 0-1 범위로 정규화

        # 로깅
        self._logger.debug(
            f"점수 기반 필터 - {p_result.stock_code}: "
            f"매력도={scores['price_attractiveness']:.0f}, "
            f"리스크={scores['risk']:.0f}, "
            f"신뢰도={scores['confidence']:.0f}, "
            f"기술={scores['technical']:.0f}, "
            f"거래량={scores['volume']:.0f} → "
            f"복합점수={normalized_score:.2f}"
        )

        # 통과 여부 판단
        passed = normalized_score >= self._filtering_criteria.min_composite_score

        if passed:
            self._logger.info(
                f"✅ {p_result.stock_code} ({p_result.stock_name}) 점수 기반 필터 통과! "
                f"복합점수: {normalized_score:.2f} >= {self._filtering_criteria.min_composite_score:.2f}"
            )
        else:
            self._logger.debug(
                f"❌ {p_result.stock_code} 점수 기반 필터 미달: "
                f"복합점수 {normalized_score:.2f} < {self._filtering_criteria.min_composite_score:.2f}"
            )

        return passed

    def _legacy_and_filter(self, p_result: PriceAttractivenessLegacy) -> bool:
        """기존 AND 필터링 방식 (호환성 유지용)

        Args:
            p_result: 분석 결과

        Returns:
            필터링 통과 여부
        """
        # 디버깅 로그
        self._logger.debug(f"AND 필터 검사: {p_result.stock_code} - "
                          f"total_score={p_result.total_score}, "
                          f"risk_score={p_result.risk_score}, "
                          f"confidence={p_result.confidence}, "
                          f"technical_score={p_result.technical_score}")

        # 가격 매력도 점수
        if p_result.total_score < self._filtering_criteria.price_attractiveness:
            return False

        # 리스크 점수
        if p_result.risk_score > self._filtering_criteria.risk_score_max:
            return False

        # 신뢰도
        if p_result.confidence < self._filtering_criteria.confidence_min:
            return False

        # 기술적 점수
        if p_result.technical_score < self._filtering_criteria.min_technical_score:
            return False

        # 거래량 점수
        if p_result.volume_score < self._filtering_criteria.liquidity_score:
            return False

        self._logger.info(f"✅ {p_result.stock_code} AND 필터 통과!")
        return True
    
    def _create_daily_trading_list(self, p_selected_stocks: List[PriceAttractivenessLegacy],
                                 p_market_condition: str, p_market_indicators: MarketIndicators) -> Dict:
        """일일 매매 리스트 생성
        
        Args:
            p_selected_stocks: 선정된 종목 리스트
            p_market_condition: 시장 상황
            p_market_indicators: 시장 지표
            
        Returns:
            일일 매매 리스트 데이터
        """
        _v_daily_selections = []
        _v_total_weight = 0.0
        
        for i, stock in enumerate(p_selected_stocks):
            # 포지션 사이징 계산
            _v_position_size = self._calculate_position_size(stock, len(p_selected_stocks))
            _v_total_weight += _v_position_size
            
            # predicted_class 계산: expected_return > 0이면 성공(1), 아니면 실패(0)
            _v_predicted_class = 1 if stock.expected_return > 0 else 0

            # DailySelection 객체 생성
            _v_selection = DailySelection(
                stock_code=stock.stock_code,
                stock_name=stock.stock_name,
                selection_date=datetime.now().strftime("%Y-%m-%d"),
                selection_reason=stock.selection_reason,
                price_attractiveness=stock.total_score,
                entry_price=stock.entry_price,
                target_price=stock.target_price,
                stop_loss=stock.stop_loss,
                expected_return=stock.expected_return,
                risk_score=stock.risk_score,
                volume_score=stock.volume_score,
                technical_signals=[signal.signal_name for signal in stock.technical_signals],
                sector=stock.sector,
                market_cap=0.0,  # 실제로는 stock에서 가져옴
                priority=i + 1,
                position_size=_v_position_size,
                confidence=stock.confidence,
                predicted_class=_v_predicted_class,
                model_name="ensemble"
            )
            
            _v_daily_selections.append(_v_selection)
        
        # 포지션 사이즈 정규화
        if _v_total_weight > 0:
            for selection in _v_daily_selections:
                selection.position_size = selection.position_size / _v_total_weight * 0.8  # 80% 투자
        
        # 섹터별 분포 계산
        _v_sector_distribution = {}
        for selection in _v_daily_selections:
            _v_sector_distribution[selection.sector] = _v_sector_distribution.get(selection.sector, 0) + 1
        
        # 메타데이터 생성
        _v_metadata = {
            "total_selected": len(_v_daily_selections),
            "watchlist_count": len(self._watchlist_manager.list_stocks(p_status="active")),
            "selection_rate": len(_v_daily_selections) / max(len(self._watchlist_manager.list_stocks(p_status="active")), 1),
            "avg_attractiveness": sum(s.price_attractiveness for s in _v_daily_selections) / max(len(_v_daily_selections), 1),
            "sector_distribution": _v_sector_distribution,
            "market_indicators": p_market_indicators.to_dict(),
            "filtering_criteria": asdict(self._filtering_criteria)
        }
        
        # 최종 일일 매매 리스트 구성
        _v_daily_list = {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "market_date": datetime.now().strftime("%Y-%m-%d"),
            "market_condition": p_market_condition,
            "data": {
                "selected_stocks": [selection.to_dict() for selection in _v_daily_selections]
            },
            "metadata": _v_metadata
        }
        
        return _v_daily_list
    
    def _calculate_position_size(self, p_stock: PriceAttractivenessLegacy, p_total_stocks: int) -> float:
        """포지션 사이즈 계산 (D단계: 포트폴리오 최적화 적용 가능)

        Args:
            p_stock: 종목 분석 결과
            p_total_stocks: 전체 선정 종목 수

        Returns:
            포지션 비중 (0-1)
        """
        # D단계: 포트폴리오 최적화가 활성화되면 최적 가중치 사용
        # 현재는 기본 스코어 기반 가중치 사용

        # 기본 균등 배분
        _v_base_weight = 1.0 / p_total_stocks

        # 점수와 신뢰도에 따른 가중치 조정
        _v_score_multiplier = p_stock.total_score / 100
        _v_confidence_multiplier = p_stock.confidence
        
        _v_adjusted_weight = _v_base_weight * _v_score_multiplier * _v_confidence_multiplier
        
        # 최대 20% 제한
        return min(_v_adjusted_weight, 0.2)
    
    def _save_daily_list(self, p_daily_list: Dict) -> bool:
        """일일 매매 리스트 저장
        
        Args:
            p_daily_list: 일일 매매 리스트 데이터
            
        Returns:
            저장 성공 여부
        """
        try:
            _v_date = datetime.now().strftime("%Y%m%d")
            _v_file_path = os.path.join(self._output_dir, f"daily_selection_{_v_date}.json")
            
            with open(_v_file_path, 'w', encoding='utf-8') as f:
                json.dump(p_daily_list, f, ensure_ascii=False, indent=2)
            
            # 최신 파일 링크 생성
            _v_latest_path = os.path.join(self._output_dir, "latest_selection.json")
            with open(_v_latest_path, 'w', encoding='utf-8') as f:
                json.dump(p_daily_list, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"일일 매매 리스트 저장 완료: {_v_file_path}")
            return True
            
        except Exception as e:
            self._logger.error(f"일일 매매 리스트 저장 실패: {e}", exc_info=True)
            return False
    
    def _send_notification(self, p_daily_list: Dict):
        """선정 결과 알림 발송
        
        Args:
            p_daily_list: 일일 매매 리스트 데이터
        """
        try:
            _v_selected_count = p_daily_list["metadata"]["total_selected"]
            _v_avg_score = p_daily_list["metadata"]["avg_attractiveness"]
            _v_market_condition = p_daily_list["market_condition"]
            
            _v_message = f"""
📈 일일 매매 리스트 업데이트
📅 날짜: {p_daily_list["market_date"]}
🎯 선정 종목: {_v_selected_count}개
📊 평균 점수: {_v_avg_score:.1f}점
🌊 시장 상황: {_v_market_condition}
            """.strip()
            
            self._logger.info(f"알림 발송: {_v_message}")
            # 실제로는 슬랙, 이메일, SMS 등으로 알림 발송
            
        except Exception as e:
            self._logger.error(f"알림 발송 실패: {e}", exc_info=True)
    
    def get_latest_selection(self) -> Optional[Dict]:
        """최신 일일 선정 결과 조회
        
        Returns:
            최신 일일 매매 리스트 (없으면 None)
        """
        try:
            _v_latest_path = os.path.join(self._output_dir, "latest_selection.json")
            
            if not os.path.exists(_v_latest_path):
                return None
            
            with open(_v_latest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            self._logger.error(f"최신 선정 결과 조회 실패: {e}", exc_info=True)
            return None
    
    def get_selection_history(self, p_days: int = 7) -> List[Dict]:
        """선정 이력 조회
        
        Args:
            p_days: 조회할 일수
            
        Returns:
            선정 이력 리스트
        """
        _v_history = []
        
        try:
            for i in range(p_days):
                _v_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                _v_file_path = os.path.join(self._output_dir, f"daily_selection_{_v_date}.json")
                
                if os.path.exists(_v_file_path):
                    with open(_v_file_path, 'r', encoding='utf-8') as f:
                        _v_data = json.load(f)
                        _v_history.append(_v_data)
            
            return _v_history
            
        except Exception as e:
            self._logger.error(f"선정 이력 조회 실패: {e}", exc_info=True)
            return []
    
    def update_filtering_criteria(self, p_criteria: FilteringCriteria):
        """필터링 기준 업데이트
        
        Args:
            p_criteria: 새로운 필터링 기준
        """
        self._filtering_criteria = p_criteria
        self._logger.info("필터링 기준 업데이트 완료")
    
    def _send_daily_update_complete_notification(self, selected_count: int) -> None:
        """일일 업데이트 완료 텔레그램 알림 전송"""
        try:
            notifier = get_telegram_notifier()
            if not notifier.is_enabled():
                self._logger.debug("텔레그램 알림이 비활성화됨")
                return
            
            # 일일 업데이트 완료 알림 전송
            success = notifier.send_daily_update_complete(selected_count)
            if success:
                self._logger.info("일일 업데이트 완료 텔레그램 알림 전송 성공")
                print("📱 일일 업데이트 완료 텔레그램 알림 전송됨")
            else:
                self._logger.warning("일일 업데이트 완료 텔레그램 알림 전송 실패")
                
        except Exception as e:
            self._logger.error(f"일일 업데이트 완료 알림 전송 오류: {e}", exc_info=True)


if __name__ == "__main__":
    # 테스트 실행
    updater = DailyUpdater()
    
    # 즉시 업데이트 실행
    print("일일 업데이트 테스트 실행...")
    success = updater.run_daily_update(p_force_run=True)
    
    if success:
        print("업데이트 성공!")
        
        # 최신 결과 조회
        latest = updater.get_latest_selection()
        if latest:
            selected_count = latest["metadata"]["total_selected"]
            avg_score = latest["metadata"]["avg_attractiveness"]
            print(f"선정 종목: {selected_count}개, 평균 점수: {avg_score:.1f}점")
    else:
        print("업데이트 실패!")
    
    # 스케줄러 테스트 (주석 해제하여 사용)
    # print("스케줄러 시작...")
    # updater.start_scheduler()
    # time.sleep(60)  # 1분 대기
    # updater.stop_scheduler()
    # print("스케줄러 종료") 