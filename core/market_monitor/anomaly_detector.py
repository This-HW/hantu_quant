"""
이상 감지 시스템

시장의 비정상적인 상황을 자동으로 감지하고 분석하는 시스템
"""

import numpy as np
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import warnings
from scipy import stats

from ..utils.logging import get_logger
from .market_monitor import MarketSnapshot, StockSnapshot, MarketStatus

logger = get_logger(__name__)

class AnomalyType(Enum):
    """이상 유형"""
    PRICE_SPIKE = "price_spike"           # 급격한 가격 변동
    VOLUME_SURGE = "volume_surge"         # 거래량 급증
    MARKET_CRASH = "market_crash"         # 시장 급락
    UNUSUAL_PATTERN = "unusual_pattern"   # 비정상 패턴
    CORRELATION_BREAK = "correlation_break"  # 상관관계 이상
    VOLATILITY_SPIKE = "volatility_spike" # 변동성 급증
    NEWS_IMPACT = "news_impact"           # 뉴스 영향
    TECHNICAL_ANOMALY = "technical_anomaly"  # 기술적 이상

class AnomalySeverity(Enum):
    """이상 심각도"""
    LOW = "low"           # 낮음
    MEDIUM = "medium"     # 보통
    HIGH = "high"         # 높음
    CRITICAL = "critical" # 긴급

@dataclass
class AnomalyConfig:
    """이상 감지 설정"""
    # 가격 변동 임계값
    price_spike_threshold: float = 0.15        # 15% 이상 급변동
    price_spike_critical: float = 0.30         # 30% 이상 긴급
    
    # 거래량 임계값
    volume_surge_threshold: float = 5.0        # 평균 대비 5배 이상
    volume_surge_critical: float = 10.0        # 평균 대비 10배 이상
    
    # 시장 지수 임계값
    market_drop_threshold: float = 0.03        # 3% 이상 하락
    market_drop_critical: float = 0.05         # 5% 이상 하락
    
    # 변동성 임계값
    volatility_threshold: float = 0.02         # 2% 이상 변동성
    volatility_critical: float = 0.05          # 5% 이상 변동성
    
    # 상관관계 임계값
    correlation_threshold: float = 0.3         # 상관계수 0.3 이하
    
    # 감지 기간 설정
    detection_window: int = 60                 # 감지 윈도우 (분)
    historical_days: int = 30                  # 과거 데이터 비교 기간
    
    # 필터링 설정
    min_market_cap: float = 100000000          # 최소 시가총액 (1억)
    min_trading_value: float = 1000000         # 최소 거래대금 (100만원)
    
    # 알림 설정
    enable_realtime_alerts: bool = True        # 실시간 알림
    alert_cooldown: int = 300                  # 알림 쿨다운 (초)

@dataclass
class AnomalyAlert:
    """이상 알림"""
    alert_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    timestamp: datetime
    title: str
    description: str
    
    # 관련 정보
    affected_stocks: List[str] = field(default_factory=list)
    market_impact: Optional[float] = None
    confidence_score: float = 0.0
    
    # 상세 데이터
    data: Dict[str, Any] = field(default_factory=dict)
    
    # 추천 조치
    recommendations: List[str] = field(default_factory=list)
    
    # 메타데이터
    detection_method: str = ""
    false_positive_risk: float = 0.0

