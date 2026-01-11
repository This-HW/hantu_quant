"""
백테스트 결과 vs 실제 성과 추적 시스템

백테스트 예측과 실제 거래 결과를 비교하여 모델의 정확성을 평가
"""

import numpy as np
import pandas as pd
import sqlite3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import warnings

from core.utils.log_utils import get_logger

logger = get_logger(__name__)

class TrackingStatus(Enum):
    """추적 상태"""
    PREDICTED = "predicted"      # 백테스트 예측 완료
    EXECUTED = "executed"        # 실제 거래 실행
    COMPLETED = "completed"      # 결과 확정
    CANCELLED = "cancelled"      # 거래 취소
    ERROR = "error"             # 오류 발생

class PerformanceMetric(Enum):
    """성과 지표"""
    RETURN = "return"           # 수익률
    VOLATILITY = "volatility"   # 변동성
    SHARPE_RATIO = "sharpe_ratio"   # 샤프 비율
    MAX_DRAWDOWN = "max_drawdown"   # 최대 낙폭
    WIN_RATE = "win_rate"       # 승률

@dataclass
class BacktestPrediction:
    """백테스트 예측"""
    prediction_id: str
    strategy_name: str
    prediction_date: str
    
    # 예측 정보
    target_stocks: List[str]
    predicted_returns: Dict[str, float]  # 종목별 예상 수익률
    predicted_weights: Dict[str, float]  # 종목별 비중
    
    # 예상 성과
    expected_return: float
    expected_volatility: float
    expected_sharpe_ratio: float
    expected_max_drawdown: float
    
    # 예측 근거
    model_confidence: float
    feature_importance: Dict[str, float]
    market_conditions: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

@dataclass
class ActualPerformance:
    """실제 성과"""
    performance_id: str
    prediction_id: str
    execution_date: str
    completion_date: str
    
    # 실행 정보
    executed_stocks: List[str]
    actual_returns: Dict[str, float]    # 종목별 실제 수익률
    actual_weights: Dict[str, float]    # 종목별 실제 비중
    
    # 실제 성과
    actual_return: float
    actual_volatility: float
    actual_sharpe_ratio: float
    actual_max_drawdown: float
    
    # 실행 세부사항
    execution_costs: float
    slippage: float
    market_impact: float
    
    # 상태
    status: TrackingStatus
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['status'] = self.status.value
        return result

@dataclass
class PerformanceComparison:
    """성과 비교"""
    comparison_id: str
    prediction_id: str
    comparison_date: str
    
    # 예측 vs 실제 비교
    return_difference: float        # 수익률 차이
    volatility_difference: float    # 변동성 차이
    sharpe_difference: float        # 샤프 비율 차이
    
    # 정확도 지표
    prediction_accuracy: float      # 예측 정확도 (0-1)
    direction_accuracy: float       # 방향 정확도 (상승/하락)
    magnitude_accuracy: float       # 크기 정확도
    
    # 오차 분석
    mean_absolute_error: float      # 평균 절대 오차
    root_mean_square_error: float   # 평균 제곱근 오차
    correlation: float              # 상관계수
    
    # 분석 결과
    analysis_summary: Dict[str, Any]
    improvement_suggestions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

