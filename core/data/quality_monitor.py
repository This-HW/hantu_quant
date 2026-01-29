"""
주가 데이터 품질 모니터링 시스템

주가 데이터의 이상값을 자동으로 감지하고 품질을 관리
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict
import sqlite3
import threading
import time
from enum import Enum
import json

from ..utils.logging import get_logger

logger = get_logger(__name__)

class AnomalyType(Enum):
    """이상값 유형"""
    PRICE_SPIKE = "price_spike"           # 급격한 가격 변동
    VOLUME_SPIKE = "volume_spike"         # 급격한 거래량 변동  
    ZERO_VOLUME = "zero_volume"           # 거래량 0
    PRICE_GAP = "price_gap"               # 가격 갭
    STATIC_PRICE = "static_price"         # 가격 정체
    NEGATIVE_PRICE = "negative_price"     # 음수 가격
    MISSING_DATA = "missing_data"         # 데이터 누락
    DUPLICATE_DATA = "duplicate_data"     # 중복 데이터
    INVALID_RANGE = "invalid_range"       # 유효하지 않은 범위

class AnomalySeverity(Enum):
    """이상값 심각도"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class DataAnomaly:
    """데이터 이상값 정보"""
    stock_code: str
    stock_name: str
    date: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    
    # 이상값 상세 정보
    current_value: float
    expected_range: Tuple[float, float]
    z_score: Optional[float] = None
    
    # 컨텍스트 정보
    previous_value: Optional[float] = None
    next_value: Optional[float] = None
    market_context: Optional[str] = None  # 'market_wide', 'sector_specific', 'stock_specific'
    
    # 메타데이터
    description: str = ""
    auto_correctable: bool = False
    correction_suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['anomaly_type'] = self.anomaly_type.value
        result['severity'] = self.severity.value
        return result

@dataclass
class QualityMetrics:
    """데이터 품질 지표"""
    date: str
    total_stocks_checked: int
    
    # 이상값 통계
    total_anomalies: int
    anomalies_by_type: Dict[str, int]
    anomalies_by_severity: Dict[str, int]
    
    # 품질 지표
    data_completeness: float  # 0-1 (1이 완전)
    data_accuracy: float      # 0-1 (1이 정확)
    overall_quality_score: float  # 0-100
    
    # 개선 제안
    critical_issues: List[str]
    improvement_suggestions: List[str]

class QualityRule:
    """데이터 품질 검증 규칙"""
    
    def __init__(self, name: str, check_function: callable, 
                 severity: AnomalySeverity = AnomalySeverity.MEDIUM):
        self.name = name
        self.check_function = check_function
        self.severity = severity
        self.enabled = True