class StatisticalAnalyzer:
    """통계적 분석기"""
    
    def __init__(self):
        self._logger = logger
        self._price_history = {}
        self._volume_history = {}
        self._correlation_matrix = None
    
    def update_historical_data(self, snapshots: List[MarketSnapshot]):
        """과거 데이터 업데이트"""
        try:
            for snapshot in snapshots:
                for stock in snapshot.stock_snapshots:
                    stock_code = stock.stock_code
                    
                    # 가격 히스토리 업데이트
                    if stock_code not in self._price_history:
                        self._price_history[stock_code] = []
                    
                    self._price_history[stock_code].append({
                        'timestamp': snapshot.timestamp,
                        'price': stock.current_price,
                        'change_rate': stock.price_change_rate
                    })
                    
                    # 거래량 히스토리 업데이트
                    if stock_code not in self._volume_history:
                        self._volume_history[stock_code] = []
                    
                    self._volume_history[stock_code].append({
                        'timestamp': snapshot.timestamp,
                        'volume': stock.volume,
                        'volume_ratio': stock.volume_ratio
                    })
            
            # 오래된 데이터 정리 (30일)
            cutoff_time = datetime.now() - timedelta(days=30)
            self._cleanup_old_data(cutoff_time)
            
        except Exception as e:
            self._logger.error(f"과거 데이터 업데이트 실패: {e}")
    
    def _cleanup_old_data(self, cutoff_time: datetime):
        """오래된 데이터 정리"""
        for stock_code in list(self._price_history.keys()):
            self._price_history[stock_code] = [
                item for item in self._price_history[stock_code]
                if item['timestamp'] > cutoff_time
            ]
            
            if not self._price_history[stock_code]:
                del self._price_history[stock_code]
        
        for stock_code in list(self._volume_history.keys()):
            self._volume_history[stock_code] = [
                item for item in self._volume_history[stock_code]
                if item['timestamp'] > cutoff_time
            ]
            
            if not self._volume_history[stock_code]:
                del self._volume_history[stock_code]
    
    def detect_price_anomalies(self, current_snapshot: MarketSnapshot, config: AnomalyConfig) -> List[Dict]:
        """가격 이상 감지"""
        anomalies = []
        
        try:
            for stock in current_snapshot.stock_snapshots:
                stock_code = stock.stock_code
                
                # 시가총액 필터링
                if stock.market_cap < config.min_market_cap:
                    continue
                
                # 거래대금 필터링
                if stock.trading_value < config.min_trading_value:
                    continue
                
                # 급격한 가격 변동 감지
                abs_change = abs(stock.price_change_rate)
                
                if abs_change >= config.price_spike_critical:
                    severity = AnomalySeverity.CRITICAL
                elif abs_change >= config.price_spike_threshold:
                    severity = AnomalySeverity.HIGH
                else:
                    continue
                
                # 과거 데이터와 비교
                historical_stats = self._get_price_statistics(stock_code)
                
                anomaly = {
                    'type': AnomalyType.PRICE_SPIKE,
                    'severity': severity,
                    'stock_code': stock_code,
                    'stock_name': stock.stock_name,
                    'current_change': stock.price_change_rate,
                    'current_price': stock.current_price,
                    'historical_mean': historical_stats.get('mean_change', 0),
                    'historical_std': historical_stats.get('std_change', 0),
                    'z_score': self._calculate_z_score(stock.price_change_rate, historical_stats),
                    'confidence': min(abs_change / config.price_spike_threshold, 1.0)
                }
                
                anomalies.append(anomaly)
                
        except Exception as e:
            self._logger.error(f"가격 이상 감지 실패: {e}")
        
        return anomalies
    
    def detect_volume_anomalies(self, current_snapshot: MarketSnapshot, config: AnomalyConfig) -> List[Dict]:
        """거래량 이상 감지"""
        anomalies = []
        
        try:
            for stock in current_snapshot.stock_snapshots:
                stock_code = stock.stock_code
                
                # 필터링
                if stock.market_cap < config.min_market_cap:
                    continue
                
                # 거래량 급증 감지
                volume_ratio = stock.volume_ratio
                
                if volume_ratio >= config.volume_surge_critical:
                    severity = AnomalySeverity.CRITICAL
                elif volume_ratio >= config.volume_surge_threshold:
                    severity = AnomalySeverity.HIGH
                else:
                    continue
                
                # 과거 거래량 패턴 분석
                historical_stats = self._get_volume_statistics(stock_code)
                
                anomaly = {
                    'type': AnomalyType.VOLUME_SURGE,
                    'severity': severity,
                    'stock_code': stock_code,
                    'stock_name': stock.stock_name,
                    'current_volume': stock.volume,
                    'volume_ratio': volume_ratio,
                    'avg_volume': stock.volume_avg_20d,
                    'historical_max': historical_stats.get('max_ratio', 0),
                    'confidence': min(volume_ratio / config.volume_surge_threshold, 1.0)
                }
                
                anomalies.append(anomaly)
                
        except Exception as e:
            self._logger.error(f"거래량 이상 감지 실패: {e}")
        
        return anomalies
    
    def detect_market_anomalies(self, current_snapshot: MarketSnapshot, config: AnomalyConfig) -> List[Dict]:
        """시장 전체 이상 감지"""
        anomalies = []
        
        try:
            # 시장 지수 급락 감지
            kospi_change = current_snapshot.kospi_change
            kosdaq_change = current_snapshot.kosdaq_change
            
            market_changes = [kospi_change, kosdaq_change]
            worst_change = min(market_changes)
            
            if worst_change <= -config.market_drop_critical:
                severity = AnomalySeverity.CRITICAL
            elif worst_change <= -config.market_drop_threshold:
                severity = AnomalySeverity.HIGH
            else:
                severity = None
            
            if severity:
                anomaly = {
                    'type': AnomalyType.MARKET_CRASH,
                    'severity': severity,
                    'kospi_change': kospi_change,
                    'kosdaq_change': kosdaq_change,
                    'worst_change': worst_change,
                    'advance_decline_ratio': current_snapshot.advance_decline_ratio,
                    'declining_stocks': current_snapshot.declining_stocks,
                    'total_stocks': current_snapshot.total_stocks
                }
                
                anomalies.append(anomaly)
            
            # 상승/하락 비율 이상
            ad_ratio = current_snapshot.advance_decline_ratio
            if ad_ratio > 10.0 or ad_ratio < 0.1:
                anomaly = {
                    'type': AnomalyType.UNUSUAL_PATTERN,
                    'severity': AnomalySeverity.HIGH if ad_ratio > 20.0 or ad_ratio < 0.05 else AnomalySeverity.MEDIUM,
                    'advance_decline_ratio': ad_ratio,
                    'pattern_type': 'extreme_ad_ratio'
                }
                
                anomalies.append(anomaly)
                
        except Exception as e:
            self._logger.error(f"시장 이상 감지 실패: {e}")
        
        return anomalies
    
    def detect_correlation_anomalies(self, recent_snapshots: List[MarketSnapshot], config: AnomalyConfig) -> List[Dict]:
        """상관관계 이상 감지"""
        anomalies = []
        
        try:
            if len(recent_snapshots) < 10:  # 최소 10개 스냅샷 필요
                return anomalies
            
            # 종목별 수익률 매트릭스 생성
            stock_returns = self._build_returns_matrix(recent_snapshots)
            
            if stock_returns.empty:
                return anomalies
            
            # 상관계수 매트릭스 계산
            correlation_matrix = stock_returns.corr()
            
            # 이상 상관관계 감지
            for i, stock1 in enumerate(correlation_matrix.columns):
                for j, stock2 in enumerate(correlation_matrix.columns):
                    if i >= j:  # 중복 제거
                        continue
                    
                    correlation = correlation_matrix.loc[stock1, stock2]
                    
                    # 비정상적으로 낮은 상관관계 (보통 양의 상관관계를 가져야 하는 종목들)
                    if not np.isnan(correlation) and correlation < config.correlation_threshold:
                        anomaly = {
                            'type': AnomalyType.CORRELATION_BREAK,
                            'severity': AnomalySeverity.MEDIUM,
                            'stock1': stock1,
                            'stock2': stock2,
                            'correlation': correlation,
                            'expected_correlation': 0.7  # 예상 상관계수
                        }
                        
                        anomalies.append(anomaly)
                        
        except Exception as e:
            self._logger.error(f"상관관계 이상 감지 실패: {e}")
        
        return anomalies
    
    def _get_price_statistics(self, stock_code: str) -> Dict[str, float]:
        """가격 통계 정보 조회"""
        if stock_code not in self._price_history:
            return {}
        
        history = self._price_history[stock_code]
        if not history:
            return {}
        
        changes = [item['change_rate'] for item in history]
        
        return {
            'mean_change': np.mean(changes),
            'std_change': np.std(changes),
            'min_change': np.min(changes),
            'max_change': np.max(changes)
        }
    
    def _get_volume_statistics(self, stock_code: str) -> Dict[str, float]:
        """거래량 통계 정보 조회"""
        if stock_code not in self._volume_history:
            return {}
        
        history = self._volume_history[stock_code]
        if not history:
            return {}
        
        ratios = [item['volume_ratio'] for item in history]
        
        return {
            'mean_ratio': np.mean(ratios),
            'std_ratio': np.std(ratios),
            'max_ratio': np.max(ratios),
            'percentile_95': np.percentile(ratios, 95)
        }
    
    def _calculate_z_score(self, value: float, stats: Dict[str, float]) -> Optional[float]:
        """Z-score 계산"""
        try:
            mean = stats.get('mean_change', 0)
            std = stats.get('std_change', 1)
            
            if std == 0:
                return None
            
            return (value - mean) / std
            
        except:
            return None
    
    def _build_returns_matrix(self, snapshots: List[MarketSnapshot]) -> pd.DataFrame:
        """수익률 매트릭스 구성"""
        try:
            data = {}
            
            for snapshot in snapshots:
                timestamp = snapshot.timestamp
                
                for stock in snapshot.stock_snapshots:
                    stock_code = stock.stock_code
                    
                    if stock_code not in data:
                        data[stock_code] = {}
                    
                    data[stock_code][timestamp] = stock.price_change_rate
            
            # DataFrame 생성
            df = pd.DataFrame(data)
            df = df.dropna(axis=1, thresh=len(df) * 0.8)  # 80% 이상 데이터가 있는 종목만
            
            return df
            
        except Exception as e:
            self._logger.error(f"수익률 매트릭스 구성 실패: {e}")
            return pd.DataFrame()

