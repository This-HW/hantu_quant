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
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import threading

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from core.watchlist.watchlist_manager import WatchlistManager
from core.daily_selection.price_analyzer import PriceAnalyzer, PriceAttractivenessLegacy
from core.utils.log_utils import get_logger
from core.utils.telegram_notifier import get_telegram_notifier
from core.interfaces.trading import IDailyUpdater, PriceAttractiveness, DailySelection

# 새로운 아키텍처 imports - 사용 가능할 때만 import
try:
    from core.plugins.decorators import plugin  # noqa: F401
    from core.di.injector import inject  # noqa: F401

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
    """필터링 기준 데이터 클래스 (A단계: 강화된 기준 적용 - 현실적 조정)"""

    price_attractiveness: float = 46.0  # 가격 매력도 점수 기준 (상위 30%) [A단계]
    volume_threshold: float = 1.5  # 평균 거래량 대비 배수
    volatility_range: tuple = (0.1, 0.4)  # 변동성 범위 (10-40%)
    market_cap_min: float = 10000000000  # 최소 시가총액 (100억원)
    liquidity_score: float = 10.0  # 유동성 점수 기준
    risk_score_max: float = 43.0  # 최대 리스크 점수 (중위수 기준) [A단계]
    sector_limit: int = 3  # 섹터별 최대 종목 수 [A단계]
    total_limit: int = 20  # 전체 최대 종목 수 (95 → 20) [A단계]
    confidence_min: float = 0.62  # 최소 신뢰도 (상위 40%) [A단계]

    # A단계 추가: 상대 강도 필터
    min_relative_strength: float = 0.6  # 시장 대비 상위 40%
    min_technical_score: float = 40.0  # 기술적 점수 최소값


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
    expected_return: float  # 기대 수익률 필드 추가
    risk_score: float
    volume_score: float
    technical_signals: List[str]
    sector: str
    market_cap: float
    priority: int
    position_size: float  # 포트폴리오 비중
    confidence: float  # 신뢰도 (0-1)
    predicted_class: int = 1  # 예측 분류 (0: 실패예상, 1: 성공예상) - Phase 4 학습용
    model_name: str = "ensemble"  # 예측 모델명

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)

    def to_daily_selection(self) -> DailySelection:
        """새로운 DailySelection으로 변환"""
        return DailySelection(
            stock_code=self.stock_code,
            stock_name=self.stock_name,
            selection_date=(
                datetime.fromisoformat(self.selection_date)
                if isinstance(self.selection_date, str)
                else self.selection_date
            ),
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
            confidence=self.confidence,
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
    category="daily_selection",
)
class DailyUpdater(IDailyUpdater):
    """일일 업데이트 스케줄러 클래스 - 새로운 아키텍처 적용"""

    @inject
    def __init__(
        self,
        p_watchlist_file: str = "data/watchlist/watchlist.json",
        p_output_dir: str = "data/daily_selection",
        watchlist_manager=None,
        price_analyzer=None,
        logger=None,
        use_momentum_selector: bool = True,  # 새로운 모멘텀 선정 사용 여부
        total_capital: float = 10_000_000,
    ):  # 총 투자 자본금 (기본 1천만원)
        """초기화 메서드

        Args:
            p_watchlist_file: 감시 리스트 파일 경로
            p_output_dir: 출력 디렉토리
            watchlist_manager: 감시 리스트 관리자 (DI)
            price_analyzer: 가격 분석기 (DI)
            logger: 로거 (DI)
            use_momentum_selector: 새로운 모멘텀 기반 선정 사용 여부 (기본 True)
            total_capital: 총 투자 자본금 (포지션 사이징용)
        """
        self._watchlist_file = p_watchlist_file
        self._output_dir = p_output_dir
        self._logger = logger or get_logger(__name__)

        # 컴포넌트 초기화 (DI 또는 직접 생성)
        self._watchlist_manager = watchlist_manager or WatchlistManager(
            p_watchlist_file
        )
        self._price_analyzer = price_analyzer or PriceAnalyzer()
        self._market_analyzer = MarketConditionAnalyzer()

        # KIS API 인스턴스 (공유하여 rate limiting 적용)
        self._kis_api = None  # lazy initialization

        # 새로운 모멘텀 선정 시스템
        self._use_momentum_selector = use_momentum_selector
        self._total_capital = total_capital
        self._momentum_selector = None  # lazy initialization

        # 필터링 기준 및 상태
        self._filtering_criteria = FilteringCriteria()
        self._scheduler_running = False
        self._scheduler_thread = None

        # 출력 디렉토리 생성
        os.makedirs(self._output_dir, exist_ok=True)

        self._logger.info("DailyUpdater 초기화 완료 (새 아키텍처)")

    def initialize(self):
        """플러그인 초기화 메서드 (플러그인 데코레이터 요구사항)"""
        self._logger.info("DailyUpdater 플러그인 초기화 완료")
        return True

    def _get_kis_api(self):
        """KIS API 싱글톤 인스턴스 반환 (rate limiting 공유)"""
        if self._kis_api is None:
            from core.api.kis_api import KISAPI

            self._kis_api = KISAPI()
            self._logger.info("KIS API 인스턴스 초기화 완료")
        return self._kis_api

    def _get_momentum_selector(self):
        """MomentumSelector 싱글톤 인스턴스 반환 (API 인스턴스 공유)"""
        if self._momentum_selector is None:
            from core.selection import MomentumSelector

            # KIS API 인스턴스 공유 (Rate Limit 효율화)
            self._momentum_selector = MomentumSelector(api_client=self._get_kis_api())
            self._logger.info("MomentumSelector 인스턴스 초기화 완료 (API 공유)")
        return self._momentum_selector

    def run_daily_update(
        self,
        p_force_run: bool = False,
        distributed_mode: bool = False,
        batch_index: Optional[int] = None
    ) -> bool:
        """일일 업데이트 실행 (새 인터페이스 구현)

        Args:
            p_force_run: 강제 실행 여부
            distributed_mode: 분산 모드 활성화 (스케줄러 사용)
            batch_index: 배치 번호 (분산 모드 시)

        Returns:
            bool: 성공 여부
        """
        try:
            # 분산 모드 분기
            if distributed_mode:
                if batch_index is None:
                    self._logger.error("분산 모드에서 batch_index 필수")
                    return False
                return self.run_distributed_update(batch_index)

            # 기존 단일 실행 모드 (하위 호환)
            self._logger.info("=" * 50)
            self._logger.info("일일 업데이트 시작 (단일 실행 모드)")
            self._logger.info(
                f"선정 방식: {'모멘텀 기반 (신규)' if self._use_momentum_selector else '기존 방식'}"
            )

            # 1. 시장 상황 분석
            _v_market_condition = self.analyze_market_condition()

            # 2. 감시 리스트에서 종목 데이터 준비
            _v_watchlist_stocks = self._watchlist_manager.list_stocks(p_status="active")
            self._logger.info(f"감시 리스트 종목 수: {len(_v_watchlist_stocks)}개")

            if not _v_watchlist_stocks:
                self._logger.warning("감시 리스트에 종목이 없습니다")
                return False

            # ========================================
            # 선정 방식 분기
            # ========================================
            if self._use_momentum_selector:
                # 새로운 모멘텀 기반 선정
                _v_daily_list = self._run_momentum_selection(
                    _v_watchlist_stocks, _v_market_condition
                )
            else:
                # 기존 방식 선정
                _v_daily_list = self._run_legacy_selection(
                    _v_watchlist_stocks, _v_market_condition
                )

            # 결과 저장
            _v_save_success = self._save_daily_list(_v_daily_list)

            if _v_save_success:
                _v_stock_count = len(_v_daily_list.get("stocks", []))
                self._logger.info(
                    f"일일 업데이트 완료 - 선정 종목: {_v_stock_count}개"
                )

                # 텔레그램 알림
                self._send_daily_update_complete_notification(_v_stock_count)

                return True
            else:
                self._logger.error("일일 리스트 저장 실패")
                return False

        except Exception as e:
            import traceback

            self._logger.error(f"일일 업데이트 오류: {e}", exc_info=True)
            self._logger.error(f"상세 에러: {traceback.format_exc()}", exc_info=True)
            return False

    def _run_momentum_selection(
        self, watchlist_stocks: List[Dict], market_condition: str
    ) -> Dict:
        """
        새로운 모멘텀 기반 종목 선정

        Args:
            watchlist_stocks: 감시 리스트 종목들
            market_condition: 시장 상황

        Returns:
            Dict: 선정 결과 (stocks 키 포함, DB 저장 형식 호환)
        """
        try:
            self._logger.info("=== 모멘텀 기반 선정 시작 ===")

            # MomentumSelector 인스턴스
            selector = self._get_momentum_selector()

            # 종목 데이터 준비 (기존 형식 → 새 형식)
            prepared_stocks = self._prepare_stock_data(watchlist_stocks)

            # 모멘텀 기반 선정 실행
            selection_results = selector.select_stocks(
                watchlist=prepared_stocks, total_capital=self._total_capital
            )

            self._logger.info(f"모멘텀 선정 결과: {len(selection_results)}개")

            # 기존 형식으로 변환 (DailySelectionLegacy 호환)
            daily_list = []
            for result in selection_results:
                daily_item = {
                    "stock_code": result.stock_code,
                    "stock_name": result.stock_name,
                    "selection_date": result.selection_date,
                    "selection_reason": result.selection_reason,
                    "price_attractiveness": result.price_attractiveness,
                    "entry_price": result.entry_price,
                    "target_price": result.target_price,
                    "stop_loss": result.stop_loss,
                    "expected_return": result.expected_return,
                    "risk_score": result.risk_score,
                    "volume_score": result.volume_score,
                    "technical_signals": result.technical_signals,
                    "sector": result.sector,
                    "market_cap": result.market_cap,
                    "priority": result.priority,
                    "position_size": result.position_size,
                    "position_amount": result.position_amount,
                    "confidence": result.confidence,
                    "predicted_class": result.predicted_class,
                    "model_name": result.model_name,
                    # ATR 기반 신규 필드
                    "atr_value": result.atr_value,
                    "daily_volatility": result.daily_volatility,
                    "technical_score": result.technical_score,
                }
                daily_list.append(daily_item)

            # DB 저장 형식에 맞게 dict로 래핑 (fix: AttributeError 'list' has no .get())
            metadata = {
                "selection_method": "momentum",
                "total_stocks": len(daily_list),
                "selector_version": selector.__class__.__name__,
            }

            return {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "market_date": datetime.now().strftime("%Y-%m-%d"),
                "market_condition": market_condition,
                "data": {
                    "selected_stocks": daily_list
                },
                "stocks": daily_list,  # 호환성 유지 (DB 로드 형식과 통일)
                "metadata": metadata,
            }

        except Exception as e:
            self._logger.error(
                f"모멘텀 선정 실패, 기존 방식으로 폴백: {e}", exc_info=True
            )
            return self._run_legacy_selection(watchlist_stocks, market_condition)

    def _run_legacy_selection(
        self, watchlist_stocks: List[Dict], market_condition: str
    ) -> List[Dict]:
        """
        기존 방식 종목 선정 (폴백용)

        Args:
            watchlist_stocks: 감시 리스트 종목들
            market_condition: 시장 상황

        Returns:
            List[Dict]: 선정 종목 리스트
        """
        self._logger.info("=== 기존 방식 선정 시작 ===")

        # 시장 상황에 따른 기준 조정
        self._adjust_criteria_by_market(market_condition)

        # 종목 데이터 준비
        _v_stock_data_list = self._prepare_stock_data(watchlist_stocks)

        # 가격 매력도 분석
        _v_analysis_results = []
        for _v_stock_data in _v_stock_data_list:
            try:
                _v_result = self._price_analyzer.analyze_price_attractiveness(
                    _v_stock_data
                )
                _v_analysis_results.append(_v_result)
            except Exception as e:
                self._logger.debug(
                    f"종목 {_v_stock_data.get('stock_code')} 분석 오류: {e}"
                )
                continue

        # 필터링 및 선정
        _v_selected_stocks = self._filter_and_select_stocks(_v_analysis_results)

        # 일일 매매 리스트 생성
        _v_market_indicators = self._market_analyzer.get_market_indicators()
        _v_daily_list = self._create_daily_trading_list(
            _v_selected_stocks, market_condition, _v_market_indicators
        )

        return _v_daily_list

    def analyze_market_condition(self) -> str:
        """시장 상황 분석 (새 인터페이스 구현)"""
        return self._market_analyzer.analyze_market_condition()

    def filter_and_select_stocks(
        self, p_analysis_results: List[PriceAttractiveness]
    ) -> List[PriceAttractiveness]:
        """종목 필터링 및 선정 (새 인터페이스 구현)"""
        # PriceAttractiveness를 기존 형식으로 변환
        _v_legacy_results = []
        for result in p_analysis_results:
            _v_legacy_result = PriceAttractivenessLegacy(
                stock_code=result.stock_code,
                stock_name=result.stock_name,
                analysis_date=(
                    result.analysis_date.isoformat()
                    if isinstance(result.analysis_date, datetime)
                    else str(result.analysis_date)
                ),
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
                sector=result.sector,
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

    def create_daily_trading_list(
        self, p_selected_stocks: List[PriceAttractiveness]
    ) -> Dict:
        """일일 매매 리스트 생성 (새 인터페이스 구현)"""
        _v_market_condition = self.analyze_market_condition()
        _v_market_indicators = self._market_analyzer.get_market_indicators()

        # PriceAttractiveness를 기존 형식으로 변환
        _v_legacy_stocks = []
        for stock in p_selected_stocks:
            _v_legacy_stock = PriceAttractivenessLegacy(
                stock_code=stock.stock_code,
                stock_name=stock.stock_name,
                analysis_date=(
                    stock.analysis_date.isoformat()
                    if isinstance(stock.analysis_date, datetime)
                    else str(stock.analysis_date)
                ),
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
                sector=stock.sector,
            )
            _v_legacy_stocks.append(_v_legacy_stock)

        return self._create_daily_trading_list(
            _v_legacy_stocks, _v_market_condition, _v_market_indicators
        )

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
            self._scheduler_thread = threading.Thread(
                target=self._run_scheduler_loop, daemon=True
            )
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

    def _adjust_criteria_by_market(self, p_market_condition: str):
        """시장 상황에 따른 필터링 기준 조정

        Args:
            p_market_condition: 시장 상황
        """
        if p_market_condition == "bull_market":
            # 상승장: 기준 완화
            self._filtering_criteria.price_attractiveness = 65.0
            self._filtering_criteria.volume_threshold = 1.3
            self._filtering_criteria.risk_score_max = 50.0
            self._filtering_criteria.total_limit = 20

        elif p_market_condition == "bear_market":
            # 하락장: 기준 강화
            self._filtering_criteria.price_attractiveness = 80.0
            self._filtering_criteria.volume_threshold = 2.0
            self._filtering_criteria.risk_score_max = 30.0
            self._filtering_criteria.total_limit = 10

        else:  # sideways
            # 횡보장: 기본 기준 유지 (총량 제한 없음)
            self._filtering_criteria = FilteringCriteria()

        self._logger.info(f"필터링 기준 조정 완료 - 시장상황: {p_market_condition}")

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
                today_codes = {
                    s.get("stock_code")
                    for s in payload.get("stocks", [])
                    if s.get("stock_code")
                }
                if today_codes:
                    p_watchlist_stocks = [
                        s for s in p_watchlist_stocks if s.stock_code in today_codes
                    ]
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
                "volatility": stock_info.get(
                    "volatility", 0.15
                ),  # 일봉 데이터 기반 실제 변동성
                "sector_momentum": self._get_sector_momentum(stock.sector),
                "recent_close_prices": stock_info.get("recent_close_prices", []),
                "recent_volumes": stock_info.get("recent_volumes", []),
                "volume": stock_info.get("volume", 0),
                "avg_volume": stock_info.get("avg_volume", 0),
                "volume_ratio": stock_info.get("volume_ratio", 1.0),
            }
            _v_stock_data_list.append(_v_stock_data)

            # 진행 상황 로깅 (50개마다)
            if idx % 50 == 0:
                self._logger.info(f"API 데이터 조회 진행: {idx}/{total_stocks}개")

        self._logger.info(f"API 데이터 조회 완료: {total_stocks}개 종목")
        return _v_stock_data_list

    def _get_stock_info_combined(self, p_stock_code: str) -> Dict:
        """종목 정보 통합 조회 (현재가 + 시가총액 + 일봉 데이터)"""
        result = {
            "current_price": 0.0,
            "market_cap": 0.0,
            "recent_close_prices": [],
            "recent_volumes": [],
            "volume": 0,
            "avg_volume": 0,
            "volume_ratio": 1.0,
            "volatility": 0.15,  # 기본값 15%
        }
        try:
            kis = self._get_kis_api()

            # 1. 현재가 + 시가총액 조회
            info = kis.get_stock_info(p_stock_code) or {}
            result["current_price"] = float(info.get("current_price", 0.0))
            result["market_cap"] = float(info.get("market_cap", 0.0))

            # 2. 일봉 데이터 조회 (최근 30일)
            df_history = kis.get_stock_history(p_stock_code, period="D", count=30)
            if df_history is not None and not df_history.empty:
                # close, volume 컬럼 추출 (오래된 순서로 정렬)
                df_sorted = df_history.sort_values(by="date", ascending=True)
                result["recent_close_prices"] = df_sorted["close"].tolist()
                result["recent_volumes"] = df_sorted["volume"].tolist()

                # 거래량 관련 지표 계산
                volumes = result["recent_volumes"]
                if volumes:
                    result["volume"] = volumes[-1] if volumes else 0  # 최근 거래량
                    result["avg_volume"] = (
                        sum(volumes) / len(volumes) if volumes else 0
                    )  # 평균 거래량
                    if result["avg_volume"] > 0:
                        result["volume_ratio"] = (
                            result["volume"] / result["avg_volume"]
                        )  # 거래량 비율

                # 변동성 계산 (일간 수익률의 표준편차)
                prices = result["recent_close_prices"]
                if len(prices) >= 2:
                    import numpy as np

                    returns = np.diff(prices) / np.array(prices[:-1])
                    result["volatility"] = (
                        float(np.std(returns)) if len(returns) > 0 else 0.15
                    )

            return result
        except Exception as e:
            self._logger.warning(
                f"종목 정보 조회 실패 ({p_stock_code}): {e}", exc_info=True
            )
            return result

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

    def _filter_and_select_stocks(
        self, p_analysis_results: List[PriceAttractivenessLegacy]
    ) -> List[PriceAttractivenessLegacy]:
        """분석 결과를 필터링하여 매매 대상 선정 (방안 A + 방안 C 통합)

        Args:
            p_analysis_results: 가격 매력도 분석 결과 리스트

        Returns:
            선정된 종목 리스트
        """
        _v_filtered_stocks = []
        _v_sector_count = {}

        # 점수순으로 정렬
        _v_sorted_results = sorted(
            p_analysis_results, key=lambda x: x.total_score, reverse=True
        )

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
            if (
                self._filtering_criteria.total_limit
                and len(_v_filtered_stocks) >= self._filtering_criteria.total_limit
            ):
                break

            _v_filtered_stocks.append(result)
            _v_sector_count[result.sector] += 1

        self._logger.info(
            f"필터링 완료: {len(_v_filtered_stocks)}개 종목 선정 (추세 + 멀티전략 필터)"
        )
        return _v_filtered_stocks

    def _apply_trend_filter(
        self, p_results: List[PriceAttractivenessLegacy]
    ) -> List[PriceAttractivenessLegacy]:
        """추세 추종 필터 적용 (방안 A 통합)

        Args:
            p_results: 분석 결과 리스트

        Returns:
            추세 조건을 통과한 종목 리스트
        """
        try:
            from core.daily_selection.trend_follower import get_trend_follower

            trend_follower = get_trend_follower()
            api = self._get_kis_api()  # 싱글톤 사용하여 rate limiting 공유

            # 종목별 가격 데이터 수집
            market_data = {}
            for result in p_results:
                try:
                    df = api.get_stock_history(result.stock_code, period="D", count=60)
                    if df is not None and len(df) >= 60:
                        market_data[result.stock_code] = df
                except Exception as e:
                    self._logger.debug(
                        f"종목 {result.stock_code} 가격 데이터 수집 실패: {e}"
                    )
                    continue

            # 추세 추종 필터 적용
            stocks_dict = [
                {"stock_code": r.stock_code, "stock_name": r.stock_name}
                for r in p_results
            ]
            filtered_codes = {
                s["stock_code"]
                for s in trend_follower.filter_stocks(stocks_dict, market_data)
            }

            # 추세 조건 통과한 종목만 반환
            trend_filtered = [r for r in p_results if r.stock_code in filtered_codes]

            self._logger.info(
                f"추세 추종 필터: {len(p_results)}개 → {len(trend_filtered)}개"
            )

            return trend_filtered

        except Exception as e:
            self._logger.warning(f"추세 필터 적용 실패 (원본 리스트 사용): {e}")
            return p_results  # 실패 시 원본 리스트 반환

    def _apply_multi_strategy_ensemble(
        self, p_results: List[PriceAttractivenessLegacy]
    ) -> List[PriceAttractivenessLegacy]:
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
            market_index_data = api.get_stock_history(
                "0001", period="D", count=60
            )  # KOSPI 지수

            if market_index_data is None or len(market_index_data) < 20:
                self._logger.warning("시장 지수 데이터 부족 - 멀티 전략 건너뜀")
                return p_results

            # 종목 데이터를 Dict 형식으로 변환
            candidate_stocks = []
            result_map = {}  # stock_code -> PriceAttractivenessLegacy 매핑

            for result in p_results:
                stock_dict = {
                    "stock_code": result.stock_code,
                    "stock_name": result.stock_name,
                    "price_attractiveness": result.total_score,
                    "technical_score": result.technical_score,
                    "risk_score": result.risk_score,
                    "confidence": result.confidence,
                    "volume_score": result.volume_score,
                }
                candidate_stocks.append(stock_dict)
                result_map[result.stock_code] = result

            # 앙상블 방식으로 종목 선정 (최대 30개)
            ensemble_stocks = multi_strategy.get_ensemble_stocks(
                candidate_stocks=candidate_stocks,
                market_index_data=market_index_data,
                max_stocks=min(30, len(candidate_stocks)),
            )

            # 선정된 종목들을 원본 객체로 복구하고 앙상블 점수로 정렬
            ensemble_results = []
            for stock in ensemble_stocks:
                code = stock["stock_code"]
                original = result_map[code]
                # 앙상블 점수를 기록 (나중에 참고용)
                original.ensemble_score = stock.get(
                    "ensemble_score", original.total_score
                )
                ensemble_results.append(original)

            self._logger.info(
                f"멀티 전략 앙상블: {len(p_results)}개 → {len(ensemble_results)}개"
            )

            return ensemble_results

        except Exception as e:
            self._logger.warning(f"멀티 전략 앙상블 적용 실패 (원본 리스트 사용): {e}")
            import traceback

            self._logger.debug(traceback.format_exc())
            return p_results  # 실패 시 원본 리스트 반환

    def _passes_basic_filters(self, p_result: PriceAttractivenessLegacy) -> bool:
        """기본 필터링 조건 확인 (안전 필터만 적용 - Phase A 개선)

        Args:
            p_result: 분석 결과

        Returns:
            필터링 통과 여부
        """
        # Phase A 개선: 안전 필터만 적용 (과도한 리스크만 제외)

        # 리스크 점수 (완화: 60점 이하)
        if p_result.risk_score > 60:
            self._logger.debug(
                f"❌ {p_result.stock_code} 리스크 필터링 실패: {p_result.risk_score} > 60"
            )
            return False

        # 최소 유동성 (완화: 5점 이상)
        if p_result.volume_score < 5:
            self._logger.debug(
                f"❌ {p_result.stock_code} 거래량 필터링 실패: {p_result.volume_score} < 5"
            )
            return False

        self._logger.debug(f"✅ {p_result.stock_code} 안전 필터 통과")
        return True

    def _calculate_composite_score(self, stock_data: Dict) -> float:
        """종합 점수 계산 (Phase A 개선)

        Args:
            stock_data: 종목 데이터

        Returns:
            종합 점수 (0-100)
        """
        technical = stock_data.get("technical_score", 0)
        volume = stock_data.get("volume_score", 0)
        risk = stock_data.get("risk_score", 50)
        confidence = stock_data.get("confidence", 0.5)

        composite = (
            technical * 0.35 +
            volume * 0.25 +
            (100 - risk) * 0.25 +
            confidence * 100 * 0.15
        )
        return composite

    def _select_top_n_adaptive(
        self,
        candidates: List[Dict],
        market_condition: str
    ) -> List[Dict]:
        """시장 적응형 상위 N개 선정 (Phase A 개선)

        Args:
            candidates: 후보 종목 리스트 (안전 필터 통과한 종목들)
            market_condition: 시장 상황 (bullish/neutral/bearish)

        Returns:
            선정된 종목 리스트
        """
        if not candidates:
            return []

        # 1. 종합 점수 계산
        for stock in candidates:
            stock["composite_score"] = self._calculate_composite_score(stock)

        # 2. 종합 점수로 정렬 (내림차순)
        candidates.sort(key=lambda x: x["composite_score"], reverse=True)

        # 3. 시장 상황별 목표 선정 수
        target_counts = {
            "bullish": 12,
            "neutral": 8,
            "bearish": 5
        }
        target_count = target_counts.get(market_condition, 8)

        self._logger.info(
            f"시장 상황: {market_condition}, 목표 선정 수: {target_count}개, "
            f"후보 종목: {len(candidates)}개"
        )

        # 4. 섹터별 제한 적용하며 선정
        selected = []
        sector_count = {}

        for stock in candidates:
            sector = stock.get("sector", "기타")

            # 섹터당 최대 3개 제한
            if sector_count.get(sector, 0) >= 3:
                self._logger.debug(
                    f"섹터 제한: {stock['stock_code']} ({sector}) - "
                    f"이미 {sector_count[sector]}개 선정됨"
                )
                continue

            selected.append(stock)
            sector_count[sector] = sector_count.get(sector, 0) + 1

            # 목표 수량 도달 시 종료
            if len(selected) >= target_count:
                break

        self._logger.info(
            f"선정 완료: {len(selected)}개 종목 (섹터 분포: {sector_count})"
        )

        return selected

    def _create_daily_trading_list(
        self,
        p_selected_stocks: List[PriceAttractivenessLegacy],
        p_market_condition: str,
        p_market_indicators: MarketIndicators,
    ) -> Dict:
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
            _v_position_size = self._calculate_position_size(
                stock, len(p_selected_stocks)
            )
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
                technical_signals=[
                    signal.signal_name for signal in stock.technical_signals
                ],
                sector=stock.sector,
                market_cap=0.0,  # 실제로는 stock에서 가져옴
                priority=i + 1,
                position_size=_v_position_size,
                confidence=stock.confidence,
                predicted_class=_v_predicted_class,
                model_name="ensemble",
            )

            _v_daily_selections.append(_v_selection)

        # 포지션 사이즈 정규화
        if _v_total_weight > 0:
            for selection in _v_daily_selections:
                selection.position_size = (
                    selection.position_size / _v_total_weight * 0.8
                )  # 80% 투자

        # 섹터별 분포 계산
        _v_sector_distribution = {}
        for selection in _v_daily_selections:
            _v_sector_distribution[selection.sector] = (
                _v_sector_distribution.get(selection.sector, 0) + 1
            )

        # 메타데이터 생성
        _v_metadata = {
            "total_selected": len(_v_daily_selections),
            "watchlist_count": len(
                self._watchlist_manager.list_stocks(p_status="active")
            ),
            "selection_rate": len(_v_daily_selections)
            / max(len(self._watchlist_manager.list_stocks(p_status="active")), 1),
            "avg_attractiveness": sum(
                s.price_attractiveness for s in _v_daily_selections
            )
            / max(len(_v_daily_selections), 1),
            "sector_distribution": _v_sector_distribution,
            "market_indicators": p_market_indicators.to_dict(),
            "filtering_criteria": asdict(self._filtering_criteria),
        }

        # 최종 일일 매매 리스트 구성
        # 선정 종목 리스트 생성
        selected_stocks_list = [selection.to_dict() for selection in _v_daily_selections]

        _v_daily_list = {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "market_date": datetime.now().strftime("%Y-%m-%d"),
            "market_condition": p_market_condition,
            "data": {
                "selected_stocks": selected_stocks_list
            },
            "stocks": selected_stocks_list,  # 호환성 유지 (DB 로드 형식과 통일)
            "metadata": _v_metadata,
        }

        return _v_daily_list

    def _calculate_position_size(
        self, p_stock: PriceAttractivenessLegacy, p_total_stocks: int
    ) -> float:
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

        _v_adjusted_weight = (
            _v_base_weight * _v_score_multiplier * _v_confidence_multiplier
        )

        # 최대 20% 제한
        return min(_v_adjusted_weight, 0.2)

    def _save_daily_list(self, p_daily_list: Dict) -> bool:
        """일일 매매 리스트 저장 (DB 우선, 실패 시 JSON 폴백)

        Args:
            p_daily_list: 일일 매매 리스트 데이터

        Returns:
            저장 성공 여부
        """
        try:
            _v_date = datetime.now().strftime("%Y%m%d")
            _v_selection_date = datetime.now().date()

            # list가 전달된 경우 dict로 감싸기
            if isinstance(p_daily_list, list):
                p_daily_list = {"stocks": p_daily_list, "market_condition": ""}

            # === 1. DB에 저장 시도 ===
            db_saved = self._save_selection_to_db(p_daily_list, _v_selection_date)
            if db_saved:
                self._logger.info("선정 결과 DB 저장 완료")
                return True

            # === 2. DB 실패 시에만 JSON 폴백 저장 ===
            self._logger.warning("선정 결과 DB 저장 실패 - JSON 폴백 저장")

            _v_file_path = os.path.join(
                self._output_dir, f"daily_selection_{_v_date}.json"
            )

            # 폴백 여부를 metadata에 추가
            if "metadata" in p_daily_list:
                p_daily_list["metadata"]["db_fallback"] = True

            # 디렉토리 생성
            os.makedirs(self._output_dir, exist_ok=True)

            with open(_v_file_path, "w", encoding="utf-8") as f:
                json.dump(p_daily_list, f, ensure_ascii=False, indent=2)

            # 최신 파일 링크 생성
            _v_latest_path = os.path.join(self._output_dir, "latest_selection.json")
            with open(_v_latest_path, "w", encoding="utf-8") as f:
                json.dump(p_daily_list, f, ensure_ascii=False, indent=2)

            self._logger.info(f"일일 매매 리스트 JSON 폴백 저장 완료: {_v_file_path}")
            return True

        except Exception as e:
            self._logger.error(f"일일 매매 리스트 저장 실패: {e}", exc_info=True)
            return False

    def _convert_to_native_type(self, value):
        """Numpy 타입을 Python 네이티브 타입으로 변환

        Args:
            value: 변환할 값

        Returns:
            Python 네이티브 타입으로 변환된 값
        """
        if value is None:
            return None
        # numpy 타입 확인 (hasattr로 item 메서드 확인)
        if hasattr(value, "item"):
            return value.item()
        return value

    def _save_selection_to_db(self, p_daily_list: Dict, p_selection_date) -> bool:
        """선정 결과를 DB에 저장

        Args:
            p_daily_list: 일일 매매 리스트 데이터
            p_selection_date: 선정 날짜

        Returns:
            저장 성공 여부
        """
        try:
            from core.database.session import DatabaseSession
            from core.database.models import SelectionResult

            db = DatabaseSession()
            with db.get_session() as session:
                # 기존 데이터 삭제 (같은 날짜)
                session.query(SelectionResult).filter(
                    SelectionResult.selection_date == p_selection_date
                ).delete()

                # 새 데이터 저장
                saved_count = 0
                stocks = p_daily_list.get("stocks", [])
                market_condition = p_daily_list.get("market_condition", "")

                for stock in stocks:
                    selection_record = SelectionResult(
                        selection_date=p_selection_date,
                        stock_code=stock.get("stock_code", ""),
                        stock_name=stock.get("stock_name", ""),
                        total_score=self._convert_to_native_type(
                            stock.get("total_score", 0.0)
                        ),
                        technical_score=self._convert_to_native_type(
                            stock.get("technical_score", 0.0)
                        ),
                        volume_score=self._convert_to_native_type(
                            stock.get("volume_score", 0.0)
                        ),
                        pattern_score=self._convert_to_native_type(
                            stock.get("pattern_score", 0.0)
                        ),
                        risk_score=self._convert_to_native_type(
                            stock.get("risk_score", 0.0)
                        ),
                        entry_price=self._convert_to_native_type(
                            stock.get("entry_price")
                        ),
                        target_price=self._convert_to_native_type(
                            stock.get("target_price")
                        ),
                        stop_loss=self._convert_to_native_type(stock.get("stop_loss")),
                        expected_return=self._convert_to_native_type(
                            stock.get("expected_return")
                        ),
                        confidence=self._convert_to_native_type(
                            stock.get("confidence")
                        ),
                        signal=stock.get("signal", "buy"),
                        selection_reason=stock.get("selection_reason", ""),
                        market_condition=market_condition,
                    )
                    session.add(selection_record)
                    saved_count += 1

                session.commit()
                self._logger.info(f"선정 결과 DB 저장 완료: {saved_count}건")
                return True

        except Exception as e:
            self._logger.error(f"선정 결과 DB 저장 실패: {e}", exc_info=True)
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
        """최신 일일 선정 결과 조회 (DB 우선, JSON 폴백)

        Returns:
            최신 일일 매매 리스트 (없으면 None)
        """
        # === 1. DB에서 먼저 로드 시도 ===
        try:
            from core.database.session import DatabaseSession
            from core.database.models import SelectionResult

            db = DatabaseSession()
            with db.get_session() as session:
                # 가장 최근 날짜의 선정 결과 조회
                from sqlalchemy import func

                latest_date = session.query(
                    func.max(SelectionResult.selection_date)
                ).scalar()

                if latest_date:
                    results = (
                        session.query(SelectionResult)
                        .filter(SelectionResult.selection_date == latest_date)
                        .all()
                    )

                    if results:
                        stocks = []
                        for r in results:
                            stocks.append(
                                {
                                    "stock_code": r.stock_code,
                                    "stock_name": r.stock_name,
                                    "total_score": r.total_score,
                                    "technical_score": r.technical_score,
                                    "volume_score": r.volume_score,
                                    "entry_price": r.entry_price,
                                    "target_price": r.target_price,
                                    "stop_loss": r.stop_loss,
                                    "signal": r.signal,
                                    "confidence": r.confidence,
                                    "selection_reason": r.selection_reason,
                                }
                            )

                        self._logger.info(
                            f"최신 선정 결과 DB 로드: {len(stocks)}개 ({latest_date})"
                        )
                        # JSON 저장 형식과 일치하도록 반환
                        return {
                            "market_date": str(latest_date),
                            "data": {
                                "selected_stocks": stocks
                            },
                            "stocks": stocks,  # 호환성 유지
                            "metadata": {
                                "total_selected": len(stocks),
                                "source": "database",
                            },
                        }

        except Exception as e:
            self._logger.warning(f"DB 로드 실패, JSON 폴백: {e}")

        # === 2. JSON 파일에서 폴백 로드 ===
        try:
            _v_latest_path = os.path.join(self._output_dir, "latest_selection.json")

            if not os.path.exists(_v_latest_path):
                return None

            with open(_v_latest_path, "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception as e:
            self._logger.error(f"최신 선정 결과 조회 실패: {e}", exc_info=True)
            return None

    def get_selection_history(self, p_days: int = 7) -> List[Dict]:
        """선정 이력 조회 (DB 우선, JSON 폴백)

        Args:
            p_days: 조회할 일수

        Returns:
            선정 이력 리스트
        """
        # === 1. DB에서 먼저 로드 시도 ===
        try:
            from core.database.session import DatabaseSession
            from core.database.models import SelectionResult

            db = DatabaseSession()
            with db.get_session() as session:
                # 최근 p_days일간의 고유한 날짜 조회
                start_date = (datetime.now() - timedelta(days=p_days)).date()
                dates = (
                    session.query(SelectionResult.selection_date)
                    .filter(SelectionResult.selection_date >= start_date)
                    .distinct()
                    .order_by(SelectionResult.selection_date.desc())
                    .all()
                )

                if dates:
                    _v_history = []
                    for (date_val,) in dates:
                        results = (
                            session.query(SelectionResult)
                            .filter(SelectionResult.selection_date == date_val)
                            .all()
                        )

                        stocks = []
                        for r in results:
                            stocks.append(
                                {
                                    "stock_code": r.stock_code,
                                    "stock_name": r.stock_name,
                                    "total_score": r.total_score,
                                    "technical_score": r.technical_score,
                                    "signal": r.signal,
                                }
                            )

                        _v_history.append(
                            {
                                "market_date": str(date_val),
                                "stocks": stocks,
                                "metadata": {
                                    "total_selected": len(stocks),
                                    "source": "database",
                                },
                            }
                        )

                    self._logger.info(f"선정 이력 DB 로드: {len(_v_history)}일치")
                    return _v_history

        except Exception as e:
            self._logger.warning(f"DB 이력 로드 실패, JSON 폴백: {e}")

        # === 2. JSON 파일에서 폴백 로드 ===
        _v_history = []

        try:
            for i in range(p_days):
                _v_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                _v_file_path = os.path.join(
                    self._output_dir, f"daily_selection_{_v_date}.json"
                )

                if os.path.exists(_v_file_path):
                    with open(_v_file_path, "r", encoding="utf-8") as f:
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

    # ==================== 분산 배치 처리 메서드 ====================

    def calculate_composite_priority(self, stock_dict: Dict) -> float:
        """복합 우선순위 계산 (기술적 점수 50% + 거래량 30% + 변동성 20%)

        Args:
            stock_dict: 종목 딕셔너리

        Returns:
            float: 0-100점 정규화된 우선순위
        """
        try:
            # 기술적 점수 (0-100)
            technical = stock_dict.get("technical_score", 50.0)

            # 거래량 점수 (0-100)
            volume = stock_dict.get("volume_score", 50.0)

            # 변동성 점수 (0-100, 변동성이 적절한 범위일수록 높음)
            volatility_raw = stock_dict.get("volatility", 0.15)
            # 변동성 10-30%를 최적 범위로 정규화
            if volatility_raw < 0.1:
                volatility_score = volatility_raw * 500  # 0-50점
            elif volatility_raw <= 0.3:
                volatility_score = 100.0  # 최적 범위
            else:
                volatility_score = max(0, 100 - (volatility_raw - 0.3) * 200)  # 감점

            # 복합 우선순위 계산
            composite = (
                technical * 0.5 +
                volume * 0.3 +
                volatility_score * 0.2
            )

            return max(0.0, min(100.0, composite))

        except Exception as e:
            self._logger.warning(f"우선순위 계산 실패: {e}", exc_info=True)
            return 50.0  # 기본값

    def distribute_stocks_to_batches(
        self,
        watchlist_stocks: List[Dict],
        num_batches: int = 18
    ) -> List[List[Dict]]:
        """감시 리스트를 18개 배치로 균등 분산

        Args:
            watchlist_stocks: 전체 감시 리스트 (Phase 1 완료 후)
            num_batches: 배치 수 (기본 18개)

        Returns:
            List[List[Dict]]: 18개 배치 리스트

        배치 전략:
        - 총 종목 수를 18로 나눔 (예: 360개 → 20개/배치)
        - 우선순위 순으로 라운드로빈 배치 (고른 분산)
        - 마지막 배치는 나머지 종목 포함
        """
        try:
            total_count = len(watchlist_stocks)
            self._logger.info(f"배치 분산 시작: 총 {total_count}개 종목 → {num_batches}개 배치")

            if total_count == 0:
                self._logger.warning("감시 리스트가 비어있음")
                return [[] for _ in range(num_batches)]

            # 1. 우선순위 계산 및 정렬
            stocks_with_priority = []
            for stock in watchlist_stocks:
                priority = self.calculate_composite_priority(stock)
                stocks_with_priority.append({
                    **stock,
                    "composite_priority": priority
                })

            # 우선순위 내림차순 정렬 (높은 우선순위가 앞)
            stocks_with_priority.sort(key=lambda x: x["composite_priority"], reverse=True)

            # 2. 라운드로빈 배치 분산
            batches = [[] for _ in range(num_batches)]
            for idx, stock in enumerate(stocks_with_priority):
                batch_idx = idx % num_batches
                batches[batch_idx].append(stock)

            # 3. 배치별 통계 로깅
            for i, batch in enumerate(batches):
                if batch:
                    priorities = [s["composite_priority"] for s in batch]
                    avg_priority = sum(priorities) / len(priorities)
                    self._logger.info(
                        f"배치 {i}: {len(batch)}개 종목, "
                        f"평균 우선순위: {avg_priority:.2f}, "
                        f"범위: {min(priorities):.2f}-{max(priorities):.2f}"
                    )
                else:
                    self._logger.info(f"배치 {i}: 0개 종목")

            self._logger.info(f"배치 분산 완료: {num_batches}개 배치 생성")
            return batches

        except Exception as e:
            self._logger.error(f"배치 분산 실패: {e}", exc_info=True)
            # 실패 시 빈 배치 반환
            return [[] for _ in range(num_batches)]

    async def process_batch(
        self,
        batch_index: int,
        batch_stocks: List[Dict],
        market_condition: str
    ) -> List[Dict]:
        """단일 배치 처리 (비동기)

        Args:
            batch_index: 배치 번호 (0-17)
            batch_stocks: 배치 종목 리스트
            market_condition: 시장 상황

        Returns:
            List[Dict]: 선정된 종목 리스트

        처리 흐름:
        1. 배치 시작 로깅
        2. AsyncKISAPI 사용하여 병렬 가격 조회
        3. 가격 매력도 분석
        4. 필터링 기준 적용
        5. 선정 결과 반환
        6. 에러 시 빈 리스트 반환 (부분 실패 허용)
        """
        try:
            self._logger.info(f"배치 {batch_index} 처리 시작: {len(batch_stocks)}개 종목")

            if not batch_stocks:
                self._logger.warning(f"배치 {batch_index}: 종목 없음")
                return []

            # AsyncKISClient 사용하여 병렬 가격 조회
            try:
                from core.api.async_client import AsyncKISClient
                async_api = AsyncKISClient()
            except Exception as e:
                self._logger.error(f"AsyncKISClient import 실패: {e}", exc_info=True)
                return []

            # 병렬 가격 조회
            selected_stocks = []
            tasks = []
            stock_codes = [s.get("stock_code") or s.get("stock_code") for s in batch_stocks]

            for stock in batch_stocks:
                stock_code = stock.get("stock_code")
                if not stock_code:
                    continue
                # 비동기 가격 조회 태스크 생성
                task = async_api.get_price(stock_code)
                tasks.append((stock, task))

            # 병렬 실행
            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

            # 결과 처리
            for (stock, _), result in zip(tasks, results):
                try:
                    if isinstance(result, Exception):
                        self._logger.debug(f"가격 조회 실패 ({stock.get('stock_code')}): {result}")
                        continue

                    current_price = result.current_price if result else 0.0
                    if current_price <= 0:
                        continue

                    # 가격 매력도 분석
                    stock_data = {
                        **stock,
                        "current_price": current_price
                    }

                    # PriceAnalyzer로 분석
                    analysis_result = self._price_analyzer.analyze_price_attractiveness(stock_data)

                    # 필터링 기준 적용
                    if self._passes_basic_filters(analysis_result):
                        selected_stocks.append({
                            "stock_code": stock.get("stock_code"),
                            "stock_name": stock.get("stock_name"),
                            "current_price": current_price,
                            "total_score": analysis_result.total_score,
                            "technical_score": analysis_result.technical_score,
                            "volume_score": analysis_result.volume_score,
                            "risk_score": analysis_result.risk_score,
                            "confidence": analysis_result.confidence,
                            "entry_price": analysis_result.entry_price,
                            "target_price": analysis_result.target_price,
                            "stop_loss": analysis_result.stop_loss,
                            "expected_return": analysis_result.expected_return,
                            "selection_reason": analysis_result.selection_reason,
                            "sector": stock.get("sector", "기타"),
                            "market_cap": stock.get("market_cap", 0.0),
                        })

                except Exception as e:
                    self._logger.debug(f"종목 처리 실패 ({stock.get('stock_code')}): {e}")
                    continue

            # 진행률 로깅
            self._logger.info(
                f"배치 {batch_index} 완료: {len(selected_stocks)}/{len(batch_stocks)} 종목 선정"
            )

            return selected_stocks

        except Exception as e:
            self._logger.error(f"배치 {batch_index} 처리 실패: {e}", exc_info=True)
            return []  # 부분 실패 허용

    def wait_for_phase1(self, timeout: int = 1800) -> bool:
        """Phase 1 (종목 스크리닝) 완료 대기

        Args:
            timeout: 최대 대기 시간 (초, 기본 30분)

        Returns:
            bool: Phase 1 완료 여부

        완료 조건:
        - data/watchlist/watchlist.json 파일 존재
        - 파일 수정 시간이 금일 06:00 이후
        - 파일 크기 > 0
        """
        try:
            self._logger.info("Phase 1 완료 대기 시작...")
            watchlist_file = Path(self._watchlist_file)
            today = datetime.now().date()
            target_time = datetime.combine(today, datetime.min.time()).replace(hour=6, minute=0)

            start_time = time.time()
            poll_interval = 60  # 1분 간격

            while time.time() - start_time < timeout:
                # 1. 파일 존재 확인
                if not watchlist_file.exists():
                    self._logger.debug(f"watchlist.json 파일 없음, {poll_interval}초 후 재시도...")
                    time.sleep(poll_interval)
                    continue

                # 2. 파일 크기 확인
                if watchlist_file.stat().st_size == 0:
                    self._logger.debug(f"watchlist.json 파일 비어있음, {poll_interval}초 후 재시도...")
                    time.sleep(poll_interval)
                    continue

                # 3. 파일 수정 시간 확인
                mtime = datetime.fromtimestamp(watchlist_file.stat().st_mtime)
                if mtime >= target_time:
                    self._logger.info(f"Phase 1 완료 확인: {watchlist_file} (수정 시간: {mtime})")
                    return True

                self._logger.debug(
                    f"Phase 1 미완료 (수정 시간: {mtime} < {target_time}), "
                    f"{poll_interval}초 후 재시도..."
                )
                time.sleep(poll_interval)

            # timeout 초과
            self._logger.warning(f"Phase 1 대기 timeout ({timeout}초 초과)")
            return False

        except Exception as e:
            self._logger.error(f"Phase 1 대기 중 오류: {e}", exc_info=True)
            return False

    def run_distributed_update(
        self,
        batch_index: int,
        total_batches: int = 18
    ) -> bool:
        """분산 배치 실행 진입점 (스케줄러에서 호출)

        Args:
            batch_index: 현재 배치 번호 (0-17)
            total_batches: 전체 배치 수

        Returns:
            bool: 성공 여부

        처리 흐름:
        1. batch_index == 0일 때만 Phase 1 완료 대기
        2. 배치 분산 수행 (첫 호출 시만)
        3. 해당 배치 처리
        4. 부분 결과 저장 (data/daily_selection/batch_{batch_index}.json)
        5. batch_index == 17일 때 최종 병합
        """
        try:
            self._logger.info("=" * 60)
            self._logger.info(f"분산 배치 실행: 배치 {batch_index}/{total_batches - 1}")

            # 1. 첫 배치일 때만 Phase 1 완료 대기
            if batch_index == 0:
                self._logger.info("첫 배치: Phase 1 완료 대기...")
                if not self.wait_for_phase1():
                    self._logger.error("Phase 1 완료 대기 실패")
                    return False
                self._logger.info("Phase 1 완료 확인됨")

            # 2. 시장 상황 분석
            market_condition = self.analyze_market_condition()

            # 3. 감시 리스트 로드
            watchlist_stocks = self._watchlist_manager.list_stocks(p_status="active")
            self._logger.info(f"감시 리스트 종목 수: {len(watchlist_stocks)}개")

            if not watchlist_stocks:
                self._logger.warning("감시 리스트 비어있음")
                return False

            # 4. 배치 분산 (Redis 캐시 사용하여 중복 방지)
            try:
                from core.api.redis_client import cache
                cache_key = f"daily_batches:{datetime.now().strftime('%Y%m%d')}"

                # 캐시에서 배치 로드 시도
                cached_batches = cache.get(cache_key)
                if cached_batches:
                    self._logger.info("Redis에서 배치 정보 로드")
                    batches = cached_batches
                else:
                    # 배치 분산 수행
                    self._logger.info("배치 분산 수행...")
                    # 감시 리스트를 딕셔너리로 변환
                    stocks_dict = []
                    for s in watchlist_stocks:
                        if hasattr(s, '__dict__'):
                            stocks_dict.append(vars(s))
                        else:
                            stocks_dict.append(s)

                    batches = self.distribute_stocks_to_batches(stocks_dict, num_batches=total_batches)

                    # Redis에 캐시 (TTL: 2시간)
                    cache.set(cache_key, batches, ttl=7200)
                    self._logger.info("배치 정보 Redis 캐시 저장")

            except Exception as e:
                self._logger.warning(f"Redis 사용 실패, 직접 배치 분산: {e}")
                # Redis 실패 시 직접 분산
                stocks_dict = []
                for s in watchlist_stocks:
                    if hasattr(s, '__dict__'):
                        stocks_dict.append(vars(s))
                    else:
                        stocks_dict.append(s)
                batches = self.distribute_stocks_to_batches(stocks_dict, num_batches=total_batches)

            # 5. 해당 배치 처리
            if batch_index >= len(batches):
                self._logger.error(f"배치 인덱스 초과: {batch_index} >= {len(batches)}")
                return False

            batch_stocks = batches[batch_index]
            self._logger.info(f"배치 {batch_index} 종목 수: {len(batch_stocks)}개")

            # 비동기 배치 처리
            selected_stocks = asyncio.run(
                self.process_batch(batch_index, batch_stocks, market_condition)
            )

            # 6. 부분 결과 저장
            batch_file = Path(self._output_dir) / f"batch_{batch_index}.json"
            batch_file.parent.mkdir(parents=True, exist_ok=True)

            batch_data = {
                "batch_index": batch_index,
                "timestamp": datetime.now().isoformat(),
                "market_condition": market_condition,
                "total_stocks": len(batch_stocks),
                "selected_stocks": selected_stocks,
                "selected_count": len(selected_stocks)
            }

            with open(batch_file, "w", encoding="utf-8") as f:
                json.dump(batch_data, f, ensure_ascii=False, indent=2)

            self._logger.info(f"배치 {batch_index} 부분 결과 저장: {batch_file}")

            # 7. 마지막 배치일 때 최종 병합
            if batch_index == total_batches - 1:
                self._logger.info("마지막 배치: 최종 병합 시작...")
                return self._merge_batch_results(total_batches, market_condition)

            return True

        except Exception as e:
            self._logger.error(f"분산 배치 실행 실패 (배치 {batch_index}): {e}", exc_info=True)
            return False

    def _merge_batch_results(self, total_batches: int, market_condition: str) -> bool:
        """배치 결과 최종 병합

        Args:
            total_batches: 전체 배치 수
            market_condition: 시장 상황

        Returns:
            bool: 병합 성공 여부
        """
        try:
            self._logger.info(f"배치 결과 병합 시작: {total_batches}개 배치")

            all_selected_stocks = []
            batch_dir = Path(self._output_dir)

            # 모든 배치 파일 읽기
            for i in range(total_batches):
                batch_file = batch_dir / f"batch_{i}.json"
                if not batch_file.exists():
                    self._logger.warning(f"배치 {i} 파일 없음: {batch_file}")
                    continue

                try:
                    with open(batch_file, "r", encoding="utf-8") as f:
                        batch_data = json.load(f)
                        selected = batch_data.get("selected_stocks", [])
                        all_selected_stocks.extend(selected)
                        self._logger.info(f"배치 {i}: {len(selected)}개 종목 병합")
                except Exception as e:
                    self._logger.error(f"배치 {i} 파일 읽기 실패: {e}", exc_info=True)
                    continue

            # 중복 제거 (stock_code 기준)
            unique_stocks = {}
            for stock in all_selected_stocks:
                code = stock.get("stock_code")
                if code and code not in unique_stocks:
                    unique_stocks[code] = stock

            candidate_stocks = list(unique_stocks.values())

            self._logger.info(f"중복 제거 후 후보 종목: {len(candidate_stocks)}개")

            # Phase A 개선: 시장 적응형 상위 N개 선정
            final_stocks = self._select_top_n_adaptive(
                candidate_stocks,
                market_condition
            )

            self._logger.info(
                f"최종 선정 완료: {len(final_stocks)}개 종목 "
                f"(후보 {len(candidate_stocks)}개 중)"
            )

            # 최종 결과 저장
            date_str = datetime.now().strftime("%Y%m%d")
            final_file = batch_dir / f"daily_selection_{date_str}.json"

            final_data = {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "market_date": datetime.now().strftime("%Y-%m-%d"),
                "market_condition": market_condition,
                "data": {
                    "selected_stocks": final_stocks
                },
                "stocks": final_stocks,
                "metadata": {
                    "total_selected": len(final_stocks),
                    "batch_count": total_batches,
                    "source": "distributed_batches"
                }
            }

            # === DB에 저장 (우선) ===
            selection_date = datetime.now().date()
            db_saved = self._save_selection_to_db(final_data, selection_date)
            if db_saved:
                self._logger.info(f"최종 결과 DB 저장 완료: {len(final_stocks)}건")
            else:
                self._logger.warning("최종 결과 DB 저장 실패 - JSON 폴백 저장")

            # === JSON 폴백 저장 (DB 실패 시) ===
            if not db_saved:
                with open(final_file, "w", encoding="utf-8") as f:
                    json.dump(final_data, f, ensure_ascii=False, indent=2)
                self._logger.info(f"최종 결과 JSON 폴백 저장: {final_file}")

            # 배치 파일 정리 (선택적)
            # for i in range(total_batches):
            #     batch_file = batch_dir / f"batch_{i}.json"
            #     if batch_file.exists():
            #         batch_file.unlink()

            # 텔레그램 알림
            notifier = get_telegram_notifier()
            if notifier.is_enabled():
                elapsed_minutes = total_batches * 5  # 5분 간격
                message = (
                    f"✅ Phase 2 완료\n"
                    f"- {total_batches}개 배치 처리 완료\n"
                    f"- 총 선정 종목: {len(final_stocks)}개\n"
                    f"- 소요 시간: {elapsed_minutes}분"
                )
                notifier.send_message(message)

            return True

        except Exception as e:
            self._logger.error(f"배치 결과 병합 실패: {e}", exc_info=True)
            return False


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