class PerformanceTracker:
    """백테스트 vs 실제 성과 추적기"""

    def __init__(self, db_path: str = "data/performance_tracking.db",
                 use_unified_db: bool = True):
        """초기화

        Args:
            db_path: 성과 추적 데이터베이스 경로 (SQLite 폴백용)
            use_unified_db: 통합 DB 사용 여부 (기본값: True)
        """
        self._logger = logger
        self._db_path = db_path
        self._unified_db_available = False

        # 통합 DB 초기화 시도
        if use_unified_db:
            try:
                from core.database.unified_db import get_db, ensure_tables_exist
                ensure_tables_exist()
                self._unified_db_available = True
                self._logger.info("PerformanceTracker: 통합 DB 사용")
            except Exception as e:
                self._logger.warning(f"통합 DB 초기화 실패, SQLite 폴백 사용: {e}")
                self._unified_db_available = False

        # 추적 설정
        self._tracking_config = {
            'tracking_period_days': 30,     # 추적 기간
            'min_confidence_threshold': 0.6, # 최소 신뢰도
            'comparison_delay_hours': 24,   # 비교 지연 시간
            'auto_analysis': True,          # 자동 분석 여부
        }

        # 캐시된 예측
        self._active_predictions: Dict[str, BacktestPrediction] = {}

        # 성과 메트릭 계산기
        self._metric_calculators = {
            PerformanceMetric.RETURN: self._calculate_return,
            PerformanceMetric.VOLATILITY: self._calculate_volatility,
            PerformanceMetric.SHARPE_RATIO: self._calculate_sharpe_ratio,
            PerformanceMetric.MAX_DRAWDOWN: self._calculate_max_drawdown,
            PerformanceMetric.WIN_RATE: self._calculate_win_rate,
        }

        # SQLite 데이터베이스 초기화 (폴백용)
        if not self._unified_db_available:
            self._init_database()

        self._logger.info("PerformanceTracker 초기화 완료")
    
    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self._db_path) as conn:
                # 백테스트 예측 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS backtest_predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        prediction_id TEXT NOT NULL UNIQUE,
                        strategy_name TEXT NOT NULL,
                        prediction_date TEXT NOT NULL,
                        target_stocks TEXT NOT NULL,  -- JSON
                        predicted_returns TEXT NOT NULL,  -- JSON
                        predicted_weights TEXT NOT NULL,  -- JSON
                        expected_return REAL,
                        expected_volatility REAL,
                        expected_sharpe_ratio REAL,
                        expected_max_drawdown REAL,
                        model_confidence REAL,
                        feature_importance TEXT,  -- JSON
                        market_conditions TEXT,   -- JSON
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 실제 성과 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS actual_performance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        performance_id TEXT NOT NULL UNIQUE,
                        prediction_id TEXT NOT NULL,
                        execution_date TEXT NOT NULL,
                        completion_date TEXT NOT NULL,
                        executed_stocks TEXT NOT NULL,  -- JSON
                        actual_returns TEXT NOT NULL,   -- JSON
                        actual_weights TEXT NOT NULL,   -- JSON
                        actual_return REAL,
                        actual_volatility REAL,
                        actual_sharpe_ratio REAL,
                        actual_max_drawdown REAL,
                        execution_costs REAL,
                        slippage REAL,
                        market_impact REAL,
                        status TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (prediction_id) REFERENCES backtest_predictions (prediction_id)
                    )
                ''')
                
                # 성과 비교 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS performance_comparisons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        comparison_id TEXT NOT NULL UNIQUE,
                        prediction_id TEXT NOT NULL,
                        comparison_date TEXT NOT NULL,
                        return_difference REAL,
                        volatility_difference REAL,
                        sharpe_difference REAL,
                        prediction_accuracy REAL,
                        direction_accuracy REAL,
                        magnitude_accuracy REAL,
                        mean_absolute_error REAL,
                        root_mean_square_error REAL,
                        correlation REAL,
                        analysis_summary TEXT,  -- JSON
                        improvement_suggestions TEXT,  -- JSON
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (prediction_id) REFERENCES backtest_predictions (prediction_id)
                    )
                ''')
                
                # 일별 추적 데이터 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS daily_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        prediction_id TEXT NOT NULL,
                        tracking_date TEXT NOT NULL,
                        predicted_value REAL,
                        actual_value REAL,
                        difference REAL,
                        error_percentage REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(prediction_id, tracking_date),
                        FOREIGN KEY (prediction_id) REFERENCES backtest_predictions (prediction_id)
                    )
                ''')
                
                conn.commit()
                self._logger.info("성과 추적 데이터베이스 초기화 완료")
                
        except Exception as e:
            self._logger.error(f"데이터베이스 초기화 중 오류: {e}", exc_info=True)
    
    def record_backtest_prediction(self, prediction: BacktestPrediction) -> bool:
        """백테스트 예측 기록

        Args:
            prediction: 백테스트 예측 데이터

        Returns:
            기록 성공 여부
        """
        # 신뢰도 확인
        if prediction.model_confidence < self._tracking_config['min_confidence_threshold']:
            self._logger.debug(f"신뢰도 부족으로 예측 기록 스킵: {prediction.model_confidence}")
            return False

        if self._unified_db_available:
            return self._record_backtest_prediction_unified(prediction)
        return self._record_backtest_prediction_sqlite(prediction)

    def _record_backtest_prediction_unified(self, prediction: BacktestPrediction) -> bool:
        """통합 DB에 백테스트 예측 기록"""
        try:
            from core.database.unified_db import get_session
            from core.database.models import BacktestPrediction as BacktestPredictionModel
            from datetime import datetime

            with get_session() as session:
                db_prediction = BacktestPredictionModel(
                    prediction_id=prediction.prediction_id,
                    strategy_name=prediction.strategy_name,
                    prediction_date=datetime.strptime(prediction.prediction_date, '%Y-%m-%d').date(),
                    target_stocks=json.dumps(prediction.target_stocks),
                    predicted_returns=json.dumps(prediction.predicted_returns),
                    predicted_weights=json.dumps(prediction.predicted_weights),
                    expected_return=prediction.expected_return,
                    expected_volatility=prediction.expected_volatility,
                    expected_sharpe_ratio=prediction.expected_sharpe_ratio,
                    expected_max_drawdown=prediction.expected_max_drawdown,
                    model_confidence=prediction.model_confidence,
                    feature_importance=json.dumps(prediction.feature_importance),
                    market_conditions=json.dumps(prediction.market_conditions),
                )
                session.merge(db_prediction)

            # 메모리 캐시
            self._active_predictions[prediction.prediction_id] = prediction
            self._logger.info(f"백테스트 예측 기록 (통합 DB): {prediction.prediction_id}")
            return True

        except Exception as e:
            self._logger.error(f"백테스트 예측 기록 중 오류 (통합 DB): {e}", exc_info=True)
            return False

    def _record_backtest_prediction_sqlite(self, prediction: BacktestPrediction) -> bool:
        """SQLite에 백테스트 예측 기록"""
        try:
            # 데이터베이스 저장
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO backtest_predictions
                    (prediction_id, strategy_name, prediction_date, target_stocks,
                     predicted_returns, predicted_weights, expected_return,
                     expected_volatility, expected_sharpe_ratio, expected_max_drawdown,
                     model_confidence, feature_importance, market_conditions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    prediction.prediction_id, prediction.strategy_name,
                    prediction.prediction_date,
                    json.dumps(prediction.target_stocks),
                    json.dumps(prediction.predicted_returns),
                    json.dumps(prediction.predicted_weights),
                    prediction.expected_return, prediction.expected_volatility,
                    prediction.expected_sharpe_ratio, prediction.expected_max_drawdown,
                    prediction.model_confidence,
                    json.dumps(prediction.feature_importance),
                    json.dumps(prediction.market_conditions)
                ))
                conn.commit()

            # 메모리 캐시
            self._active_predictions[prediction.prediction_id] = prediction

            self._logger.info(f"백테스트 예측 기록: {prediction.prediction_id}")
            return True

        except Exception as e:
            self._logger.error(f"백테스트 예측 기록 중 오류: {e}", exc_info=True)
            return False
    
    def record_actual_performance(self, performance: ActualPerformance) -> bool:
        """실제 성과 기록

        Args:
            performance: 실제 성과 데이터

        Returns:
            기록 성공 여부
        """
        if self._unified_db_available:
            result = self._record_actual_performance_unified(performance)
        else:
            result = self._record_actual_performance_sqlite(performance)

        # 자동 비교 분석
        if result and self._tracking_config['auto_analysis']:
            self._schedule_comparison_analysis(performance.prediction_id)

        return result

    def _record_actual_performance_unified(self, performance: ActualPerformance) -> bool:
        """통합 DB에 실제 성과 기록"""
        try:
            from core.database.unified_db import get_session
            from core.database.models import ActualPerformance as ActualPerformanceModel
            from datetime import datetime

            with get_session() as session:
                db_performance = ActualPerformanceModel(
                    performance_id=performance.performance_id,
                    prediction_id=performance.prediction_id,
                    execution_date=datetime.strptime(performance.execution_date, '%Y-%m-%d').date(),
                    completion_date=datetime.strptime(performance.completion_date, '%Y-%m-%d').date(),
                    executed_stocks=json.dumps(performance.executed_stocks),
                    actual_returns=json.dumps(performance.actual_returns),
                    actual_weights=json.dumps(performance.actual_weights),
                    actual_return=performance.actual_return,
                    actual_volatility=performance.actual_volatility,
                    actual_sharpe_ratio=performance.actual_sharpe_ratio,
                    actual_max_drawdown=performance.actual_max_drawdown,
                    execution_costs=performance.execution_costs,
                    slippage=performance.slippage,
                    market_impact=performance.market_impact,
                    status=performance.status.value,
                )
                session.merge(db_performance)

            self._logger.info(f"실제 성과 기록 (통합 DB): {performance.performance_id}")
            return True

        except Exception as e:
            self._logger.error(f"실제 성과 기록 중 오류 (통합 DB): {e}", exc_info=True)
            return False

    def _record_actual_performance_sqlite(self, performance: ActualPerformance) -> bool:
        """SQLite에 실제 성과 기록"""
        try:
            # 데이터베이스 저장
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO actual_performance
                    (performance_id, prediction_id, execution_date, completion_date,
                     executed_stocks, actual_returns, actual_weights,
                     actual_return, actual_volatility, actual_sharpe_ratio,
                     actual_max_drawdown, execution_costs, slippage,
                     market_impact, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    performance.performance_id, performance.prediction_id,
                    performance.execution_date, performance.completion_date,
                    json.dumps(performance.executed_stocks),
                    json.dumps(performance.actual_returns),
                    json.dumps(performance.actual_weights),
                    performance.actual_return, performance.actual_volatility,
                    performance.actual_sharpe_ratio, performance.actual_max_drawdown,
                    performance.execution_costs, performance.slippage,
                    performance.market_impact, performance.status.value
                ))
                conn.commit()

            self._logger.info(f"실제 성과 기록: {performance.performance_id}")
            return True

        except Exception as e:
            self._logger.error(f"실제 성과 기록 중 오류: {e}", exc_info=True)
            return False
    
    def _schedule_comparison_analysis(self, prediction_id: str):
        """비교 분석 스케줄링"""
        try:
            # 지연 시간 후 비교 분석 실행
            import threading
            
            def delayed_analysis():
                import time
                time.sleep(self._tracking_config['comparison_delay_hours'] * 3600)
                self.perform_comparison_analysis(prediction_id)
            
            thread = threading.Thread(target=delayed_analysis, daemon=True)
            thread.start()
            
        except Exception as e:
            self._logger.error(f"비교 분석 스케줄링 중 오류: {e}", exc_info=True)
    
    def perform_comparison_analysis(self, prediction_id: str) -> Optional[PerformanceComparison]:
        """예측 vs 실제 비교 분석
        
        Args:
            prediction_id: 예측 ID
            
        Returns:
            비교 분석 결과
        """
        try:
            # 예측 및 실제 데이터 조회
            prediction_data = self._get_prediction_data(prediction_id)
            performance_data = self._get_performance_data(prediction_id)
            
            if not prediction_data or not performance_data:
                self._logger.warning(f"비교 분석을 위한 데이터 부족: {prediction_id}")
                return None
            
            # 비교 분석 실행
            comparison = self._calculate_comparison_metrics(prediction_data, performance_data)
            
            # 분석 결과 저장
            self._save_comparison_result(comparison)
            
            self._logger.info(f"비교 분석 완료: {prediction_id}")
            return comparison
            
        except Exception as e:
            self._logger.error(f"비교 분석 중 오류: {e}", exc_info=True)
            return None
    
    def _get_prediction_data(self, prediction_id: str) -> Optional[Dict]:
        """예측 데이터 조회"""
        if self._unified_db_available:
            return self._get_prediction_data_unified(prediction_id)
        return self._get_prediction_data_sqlite(prediction_id)

    def _get_prediction_data_unified(self, prediction_id: str) -> Optional[Dict]:
        """통합 DB에서 예측 데이터 조회"""
        try:
            from core.database.unified_db import get_session
            from core.database.models import BacktestPrediction as BacktestPredictionModel

            with get_session() as session:
                row = session.query(BacktestPredictionModel).filter_by(
                    prediction_id=prediction_id
                ).first()

                if row:
                    return {
                        'prediction_id': row.prediction_id,
                        'strategy_name': row.strategy_name,
                        'prediction_date': row.prediction_date.isoformat() if row.prediction_date else None,
                        'target_stocks': json.loads(row.target_stocks) if row.target_stocks else [],
                        'predicted_returns': json.loads(row.predicted_returns) if row.predicted_returns else {},
                        'predicted_weights': json.loads(row.predicted_weights) if row.predicted_weights else {},
                        'expected_return': row.expected_return,
                        'expected_volatility': row.expected_volatility,
                        'expected_sharpe_ratio': row.expected_sharpe_ratio,
                        'expected_max_drawdown': row.expected_max_drawdown,
                        'model_confidence': row.model_confidence,
                        'feature_importance': json.loads(row.feature_importance) if row.feature_importance else {},
                        'market_conditions': json.loads(row.market_conditions) if row.market_conditions else {}
                    }
                return None

        except Exception as e:
            self._logger.error(f"예측 데이터 조회 중 오류 (통합 DB): {e}", exc_info=True)
            return None

    def _get_prediction_data_sqlite(self, prediction_id: str) -> Optional[Dict]:
        """SQLite에서 예측 데이터 조회"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    'SELECT * FROM backtest_predictions WHERE prediction_id = ?',
                    (prediction_id,)
                )
                row = cursor.fetchone()

                if row:
                    return {
                        'prediction_id': row[1],
                        'strategy_name': row[2],
                        'prediction_date': row[3],
                        'target_stocks': json.loads(row[4]),
                        'predicted_returns': json.loads(row[5]),
                        'predicted_weights': json.loads(row[6]),
                        'expected_return': row[7],
                        'expected_volatility': row[8],
                        'expected_sharpe_ratio': row[9],
                        'expected_max_drawdown': row[10],
                        'model_confidence': row[11],
                        'feature_importance': json.loads(row[12]) if row[12] else {},
                        'market_conditions': json.loads(row[13]) if row[13] else {}
                    }
                return None

        except Exception as e:
            self._logger.error(f"예측 데이터 조회 중 오류: {e}", exc_info=True)
            return None
    
    def _get_performance_data(self, prediction_id: str) -> Optional[Dict]:
        """실제 성과 데이터 조회"""
        if self._unified_db_available:
            return self._get_performance_data_unified(prediction_id)
        return self._get_performance_data_sqlite(prediction_id)

    def _get_performance_data_unified(self, prediction_id: str) -> Optional[Dict]:
        """통합 DB에서 실제 성과 데이터 조회"""
        try:
            from core.database.unified_db import get_session
            from core.database.models import ActualPerformance as ActualPerformanceModel

            with get_session() as session:
                row = session.query(ActualPerformanceModel).filter_by(
                    prediction_id=prediction_id
                ).first()

                if row:
                    return {
                        'performance_id': row.performance_id,
                        'prediction_id': row.prediction_id,
                        'execution_date': row.execution_date.isoformat() if row.execution_date else None,
                        'completion_date': row.completion_date.isoformat() if row.completion_date else None,
                        'executed_stocks': json.loads(row.executed_stocks) if row.executed_stocks else [],
                        'actual_returns': json.loads(row.actual_returns) if row.actual_returns else {},
                        'actual_weights': json.loads(row.actual_weights) if row.actual_weights else {},
                        'actual_return': row.actual_return,
                        'actual_volatility': row.actual_volatility,
                        'actual_sharpe_ratio': row.actual_sharpe_ratio,
                        'actual_max_drawdown': row.actual_max_drawdown,
                        'execution_costs': row.execution_costs,
                        'slippage': row.slippage,
                        'market_impact': row.market_impact,
                        'status': row.status
                    }
                return None

        except Exception as e:
            self._logger.error(f"실제 성과 데이터 조회 중 오류 (통합 DB): {e}", exc_info=True)
            return None

    def _get_performance_data_sqlite(self, prediction_id: str) -> Optional[Dict]:
        """SQLite에서 실제 성과 데이터 조회"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    'SELECT * FROM actual_performance WHERE prediction_id = ?',
                    (prediction_id,)
                )
                row = cursor.fetchone()

                if row:
                    return {
                        'performance_id': row[1],
                        'prediction_id': row[2],
                        'execution_date': row[3],
                        'completion_date': row[4],
                        'executed_stocks': json.loads(row[5]),
                        'actual_returns': json.loads(row[6]),
                        'actual_weights': json.loads(row[7]),
                        'actual_return': row[8],
                        'actual_volatility': row[9],
                        'actual_sharpe_ratio': row[10],
                        'actual_max_drawdown': row[11],
                        'execution_costs': row[12],
                        'slippage': row[13],
                        'market_impact': row[14],
                        'status': row[15]
                    }
                return None

        except Exception as e:
            self._logger.error(f"실제 성과 데이터 조회 중 오류: {e}", exc_info=True)
            return None
    
    def _calculate_comparison_metrics(self, prediction_data: Dict, 
                                   performance_data: Dict) -> PerformanceComparison:
        """비교 지표 계산"""
        try:
            # 기본 차이값 계산
            return_diff = performance_data['actual_return'] - prediction_data['expected_return']
            volatility_diff = performance_data['actual_volatility'] - prediction_data['expected_volatility']
            sharpe_diff = performance_data['actual_sharpe_ratio'] - prediction_data['expected_sharpe_ratio']
            
            # 정확도 계산
            prediction_accuracy = self._calculate_prediction_accuracy(
                prediction_data['expected_return'], 
                performance_data['actual_return']
            )
            
            direction_accuracy = self._calculate_direction_accuracy(
                prediction_data['predicted_returns'],
                performance_data['actual_returns']
            )
            
            magnitude_accuracy = self._calculate_magnitude_accuracy(
                prediction_data['predicted_returns'],
                performance_data['actual_returns']
            )
            
            # 오차 분석
            mae, rmse, correlation = self._calculate_error_metrics(
                prediction_data['predicted_returns'],
                performance_data['actual_returns']
            )
            
            # 분석 요약 생성
            analysis_summary = self._generate_analysis_summary(
                prediction_data, performance_data, {
                    'return_diff': return_diff,
                    'prediction_accuracy': prediction_accuracy,
                    'direction_accuracy': direction_accuracy
                }
            )
            
            # 개선 제안
            improvement_suggestions = self._generate_improvement_suggestions(
                prediction_accuracy, direction_accuracy, magnitude_accuracy
            )
            
            comparison_id = f"comp_{prediction_data['prediction_id']}_{int(time.time())}"
            
            return PerformanceComparison(
                comparison_id=comparison_id,
                prediction_id=prediction_data['prediction_id'],
                comparison_date=datetime.now().strftime('%Y-%m-%d'),
                return_difference=return_diff,
                volatility_difference=volatility_diff,
                sharpe_difference=sharpe_diff,
                prediction_accuracy=prediction_accuracy,
                direction_accuracy=direction_accuracy,
                magnitude_accuracy=magnitude_accuracy,
                mean_absolute_error=mae,
                root_mean_square_error=rmse,
                correlation=correlation,
                analysis_summary=analysis_summary,
                improvement_suggestions=improvement_suggestions
            )
            
        except Exception as e:
            self._logger.error(f"비교 지표 계산 중 오류: {e}", exc_info=True)
            raise
    
    def _calculate_prediction_accuracy(self, predicted: float, actual: float) -> float:
        """예측 정확도 계산 (0-1 점수)"""
        if predicted == 0:
            return 1.0 if actual == 0 else 0.0
        
        error_rate = abs(predicted - actual) / abs(predicted)
        return max(0.0, 1.0 - error_rate)
    
    def _calculate_direction_accuracy(self, predicted_returns: Dict[str, float],
                                    actual_returns: Dict[str, float]) -> float:
        """방향 정확도 계산"""
        correct_directions = 0
        total_stocks = 0
        
        for stock in predicted_returns:
            if stock in actual_returns:
                predicted_sign = 1 if predicted_returns[stock] > 0 else -1
                actual_sign = 1 if actual_returns[stock] > 0 else -1
                
                if predicted_sign == actual_sign:
                    correct_directions += 1
                total_stocks += 1
        
        return correct_directions / total_stocks if total_stocks > 0 else 0.0
    
    def _calculate_magnitude_accuracy(self, predicted_returns: Dict[str, float],
                                    actual_returns: Dict[str, float]) -> float:
        """크기 정확도 계산"""
        accuracies = []
        
        for stock in predicted_returns:
            if stock in actual_returns:
                accuracy = self._calculate_prediction_accuracy(
                    predicted_returns[stock], actual_returns[stock]
                )
                accuracies.append(accuracy)
        
        return float(np.mean(accuracies)) if accuracies else 0.0
    
    def _calculate_error_metrics(self, predicted_returns: Dict[str, float],
                               actual_returns: Dict[str, float]) -> Tuple[float, float, float]:
        """오차 지표 계산"""
        predicted_values = []
        actual_values = []
        
        for stock in predicted_returns:
            if stock in actual_returns:
                predicted_values.append(predicted_returns[stock])
                actual_values.append(actual_returns[stock])
        
        if not predicted_values:
            return 0.0, 0.0, 0.0
        
        predicted_array = np.array(predicted_values)
        actual_array = np.array(actual_values)
        
        # MAE (Mean Absolute Error)
        mae = np.mean(np.abs(predicted_array - actual_array))
        
        # RMSE (Root Mean Square Error)
        rmse = np.sqrt(np.mean((predicted_array - actual_array) ** 2))
        
        # Correlation
        correlation = float(np.corrcoef(predicted_array, actual_array)[0, 1]) if len(predicted_values) > 1 else 0.0
        
        return float(mae), float(rmse), correlation
    
    def _generate_analysis_summary(self, prediction_data: Dict, 
                                 performance_data: Dict, metrics: Dict) -> Dict[str, Any]:
        """분석 요약 생성"""
        return {
            'prediction_date': prediction_data['prediction_date'],
            'strategy_name': prediction_data['strategy_name'],
            'model_confidence': prediction_data['model_confidence'],
            'return_difference_pct': metrics['return_diff'],
            'prediction_accuracy_pct': metrics['prediction_accuracy'] * 100,
            'direction_accuracy_pct': metrics['direction_accuracy'] * 100,
            'execution_costs_pct': performance_data['execution_costs'],
            'slippage_pct': performance_data['slippage'],
            'overall_rating': self._calculate_overall_rating(metrics),
            'key_insights': self._extract_key_insights(prediction_data, performance_data, metrics)
        }
    
    def _calculate_overall_rating(self, metrics: Dict) -> str:
        """전체 평가 등급 계산"""
        accuracy = metrics['prediction_accuracy']
        direction = metrics['direction_accuracy']
        
        combined_score = (accuracy + direction) / 2
        
        if combined_score >= 0.8:
            return "Excellent"
        elif combined_score >= 0.6:
            return "Good"
        elif combined_score >= 0.4:
            return "Fair"
        else:
            return "Poor"
    
    def _extract_key_insights(self, prediction_data: Dict, 
                            performance_data: Dict, metrics: Dict) -> List[str]:
        """주요 인사이트 추출"""
        insights = []
        
        if metrics['prediction_accuracy'] > 0.8:
            insights.append("예측 정확도가 매우 높습니다")
        elif metrics['prediction_accuracy'] < 0.4:
            insights.append("예측 정확도 개선이 필요합니다")
        
        if metrics['direction_accuracy'] > 0.7:
            insights.append("방향 예측이 우수합니다")
        elif metrics['direction_accuracy'] < 0.5:
            insights.append("방향 예측 정확도가 낮습니다")
        
        if performance_data['execution_costs'] > 0.5:
            insights.append("실행 비용이 높습니다")
        
        if performance_data['slippage'] > 0.2:
            insights.append("슬리피지가 큽니다")
        
        return insights
    
    def _generate_improvement_suggestions(self, prediction_accuracy: float,
                                        direction_accuracy: float,
                                        magnitude_accuracy: float) -> List[str]:
        """개선 제안 생성"""
        suggestions = []
        
        if prediction_accuracy < 0.6:
            suggestions.append("모델 재학습 및 피처 개선 필요")
            suggestions.append("백테스트 기간 및 조건 재검토")
        
        if direction_accuracy < 0.6:
            suggestions.append("방향성 예측 모델 개선")
            suggestions.append("시장 환경 변수 추가 고려")
        
        if magnitude_accuracy < 0.5:
            suggestions.append("수익률 크기 예측 정확도 향상")
            suggestions.append("리스크 모델 개선")
        
        return suggestions
    
    def _save_comparison_result(self, comparison: PerformanceComparison):
        """비교 결과 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO performance_comparisons
                    (comparison_id, prediction_id, comparison_date,
                     return_difference, volatility_difference, sharpe_difference,
                     prediction_accuracy, direction_accuracy, magnitude_accuracy,
                     mean_absolute_error, root_mean_square_error, correlation,
                     analysis_summary, improvement_suggestions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    comparison.comparison_id, comparison.prediction_id,
                    comparison.comparison_date, comparison.return_difference,
                    comparison.volatility_difference, comparison.sharpe_difference,
                    comparison.prediction_accuracy, comparison.direction_accuracy,
                    comparison.magnitude_accuracy, comparison.mean_absolute_error,
                    comparison.root_mean_square_error, comparison.correlation,
                    json.dumps(comparison.analysis_summary, ensure_ascii=False),
                    json.dumps(comparison.improvement_suggestions, ensure_ascii=False)
                ))
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"비교 결과 저장 중 오류: {e}", exc_info=True)
    
    # 성과 메트릭 계산 메서드들
    def _calculate_return(self, data: List[float]) -> float:
        """수익률 계산"""
        return sum(data)
    
    def _calculate_volatility(self, data: List[float]) -> float:
        """변동성 계산"""
        return float(np.std(data)) if data else 0.0
    
    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.03) -> float:
        """샤프 비율 계산"""
        if not returns or np.std(returns) == 0:
            return 0.0
        
        excess_returns = np.array(returns) - risk_free_rate / 252
        return float(np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252))
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """최대 낙폭 계산"""
        if not returns:
            return 0.0
        
        cumulative = np.cumprod(1 + np.array(returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return float(abs(np.min(drawdown)))
    
    def _calculate_win_rate(self, returns: List[float]) -> float:
        """승률 계산"""
        if not returns:
            return 0.0
        
        winning_trades = sum(1 for r in returns if r > 0)
        return winning_trades / len(returns)
    
    def get_tracking_summary(self, days: int = 30) -> Dict[str, Any]:
        """추적 요약 정보 조회"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            with sqlite3.connect(self._db_path) as conn:
                # 기본 통계
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM backtest_predictions 
                    WHERE prediction_date >= ?
                ''', (cutoff_date,))
                total_predictions = cursor.fetchone()[0]
                
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM actual_performance ap
                    JOIN backtest_predictions bp ON ap.prediction_id = bp.prediction_id
                    WHERE bp.prediction_date >= ?
                ''', (cutoff_date,))
                completed_tracking = cursor.fetchone()[0]
                
                cursor = conn.execute('''
                    SELECT AVG(prediction_accuracy), AVG(direction_accuracy)
                    FROM performance_comparisons pc
                    JOIN backtest_predictions bp ON pc.prediction_id = bp.prediction_id
                    WHERE bp.prediction_date >= ?
                ''', (cutoff_date,))
                accuracy_stats = cursor.fetchone()
                
                return {
                    'period_days': days,
                    'total_predictions': total_predictions,
                    'completed_tracking': completed_tracking,
                    'tracking_completion_rate': (completed_tracking / total_predictions * 100) if total_predictions > 0 else 0,
                    'avg_prediction_accuracy': accuracy_stats[0] or 0.0,
                    'avg_direction_accuracy': accuracy_stats[1] or 0.0,
                }
                
        except Exception as e:
            self._logger.error(f"추적 요약 조회 중 오류: {e}", exc_info=True)
            return {}

# 글로벌 인스턴스
_performance_tracker: Optional[PerformanceTracker] = None

def get_performance_tracker() -> PerformanceTracker:
    """성과 추적기 인스턴스 반환 (싱글톤)"""
    global _performance_tracker
    if _performance_tracker is None:
        _performance_tracker = PerformanceTracker()
    return _performance_tracker 