class PatternAnalyzer:
    """패턴 분석기"""
    
    def __init__(self):
        self._logger = logger
        self._pattern_cache = {}
    
    def detect_unusual_patterns(self, current_snapshot: MarketSnapshot, 
                              recent_snapshots: List[MarketSnapshot], 
                              config: AnomalyConfig) -> List[Dict]:
        """비정상 패턴 감지"""
        anomalies = []
        
        try:
            # 연속 급등/급락 패턴
            consecutive_anomalies = self._detect_consecutive_patterns(recent_snapshots)
            anomalies.extend(consecutive_anomalies)
            
            # 동조화 패턴 (모든 종목이 같은 방향으로 움직임)
            synchronization_anomalies = self._detect_synchronization_patterns(current_snapshot)
            anomalies.extend(synchronization_anomalies)
            
            # 거래량-가격 불일치 패턴
            volume_price_anomalies = self._detect_volume_price_divergence(current_snapshot)
            anomalies.extend(volume_price_anomalies)
            
        except Exception as e:
            self._logger.error(f"패턴 분석 실패: {e}")
        
        return anomalies
    
    def _detect_consecutive_patterns(self, snapshots: List[MarketSnapshot]) -> List[Dict]:
        """연속 패턴 감지"""
        anomalies = []
        
        if len(snapshots) < 3:
            return anomalies
        
        try:
            # 최근 3개 스냅샷에서 연속 급락 패턴 감지
            recent_3 = snapshots[-3:]
            
            consecutive_drops = 0
            consecutive_rises = 0
            
            for snapshot in recent_3:
                if snapshot.kospi_change < -0.02:  # 2% 이상 하락
                    consecutive_drops += 1
                elif snapshot.kospi_change > 0.02:  # 2% 이상 상승
                    consecutive_rises += 1
            
            if consecutive_drops >= 3:
                anomaly = {
                    'type': AnomalyType.UNUSUAL_PATTERN,
                    'severity': AnomalySeverity.HIGH,
                    'pattern_type': 'consecutive_drops',
                    'consecutive_count': consecutive_drops,
                    'avg_drop': np.mean([s.kospi_change for s in recent_3])
                }
                anomalies.append(anomaly)
            
            if consecutive_rises >= 3:
                anomaly = {
                    'type': AnomalyType.UNUSUAL_PATTERN,
                    'severity': AnomalySeverity.MEDIUM,
                    'pattern_type': 'consecutive_rises',
                    'consecutive_count': consecutive_rises,
                    'avg_rise': np.mean([s.kospi_change for s in recent_3])
                }
                anomalies.append(anomaly)
                
        except Exception as e:
            self._logger.error(f"연속 패턴 감지 실패: {e}")
        
        return anomalies
    
    def _detect_synchronization_patterns(self, snapshot: MarketSnapshot) -> List[Dict]:
        """동조화 패턴 감지"""
        anomalies = []
        
        try:
            if not snapshot.stock_snapshots:
                return anomalies
            
            # 모든 종목의 변동 방향 분석
            price_changes = [stock.price_change_rate for stock in snapshot.stock_snapshots]
            
            positive_count = sum(1 for change in price_changes if change > 0.01)
            negative_count = sum(1 for change in price_changes if change < -0.01)
            total_count = len(price_changes)
            
            # 90% 이상이 같은 방향으로 움직이는 경우
            if positive_count / total_count > 0.9:
                anomaly = {
                    'type': AnomalyType.UNUSUAL_PATTERN,
                    'severity': AnomalySeverity.MEDIUM,
                    'pattern_type': 'mass_buying',
                    'sync_ratio': positive_count / total_count,
                    'avg_change': np.mean([change for change in price_changes if change > 0])
                }
                anomalies.append(anomaly)
            
            if negative_count / total_count > 0.9:
                anomaly = {
                    'type': AnomalyType.UNUSUAL_PATTERN,
                    'severity': AnomalySeverity.HIGH,
                    'pattern_type': 'mass_selling',
                    'sync_ratio': negative_count / total_count,
                    'avg_change': np.mean([change for change in price_changes if change < 0])
                }
                anomalies.append(anomaly)
                
        except Exception as e:
            self._logger.error(f"동조화 패턴 감지 실패: {e}")
        
        return anomalies
    
    def _detect_volume_price_divergence(self, snapshot: MarketSnapshot) -> List[Dict]:
        """거래량-가격 불일치 패턴 감지"""
        anomalies = []
        
        try:
            for stock in snapshot.stock_snapshots:
                # 가격은 크게 오르는데 거래량이 적은 경우 (의심스러운 상승)
                if (stock.price_change_rate > 0.05 and  # 5% 이상 상승
                    stock.volume_ratio < 0.5):  # 거래량은 평균의 절반 이하
                    
                    anomaly = {
                        'type': AnomalyType.UNUSUAL_PATTERN,
                        'severity': AnomalySeverity.MEDIUM,
                        'stock_code': stock.stock_code,
                        'pattern_type': 'price_up_volume_down',
                        'price_change': stock.price_change_rate,
                        'volume_ratio': stock.volume_ratio
                    }
                    anomalies.append(anomaly)
                
                # 가격은 크게 떨어지는데 거래량이 매우 많은 경우 (공포 매도)
                if (stock.price_change_rate < -0.05 and  # 5% 이상 하락
                    stock.volume_ratio > 5.0):  # 거래량은 평균의 5배 이상
                    
                    anomaly = {
                        'type': AnomalyType.UNUSUAL_PATTERN,
                        'severity': AnomalySeverity.HIGH,
                        'stock_code': stock.stock_code,
                        'pattern_type': 'panic_selling',
                        'price_change': stock.price_change_rate,
                        'volume_ratio': stock.volume_ratio
                    }
                    anomalies.append(anomaly)
                    
        except Exception as e:
            self._logger.error(f"거래량-가격 불일치 감지 실패: {e}")
        
        return anomalies

