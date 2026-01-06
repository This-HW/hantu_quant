"""
AI 모델 성능 저하 감지 시스템

AI 모델의 성능을 지속적으로 모니터링하고 성능 저하를 감지
"""

import numpy as np
import pandas as pd
import sqlite3
import json
import threading
import time
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import warnings

from core.utils.log_utils import get_logger

logger = get_logger(__name__)

class ModelType(Enum):
    """모델 유형"""
    STOCK_SCREENER = "stock_screener"
    PRICE_PREDICTOR = "price_predictor" 
    MOMENTUM_STRATEGY = "momentum_strategy"
    RISK_ASSESSOR = "risk_assessor"
    PORTFOLIO_OPTIMIZER = "portfolio_optimizer"

class PerformanceDegradationType(Enum):
    """성능 저하 유형"""
    ACCURACY_DROP = "accuracy_drop"
    PREDICTION_DRIFT = "prediction_drift"
    FEATURE_DRIFT = "feature_drift"
    CONCEPT_DRIFT = "concept_drift"
    DATA_QUALITY_ISSUE = "data_quality_issue"
    OVERFITTING = "overfitting"

@dataclass
class ModelPerformanceMetrics:
    """모델 성능 지표"""
    model_name: str
    model_type: ModelType
    measurement_date: str
    
    # 기본 성능 지표
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    
    # 예측 관련 지표
    prediction_accuracy: float  # 가격 예측 정확도
    directional_accuracy: float  # 방향 예측 정확도
    
    # 수익성 지표
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    
    # 안정성 지표
    prediction_variance: float
    feature_importance_stability: float
    
    # 데이터 품질 지표
    data_coverage: float  # 데이터 커버리지
    missing_data_ratio: float
    outlier_ratio: float
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['model_type'] = self.model_type.value
        return result

@dataclass
class PerformanceDegradationAlert:
    """성능 저하 알림"""
    alert_id: str
    model_name: str
    degradation_type: PerformanceDegradationType
    severity: str  # 'low', 'medium', 'high', 'critical'
    
    # 성능 정보
    current_performance: float
    baseline_performance: float
    performance_drop: float
    
    # 컨텍스트
    detection_date: str
    affected_period: str
    root_cause_analysis: Dict[str, Any]
    
    # 권장 조치
    recommended_actions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['degradation_type'] = self.degradation_type.value
        return result

