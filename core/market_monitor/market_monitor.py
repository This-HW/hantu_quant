"""
실시간 시장 모니터링 시스템

시장 상황을 실시간으로 감시하고 분석하는 핵심 시스템
"""

import numpy as np
import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum

from ..utils.logging import get_logger

logger = get_logger(__name__)

class MarketStatus(Enum):
    """시장 상태"""
    NORMAL = "normal"           # 정상
    VOLATILE = "volatile"       # 변동성 높음
    DECLINING = "declining"     # 하락세
    RISING = "rising"           # 상승세
    SIDEWAYS = "sideways"       # 횡보
    ABNORMAL = "abnormal"       # 비정상

class MonitoringLevel(Enum):
    """모니터링 레벨"""
    LOW = "low"                 # 낮음 (1시간 간격)
    MEDIUM = "medium"           # 보통 (30분 간격)
    HIGH = "high"               # 높음 (10분 간격)
    CRITICAL = "critical"       # 긴급 (1분 간격)

@dataclass
class MonitoringConfig:
    """모니터링 설정"""
    monitoring_level: MonitoringLevel = MonitoringLevel.MEDIUM
    update_interval: int = 1800     # 업데이트 간격 (초)
    max_symbols: int = 100          # 최대 모니터링 종목 수
    price_change_threshold: float = 0.05  # 가격 변동 임계값 (5%)
    volume_change_threshold: float = 2.0   # 거래량 변동 임계값 (2배)
    market_cap_threshold: float = 1000000000  # 시가총액 임계값 (10억)
    save_snapshots: bool = True     # 스냅샷 저장 여부
    enable_alerts: bool = True      # 알림 활성화
    data_retention_days: int = 30   # 데이터 보관 기간

@dataclass
class StockSnapshot:
    """종목 스냅샷"""
    stock_code: str
    stock_name: str
    timestamp: datetime
    current_price: float
    previous_close: float
    price_change: float
    price_change_rate: float
    volume: int
    volume_avg_20d: int
    volume_ratio: float
    market_cap: float
    trading_value: float
    
    # 기술적 지표
    rsi: Optional[float] = None
    ma5: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    
    # 상태 정보
    status: MarketStatus = MarketStatus.NORMAL
    alerts: List[str] = field(default_factory=list)

@dataclass
class MarketSnapshot:
    """시장 전체 스냅샷"""
    timestamp: datetime
    market_status: MarketStatus
    kospi_index: float
    kosdaq_index: float
    kospi_change: float
    kosdaq_change: float
    total_trading_value: float
    advance_decline_ratio: float  # 상승/하락 비율
    
    # 종목 통계
    total_stocks: int
    rising_stocks: int
    declining_stocks: int
    unchanged_stocks: int
    limit_up_stocks: int
    limit_down_stocks: int
    
    # 거래량 정보
    high_volume_stocks: List[str] = field(default_factory=list)
    high_volatility_stocks: List[str] = field(default_factory=list)
    
    # 섹터 정보
    sector_performance: Dict[str, float] = field(default_factory=dict)
    
    # 종목별 스냅샷
    stock_snapshots: List[StockSnapshot] = field(default_factory=list)