class AnomalyDetector:
    """종합 이상 감지 시스템"""
    
    def __init__(self, config: AnomalyConfig = None, data_dir: str = "data/anomaly_detection"):
        """
        초기화
        
        Args:
            config: 이상 감지 설정
            data_dir: 데이터 저장 디렉토리
        """
        self._logger = logger
        self._config = config or AnomalyConfig()
        self._data_dir = data_dir
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 분석 컴포넌트
        self._statistical_analyzer = StatisticalAnalyzer()
        self._pattern_analyzer = PatternAnalyzer()
        
        # 감지 기록
        self._detected_anomalies = []
        self._alert_history = []
        self._last_alerts = {}
        
        self._logger.info("이상 감지 시스템 초기화 완료")
    
    def detect_anomalies(self, current_snapshot: MarketSnapshot, 
                        recent_snapshots: List[MarketSnapshot]) -> List[AnomalyAlert]:
        """종합 이상 감지"""
        alerts = []
        
        try:
            # 과거 데이터 업데이트
            self._statistical_analyzer.update_historical_data(recent_snapshots)
            
            # 1. 가격 이상 감지
            price_anomalies = self._statistical_analyzer.detect_price_anomalies(current_snapshot, self._config)
            alerts.extend(self._convert_to_alerts(price_anomalies, 'statistical_price'))
            
            # 2. 거래량 이상 감지
            volume_anomalies = self._statistical_analyzer.detect_volume_anomalies(current_snapshot, self._config)
            alerts.extend(self._convert_to_alerts(volume_anomalies, 'statistical_volume'))
            
            # 3. 시장 전체 이상 감지
            market_anomalies = self._statistical_analyzer.detect_market_anomalies(current_snapshot, self._config)
            alerts.extend(self._convert_to_alerts(market_anomalies, 'market_wide'))
            
            # 4. 상관관계 이상 감지
            correlation_anomalies = self._statistical_analyzer.detect_correlation_anomalies(recent_snapshots, self._config)
            alerts.extend(self._convert_to_alerts(correlation_anomalies, 'correlation'))
            
            # 5. 패턴 이상 감지
            pattern_anomalies = self._pattern_analyzer.detect_unusual_patterns(current_snapshot, recent_snapshots, self._config)
            alerts.extend(self._convert_to_alerts(pattern_anomalies, 'pattern'))
            
            # 6. 중복 제거 및 필터링
            filtered_alerts = self._filter_and_deduplicate_alerts(alerts)
            
            # 7. 알림 기록
            self._record_alerts(filtered_alerts)
            
            return filtered_alerts
            
        except Exception as e:
            self._logger.error(f"이상 감지 실패: {e}")
            return []
    
    def _convert_to_alerts(self, anomalies: List[Dict], detection_method: str) -> List[AnomalyAlert]:
        """이상 데이터를 알림으로 변환"""
        alerts = []
        
        for anomaly in anomalies:
            try:
                anomaly_type = anomaly.get('type', AnomalyType.UNUSUAL_PATTERN)
                severity = anomaly.get('severity', AnomalySeverity.MEDIUM)
                
                # 알림 ID 생성
                alert_id = f"{anomaly_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(alerts)}"
                
                # 제목 및 설명 생성
                title, description = self._generate_alert_content(anomaly)
                
                # 추천사항 생성
                recommendations = self._generate_recommendations(anomaly)
                
                # 신뢰도 점수 계산
                confidence_score = anomaly.get('confidence', 0.5)
                
                # 거짓 양성 위험도 계산
                false_positive_risk = self._calculate_false_positive_risk(anomaly, detection_method)
                
                alert = AnomalyAlert(
                    alert_id=alert_id,
                    anomaly_type=anomaly_type,
                    severity=severity,
                    timestamp=datetime.now(),
                    title=title,
                    description=description,
                    affected_stocks=self._extract_affected_stocks(anomaly),
                    market_impact=self._calculate_market_impact(anomaly),
                    confidence_score=confidence_score,
                    data=anomaly,
                    recommendations=recommendations,
                    detection_method=detection_method,
                    false_positive_risk=false_positive_risk
                )
                
                alerts.append(alert)
                
            except Exception as e:
                self._logger.error(f"알림 변환 실패: {e}")
        
        return alerts
    
    def _generate_alert_content(self, anomaly: Dict) -> Tuple[str, str]:
        """알림 제목 및 설명 생성"""
        anomaly_type = anomaly.get('type')
        
        if anomaly_type == AnomalyType.PRICE_SPIKE:
            stock_name = anomaly.get('stock_name', anomaly.get('stock_code', ''))
            change = anomaly.get('current_change', 0)
            title = f"급격한 가격 변동: {stock_name}"
            description = f"{stock_name}이 {change:.1%} 변동했습니다. Z-score: {anomaly.get('z_score', 'N/A')}"
            
        elif anomaly_type == AnomalyType.VOLUME_SURGE:
            stock_name = anomaly.get('stock_name', anomaly.get('stock_code', ''))
            ratio = anomaly.get('volume_ratio', 0)
            title = f"거래량 급증: {stock_name}"
            description = f"{stock_name}의 거래량이 평균 대비 {ratio:.1f}배 증가했습니다."
            
        elif anomaly_type == AnomalyType.MARKET_CRASH:
            worst_change = anomaly.get('worst_change', 0)
            title = "시장 급락 감지"
            description = f"시장 지수가 {worst_change:.1%} 하락했습니다. 상승/하락 비율: {anomaly.get('advance_decline_ratio', 'N/A')}"
            
        elif anomaly_type == AnomalyType.UNUSUAL_PATTERN:
            pattern_type = anomaly.get('pattern_type', 'unknown')
            title = f"비정상 패턴 감지: {pattern_type}"
            description = f"시장에서 {pattern_type} 패턴이 감지되었습니다."
            
        else:
            title = f"이상 상황 감지: {anomaly_type.value}"
            description = "상세한 분석이 필요한 이상 상황이 감지되었습니다."
        
        return title, description
    
    def _generate_recommendations(self, anomaly: Dict) -> List[str]:
        """추천사항 생성"""
        recommendations = []
        anomaly_type = anomaly.get('type')
        severity = anomaly.get('severity')
        
        if anomaly_type == AnomalyType.PRICE_SPIKE:
            if severity == AnomalySeverity.CRITICAL:
                recommendations.extend([
                    "거래 중단을 고려하세요",
                    "포지션 크기를 줄이세요",
                    "뉴스 및 공시사항을 확인하세요"
                ])
            else:
                recommendations.extend([
                    "신중한 거래를 권장합니다",
                    "추가 정보 수집이 필요합니다"
                ])
        
        elif anomaly_type == AnomalyType.VOLUME_SURGE:
            recommendations.extend([
                "시장 관심도 증가 확인",
                "뉴스 및 공시 확인",
                "기술적 분석 재검토"
            ])
        
        elif anomaly_type == AnomalyType.MARKET_CRASH:
            recommendations.extend([
                "전체 포트폴리오 리스크 점검",
                "헤지 전략 고려",
                "현금 비중 증대 검토"
            ])
        
        elif anomaly_type == AnomalyType.UNUSUAL_PATTERN:
            recommendations.extend([
                "패턴 지속성 모니터링",
                "관련 종목 분석",
                "시장 참여자 행동 분석"
            ])
        
        return recommendations
    
    def _extract_affected_stocks(self, anomaly: Dict) -> List[str]:
        """영향받은 종목 추출"""
        affected_stocks = []
        
        if 'stock_code' in anomaly:
            affected_stocks.append(anomaly['stock_code'])
        
        if 'stock1' in anomaly and 'stock2' in anomaly:
            affected_stocks.extend([anomaly['stock1'], anomaly['stock2']])
        
        return affected_stocks
    
    def _calculate_market_impact(self, anomaly: Dict) -> Optional[float]:
        """시장 영향도 계산"""
        anomaly_type = anomaly.get('type')
        
        if anomaly_type == AnomalyType.MARKET_CRASH:
            return abs(anomaly.get('worst_change', 0))
        
        elif anomaly_type == AnomalyType.PRICE_SPIKE:
            # 시가총액을 고려한 영향도 (단순화)
            return abs(anomaly.get('current_change', 0)) * 0.1
        
        elif anomaly_type == AnomalyType.VOLUME_SURGE:
            return anomaly.get('volume_ratio', 1) * 0.01
        
        return None
    
    def _calculate_false_positive_risk(self, anomaly: Dict, detection_method: str) -> float:
        """거짓 양성 위험도 계산"""
        base_risk = 0.1  # 기본 10%
        
        # 감지 방법별 조정
        if detection_method == 'statistical_price':
            z_score = anomaly.get('z_score')
            if z_score and abs(z_score) > 3:
                base_risk *= 0.5  # Z-score가 높으면 위험도 낮춤
        
        elif detection_method == 'pattern':
            # 패턴 기반 감지는 상대적으로 위험도 높음
            base_risk *= 1.5
        
        # 신뢰도 점수로 조정
        confidence = anomaly.get('confidence', 0.5)
        base_risk *= (1 - confidence)
        
        return min(base_risk, 0.9)  # 최대 90%
    
    def _filter_and_deduplicate_alerts(self, alerts: List[AnomalyAlert]) -> List[AnomalyAlert]:
        """알림 필터링 및 중복 제거"""
        filtered_alerts = []
        
        for alert in alerts:
            # 쿨다운 체크
            if self._is_in_cooldown(alert):
                continue
            
            # 거짓 양성 위험도 체크
            if alert.false_positive_risk > 0.7:
                continue
            
            # 신뢰도 체크
            if alert.confidence_score < 0.3:
                continue
            
            filtered_alerts.append(alert)
        
        return filtered_alerts
    
    def _is_in_cooldown(self, alert: AnomalyAlert) -> bool:
        """쿨다운 상태 확인"""
        key = f"{alert.anomaly_type.value}_{','.join(alert.affected_stocks)}"
        
        if key in self._last_alerts:
            last_time = self._last_alerts[key]
            if (datetime.now() - last_time).total_seconds() < self._config.alert_cooldown:
                return True
        
        self._last_alerts[key] = datetime.now()
        return False
    
    def _record_alerts(self, alerts: List[AnomalyAlert]):
        """알림 기록"""
        for alert in alerts:
            self._alert_history.append(alert)
            
            # 파일로 저장
            self._save_alert(alert)
        
        # 오래된 기록 정리
        cutoff_time = datetime.now() - timedelta(days=30)
        self._alert_history = [
            alert for alert in self._alert_history
            if alert.timestamp > cutoff_time
        ]
    
    def _save_alert(self, alert: AnomalyAlert):
        """알림 저장"""
        try:
            timestamp_str = alert.timestamp.strftime('%Y%m%d_%H%M%S')
            filename = f"anomaly_alert_{timestamp_str}_{alert.alert_id}.json"
            filepath = os.path.join(self._data_dir, filename)
            
            # 알림 직렬화
            alert_dict = asdict(alert)
            alert_dict['timestamp'] = alert.timestamp.isoformat()
            alert_dict['anomaly_type'] = alert.anomaly_type.value
            alert_dict['severity'] = alert.severity.value
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(alert_dict, f, ensure_ascii=False, indent=2, default=str)
                
        except Exception as e:
            self._logger.error(f"알림 저장 실패: {e}")
    
    def get_recent_alerts(self, hours: int = 24, severity: AnomalySeverity = None) -> List[AnomalyAlert]:
        """최근 알림 조회"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        alerts = [
            alert for alert in self._alert_history
            if alert.timestamp > cutoff_time
        ]
        
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)
    
    def get_detection_summary(self) -> Dict[str, Any]:
        """감지 요약 정보"""
        recent_alerts = self.get_recent_alerts(24)
        
        return {
            'total_alerts_24h': len(recent_alerts),
            'critical_alerts': len([a for a in recent_alerts if a.severity == AnomalySeverity.CRITICAL]),
            'high_alerts': len([a for a in recent_alerts if a.severity == AnomalySeverity.HIGH]),
            'medium_alerts': len([a for a in recent_alerts if a.severity == AnomalySeverity.MEDIUM]),
            'low_alerts': len([a for a in recent_alerts if a.severity == AnomalySeverity.LOW]),
            'most_common_type': self._get_most_common_anomaly_type(recent_alerts),
            'avg_confidence_score': np.mean([a.confidence_score for a in recent_alerts]) if recent_alerts else 0,
            'config': asdict(self._config)
        }
    
    def _get_most_common_anomaly_type(self, alerts: List[AnomalyAlert]) -> str:
        """가장 빈번한 이상 유형"""
        if not alerts:
            return "none"
        
        type_counts = {}
        for alert in alerts:
            type_name = alert.anomaly_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return max(type_counts, key=type_counts.get)

# 전역 인스턴스
_anomaly_detector = None

def get_anomaly_detector() -> AnomalyDetector:
    """이상 감지 시스템 싱글톤 인스턴스 반환"""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector 