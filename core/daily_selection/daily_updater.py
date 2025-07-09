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
from core.daily_selection.price_analyzer import PriceAnalyzer, PriceAttractiveness
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

@dataclass
class FilteringCriteria:
    """필터링 기준 데이터 클래스"""
    price_attractiveness: float = 70.0      # 가격 매력도 점수 기준
    volume_threshold: float = 1.5           # 평균 거래량 대비 배수
    volatility_range: tuple = (0.1, 0.4)    # 변동성 범위 (10-40%)
    market_cap_min: float = 1000000000000   # 최소 시가총액 (1조원)
    liquidity_score: float = 60.0           # 유동성 점수 기준
    risk_score_max: float = 40.0            # 최대 리스크 점수
    sector_limit: int = 3                   # 섹터별 최대 종목 수
    total_limit: int = 15                   # 전체 최대 종목 수
    confidence_min: float = 0.5             # 최소 신뢰도

@dataclass
class DailySelection:
    """일일 선정 종목 데이터 클래스"""
    stock_code: str
    stock_name: str
    selection_date: str
    selection_reason: str
    price_attractiveness: float
    entry_price: float
    target_price: float
    stop_loss: float
    expected_return: float
    risk_score: float
    volume_score: float
    technical_signals: List[str]
    sector: str
    market_cap: float
    priority: int
    position_size: float        # 포트폴리오 비중
    confidence: float           # 신뢰도
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)

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
        """초기화"""
        self._v_indicators = MarketIndicators()
    
    def analyze_market_condition(self) -> str:
        """시장 상황 분석
        
        Returns:
            시장 상황 ('bull_market', 'bear_market', 'sideways')
        """
        try:
            # 실제로는 API를 통해 시장 지표 수집
            self._update_market_indicators()
            
            # 간단한 시장 상황 판단 로직
            # 실제로는 더 복잡한 알고리즘 사용
            _v_kospi_trend = self._calculate_trend_strength(self._v_indicators.kospi)
            _v_volatility = self._v_indicators.vix
            
            if _v_kospi_trend > 0.02 and _v_volatility < 20:
                return "bull_market"
            elif _v_kospi_trend < -0.02 or _v_volatility > 30:
                return "bear_market"
            else:
                return "sideways"
                
        except Exception as e:
            logger.error(f"시장 상황 분석 오류: {e}")
            return "sideways"
    
    def _update_market_indicators(self):
        """시장 지표 업데이트 (더미 데이터)"""
        # 실제로는 API에서 실시간 데이터 수집
        self._v_indicators = MarketIndicators(
            kospi=2650.5,
            kosdaq=850.2,
            vix=18.5,
            usd_krw=1320.5,
            interest_rate=3.5,
            oil_price=75.2
        )
    
    def _calculate_trend_strength(self, p_current_value: float) -> float:
        """추세 강도 계산 (더미 구현)"""
        # 실제로는 과거 데이터와 비교하여 추세 강도 계산
        return 0.01  # 임시 값
    
    def get_market_indicators(self) -> MarketIndicators:
        """현재 시장 지표 반환"""
        return self._v_indicators