class MarketDataProcessor:
    """시장 데이터 처리기"""
    
    def __init__(self):
        self._logger = logger
        self._price_history = {}
        self._volume_history = {}
        self._last_update = {}
    
    def process_market_data(self, raw_data: Dict[str, Any]) -> MarketSnapshot:
        """원시 시장 데이터를 처리하여 스냅샷 생성"""
        try:
            timestamp = datetime.now()
            
            # 시장 지수 정보 추출
            kospi_index = self._extract_index_data(raw_data.get('kospi', {}))
            kosdaq_index = self._extract_index_data(raw_data.get('kosdaq', {}))
            
            # 종목별 데이터 처리
            stock_snapshots = []
            stock_data = raw_data.get('stocks', [])
            
            for stock_info in stock_data:
                snapshot = self._process_stock_data(stock_info, timestamp)
                if snapshot:
                    stock_snapshots.append(snapshot)
            
            # 시장 통계 계산
            market_stats = self._calculate_market_statistics(stock_snapshots)
            
            # 시장 상태 결정
            market_status = self._determine_market_status(kospi_index, kosdaq_index, market_stats)
            
            # 시장 스냅샷 생성
            market_snapshot = MarketSnapshot(
                timestamp=timestamp,
                market_status=market_status,
                kospi_index=kospi_index.get('value', 0),
                kosdaq_index=kosdaq_index.get('value', 0),
                kospi_change=kospi_index.get('change_rate', 0),
                kosdaq_change=kosdaq_index.get('change_rate', 0),
                total_trading_value=market_stats['total_trading_value'],
                advance_decline_ratio=market_stats['advance_decline_ratio'],
                **market_stats,
                stock_snapshots=stock_snapshots
            )
            
            return market_snapshot
            
        except Exception as e:
            self._logger.error(f"시장 데이터 처리 실패: {e}", exc_info=True)
            return self._create_empty_snapshot()
    
    def _extract_index_data(self, index_data: Dict) -> Dict[str, float]:
        """지수 데이터 추출"""
        try:
            return {
                'value': float(index_data.get('current_price', 0)),
                'change': float(index_data.get('price_change', 0)),
                'change_rate': float(index_data.get('price_change_rate', 0))
            }
        except:
            return {'value': 0, 'change': 0, 'change_rate': 0}
    
    def _process_stock_data(self, stock_info: Dict, timestamp: datetime) -> Optional[StockSnapshot]:
        """개별 종목 데이터 처리"""
        try:
            stock_code = stock_info.get('stock_code', '')
            if not stock_code:
                return None
            
            # 기본 정보
            current_price = float(stock_info.get('current_price', 0))
            previous_close = float(stock_info.get('previous_close', current_price))
            volume = int(stock_info.get('volume', 0))
            
            # 변화율 계산
            price_change = current_price - previous_close
            price_change_rate = (price_change / previous_close) if previous_close > 0 else 0
            
            # 거래량 비율 계산
            volume_avg_20d = int(stock_info.get('volume_avg_20d', volume))
            volume_ratio = (volume / volume_avg_20d) if volume_avg_20d > 0 else 1.0
            
            # 시가총액 및 거래대금
            shares_outstanding = int(stock_info.get('shares_outstanding', 1000000))
            market_cap = current_price * shares_outstanding
            trading_value = current_price * volume
            
            # 기술적 지표 계산
            technical_indicators = self._calculate_technical_indicators(stock_code, current_price)
            
            # 종목 상태 결정
            status = self._determine_stock_status(price_change_rate, volume_ratio)
            
            # 알림 조건 체크
            alerts = self._check_alert_conditions(stock_code, price_change_rate, volume_ratio)
            
            snapshot = StockSnapshot(
                stock_code=stock_code,
                stock_name=stock_info.get('stock_name', stock_code),
                timestamp=timestamp,
                current_price=current_price,
                previous_close=previous_close,
                price_change=price_change,
                price_change_rate=price_change_rate,
                volume=volume,
                volume_avg_20d=volume_avg_20d,
                volume_ratio=volume_ratio,
                market_cap=market_cap,
                trading_value=trading_value,
                status=status,
                alerts=alerts,
                **technical_indicators
            )
            
            # 가격 히스토리 업데이트
            self._update_price_history(stock_code, current_price, timestamp)
            
            return snapshot
            
        except Exception as e:
            self._logger.error(f"종목 데이터 처리 실패 ({stock_info.get('stock_code', 'unknown')}): {e}", exc_info=True)
            return None
    
    def _calculate_technical_indicators(self, stock_code: str, current_price: float) -> Dict[str, Optional[float]]:
        """기술적 지표 계산"""
        try:
            # 가격 히스토리가 충분하지 않으면 None 반환
            if stock_code not in self._price_history or len(self._price_history[stock_code]) < 20:
                return {
                    'rsi': None,
                    'ma5': None,
                    'ma20': None,
                    'ma60': None,
                    'bollinger_upper': None,
                    'bollinger_lower': None
                }
            
            prices = self._price_history[stock_code]
            
            # 이동평균
            ma5 = np.mean(prices[-5:]) if len(prices) >= 5 else None
            ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else None
            ma60 = np.mean(prices[-60:]) if len(prices) >= 60 else None
            
            # RSI 계산
            rsi = self._calculate_rsi(prices)
            
            # 볼린저 밴드
            bollinger_upper, bollinger_lower = self._calculate_bollinger_bands(prices)
            
            return {
                'rsi': rsi,
                'ma5': float(ma5) if ma5 is not None else None,
                'ma20': float(ma20) if ma20 is not None else None,
                'ma60': float(ma60) if ma60 is not None else None,
                'bollinger_upper': bollinger_upper,
                'bollinger_lower': bollinger_lower
            }
            
        except Exception as e:
            self._logger.error(f"기술적 지표 계산 실패 ({stock_code}): {e}", exc_info=True)
            return {
                'rsi': None, 'ma5': None, 'ma20': None, 'ma60': None,
                'bollinger_upper': None, 'bollinger_lower': None
            }
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """RSI 계산"""
        try:
            if len(prices) < period + 1:
                return None
            
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi)
            
        except:
            return None
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2.0) -> Tuple[Optional[float], Optional[float]]:
        """볼린저 밴드 계산"""
        try:
            if len(prices) < period:
                return None, None
            
            recent_prices = prices[-period:]
            sma = np.mean(recent_prices)
            std = np.std(recent_prices)
            
            upper = sma + (std * std_dev)
            lower = sma - (std * std_dev)
            
            return float(upper), float(lower)
            
        except:
            return None, None
    
    def _determine_stock_status(self, price_change_rate: float, volume_ratio: float) -> MarketStatus:
        """종목 상태 결정"""
        # 급격한 가격 변동
        if abs(price_change_rate) > 0.15:  # 15% 이상
            return MarketStatus.ABNORMAL
        
        # 높은 변동성
        if abs(price_change_rate) > 0.05 and volume_ratio > 3.0:
            return MarketStatus.VOLATILE
        
        # 상승세
        if price_change_rate > 0.03:
            return MarketStatus.RISING
        
        # 하락세
        if price_change_rate < -0.03:
            return MarketStatus.DECLINING
        
        # 정상
        return MarketStatus.NORMAL
    
    def _check_alert_conditions(self, stock_code: str, price_change_rate: float, volume_ratio: float) -> List[str]:
        """알림 조건 체크"""
        alerts = []
        
        # 급등/급락 알림
        if price_change_rate > 0.10:
            alerts.append(f"급등 감지: {price_change_rate:.1%}")
        elif price_change_rate < -0.10:
            alerts.append(f"급락 감지: {price_change_rate:.1%}")
        
        # 거래량 급증 알림
        if volume_ratio > 5.0:
            alerts.append(f"거래량 급증: {volume_ratio:.1f}배")
        
        # 기술적 분석 알림
        if stock_code in self._price_history:
            prices = self._price_history[stock_code]
            if len(prices) >= 20:
                current_price = prices[-1]
                ma20 = np.mean(prices[-20:])
                
                # 이동평균 돌파
                if len(prices) >= 2:
                    prev_price = prices[-2]
                    if prev_price <= ma20 < current_price:
                        alerts.append("20일 이동평균 상향 돌파")
                    elif prev_price >= ma20 > current_price:
                        alerts.append("20일 이동평균 하향 이탈")
        
        return alerts
    
    def _calculate_market_statistics(self, stock_snapshots: List[StockSnapshot]) -> Dict[str, Any]:
        """시장 통계 계산"""
        if not stock_snapshots:
            return {
                'total_stocks': 0,
                'rising_stocks': 0,
                'declining_stocks': 0,
                'unchanged_stocks': 0,
                'limit_up_stocks': 0,
                'limit_down_stocks': 0,
                'total_trading_value': 0,
                'advance_decline_ratio': 0,
                'high_volume_stocks': [],
                'high_volatility_stocks': [],
                'sector_performance': {}
            }
        
        total_stocks = len(stock_snapshots)
        rising_stocks = sum(1 for s in stock_snapshots if s.price_change_rate > 0)
        declining_stocks = sum(1 for s in stock_snapshots if s.price_change_rate < 0)
        unchanged_stocks = total_stocks - rising_stocks - declining_stocks
        
        # 상한가/하한가 (임시로 ±30%로 설정)
        limit_up_stocks = sum(1 for s in stock_snapshots if s.price_change_rate >= 0.30)
        limit_down_stocks = sum(1 for s in stock_snapshots if s.price_change_rate <= -0.30)
        
        # 총 거래대금
        total_trading_value = sum(s.trading_value for s in stock_snapshots)
        
        # 상승/하락 비율
        advance_decline_ratio = (rising_stocks / declining_stocks) if declining_stocks > 0 else float('inf')
        
        # 고거래량 종목 (상위 10개)
        high_volume_stocks = sorted(
            [s.stock_code for s in stock_snapshots],
            key=lambda code: next(s.volume_ratio for s in stock_snapshots if s.stock_code == code),
            reverse=True
        )[:10]
        
        # 고변동성 종목 (상위 10개)
        high_volatility_stocks = sorted(
            [s.stock_code for s in stock_snapshots],
            key=lambda code: abs(next(s.price_change_rate for s in stock_snapshots if s.stock_code == code)),
            reverse=True
        )[:10]
        
        return {
            'total_stocks': total_stocks,
            'rising_stocks': rising_stocks,
            'declining_stocks': declining_stocks,
            'unchanged_stocks': unchanged_stocks,
            'limit_up_stocks': limit_up_stocks,
            'limit_down_stocks': limit_down_stocks,
            'total_trading_value': total_trading_value,
            'advance_decline_ratio': advance_decline_ratio,
            'high_volume_stocks': high_volume_stocks,
            'high_volatility_stocks': high_volatility_stocks,
            'sector_performance': {}  # 섹터 정보는 별도 구현 필요
        }
    
    def _determine_market_status(self, kospi_data: Dict, kosdaq_data: Dict, market_stats: Dict) -> MarketStatus:
        """시장 전체 상태 결정"""
        kospi_change = kospi_data.get('change_rate', 0)
        kosdaq_change = kosdaq_data.get('change_rate', 0)
        
        # 전체 시장 평균 변화율
        market_change = (kospi_change + kosdaq_change) / 2
        
        # 상승/하락 비율
        advance_decline_ratio = market_stats.get('advance_decline_ratio', 1.0)
        
        # 비정상 상황 (극심한 변동)
        if abs(market_change) > 0.05 or advance_decline_ratio > 5.0 or advance_decline_ratio < 0.2:
            return MarketStatus.ABNORMAL
        
        # 변동성 높음
        if abs(market_change) > 0.02:
            return MarketStatus.VOLATILE
        
        # 상승세
        if market_change > 0.01 and advance_decline_ratio > 1.5:
            return MarketStatus.RISING
        
        # 하락세
        if market_change < -0.01 and advance_decline_ratio < 0.7:
            return MarketStatus.DECLINING
        
        # 횡보
        if abs(market_change) < 0.005:
            return MarketStatus.SIDEWAYS
        
        # 정상
        return MarketStatus.NORMAL
    
    def _update_price_history(self, stock_code: str, price: float, timestamp: datetime):
        """가격 히스토리 업데이트"""
        if stock_code not in self._price_history:
            self._price_history[stock_code] = []
        
        self._price_history[stock_code].append(price)
        
        # 최대 100개 데이터만 유지
        if len(self._price_history[stock_code]) > 100:
            self._price_history[stock_code] = self._price_history[stock_code][-100:]
        
        self._last_update[stock_code] = timestamp
    
    def _create_empty_snapshot(self) -> MarketSnapshot:
        """빈 스냅샷 생성"""
        return MarketSnapshot(
            timestamp=datetime.now(),
            market_status=MarketStatus.NORMAL,
            kospi_index=0,
            kosdaq_index=0,
            kospi_change=0,
            kosdaq_change=0,
            total_trading_value=0,
            advance_decline_ratio=1.0,
            total_stocks=0,
            rising_stocks=0,
            declining_stocks=0,
            unchanged_stocks=0,
            limit_up_stocks=0,
            limit_down_stocks=0
        )