class ModelPerformanceMonitor:
    """AI 모델 성능 모니터"""
    
    def __init__(self, db_path: str = "data/model_performance.db"):
        """초기화
        
        Args:
            db_path: 성능 데이터베이스 경로
        """
        self._logger = logger
        self._db_path = db_path
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 성능 임계값 설정
        self._performance_thresholds = {
            'accuracy_drop_warning': 0.05,    # 5% 정확도 하락 시 경고
            'accuracy_drop_critical': 0.15,   # 15% 정확도 하락 시 심각
            'prediction_variance_high': 0.3,  # 예측 분산 높음
            'sharpe_ratio_low': 1.0,          # 샤프 비율 낮음
            'max_drawdown_high': 0.2,         # 최대 낙폭 20% 이상
        }
        
        # 모델별 기준선 성능
        self._baseline_performance: Dict[str, ModelPerformanceMetrics] = {}
        
        # 성능 이력
        self._performance_history: Dict[str, List[ModelPerformanceMetrics]] = {}
        
        # 알림 콜백
        self._alert_callbacks: List[callable] = []
        
        # 데이터베이스 초기화
        self._init_database()
        
        # 스케줄러 설정
        self._setup_scheduler()
        
        self._logger.info("ModelPerformanceMonitor 초기화 완료")
    
    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self._db_path) as conn:
                # 모델 성능 지표 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS model_performance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        model_name TEXT NOT NULL,
                        model_type TEXT NOT NULL,
                        measurement_date TEXT NOT NULL,
                        accuracy REAL,
                        precision REAL,
                        recall REAL,
                        f1_score REAL,
                        prediction_accuracy REAL,
                        directional_accuracy REAL,
                        profit_factor REAL,
                        sharpe_ratio REAL,
                        max_drawdown REAL,
                        prediction_variance REAL,
                        feature_importance_stability REAL,
                        data_coverage REAL,
                        missing_data_ratio REAL,
                        outlier_ratio REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(model_name, measurement_date)
                    )
                ''')
                
                # 성능 저하 알림 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS performance_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        alert_id TEXT NOT NULL UNIQUE,
                        model_name TEXT NOT NULL,
                        degradation_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        current_performance REAL,
                        baseline_performance REAL,
                        performance_drop REAL,
                        detection_date TEXT NOT NULL,
                        affected_period TEXT,
                        root_cause_analysis TEXT,  -- JSON
                        recommended_actions TEXT,  -- JSON
                        resolved INTEGER DEFAULT 0,
                        resolved_date TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 모델 기준선 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS model_baselines (
                        model_name TEXT PRIMARY KEY,
                        model_type TEXT NOT NULL,
                        baseline_metrics TEXT NOT NULL,  -- JSON
                        established_date TEXT NOT NULL,
                        last_updated TEXT NOT NULL
                    )
                ''')
                
                conn.commit()
                self._logger.info("모델 성능 모니터링 데이터베이스 초기화 완료")
                
        except Exception as e:
            self._logger.error(f"데이터베이스 초기화 중 오류: {e}", exc_info=True)
    
    def _setup_scheduler(self):
        """스케줄러 설정"""
        # 매일 오후 9시에 일일 성능 평가
        schedule.every().day.at("21:00").do(self._run_daily_evaluation)
        
        # 매주 월요일 오전 10시에 주간 성능 분석
        schedule.every().monday.at("10:00").do(self._run_weekly_analysis)
        
        # 매월 1일 오전 11시에 월간 성능 리뷰
        schedule.every().month.do(self._run_monthly_review)
    
    def add_alert_callback(self, callback: callable):
        """알림 콜백 추가"""
        self._alert_callbacks.append(callback)
    
    def record_model_performance(self, metrics: ModelPerformanceMetrics):
        """모델 성능 기록
        
        Args:
            metrics: 성능 지표
        """
        try:
            # 데이터베이스 저장
            self._save_performance_metrics(metrics)
            
            # 메모리 캐시 업데이트
            if metrics.model_name not in self._performance_history:
                self._performance_history[metrics.model_name] = []
            
            self._performance_history[metrics.model_name].append(metrics)
            
            # 최근 30일 데이터만 유지
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            self._performance_history[metrics.model_name] = [
                m for m in self._performance_history[metrics.model_name]
                if m.measurement_date >= cutoff_date
            ]
            
            # 성능 저하 검사
            self._check_performance_degradation(metrics)
            
            self._logger.debug(f"모델 성능 기록: {metrics.model_name} - 정확도 {metrics.accuracy:.3f}")
            
        except Exception as e:
            self._logger.error(f"모델 성능 기록 중 오류: {e}", exc_info=True)
    
    def _save_performance_metrics(self, metrics: ModelPerformanceMetrics):
        """성능 지표 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO model_performance
                    (model_name, model_type, measurement_date, accuracy, precision,
                     recall, f1_score, prediction_accuracy, directional_accuracy,
                     profit_factor, sharpe_ratio, max_drawdown, prediction_variance,
                     feature_importance_stability, data_coverage, missing_data_ratio,
                     outlier_ratio)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metrics.model_name, metrics.model_type.value, metrics.measurement_date,
                    metrics.accuracy, metrics.precision, metrics.recall, metrics.f1_score,
                    metrics.prediction_accuracy, metrics.directional_accuracy,
                    metrics.profit_factor, metrics.sharpe_ratio, metrics.max_drawdown,
                    metrics.prediction_variance, metrics.feature_importance_stability,
                    metrics.data_coverage, metrics.missing_data_ratio, metrics.outlier_ratio
                ))
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"성능 지표 저장 중 오류: {e}", exc_info=True)
    
    def establish_baseline(self, model_name: str, model_type: ModelType):
        """모델 기준선 성능 설정
        
        Args:
            model_name: 모델명
            model_type: 모델 유형
        """
        try:
            # 최근 30일 성능 데이터로 기준선 계산
            recent_metrics = self._get_recent_performance(model_name, 30)
            
            if len(recent_metrics) < 5:  # 최소 5개 데이터 포인트 필요
                self._logger.warning(f"기준선 설정을 위한 데이터 부족: {model_name}")
                return
            
            # 기준선 지표 계산 (평균값 사용)
            baseline_metrics = ModelPerformanceMetrics(
                model_name=model_name,
                model_type=model_type,
                measurement_date=datetime.now().strftime('%Y-%m-%d'),
                accuracy=np.mean([m.accuracy for m in recent_metrics]),
                precision=np.mean([m.precision for m in recent_metrics]),
                recall=np.mean([m.recall for m in recent_metrics]),
                f1_score=np.mean([m.f1_score for m in recent_metrics]),
                prediction_accuracy=np.mean([m.prediction_accuracy for m in recent_metrics]),
                directional_accuracy=np.mean([m.directional_accuracy for m in recent_metrics]),
                profit_factor=np.mean([m.profit_factor for m in recent_metrics]),
                sharpe_ratio=np.mean([m.sharpe_ratio for m in recent_metrics]),
                max_drawdown=np.mean([m.max_drawdown for m in recent_metrics]),
                prediction_variance=np.mean([m.prediction_variance for m in recent_metrics]),
                feature_importance_stability=np.mean([m.feature_importance_stability for m in recent_metrics]),
                data_coverage=np.mean([m.data_coverage for m in recent_metrics]),
                missing_data_ratio=np.mean([m.missing_data_ratio for m in recent_metrics]),
                outlier_ratio=np.mean([m.outlier_ratio for m in recent_metrics])
            )
            
            # 기준선 저장
            self._baseline_performance[model_name] = baseline_metrics
            self._save_baseline(baseline_metrics)
            
            self._logger.info(f"모델 기준선 설정 완료: {model_name} (정확도 {baseline_metrics.accuracy:.3f})")
            
        except Exception as e:
            self._logger.error(f"기준선 설정 중 오류: {e}", exc_info=True)
    
    def _save_baseline(self, baseline_metrics: ModelPerformanceMetrics):
        """기준선 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO model_baselines
                    (model_name, model_type, baseline_metrics, established_date, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    baseline_metrics.model_name, baseline_metrics.model_type.value,
                    json.dumps(baseline_metrics.to_dict(), ensure_ascii=False),
                    baseline_metrics.measurement_date, datetime.now().strftime('%Y-%m-%d')
                ))
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"기준선 저장 중 오류: {e}", exc_info=True)
    
    def _check_performance_degradation(self, current_metrics: ModelPerformanceMetrics):
        """성능 저하 검사
        
        Args:
            current_metrics: 현재 성능 지표
        """
        try:
            model_name = current_metrics.model_name
            
            # 기준선 성능 확인
            if model_name not in self._baseline_performance:
                self._load_baseline(model_name)
            
            if model_name not in self._baseline_performance:
                self._logger.debug(f"기준선 없음: {model_name}")
                return
            
            baseline = self._baseline_performance[model_name]
            alerts = []
            
            # 정확도 저하 검사
            accuracy_drop = baseline.accuracy - current_metrics.accuracy
            if accuracy_drop > self._performance_thresholds['accuracy_drop_critical']:
                severity = 'critical'
            elif accuracy_drop > self._performance_thresholds['accuracy_drop_warning']:
                severity = 'high'
            else:
                severity = None
            
            if severity:
                alert = self._create_degradation_alert(
                    model_name, PerformanceDegradationType.ACCURACY_DROP,
                    severity, current_metrics.accuracy, baseline.accuracy,
                    accuracy_drop, current_metrics.measurement_date
                )
                alerts.append(alert)
            
            # 예측 분산 증가 검사
            if current_metrics.prediction_variance > self._performance_thresholds['prediction_variance_high']:
                alert = self._create_degradation_alert(
                    model_name, PerformanceDegradationType.PREDICTION_DRIFT,
                    'medium', current_metrics.prediction_variance,
                    baseline.prediction_variance,
                    current_metrics.prediction_variance - baseline.prediction_variance,
                    current_metrics.measurement_date
                )
                alerts.append(alert)
            
            # 샤프 비율 저하 검사
            if current_metrics.sharpe_ratio < self._performance_thresholds['sharpe_ratio_low']:
                alert = self._create_degradation_alert(
                    model_name, PerformanceDegradationType.OVERFITTING,
                    'medium', current_metrics.sharpe_ratio, baseline.sharpe_ratio,
                    baseline.sharpe_ratio - current_metrics.sharpe_ratio,
                    current_metrics.measurement_date
                )
                alerts.append(alert)
            
            # 최대 낙폭 증가 검사
            if current_metrics.max_drawdown > self._performance_thresholds['max_drawdown_high']:
                alert = self._create_degradation_alert(
                    model_name, PerformanceDegradationType.CONCEPT_DRIFT,
                    'high', current_metrics.max_drawdown, baseline.max_drawdown,
                    current_metrics.max_drawdown - baseline.max_drawdown,
                    current_metrics.measurement_date
                )
                alerts.append(alert)
            
            # 데이터 품질 문제 검사
            if (current_metrics.missing_data_ratio > 0.1 or  # 10% 이상 누락
                current_metrics.outlier_ratio > 0.05):       # 5% 이상 이상값
                alert = self._create_degradation_alert(
                    model_name, PerformanceDegradationType.DATA_QUALITY_ISSUE,
                    'medium', current_metrics.data_coverage, baseline.data_coverage,
                    baseline.data_coverage - current_metrics.data_coverage,
                    current_metrics.measurement_date
                )
                alerts.append(alert)
            
            # 알림 처리
            for alert in alerts:
                self._process_alert(alert)
                
        except Exception as e:
            self._logger.error(f"성능 저하 검사 중 오류: {e}", exc_info=True)
    
    def _create_degradation_alert(self, model_name: str, degradation_type: PerformanceDegradationType,
                                severity: str, current_perf: float, baseline_perf: float,
                                performance_drop: float, detection_date: str) -> PerformanceDegradationAlert:
        """성능 저하 알림 생성"""
        # 근본 원인 분석
        root_cause_analysis = self._analyze_root_cause(model_name, degradation_type)
        
        # 권장 조치
        recommended_actions = self._get_recommended_actions(degradation_type, severity)
        
        alert_id = f"{model_name}_{degradation_type.value}_{detection_date}_{int(time.time())}"
        
        return PerformanceDegradationAlert(
            alert_id=alert_id,
            model_name=model_name,
            degradation_type=degradation_type,
            severity=severity,
            current_performance=current_perf,
            baseline_performance=baseline_perf,
            performance_drop=performance_drop,
            detection_date=detection_date,
            affected_period="recent",
            root_cause_analysis=root_cause_analysis,
            recommended_actions=recommended_actions
        )
    
    def _analyze_root_cause(self, model_name: str, degradation_type: PerformanceDegradationType) -> Dict[str, Any]:
        """근본 원인 분석"""
        analysis = {
            'model_name': model_name,
            'degradation_type': degradation_type.value,
            'analysis_date': datetime.now().isoformat(),
            'potential_causes': [],
            'confidence': 0.0
        }
        
        try:
            # 최근 성능 트렌드 분석
            recent_metrics = self._get_recent_performance(model_name, 7)
            
            if len(recent_metrics) >= 3:
                accuracies = [m.accuracy for m in recent_metrics]
                trend_slope = np.polyfit(range(len(accuracies)), accuracies, 1)[0]
                
                if trend_slope < -0.01:  # 감소 추세
                    analysis['potential_causes'].append("성능 지속적 하락 추세")
                    analysis['confidence'] += 0.3
                
                # 변동성 증가 확인
                variance = np.var(accuracies)
                if variance > 0.01:
                    analysis['potential_causes'].append("성능 변동성 증가")
                    analysis['confidence'] += 0.2
            
            # 데이터 품질 이슈 확인
            if degradation_type == PerformanceDegradationType.DATA_QUALITY_ISSUE:
                analysis['potential_causes'].extend([
                    "입력 데이터 품질 저하",
                    "누락 데이터 증가",
                    "이상값 증가"
                ])
                analysis['confidence'] += 0.4
            
            # 개념 변화 확인
            elif degradation_type == PerformanceDegradationType.CONCEPT_DRIFT:
                analysis['potential_causes'].extend([
                    "시장 환경 변화",
                    "트레이딩 패턴 변화",
                    "모델 가정 불일치"
                ])
                analysis['confidence'] += 0.3
            
        except Exception as e:
            self._logger.error(f"근본 원인 분석 중 오류: {e}", exc_info=True)
            analysis['error'] = str(e)
        
        return analysis
    
    def _get_recommended_actions(self, degradation_type: PerformanceDegradationType, severity: str) -> List[str]:
        """권장 조치 반환"""
        actions = []
        
        if degradation_type == PerformanceDegradationType.ACCURACY_DROP:
            actions.extend([
                "모델 재학습 실행",
                "피처 엔지니어링 재검토",
                "하이퍼파라미터 튜닝"
            ])
        
        elif degradation_type == PerformanceDegradationType.DATA_QUALITY_ISSUE:
            actions.extend([
                "데이터 품질 검증 강화",
                "데이터 전처리 개선",
                "이상값 필터링 강화"
            ])
        
        elif degradation_type == PerformanceDegradationType.CONCEPT_DRIFT:
            actions.extend([
                "온라인 학습 활성화",
                "적응형 모델로 전환",
                "시장 환경 분석"
            ])
        
        elif degradation_type == PerformanceDegradationType.OVERFITTING:
            actions.extend([
                "정규화 강화",
                "교차 검증 재실행",
                "모델 복잡도 감소"
            ])
        
        if severity in ['high', 'critical']:
            actions.insert(0, "즉시 모델 사용 중단 검토")
            actions.append("수동 개입 필요")
        
        return actions
    
    def _process_alert(self, alert: PerformanceDegradationAlert):
        """알림 처리"""
        try:
            # 데이터베이스 저장
            self._save_alert(alert)
            
            # 콜백 호출
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    self._logger.error(f"알림 콜백 실행 중 오류: {e}", exc_info=True)
            
            self._logger.warning(
                f"모델 성능 저하 감지: {alert.model_name} - "
                f"{alert.degradation_type.value} (심각도: {alert.severity})"
            )
            
        except Exception as e:
            self._logger.error(f"알림 처리 중 오류: {e}", exc_info=True)
    
    def _save_alert(self, alert: PerformanceDegradationAlert):
        """알림 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO performance_alerts
                    (alert_id, model_name, degradation_type, severity,
                     current_performance, baseline_performance, performance_drop,
                     detection_date, affected_period, root_cause_analysis,
                     recommended_actions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert.alert_id, alert.model_name, alert.degradation_type.value,
                    alert.severity, alert.current_performance, alert.baseline_performance,
                    alert.performance_drop, alert.detection_date, alert.affected_period,
                    json.dumps(alert.root_cause_analysis, ensure_ascii=False),
                    json.dumps(alert.recommended_actions, ensure_ascii=False)
                ))
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"알림 저장 중 오류: {e}", exc_info=True)
    
    def _load_baseline(self, model_name: str):
        """기준선 로드"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    'SELECT baseline_metrics FROM model_baselines WHERE model_name = ?',
                    (model_name,)
                )
                row = cursor.fetchone()
                
                if row:
                    baseline_data = json.loads(row[0])
                    baseline_metrics = ModelPerformanceMetrics(
                        model_name=baseline_data['model_name'],
                        model_type=ModelType(baseline_data['model_type']),
                        measurement_date=baseline_data['measurement_date'],
                        accuracy=baseline_data['accuracy'],
                        precision=baseline_data['precision'],
                        recall=baseline_data['recall'],
                        f1_score=baseline_data['f1_score'],
                        prediction_accuracy=baseline_data['prediction_accuracy'],
                        directional_accuracy=baseline_data['directional_accuracy'],
                        profit_factor=baseline_data['profit_factor'],
                        sharpe_ratio=baseline_data['sharpe_ratio'],
                        max_drawdown=baseline_data['max_drawdown'],
                        prediction_variance=baseline_data['prediction_variance'],
                        feature_importance_stability=baseline_data['feature_importance_stability'],
                        data_coverage=baseline_data['data_coverage'],
                        missing_data_ratio=baseline_data['missing_data_ratio'],
                        outlier_ratio=baseline_data['outlier_ratio']
                    )
                    self._baseline_performance[model_name] = baseline_metrics
                    
        except Exception as e:
            self._logger.error(f"기준선 로드 중 오류: {e}", exc_info=True)
    
    def _get_recent_performance(self, model_name: str, days: int) -> List[ModelPerformanceMetrics]:
        """최근 성능 데이터 조회"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM model_performance
                    WHERE model_name = ? AND measurement_date >= ?
                    ORDER BY measurement_date DESC
                ''', (model_name, cutoff_date))
                
                metrics_list = []
                for row in cursor.fetchall():
                    metrics = ModelPerformanceMetrics(
                        model_name=row[1],
                        model_type=ModelType(row[2]),
                        measurement_date=row[3],
                        accuracy=row[4],
                        precision=row[5],
                        recall=row[6],
                        f1_score=row[7],
                        prediction_accuracy=row[8],
                        directional_accuracy=row[9],
                        profit_factor=row[10],
                        sharpe_ratio=row[11],
                        max_drawdown=row[12],
                        prediction_variance=row[13],
                        feature_importance_stability=row[14],
                        data_coverage=row[15],
                        missing_data_ratio=row[16],
                        outlier_ratio=row[17]
                    )
                    metrics_list.append(metrics)
                
                return metrics_list
                
        except Exception as e:
            self._logger.error(f"최근 성능 데이터 조회 중 오류: {e}", exc_info=True)
            return []
    
    def _run_daily_evaluation(self):
        """일일 성능 평가"""
        try:
            self._logger.info("일일 모델 성능 평가 시작")
            
            # 모든 모델에 대해 성능 평가 실행
            # 실제 구현에서는 각 모델의 evaluate() 메서드 호출
            
            self._logger.info("일일 모델 성능 평가 완료")
            
        except Exception as e:
            self._logger.error(f"일일 성능 평가 중 오류: {e}", exc_info=True)
    
    def _run_weekly_analysis(self):
        """주간 성능 분석"""
        try:
            self._logger.info("주간 모델 성능 분석 시작")
            
            # 모든 모델의 주간 트렌드 분석
            # 기준선 재조정 검토
            
            self._logger.info("주간 모델 성능 분석 완료")
            
        except Exception as e:
            self._logger.error(f"주간 성능 분석 중 오류: {e}", exc_info=True)
    
    def _run_monthly_review(self):
        """월간 성능 리뷰"""
        try:
            self._logger.info("월간 모델 성능 리뷰 시작")
            
            # 모든 모델의 기준선 재설정
            # 장기 트렌드 분석
            
            self._logger.info("월간 모델 성능 리뷰 완료")
            
        except Exception as e:
            self._logger.error(f"월간 성능 리뷰 중 오류: {e}", exc_info=True)
    
    def get_model_performance_summary(self, model_name: str, days: int = 30) -> Dict[str, Any]:
        """모델 성능 요약 조회"""
        try:
            recent_metrics = self._get_recent_performance(model_name, days)
            
            if not recent_metrics:
                return {}
            
            # 성능 통계
            accuracies = [m.accuracy for m in recent_metrics]
            sharpe_ratios = [m.sharpe_ratio for m in recent_metrics]
            
            # 트렌드 분석
            trend_slope = np.polyfit(range(len(accuracies)), accuracies, 1)[0] if len(accuracies) > 1 else 0
            
            return {
                'model_name': model_name,
                'period_days': days,
                'measurement_count': len(recent_metrics),
                'latest_performance': recent_metrics[0].to_dict() if recent_metrics else None,
                'average_accuracy': np.mean(accuracies),
                'accuracy_std': np.std(accuracies),
                'accuracy_trend': 'improving' if trend_slope > 0.001 else 'declining' if trend_slope < -0.001 else 'stable',
                'average_sharpe_ratio': np.mean(sharpe_ratios),
                'best_performance_date': max(recent_metrics, key=lambda x: x.accuracy).measurement_date,
                'worst_performance_date': min(recent_metrics, key=lambda x: x.accuracy).measurement_date
            }
            
        except Exception as e:
            self._logger.error(f"모델 성능 요약 조회 중 오류: {e}", exc_info=True)
            return {}
    
    def start_monitoring(self):
        """성능 모니터링 시작"""
        if self._running:
            self._logger.warning("모니터링이 이미 실행 중입니다.")
            return
        
        self._running = True
        
        def scheduler_loop():
            while self._running:
                schedule.run_pending()
                time.sleep(60)
        
        self._monitor_thread = threading.Thread(target=scheduler_loop, daemon=True)
        self._monitor_thread.start()
        
        self._logger.info("모델 성능 모니터링 시작")
    
    def stop_monitoring(self):
        """성능 모니터링 중지"""
        if not self._running:
            return
        
        self._running = False
        schedule.clear()
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        self._logger.info("모델 성능 모니터링 중지")

# 글로벌 인스턴스
_model_performance_monitor: Optional[ModelPerformanceMonitor] = None

def get_model_performance_monitor() -> ModelPerformanceMonitor:
    """모델 성능 모니터 인스턴스 반환 (싱글톤)"""
    global _model_performance_monitor
    if _model_performance_monitor is None:
        _model_performance_monitor = ModelPerformanceMonitor()
    return _model_performance_monitor 