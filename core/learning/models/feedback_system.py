"""
Phase 4: AI 학습 시스템 - 피드백 시스템

예측 결과와 실제 성과를 비교하여 모델을 지속적으로 개선
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import json
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path

from core.utils.log_utils import get_logger
from .pattern_learner import PatternLearner, PatternFeatures
from .prediction_engine import PredictionEngine, PredictionResult

logger = get_logger(__name__)

@dataclass
class FeedbackData:
    """피드백 데이터 클래스"""
    prediction_id: str
    stock_code: str
    prediction_date: str
    
    # 예측 정보
    predicted_probability: float
    predicted_class: int
    model_name: str
    
    # 실제 결과
    actual_return_7d: Optional[float] = None
    actual_class: Optional[int] = None  # 0: 실패, 1: 성공
    
    # 피드백 메트릭
    prediction_error: Optional[float] = None
    absolute_error: Optional[float] = None
    
    # 업데이트 정보
    feedback_date: Optional[str] = None
    is_processed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

class FeedbackSystem:
    """피드백 시스템"""
    
    def __init__(self, db_path: str = "data/feedback.db", 
                 performance_db_path: str = "data/performance.db"):
        """초기화
        
        Args:
            db_path: 피드백 데이터베이스 경로
            performance_db_path: 성과 데이터베이스 경로
        """
        self._logger = logger
        self._db_path = db_path
        self._performance_db_path = performance_db_path
        
        # 데이터베이스 초기화
        self._init_database()
        
        # 성공 기준 설정
        self._success_threshold = 0.05  # 5% 이상 수익 시 성공
        
        # 재학습 기준
        self._retrain_criteria = {
            'min_feedback_count': 100,      # 최소 피드백 수
            'accuracy_drop_threshold': 0.1,  # 정확도 하락 기준
            'days_since_last_train': 30     # 마지막 학습 후 경과일
        }
        
        self._logger.info("FeedbackSystem 초기화 완료")
    
    def _init_database(self):
        """피드백 데이터베이스 초기화"""
        try:
            # 디렉토리 생성
            db_dir = Path(self._db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                
                # 피드백 테이블 생성
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS feedback_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        prediction_id TEXT UNIQUE NOT NULL,
                        stock_code TEXT NOT NULL,
                        prediction_date TEXT NOT NULL,
                        predicted_probability REAL NOT NULL,
                        predicted_class INTEGER NOT NULL,
                        model_name TEXT NOT NULL,
                        actual_return_7d REAL,
                        actual_class INTEGER,
                        prediction_error REAL,
                        absolute_error REAL,
                        feedback_date TEXT,
                        is_processed BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 모델 성능 추적 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS model_performance_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        model_name TEXT NOT NULL,
                        evaluation_date TEXT NOT NULL,
                        accuracy REAL,
                        precision_score REAL,
                        recall_score REAL,
                        f1_score REAL,
                        auc_score REAL,
                        feedback_count INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 인덱스 생성
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_prediction_id ON feedback_data(prediction_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_code ON feedback_data(stock_code)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_prediction_date ON feedback_data(prediction_date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_name ON feedback_data(model_name)")
                
                conn.commit()
                
            self._logger.info("피드백 데이터베이스 초기화 완료")
            
        except Exception as e:
            self._logger.error(f"피드백 데이터베이스 초기화 오류: {e}")
    
    def record_predictions(self, predictions: List[PredictionResult]) -> bool:
        """예측 결과 기록
        
        Args:
            predictions: 예측 결과 리스트
            
        Returns:
            bool: 기록 성공 여부
        """
        try:
            self._logger.info(f"예측 결과 기록 시작: {len(predictions)}개")
            
            recorded_count = 0
            
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                
                for prediction in predictions:
                    try:
                        # 앙상블 결과로 기록
                        prediction_id = f"{prediction.stock_code}_{prediction.prediction_date}_ensemble"
                        
                        feedback_data = FeedbackData(
                            prediction_id=prediction_id,
                            stock_code=prediction.stock_code,
                            prediction_date=prediction.prediction_date,
                            predicted_probability=prediction.ensemble_probability,
                            predicted_class=prediction.ensemble_prediction,
                            model_name="ensemble"
                        )
                        
                        # 데이터베이스에 삽입
                        cursor.execute("""
                            INSERT OR REPLACE INTO feedback_data (
                                prediction_id, stock_code, prediction_date,
                                predicted_probability, predicted_class, model_name
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            feedback_data.prediction_id,
                            feedback_data.stock_code,
                            feedback_data.prediction_date,
                            feedback_data.predicted_probability,
                            feedback_data.predicted_class,
                            feedback_data.model_name
                        ))
                        
                        recorded_count += 1
                        
                        # 개별 모델 예측도 기록
                        for model_name, model_pred in prediction.model_predictions.items():
                            model_prediction_id = f"{prediction.stock_code}_{prediction.prediction_date}_{model_name}"
                            
                            cursor.execute("""
                                INSERT OR REPLACE INTO feedback_data (
                                    prediction_id, stock_code, prediction_date,
                                    predicted_probability, predicted_class, model_name
                                ) VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                model_prediction_id,
                                model_pred.stock_code,
                                model_pred.prediction_date,
                                model_pred.success_probability,
                                model_pred.predicted_class,
                                model_name
                            ))
                        
                    except Exception as e:
                        self._logger.warning(f"예측 기록 실패: {prediction.stock_code} - {e}")
                
                conn.commit()
            
            self._logger.info(f"예측 결과 기록 완료: {recorded_count}개")
            return recorded_count > 0
            
        except Exception as e:
            self._logger.error(f"예측 결과 기록 오류: {e}")
            return False
    
    def update_feedback_from_performance(self, start_date: Optional[str] = None) -> bool:
        """성과 데이터로부터 피드백 업데이트
        
        Args:
            start_date: 업데이트 시작 날짜 (None이면 모든 미처리 데이터)
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            self._logger.info("성과 데이터로부터 피드백 업데이트 시작")
            
            # 업데이트 대상 피드백 데이터 조회
            feedback_list = self._get_pending_feedback(start_date)
            
            if not feedback_list:
                self._logger.info("업데이트할 피드백 데이터가 없습니다")
                return True
            
            updated_count = 0
            
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                
                for feedback in feedback_list:
                    try:
                        # 성과 데이터 조회
                        actual_performance = self._get_actual_performance(
                            feedback.stock_code, 
                            feedback.prediction_date
                        )
                        
                        if actual_performance is None:
                            continue
                        
                        # 실제 결과 계산
                        actual_return_7d = actual_performance
                        actual_class = 1 if actual_return_7d > self._success_threshold else 0
                        
                        # 예측 오차 계산
                        prediction_error = feedback.predicted_probability - actual_class
                        absolute_error = abs(prediction_error)
                        
                        # 피드백 데이터 업데이트
                        cursor.execute("""
                            UPDATE feedback_data 
                            SET actual_return_7d = ?,
                                actual_class = ?,
                                prediction_error = ?,
                                absolute_error = ?,
                                feedback_date = ?,
                                is_processed = TRUE,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE prediction_id = ?
                        """, (
                            actual_return_7d,
                            actual_class,
                            prediction_error,
                            absolute_error,
                            datetime.now().strftime('%Y-%m-%d'),
                            feedback.prediction_id
                        ))
                        
                        updated_count += 1
                        
                    except Exception as e:
                        self._logger.warning(f"피드백 업데이트 실패: {feedback.prediction_id} - {e}")
                
                conn.commit()
            
            self._logger.info(f"피드백 업데이트 완료: {updated_count}/{len(feedback_list)}개")
            return updated_count > 0
            
        except Exception as e:
            self._logger.error(f"피드백 업데이트 오류: {e}")
            return False
    
    def _get_pending_feedback(self, start_date: Optional[str] = None) -> List[FeedbackData]:
        """처리 대기 중인 피드백 데이터 조회"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                
                if start_date:
                    query = """
                        SELECT * FROM feedback_data 
                        WHERE is_processed = FALSE AND prediction_date >= ?
                        ORDER BY prediction_date, stock_code
                    """
                    cursor.execute(query, (start_date,))
                else:
                    # 7일 이상 경과한 예측만 (성과 데이터 확보 가능)
                    cutoff_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    query = """
                        SELECT * FROM feedback_data 
                        WHERE is_processed = FALSE AND prediction_date <= ?
                        ORDER BY prediction_date, stock_code
                    """
                    cursor.execute(query, (cutoff_date,))
                
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                feedback_list = []
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    
                    feedback = FeedbackData(
                        prediction_id=row_dict['prediction_id'],
                        stock_code=row_dict['stock_code'],
                        prediction_date=row_dict['prediction_date'],
                        predicted_probability=row_dict['predicted_probability'],
                        predicted_class=row_dict['predicted_class'],
                        model_name=row_dict['model_name'],
                        actual_return_7d=row_dict['actual_return_7d'],
                        actual_class=row_dict['actual_class'],
                        prediction_error=row_dict['prediction_error'],
                        absolute_error=row_dict['absolute_error'],
                        feedback_date=row_dict['feedback_date'],
                        is_processed=bool(row_dict['is_processed'])
                    )
                    
                    feedback_list.append(feedback)
                
                return feedback_list
                
        except Exception as e:
            self._logger.error(f"대기 중인 피드백 조회 오류: {e}")
            return []
    
    def _get_actual_performance(self, stock_code: str, prediction_date: str) -> Optional[float]:
        """실제 성과 데이터 조회"""
        try:
            with sqlite3.connect(self._performance_db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT return_7d FROM daily_performance 
                    WHERE stock_code = ? AND date = ?
                """
                
                cursor.execute(query, (stock_code, prediction_date))
                result = cursor.fetchone()
                
                if result and result[0] is not None:
                    return float(result[0])
                
                return None
                
        except Exception as e:
            self._logger.error(f"실제 성과 조회 오류: {e}")
            return None
    
    def evaluate_model_performance(self, model_name: str = "ensemble", 
                                 days_back: int = 30) -> Dict[str, Any]:
        """모델 성능 평가
        
        Args:
            model_name: 평가할 모델명
            days_back: 평가 기간 (일)
            
        Returns:
            Dict[str, Any]: 성능 지표
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT predicted_class, actual_class, predicted_probability, absolute_error
                    FROM feedback_data 
                    WHERE model_name = ? AND is_processed = TRUE 
                    AND prediction_date >= ?
                """
                
                cursor.execute(query, (model_name, cutoff_date))
                results = cursor.fetchall()
                
                if not results:
                    self._logger.warning(f"평가할 데이터가 없습니다: {model_name}")
                    return {}
                
                # 데이터 분리
                y_pred = [row[0] for row in results]
                y_true = [row[1] for row in results if row[1] is not None]
                y_pred_filtered = [y_pred[i] for i in range(len(results)) if results[i][1] is not None]
                y_proba = [row[2] for row in results if row[1] is not None]
                errors = [row[3] for row in results if row[3] is not None]
                
                if not y_true or not y_pred_filtered:
                    return {}
                
                # 성능 지표 계산
                accuracy = np.mean(np.array(y_pred_filtered) == np.array(y_true))
                
                # Precision, Recall, F1
                tp = sum(1 for i in range(len(y_true)) if y_true[i] == 1 and y_pred_filtered[i] == 1)
                fp = sum(1 for i in range(len(y_true)) if y_true[i] == 0 and y_pred_filtered[i] == 1)
                fn = sum(1 for i in range(len(y_true)) if y_true[i] == 1 and y_pred_filtered[i] == 0)
                
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
                
                # AUC Score (sklearn 없이 간단 계산)
                try:
                    from sklearn.metrics import roc_auc_score
                    auc_score = roc_auc_score(y_true, y_proba)
                except ImportError:
                    auc_score = 0.5  # 기본값
                
                # 평균 절대 오차
                mae = np.mean(errors) if errors else 0.0
                
                performance = {
                    'model_name': model_name,
                    'evaluation_date': datetime.now().strftime('%Y-%m-%d'),
                    'evaluation_period_days': days_back,
                    'total_predictions': len(results),
                    'processed_predictions': len(y_true),
                    'accuracy': float(accuracy),
                    'precision': float(precision),
                    'recall': float(recall),
                    'f1_score': float(f1),
                    'auc_score': float(auc_score),
                    'mean_absolute_error': float(mae),
                    'true_positive_rate': float(recall),
                    'false_positive_rate': float(fp / (fp + (len(y_true) - tp - fn))) if (fp + (len(y_true) - tp - fn)) > 0 else 0.0
                }
                
                # 성능 히스토리 저장
                self._save_performance_history(performance)
                
                self._logger.info(f"{model_name} 성능 평가 완료 - 정확도: {accuracy:.3f}")
                return performance
                
        except Exception as e:
            self._logger.error(f"모델 성능 평가 오류: {e}")
            return {}
    
    def _save_performance_history(self, performance: Dict[str, Any]):
        """성능 히스토리 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO model_performance_history (
                        model_name, evaluation_date, accuracy, precision_score,
                        recall_score, f1_score, auc_score, feedback_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    performance['model_name'],
                    performance['evaluation_date'],
                    performance['accuracy'],
                    performance['precision'],
                    performance['recall'],
                    performance['f1_score'],
                    performance['auc_score'],
                    performance['processed_predictions']
                ))
                
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"성능 히스토리 저장 오류: {e}")
    
    def check_retrain_needed(self) -> Dict[str, Any]:
        """재학습 필요 여부 확인
        
        Returns:
            Dict[str, Any]: 재학습 필요 정보
        """
        try:
            # 최근 성능 조회
            recent_performance = self.evaluate_model_performance("ensemble", 30)
            
            if not recent_performance:
                return {'retrain_needed': False, 'reason': 'insufficient_data'}
            
            # 재학습 조건 확인
            retrain_reasons = []
            
            # 1. 최소 피드백 수 확인
            if recent_performance['processed_predictions'] < self._retrain_criteria['min_feedback_count']:
                retrain_reasons.append(f"insufficient_feedback_count: {recent_performance['processed_predictions']}")
            
            # 2. 정확도 하락 확인
            baseline_accuracy = 0.7  # 기준 정확도
            accuracy_drop = baseline_accuracy - recent_performance['accuracy']
            if accuracy_drop > self._retrain_criteria['accuracy_drop_threshold']:
                retrain_reasons.append(f"accuracy_drop: {accuracy_drop:.3f}")
            
            # 3. 마지막 학습 후 경과일 확인 (임시로 항상 True)
            retrain_reasons.append("time_based_retrain")
            
            retrain_info = {
                'retrain_needed': len(retrain_reasons) > 0,
                'reasons': retrain_reasons,
                'current_performance': recent_performance,
                'retrain_criteria': self._retrain_criteria
            }
            
            return retrain_info
            
        except Exception as e:
            self._logger.error(f"재학습 필요 여부 확인 오류: {e}")
            return {'retrain_needed': False, 'error': str(e)}
    
    def get_feedback_summary(self, days_back: int = 30) -> Dict[str, Any]:
        """피드백 요약 정보
        
        Args:
            days_back: 조회 기간 (일)
            
        Returns:
            Dict[str, Any]: 피드백 요약
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                
                # 전체 피드백 통계
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_feedback,
                        COUNT(CASE WHEN is_processed = TRUE THEN 1 END) as processed_feedback,
                        AVG(CASE WHEN is_processed = TRUE THEN absolute_error END) as avg_error,
                        COUNT(CASE WHEN actual_class = 1 THEN 1 END) as actual_successes,
                        COUNT(CASE WHEN predicted_class = 1 THEN 1 END) as predicted_successes
                    FROM feedback_data 
                    WHERE prediction_date >= ?
                """, (cutoff_date,))
                
                result = cursor.fetchone()
                
                # 모델별 성능
                cursor.execute("""
                    SELECT model_name, 
                           COUNT(*) as count,
                           AVG(CASE WHEN is_processed = TRUE THEN absolute_error END) as avg_error
                    FROM feedback_data 
                    WHERE prediction_date >= ? AND is_processed = TRUE
                    GROUP BY model_name
                """, (cutoff_date,))
                
                model_stats = cursor.fetchall()
                
                summary = {
                    'period_days': days_back,
                    'total_feedback': result[0] if result else 0,
                    'processed_feedback': result[1] if result else 0,
                    'processing_rate': result[1] / result[0] if result and result[0] > 0 else 0.0,
                    'average_error': result[2] if result and result[2] else 0.0,
                    'actual_success_rate': result[3] / result[1] if result and result[1] > 0 else 0.0,
                    'predicted_success_rate': result[4] / result[0] if result and result[0] > 0 else 0.0,
                    'model_performance': {
                        row[0]: {'count': row[1], 'avg_error': row[2] or 0.0}
                        for row in model_stats
                    }
                }
                
                return summary
                
        except Exception as e:
            self._logger.error(f"피드백 요약 조회 오류: {e}")
            return {} 