class MarketMonitor:
    """실시간 시장 모니터링 시스템"""
    
    def __init__(self, config: MonitoringConfig = None, data_dir: str = "data/market_monitoring"):
        """
        초기화
        
        Args:
            config: 모니터링 설정
            data_dir: 데이터 저장 디렉토리
        """
        self._logger = logger
        self._config = config or MonitoringConfig()
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 컴포넌트 초기화
        self._data_processor = MarketDataProcessor()
        self._api_client = None
        
        # 모니터링 상태
        self._is_monitoring = False
        self._monitoring_thread = None
        self._stop_event = threading.Event()
        
        # 데이터 저장
        self._snapshots = []
        self._current_snapshot = None
        
        # 감시 대상 종목
        self._monitored_symbols = []
        
        # 콜백 함수들
        self._snapshot_callbacks = []
        self._alert_callbacks = []
        
        self._logger.info("실시간 시장 모니터링 시스템 초기화 완료")
    
    def set_api_client(self, api_client):
        """API 클라이언트 설정"""
        self._api_client = api_client
        self._logger.info("API 클라이언트 설정 완료")
    
    def add_symbols(self, symbols: List[str]):
        """모니터링 대상 종목 추가"""
        for symbol in symbols:
            if symbol not in self._monitored_symbols:
                self._monitored_symbols.append(symbol)
        
        # 최대 종목 수 제한
        if len(self._monitored_symbols) > self._config.max_symbols:
            self._monitored_symbols = self._monitored_symbols[:self._config.max_symbols]
        
        self._logger.info(f"모니터링 대상 종목 추가: {len(symbols)}개 (총 {len(self._monitored_symbols)}개)")
    
    def remove_symbols(self, symbols: List[str]):
        """모니터링 대상 종목 제거"""
        removed_count = 0
        for symbol in symbols:
            if symbol in self._monitored_symbols:
                self._monitored_symbols.remove(symbol)
                removed_count += 1
        
        self._logger.info(f"모니터링 대상 종목 제거: {removed_count}개 (총 {len(self._monitored_symbols)}개)")
    
    def add_snapshot_callback(self, callback: Callable[[MarketSnapshot], None]):
        """스냅샷 콜백 추가"""
        self._snapshot_callbacks.append(callback)
    
    def add_alert_callback(self, callback: Callable[[str, Dict], None]):
        """알림 콜백 추가"""
        self._alert_callbacks.append(callback)
    
    def start_monitoring(self):
        """모니터링 시작"""
        if self._is_monitoring:
            self._logger.warning("이미 모니터링이 실행 중입니다")
            return
        
        if not self._monitored_symbols:
            self._logger.warning("모니터링 대상 종목이 없습니다")
            return
        
        self._is_monitoring = True
        self._stop_event.clear()
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self._monitoring_thread.start()
        
        self._logger.info(f"실시간 모니터링 시작 - {len(self._monitored_symbols)}개 종목")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        if not self._is_monitoring:
            return
        
        self._is_monitoring = False
        self._stop_event.set()
        
        if self._monitoring_thread:
            self._monitoring_thread.join()
        
        self._logger.info("실시간 모니터링 중지")
    
    def _monitoring_loop(self):
        """모니터링 루프"""
        while self._is_monitoring and not self._stop_event.is_set():
            try:
                # 시장 데이터 수집
                market_data = self._collect_market_data()
                
                # 스냅샷 생성
                snapshot = self._data_processor.process_market_data(market_data)
                
                # 현재 스냅샷 업데이트
                self._current_snapshot = snapshot
                self._snapshots.append(snapshot)
                
                # 오래된 데이터 정리
                self._cleanup_old_data()
                
                # 스냅샷 저장
                if self._config.save_snapshots:
                    self._save_snapshot(snapshot)
                
                # 콜백 실행
                self._execute_snapshot_callbacks(snapshot)
                
                # 알림 처리
                self._process_alerts(snapshot)
                
                # 다음 업데이트까지 대기
                self._stop_event.wait(self._config.update_interval)
                
            except Exception as e:
                self._logger.error(f"모니터링 루프 오류: {e}", exc_info=True)
                time.sleep(60)  # 오류 시 1분 대기
    
    def _collect_market_data(self) -> Dict[str, Any]:
        """시장 데이터 수집"""
        try:
            if self._api_client:
                # 실제 API 데이터 수집
                return self._collect_real_data()
            else:
                # Mock 데이터 생성
                return self._generate_mock_data()
                
        except Exception as e:
            self._logger.error(f"시장 데이터 수집 실패: {e}", exc_info=True)
            return self._generate_mock_data()
    
    def _collect_real_data(self) -> Dict[str, Any]:
        """실제 API 데이터 수집"""
        market_data = {
            'timestamp': datetime.now(),
            'kospi': {},
            'kosdaq': {},
            'stocks': []
        }
        
        try:
            # 지수 데이터 수집 (실제 구현에서는 API 호출)
            market_data['kospi'] = {
                'current_price': 2500,  # Mock 데이터
                'price_change': 10,
                'price_change_rate': 0.004
            }
            
            market_data['kosdaq'] = {
                'current_price': 900,
                'price_change': -5,
                'price_change_rate': -0.0056
            }
            
            # 종목별 데이터 수집
            for symbol in self._monitored_symbols[:50]:  # 최대 50개씩 처리
                stock_data = self._get_stock_data(symbol)
                if stock_data:
                    market_data['stocks'].append(stock_data)
                    
        except Exception as e:
            self._logger.error(f"실제 데이터 수집 실패: {e}", exc_info=True)
        
        return market_data
    
    def _get_stock_data(self, symbol: str) -> Optional[Dict]:
        """개별 종목 데이터 조회"""
        try:
            # 실제 구현에서는 API 호출
            # 여기서는 Mock 데이터 반환
            base_price = np.random.uniform(10000, 100000)
            change_rate = np.random.uniform(-0.15, 0.15)
            
            return {
                'stock_code': symbol,
                'stock_name': f"종목{symbol}",
                'current_price': base_price * (1 + change_rate),
                'previous_close': base_price,
                'volume': np.random.randint(10000, 1000000),
                'volume_avg_20d': np.random.randint(50000, 500000),
                'shares_outstanding': np.random.randint(10000000, 100000000)
            }
            
        except Exception as e:
            self._logger.error(f"종목 데이터 조회 실패 ({symbol}): {e}", exc_info=True)
            return None
    
    def _generate_mock_data(self) -> Dict[str, Any]:
        """Mock 시장 데이터 생성"""
        stocks_data = []
        
        for symbol in self._monitored_symbols:
            base_price = np.random.uniform(10000, 100000)
            change_rate = np.random.normal(0, 0.03)  # 평균 0%, 표준편차 3%
            
            stocks_data.append({
                'stock_code': symbol,
                'stock_name': f"종목{symbol}",
                'current_price': base_price * (1 + change_rate),
                'previous_close': base_price,
                'volume': np.random.randint(10000, 1000000),
                'volume_avg_20d': np.random.randint(50000, 500000),
                'shares_outstanding': np.random.randint(10000000, 100000000)
            })
        
        market_data = {
            'timestamp': datetime.now(),
            'kospi': {
                'current_price': 2500 + np.random.normal(0, 20),
                'price_change': np.random.normal(0, 15),
                'price_change_rate': np.random.normal(0, 0.01)
            },
            'kosdaq': {
                'current_price': 900 + np.random.normal(0, 10),
                'price_change': np.random.normal(0, 8),
                'price_change_rate': np.random.normal(0, 0.01)
            },
            'stocks': stocks_data
        }
        
        return market_data
    
    def _cleanup_old_data(self):
        """오래된 데이터 정리"""
        if not self._snapshots:
            return
        
        cutoff_time = datetime.now() - timedelta(days=self._config.data_retention_days)
        self._snapshots = [
            snapshot for snapshot in self._snapshots
            if snapshot.timestamp > cutoff_time
        ]
    
    def _save_snapshot(self, snapshot: MarketSnapshot):
        """스냅샷 저장"""
        try:
            timestamp_str = snapshot.timestamp.strftime('%Y%m%d_%H%M%S')
            filename = f"market_snapshot_{timestamp_str}.json"
            filepath = os.path.join(self._data_dir, filename)
            
            # 스냅샷 직렬화
            snapshot_dict = asdict(snapshot)
            snapshot_dict['timestamp'] = snapshot.timestamp.isoformat()
            
            for i, stock_snapshot in enumerate(snapshot_dict['stock_snapshots']):
                stock_snapshot['timestamp'] = stock_snapshot['timestamp'].isoformat()
                stock_snapshot['status'] = stock_snapshot['status'].value
            
            snapshot_dict['market_status'] = snapshot.market_status.value
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(snapshot_dict, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            self._logger.error(f"스냅샷 저장 실패: {e}", exc_info=True)
    
    def _execute_snapshot_callbacks(self, snapshot: MarketSnapshot):
        """스냅샷 콜백 실행"""
        for callback in self._snapshot_callbacks:
            try:
                callback(snapshot)
            except Exception as e:
                self._logger.error(f"스냅샷 콜백 실행 실패: {e}", exc_info=True)
    
    def _process_alerts(self, snapshot: MarketSnapshot):
        """알림 처리"""
        try:
            alerts = []
            
            # 시장 전체 알림
            if snapshot.market_status == MarketStatus.ABNORMAL:
                alerts.append({
                    'type': 'market_abnormal',
                    'message': f"비정상적인 시장 상황 감지",
                    'data': {
                        'kospi_change': snapshot.kospi_change,
                        'kosdaq_change': snapshot.kosdaq_change,
                        'advance_decline_ratio': snapshot.advance_decline_ratio
                    }
                })
            
            # 종목별 알림
            for stock_snapshot in snapshot.stock_snapshots:
                if stock_snapshot.alerts:
                    alerts.append({
                        'type': 'stock_alert',
                        'stock_code': stock_snapshot.stock_code,
                        'stock_name': stock_snapshot.stock_name,
                        'message': ', '.join(stock_snapshot.alerts),
                        'data': {
                            'price_change_rate': stock_snapshot.price_change_rate,
                            'volume_ratio': stock_snapshot.volume_ratio,
                            'current_price': stock_snapshot.current_price
                        }
                    })
            
            # 알림 콜백 실행
            for alert in alerts:
                self._execute_alert_callbacks(alert)
                
        except Exception as e:
            self._logger.error(f"알림 처리 실패: {e}", exc_info=True)
    
    def _execute_alert_callbacks(self, alert: Dict):
        """알림 콜백 실행"""
        for callback in self._alert_callbacks:
            try:
                callback(alert['type'], alert)
            except Exception as e:
                self._logger.error(f"알림 콜백 실행 실패: {e}", exc_info=True)
    
    def get_current_snapshot(self) -> Optional[MarketSnapshot]:
        """현재 스냅샷 조회"""
        return self._current_snapshot
    
    def get_recent_snapshots(self, hours: int = 24) -> List[MarketSnapshot]:
        """최근 스냅샷 조회"""
        if not self._snapshots:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            snapshot for snapshot in self._snapshots
            if snapshot.timestamp > cutoff_time
        ]
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """모니터링 상태 조회"""
        return {
            'is_monitoring': self._is_monitoring,
            'monitored_symbols_count': len(self._monitored_symbols),
            'snapshots_count': len(self._snapshots),
            'current_snapshot_time': self._current_snapshot.timestamp.isoformat() if self._current_snapshot else None,
            'config': asdict(self._config)
        }

# 전역 인스턴스
_market_monitor = None

def get_market_monitor() -> MarketMonitor:
    """시장 모니터링 시스템 싱글톤 인스턴스 반환"""
    global _market_monitor
    if _market_monitor is None:
        _market_monitor = MarketMonitor()
    return _market_monitor 