class DailyUpdater:
    """일일 업데이트 스케줄러 메인 클래스"""
    
    def __init__(self, p_watchlist_file: str = "data/watchlist/watchlist.json",
                 p_output_dir: str = "data/daily_selection"):
        """초기화
        
        Args:
            p_watchlist_file: 감시 리스트 파일 경로
            p_output_dir: 결과 저장 디렉토리
        """
        self._v_watchlist_manager = WatchlistManager(p_watchlist_file)
        self._v_price_analyzer = PriceAnalyzer()
        self._v_market_analyzer = MarketConditionAnalyzer()
        self._v_output_dir = p_output_dir
        
        # 필터링 기준 설정
        self._v_criteria = FilteringCriteria()
        
        # 스케줄러 상태
        self._v_scheduler_running = False
        self._v_scheduler_thread = None
        
        # 디렉토리 생성
        os.makedirs(p_output_dir, exist_ok=True)
        
        logger.info("일일 업데이터 초기화 완료")
    
    def start_scheduler(self):
        """스케줄러 시작"""
        if self._v_scheduler_running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return
        
        # 매일 08:30에 실행 스케줄 설정
        schedule.clear()
        schedule.every().day.at("08:30").do(self.run_daily_update)
        
        # 테스트용: 매 5분마다 실행 (개발 중에만 사용)
        # schedule.every(5).minutes.do(self.run_daily_update)
        
        self._v_scheduler_running = True
        self._v_scheduler_thread = threading.Thread(target=self._run_scheduler_loop, daemon=True)
        self._v_scheduler_thread.start()
        
        logger.info("일일 업데이트 스케줄러 시작됨")
    
    def stop_scheduler(self):
        """스케줄러 중지"""
        self._v_scheduler_running = False
        schedule.clear()
        
        if self._v_scheduler_thread and self._v_scheduler_thread.is_alive():
            self._v_scheduler_thread.join(timeout=5)
        
        logger.info("일일 업데이트 스케줄러 중지됨")
    
    def _run_scheduler_loop(self):
        """스케줄러 루프 실행"""
        while self._v_scheduler_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 체크
            except Exception as e:
                logger.error(f"스케줄러 루프 오류: {e}")
                time.sleep(60)
    
    def run_daily_update(self, p_force_run: bool = False) -> bool:
        """일일 업데이트 실행
        
        Args:
            p_force_run: 강제 실행 여부 (스케줄 무시)
            
        Returns:
            업데이트 성공 여부
        """
        try:
            _v_start_time = datetime.now()
            logger.info(f"일일 업데이트 시작: {_v_start_time}")
            
            # 1. 시장 상황 분석
            _v_market_condition = self._v_market_analyzer.analyze_market_condition()
            _v_market_indicators = self._v_market_analyzer.get_market_indicators()
            
            logger.info(f"시장 상황: {_v_market_condition}")
            
            # 2. 시장 상황에 따른 필터링 기준 조정
            self._adjust_criteria_by_market(_v_market_condition)
            
            # 3. 감시 리스트 로드
            _v_watchlist_stocks = self._v_watchlist_manager.list_stocks(p_status="active")
            
            if not _v_watchlist_stocks:
                logger.warning("활성 감시 리스트가 비어있습니다")
                return False
            
            logger.info(f"감시 리스트 종목 수: {len(_v_watchlist_stocks)}")
            
            # 4. 가격 매력도 분석
            _v_stock_data_list = self._prepare_stock_data(_v_watchlist_stocks)
            _v_analysis_results = self._v_price_analyzer.analyze_multiple_stocks(_v_stock_data_list)
            
            logger.info(f"분석 완료 종목 수: {len(_v_analysis_results)}")
            
            # 5. 필터링 및 선정
            _v_selected_stocks = self._filter_and_select_stocks(_v_analysis_results)
            
            logger.info(f"선정된 종목 수: {len(_v_selected_stocks)}")
            
            # 6. 일일 매매 리스트 생성
            _v_daily_list = self._create_daily_trading_list(
                _v_selected_stocks, _v_market_condition, _v_market_indicators
            )
            
            # 7. 결과 저장
            _v_save_success = self._save_daily_list(_v_daily_list)
            
            _v_end_time = datetime.now()
            _v_duration = (_v_end_time - _v_start_time).total_seconds()
            
            logger.info(f"일일 업데이트 완료: {_v_duration:.1f}초 소요")
            
            # 8. 알림 발송 (선택사항)
            if _v_save_success:
                self._send_notification(_v_daily_list)
            
            return _v_save_success
            
        except Exception as e:
            logger.error(f"일일 업데이트 실행 오류: {e}")
            return False
    
    def _adjust_criteria_by_market(self, p_market_condition: str):
        """시장 상황에 따른 필터링 기준 조정
        
        Args:
            p_market_condition: 시장 상황
        """
        if p_market_condition == "bull_market":
            # 상승장: 기준 완화
            self._v_criteria.price_attractiveness = 65.0
            self._v_criteria.volume_threshold = 1.3
            self._v_criteria.risk_score_max = 50.0
            self._v_criteria.total_limit = 20
            
        elif p_market_condition == "bear_market":
            # 하락장: 기준 강화
            self._v_criteria.price_attractiveness = 80.0
            self._v_criteria.volume_threshold = 2.0
            self._v_criteria.risk_score_max = 30.0
            self._v_criteria.total_limit = 10
            
        else:  # sideways
            # 횡보장: 기본 기준 유지
            self._v_criteria = FilteringCriteria()
        
        logger.info(f"필터링 기준 조정 완료 - 시장상황: {p_market_condition}")
    
    def _prepare_stock_data(self, p_watchlist_stocks: List) -> List[Dict]:
        """감시 리스트 종목을 분석용 데이터로 변환
        
        Args:
            p_watchlist_stocks: 감시 리스트 종목들
            
        Returns:
            분석용 종목 데이터 리스트
        """
        _v_stock_data_list = []
        
        for stock in p_watchlist_stocks:
            # 실제로는 API에서 최신 데이터 수집
            _v_stock_data = {
                "stock_code": stock.stock_code,
                "stock_name": stock.stock_name,
                "current_price": self._get_current_price(stock.stock_code),
                "sector": stock.sector,
                "market_cap": self._get_market_cap(stock.stock_code),
                "volatility": self._get_volatility(stock.stock_code),
                "sector_momentum": self._get_sector_momentum(stock.sector)
            }
            _v_stock_data_list.append(_v_stock_data)
        
        return _v_stock_data_list
    
    def _get_current_price(self, p_stock_code: str) -> float:
        """현재가 조회 (더미 구현)"""
        # 실제로는 API에서 현재가 조회
        return 50000.0 + hash(p_stock_code) % 20000  # 임시 가격
    
    def _get_market_cap(self, p_stock_code: str) -> float:
        """시가총액 조회 (더미 구현)"""
        # 실제로는 API에서 시가총액 조회
        return 1000000000000 + hash(p_stock_code) % 500000000000  # 임시 시총
    
    def _get_volatility(self, p_stock_code: str) -> float:
        """변동성 조회 (더미 구현)"""
        # 실제로는 과거 데이터로부터 변동성 계산
        return 0.15 + (hash(p_stock_code) % 100) / 1000  # 15-25% 범위
    
    def _get_sector_momentum(self, p_sector: str) -> float:
        """섹터 모멘텀 조회 (더미 구현)"""
        # 실제로는 섹터 지수 분석
        return (hash(p_sector) % 200 - 100) / 1000  # -10% ~ +10% 범위
    
    def _filter_and_select_stocks(self, p_analysis_results: List[PriceAttractiveness]) -> List[PriceAttractiveness]:
        """분석 결과를 필터링하여 매매 대상 선정
        
        Args:
            p_analysis_results: 가격 매력도 분석 결과 리스트
            
        Returns:
            선정된 종목 리스트
        """
        _v_filtered_stocks = []
        _v_sector_count = {}
        
        # 점수순으로 정렬
        _v_sorted_results = sorted(p_analysis_results, key=lambda x: x.total_score, reverse=True)
        
        for result in _v_sorted_results:
            # 기본 필터링 조건 확인
            if not self._passes_basic_filters(result):
                continue
            
            # 섹터별 제한 확인
            _v_sector_count[result.sector] = _v_sector_count.get(result.sector, 0)
            if _v_sector_count[result.sector] >= self._v_criteria.sector_limit:
                continue
            
            # 전체 제한 확인
            if len(_v_filtered_stocks) >= self._v_criteria.total_limit:
                break
            
            _v_filtered_stocks.append(result)
            _v_sector_count[result.sector] += 1
        
        logger.info(f"필터링 완료: {len(_v_filtered_stocks)}개 종목 선정")
        return _v_filtered_stocks
    
    def _passes_basic_filters(self, p_result: PriceAttractiveness) -> bool:
        """기본 필터링 조건 확인
        
        Args:
            p_result: 분석 결과
            
        Returns:
            필터링 통과 여부
        """
        # 가격 매력도 점수
        if p_result.total_score < self._v_criteria.price_attractiveness:
            return False
        
        # 리스크 점수
        if p_result.risk_score > self._v_criteria.risk_score_max:
            return False
        
        # 신뢰도
        if p_result.confidence < self._v_criteria.confidence_min:
            return False
        
        # 거래량 점수 (임시로 volume_score 사용)
        if p_result.volume_score < self._v_criteria.liquidity_score:
            return False
        
        return True
    
    def _create_daily_trading_list(self, p_selected_stocks: List[PriceAttractiveness],
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
                confidence=stock.confidence
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
            "watchlist_count": len(self._v_watchlist_manager.list_stocks(p_status="active")),
            "selection_rate": len(_v_daily_selections) / max(len(self._v_watchlist_manager.list_stocks(p_status="active")), 1),
            "avg_attractiveness": sum(s.price_attractiveness for s in _v_daily_selections) / max(len(_v_daily_selections), 1),
            "sector_distribution": _v_sector_distribution,
            "market_indicators": p_market_indicators.to_dict(),
            "filtering_criteria": asdict(self._v_criteria)
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
    
    def _calculate_position_size(self, p_stock: PriceAttractiveness, p_total_stocks: int) -> float:
        """포지션 사이즈 계산
        
        Args:
            p_stock: 종목 분석 결과
            p_total_stocks: 전체 선정 종목 수
            
        Returns:
            포지션 비중 (0-1)
        """
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
            _v_file_path = os.path.join(self._v_output_dir, f"daily_selection_{_v_date}.json")
            
            with open(_v_file_path, 'w', encoding='utf-8') as f:
                json.dump(p_daily_list, f, ensure_ascii=False, indent=2)
            
            # 최신 파일 링크 생성
            _v_latest_path = os.path.join(self._v_output_dir, "latest_selection.json")
            with open(_v_latest_path, 'w', encoding='utf-8') as f:
                json.dump(p_daily_list, f, ensure_ascii=False, indent=2)
            
            logger.info(f"일일 매매 리스트 저장 완료: {_v_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"일일 매매 리스트 저장 실패: {e}")
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
            
            logger.info(f"알림 발송: {_v_message}")
            # 실제로는 슬랙, 이메일, SMS 등으로 알림 발송
            
        except Exception as e:
            logger.error(f"알림 발송 실패: {e}")
    
    def get_latest_selection(self) -> Optional[Dict]:
        """최신 일일 선정 결과 조회
        
        Returns:
            최신 일일 매매 리스트 (없으면 None)
        """
        try:
            _v_latest_path = os.path.join(self._v_output_dir, "latest_selection.json")
            
            if not os.path.exists(_v_latest_path):
                return None
            
            with open(_v_latest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"최신 선정 결과 조회 실패: {e}")
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
                _v_file_path = os.path.join(self._v_output_dir, f"daily_selection_{_v_date}.json")
                
                if os.path.exists(_v_file_path):
                    with open(_v_file_path, 'r', encoding='utf-8') as f:
                        _v_data = json.load(f)
                        _v_history.append(_v_data)
            
            return _v_history
            
        except Exception as e:
            logger.error(f"선정 이력 조회 실패: {e}")
            return []
    
    def update_filtering_criteria(self, p_criteria: FilteringCriteria):
        """필터링 기준 업데이트
        
        Args:
            p_criteria: 새로운 필터링 기준
        """
        self._v_criteria = p_criteria
        logger.info("필터링 기준 업데이트 완료")

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