class QualityMonitor:
    """주가 데이터 품질 모니터링 시스템"""
    
    def __init__(self, db_path: str = "data/quality_monitor.db"):
        """초기화
        
        Args:
            db_path: 품질 모니터링 데이터베이스 경로
        """
        self._logger = logger
        self._db_path = db_path
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 품질 검증 규칙
        self._quality_rules: List[QualityRule] = []
        
        # 통계 기반 임계값
        self._statistical_thresholds = {
            'price_change_z_score': 3.0,     # 가격 변동 Z-score 임계값
            'volume_change_z_score': 3.0,    # 거래량 변동 Z-score 임계값
            'price_gap_threshold': 0.3,      # 30% 이상 갭
            'static_days_threshold': 5,      # 5일 이상 동일 가격
        }
        
        # 캐시된 통계 데이터
        self._price_stats_cache: Dict[str, Dict] = {}
        self._volume_stats_cache: Dict[str, Dict] = {}
        
        # 데이터베이스 초기화
        self._init_database()
        
        # 기본 품질 규칙 설정
        self._setup_default_rules()
        
        self._logger.info("QualityMonitor 초기화 완료")
    
    def _init_database(self):
        """데이터베이스 테이블 초기화"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                # 이상값 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS data_anomalies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stock_code TEXT NOT NULL,
                        stock_name TEXT,
                        date TEXT NOT NULL,
                        anomaly_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        current_value REAL,
                        expected_min REAL,
                        expected_max REAL,
                        z_score REAL,
                        previous_value REAL,
                        next_value REAL,
                        market_context TEXT,
                        description TEXT,
                        auto_correctable INTEGER,
                        correction_suggestion TEXT,
                        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved INTEGER DEFAULT 0,
                        resolved_at TIMESTAMP
                    )
                ''')
                
                # 품질 지표 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS quality_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL UNIQUE,
                        total_stocks_checked INTEGER,
                        total_anomalies INTEGER,
                        anomalies_by_type TEXT,  -- JSON
                        anomalies_by_severity TEXT,  -- JSON
                        data_completeness REAL,
                        data_accuracy REAL,
                        overall_quality_score REAL,
                        critical_issues TEXT,  -- JSON
                        improvement_suggestions TEXT,  -- JSON
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 통계 캐시 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS stats_cache (
                        stock_code TEXT PRIMARY KEY,
                        price_mean REAL,
                        price_std REAL,
                        volume_mean REAL,
                        volume_std REAL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                self._logger.info("품질 모니터링 데이터베이스 초기화 완료")
                
        except Exception as e:
            self._logger.error(f"데이터베이스 초기화 중 오류: {e}")
    
    def _setup_default_rules(self):
        """기본 품질 검증 규칙 설정"""
        # 음수 가격 검증
        self.add_quality_rule(
            "negative_price_check",
            lambda data: self._check_negative_prices(data),
            AnomalySeverity.CRITICAL
        )
        
        # 0 거래량 검증
        self.add_quality_rule(
            "zero_volume_check", 
            lambda data: self._check_zero_volume(data),
            AnomalySeverity.LOW
        )
        
        # 가격 급등락 검증
        self.add_quality_rule(
            "price_spike_check",
            lambda data: self._check_price_spikes(data),
            AnomalySeverity.HIGH
        )
        
        # 거래량 급증 검증
        self.add_quality_rule(
            "volume_spike_check",
            lambda data: self._check_volume_spikes(data),
            AnomalySeverity.MEDIUM
        )
        
        # 가격 갭 검증
        self.add_quality_rule(
            "price_gap_check",
            lambda data: self._check_price_gaps(data),
            AnomalySeverity.MEDIUM
        )
        
        # 가격 정체 검증
        self.add_quality_rule(
            "static_price_check",
            lambda data: self._check_static_prices(data),
            AnomalySeverity.LOW
        )
        
        # 데이터 누락 검증
        self.add_quality_rule(
            "missing_data_check",
            lambda data: self._check_missing_data(data),
            AnomalySeverity.HIGH
        )
    
    def add_quality_rule(self, name: str, check_function: callable, 
                        severity: AnomalySeverity = AnomalySeverity.MEDIUM):
        """품질 검증 규칙 추가"""
        rule = QualityRule(name, check_function, severity)
        self._quality_rules.append(rule)
        self._logger.debug(f"품질 규칙 추가: {name}")
    
    def _update_statistics_cache(self, stock_code: str, price_data: List[float], 
                               volume_data: List[float]):
        """통계 캐시 업데이트"""
        try:
            price_mean = np.mean(price_data) if price_data else 0.0
            price_std = np.std(price_data) if len(price_data) > 1 else 0.0
            volume_mean = np.mean(volume_data) if volume_data else 0.0
            volume_std = np.std(volume_data) if len(volume_data) > 1 else 0.0
            
            self._price_stats_cache[stock_code] = {
                'mean': price_mean,
                'std': price_std
            }
            
            self._volume_stats_cache[stock_code] = {
                'mean': volume_mean,
                'std': volume_std
            }
            
            # 데이터베이스 업데이트
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO stats_cache
                    (stock_code, price_mean, price_std, volume_mean, volume_std)
                    VALUES (?, ?, ?, ?, ?)
                ''', (stock_code, price_mean, price_std, volume_mean, volume_std))
                
        except Exception as e:
            self._logger.error(f"통계 캐시 업데이트 중 오류: {e}")
    
    def _check_negative_prices(self, data: Dict) -> List[DataAnomaly]:
        """음수 가격 검증"""
        anomalies = []
        
        for record in data.get('price_data', []):
            if record.get('close', 0) < 0:
                anomaly = DataAnomaly(
                    stock_code=record['stock_code'],
                    stock_name=record.get('stock_name', ''),
                    date=record['date'],
                    anomaly_type=AnomalyType.NEGATIVE_PRICE,
                    severity=AnomalySeverity.CRITICAL,
                    current_value=record['close'],
                    expected_range=(0, float('inf')),
                    description="음수 주가 발견",
                    auto_correctable=False
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    def _check_zero_volume(self, data: Dict) -> List[DataAnomaly]:
        """0 거래량 검증"""
        anomalies = []
        
        for record in data.get('price_data', []):
            if record.get('volume', 0) == 0:
                anomaly = DataAnomaly(
                    stock_code=record['stock_code'],
                    stock_name=record.get('stock_name', ''),
                    date=record['date'],
                    anomaly_type=AnomalyType.ZERO_VOLUME,
                    severity=AnomalySeverity.LOW,
                    current_value=0,
                    expected_range=(1, float('inf')),
                    description="거래량 0 발견",
                    auto_correctable=False,
                    market_context="stock_specific"
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    def _check_price_spikes(self, data: Dict) -> List[DataAnomaly]:
        """가격 급등락 검증"""
        anomalies = []
        
        for stock_code, records in data.get('grouped_data', {}).items():
            if len(records) < 2:
                continue
                
            # 통계 정보 가져오기
            stats = self._price_stats_cache.get(stock_code)
            if not stats or stats['std'] == 0:
                continue
            
            for i in range(1, len(records)):
                current_price = records[i].get('close', 0)
                prev_price = records[i-1].get('close', 0)
                
                if prev_price == 0:
                    continue
                
                # 변화율 계산
                change_rate = (current_price - prev_price) / prev_price
                
                # Z-score 계산
                z_score = abs(change_rate) / (stats['std'] / stats['mean']) if stats['mean'] > 0 else 0
                
                if z_score > self._statistical_thresholds['price_change_z_score']:
                    severity = AnomalySeverity.CRITICAL if z_score > 5 else AnomalySeverity.HIGH
                    
                    anomaly = DataAnomaly(
                        stock_code=stock_code,
                        stock_name=records[i].get('stock_name', ''),
                        date=records[i]['date'],
                        anomaly_type=AnomalyType.PRICE_SPIKE,
                        severity=severity,
                        current_value=current_price,
                        expected_range=(prev_price * 0.7, prev_price * 1.3),  # ±30%
                        z_score=z_score,
                        previous_value=prev_price,
                        description=f"급격한 가격 변동: {change_rate*100:.1f}% (Z-score: {z_score:.2f})",
                        auto_correctable=False
                    )
                    anomalies.append(anomaly)
        
        return anomalies
    
    def _check_volume_spikes(self, data: Dict) -> List[DataAnomaly]:
        """거래량 급증 검증"""
        anomalies = []
        
        for stock_code, records in data.get('grouped_data', {}).items():
            if len(records) < 2:
                continue
                
            # 통계 정보 가져오기  
            stats = self._volume_stats_cache.get(stock_code)
            if not stats or stats['std'] == 0:
                continue
            
            for i in range(1, len(records)):
                current_volume = records[i].get('volume', 0)
                avg_volume = stats['mean']
                
                if avg_volume == 0:
                    continue
                
                # 거래량 배수 계산
                volume_multiple = current_volume / avg_volume
                
                if volume_multiple > 10:  # 평균의 10배 이상
                    severity = AnomalySeverity.HIGH if volume_multiple > 50 else AnomalySeverity.MEDIUM
                    
                    anomaly = DataAnomaly(
                        stock_code=stock_code,
                        stock_name=records[i].get('stock_name', ''),
                        date=records[i]['date'],
                        anomaly_type=AnomalyType.VOLUME_SPIKE,
                        severity=severity,
                        current_value=current_volume,
                        expected_range=(0, avg_volume * 5),  # 평균의 5배까지 정상
                        description=f"거래량 급증: 평균의 {volume_multiple:.1f}배",
                        auto_correctable=False,
                        market_context="stock_specific"
                    )
                    anomalies.append(anomaly)
        
        return anomalies
    
    def _check_price_gaps(self, data: Dict) -> List[DataAnomaly]:
        """가격 갭 검증"""
        anomalies = []
        
        for stock_code, records in data.get('grouped_data', {}).items():
            if len(records) < 2:
                continue
            
            for i in range(1, len(records)):
                current_open = records[i].get('open', 0)
                prev_close = records[i-1].get('close', 0)
                
                if prev_close == 0:
                    continue
                
                # 갭 계산
                gap_rate = abs(current_open - prev_close) / prev_close
                
                if gap_rate > self._statistical_thresholds['price_gap_threshold']:
                    severity = AnomalySeverity.HIGH if gap_rate > 0.5 else AnomalySeverity.MEDIUM
                    
                    anomaly = DataAnomaly(
                        stock_code=stock_code,
                        stock_name=records[i].get('stock_name', ''),
                        date=records[i]['date'],
                        anomaly_type=AnomalyType.PRICE_GAP,
                        severity=severity,
                        current_value=current_open,
                        expected_range=(prev_close * 0.9, prev_close * 1.1),  # ±10%
                        previous_value=prev_close,
                        description=f"큰 가격 갭: {gap_rate*100:.1f}%",
                        auto_correctable=False
                    )
                    anomalies.append(anomaly)
        
        return anomalies
    
    def _check_static_prices(self, data: Dict) -> List[DataAnomaly]:
        """가격 정체 검증"""
        anomalies = []
        
        for stock_code, records in data.get('grouped_data', {}).items():
            if len(records) < self._statistical_thresholds['static_days_threshold']:
                continue
            
            # 연속된 동일 가격 확인
            static_count = 1
            last_price = records[0].get('close', 0)
            
            for i in range(1, len(records)):
                current_price = records[i].get('close', 0)
                
                if current_price == last_price and current_price > 0:
                    static_count += 1
                else:
                    static_count = 1
                    last_price = current_price
                
                if static_count >= self._statistical_thresholds['static_days_threshold']:
                    anomaly = DataAnomaly(
                        stock_code=stock_code,
                        stock_name=records[i].get('stock_name', ''),
                        date=records[i]['date'],
                        anomaly_type=AnomalyType.STATIC_PRICE,
                        severity=AnomalySeverity.LOW,
                        current_value=current_price,
                        expected_range=(current_price * 0.95, current_price * 1.05),
                        description=f"{static_count}일 연속 동일 가격",
                        auto_correctable=False,
                        market_context="stock_specific"
                    )
                    anomalies.append(anomaly)
                    static_count = 1  # 중복 방지
        
        return anomalies
    
    def _check_missing_data(self, data: Dict) -> List[DataAnomaly]:
        """데이터 누락 검증"""
        anomalies = []
        
        # 예상 날짜 범위와 실제 데이터 비교
        expected_dates = data.get('expected_dates', [])
        actual_dates = set(record['date'] for record in data.get('price_data', []))
        
        missing_dates = set(expected_dates) - actual_dates
        
        for missing_date in missing_dates:
            # 해당 날짜에 데이터가 있어야 할 종목들 확인
            for stock_code in data.get('expected_stocks', []):
                anomaly = DataAnomaly(
                    stock_code=stock_code,
                    stock_name="",
                    date=missing_date,
                    anomaly_type=AnomalyType.MISSING_DATA,
                    severity=AnomalySeverity.HIGH,
                    current_value=0,
                    expected_range=(1, 1),  # 데이터 존재 예상
                    description=f"데이터 누락: {missing_date}",
                    auto_correctable=True,
                    correction_suggestion="API를 통해 누락된 데이터 재수집"
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    def check_data_quality(self, data: Dict[str, Any]) -> Tuple[List[DataAnomaly], QualityMetrics]:
        """데이터 품질 검증 실행
        
        Args:
            data: 검증할 데이터
                {
                    'price_data': [{'stock_code': str, 'date': str, 'close': float, 'volume': int, ...}],
                    'grouped_data': {stock_code: [records]},
                    'expected_dates': [dates],
                    'expected_stocks': [stock_codes]
                }
        
        Returns:
            Tuple[이상값 리스트, 품질 지표]
        """
        all_anomalies = []
        
        try:
            # 각 품질 규칙 실행
            for rule in self._quality_rules:
                if not rule.enabled:
                    continue
                
                try:
                    rule_anomalies = rule.check_function(data)
                    all_anomalies.extend(rule_anomalies)
                    self._logger.debug(f"품질 규칙 '{rule.name}' 실행 완료: {len(rule_anomalies)}개 이상값")
                    
                except Exception as e:
                    self._logger.error(f"품질 규칙 '{rule.name}' 실행 중 오류: {e}")
            
            # 품질 지표 계산
            quality_metrics = self._calculate_quality_metrics(data, all_anomalies)
            
            # 결과 저장
            self._save_anomalies(all_anomalies)
            self._save_quality_metrics(quality_metrics)
            
            self._logger.info(f"데이터 품질 검증 완료: {len(all_anomalies)}개 이상값 발견")
            
            return all_anomalies, quality_metrics
            
        except Exception as e:
            self._logger.error(f"데이터 품질 검증 중 오류: {e}")
            return [], None
    
    def _calculate_quality_metrics(self, data: Dict, anomalies: List[DataAnomaly]) -> QualityMetrics:
        """품질 지표 계산"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            total_stocks = len(data.get('expected_stocks', []))
            total_anomalies = len(anomalies)
            
            # 유형별 이상값 집계
            anomalies_by_type = {}
            anomalies_by_severity = {}
            
            for anomaly in anomalies:
                anomaly_type = anomaly.anomaly_type.value
                severity = anomaly.severity.value
                
                anomalies_by_type[anomaly_type] = anomalies_by_type.get(anomaly_type, 0) + 1
                anomalies_by_severity[severity] = anomalies_by_severity.get(severity, 0) + 1
            
            # 완성도 계산 (누락 데이터 기준)
            missing_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.MISSING_DATA]
            expected_data_points = len(data.get('expected_dates', [])) * total_stocks
            actual_data_points = len(data.get('price_data', []))
            data_completeness = actual_data_points / expected_data_points if expected_data_points > 0 else 1.0
            
            # 정확도 계산 (심각한 이상값 기준)
            critical_anomalies = [a for a in anomalies if a.severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]]
            data_accuracy = 1.0 - (len(critical_anomalies) / actual_data_points) if actual_data_points > 0 else 1.0
            
            # 전체 품질 점수 (0-100)
            overall_quality_score = (data_completeness * 0.4 + data_accuracy * 0.6) * 100
            
            # 중요 이슈 및 개선 제안
            critical_issues = []
            improvement_suggestions = []
            
            if anomalies_by_severity.get('critical', 0) > 0:
                critical_issues.append(f"심각한 데이터 문제 {anomalies_by_severity['critical']}건")
            
            if data_completeness < 0.9:
                critical_issues.append(f"데이터 완성도 낮음: {data_completeness*100:.1f}%")
                improvement_suggestions.append("누락된 데이터 재수집 필요")
            
            if anomalies_by_type.get('price_spike', 0) > total_stocks * 0.1:
                improvement_suggestions.append("가격 급등락 종목 추가 검토 필요")
            
            return QualityMetrics(
                date=today,
                total_stocks_checked=total_stocks,
                total_anomalies=total_anomalies,
                anomalies_by_type=anomalies_by_type,
                anomalies_by_severity=anomalies_by_severity,
                data_completeness=data_completeness,
                data_accuracy=data_accuracy,
                overall_quality_score=overall_quality_score,
                critical_issues=critical_issues,
                improvement_suggestions=improvement_suggestions
            )
            
        except Exception as e:
            self._logger.error(f"품질 지표 계산 중 오류: {e}")
            return None
    
    def _save_anomalies(self, anomalies: List[DataAnomaly]):
        """이상값 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                for anomaly in anomalies:
                    conn.execute('''
                        INSERT INTO data_anomalies
                        (stock_code, stock_name, date, anomaly_type, severity,
                         current_value, expected_min, expected_max, z_score,
                         previous_value, next_value, market_context, description,
                         auto_correctable, correction_suggestion)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        anomaly.stock_code, anomaly.stock_name, anomaly.date,
                        anomaly.anomaly_type.value, anomaly.severity.value,
                        anomaly.current_value, anomaly.expected_range[0], anomaly.expected_range[1],
                        anomaly.z_score, anomaly.previous_value, anomaly.next_value,
                        anomaly.market_context, anomaly.description,
                        1 if anomaly.auto_correctable else 0, anomaly.correction_suggestion
                    ))
                
                conn.commit()
                self._logger.debug(f"{len(anomalies)}개 이상값 저장 완료")
                
        except Exception as e:
            self._logger.error(f"이상값 저장 중 오류: {e}")
    
    def _save_quality_metrics(self, metrics: QualityMetrics):
        """품질 지표 저장"""
        if not metrics:
            return
            
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO quality_metrics
                    (date, total_stocks_checked, total_anomalies,
                     anomalies_by_type, anomalies_by_severity,
                     data_completeness, data_accuracy, overall_quality_score,
                     critical_issues, improvement_suggestions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metrics.date, metrics.total_stocks_checked, metrics.total_anomalies,
                    json.dumps(metrics.anomalies_by_type),
                    json.dumps(metrics.anomalies_by_severity),
                    metrics.data_completeness, metrics.data_accuracy, metrics.overall_quality_score,
                    json.dumps(metrics.critical_issues),
                    json.dumps(metrics.improvement_suggestions)
                ))
                
                conn.commit()
                self._logger.info(f"품질 지표 저장 완료: 점수 {metrics.overall_quality_score:.1f}")
                
        except Exception as e:
            self._logger.error(f"품질 지표 저장 중 오류: {e}")
    
    def get_recent_anomalies(self, days: int = 7, 
                           severity_filter: Optional[AnomalySeverity] = None) -> List[DataAnomaly]:
        """최근 이상값 조회"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                query = '''
                    SELECT * FROM data_anomalies 
                    WHERE date >= date('now', '-{} days')
                '''.format(days)
                
                params = []
                if severity_filter:
                    query += ' AND severity = ?'
                    params.append(severity_filter.value)
                
                query += ' ORDER BY date DESC, severity DESC'
                
                cursor = conn.execute(query, params)
                anomalies = []
                
                for row in cursor.fetchall():
                    anomaly = DataAnomaly(
                        stock_code=row[1],
                        stock_name=row[2] or '',
                        date=row[3],
                        anomaly_type=AnomalyType(row[4]),
                        severity=AnomalySeverity(row[5]),
                        current_value=row[6],
                        expected_range=(row[7], row[8]),
                        z_score=row[9],
                        previous_value=row[10],
                        next_value=row[11],
                        market_context=row[12],
                        description=row[13],
                        auto_correctable=bool(row[14]),
                        correction_suggestion=row[15]
                    )
                    anomalies.append(anomaly)
                
                return anomalies
                
        except Exception as e:
            self._logger.error(f"최근 이상값 조회 중 오류: {e}")
            return []
    
    def get_quality_trend(self, days: int = 30) -> List[QualityMetrics]:
        """품질 트렌드 조회"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                query = '''
                    SELECT * FROM quality_metrics
                    WHERE date >= date('now', '-{} days')
                    ORDER BY date DESC
                '''.format(days)
                
                cursor = conn.execute(query)
                metrics_list = []
                
                for row in cursor.fetchall():
                    metrics = QualityMetrics(
                        date=row[1],
                        total_stocks_checked=row[2],
                        total_anomalies=row[3],
                        anomalies_by_type=json.loads(row[4]) if row[4] else {},
                        anomalies_by_severity=json.loads(row[5]) if row[5] else {},
                        data_completeness=row[6],
                        data_accuracy=row[7],
                        overall_quality_score=row[8],
                        critical_issues=json.loads(row[9]) if row[9] else [],
                        improvement_suggestions=json.loads(row[10]) if row[10] else []
                    )
                    metrics_list.append(metrics)
                
                return metrics_list
                
        except Exception as e:
            self._logger.error(f"품질 트렌드 조회 중 오류: {e}")
            return []
    
    def export_quality_report(self, days: int = 7, file_path: str = "quality_report.json"):
        """품질 리포트 내보내기"""
        try:
            anomalies = self.get_recent_anomalies(days)
            quality_trend = self.get_quality_trend(days)
            
            report = {
                'generated_at': datetime.now().isoformat(),
                'period_days': days,
                'summary': {
                    'total_anomalies': len(anomalies),
                    'critical_anomalies': len([a for a in anomalies if a.severity == AnomalySeverity.CRITICAL]),
                    'latest_quality_score': quality_trend[0].overall_quality_score if quality_trend else 0
                },
                'anomalies': [anomaly.to_dict() for anomaly in anomalies],
                'quality_trend': [asdict(metric) for metric in quality_trend]
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"품질 리포트를 {file_path}에 저장했습니다.")
            
        except Exception as e:
            self._logger.error(f"품질 리포트 내보내기 중 오류: {e}")

# 글로벌 인스턴스
_quality_monitor_instance: Optional[QualityMonitor] = None

def get_quality_monitor() -> QualityMonitor:
    """품질 모니터 인스턴스 반환 (싱글톤)"""
    global _quality_monitor_instance
    if _quality_monitor_instance is None:
        _quality_monitor_instance = QualityMonitor()
    return _quality_monitor_instance 