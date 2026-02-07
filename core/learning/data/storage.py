"""
Phase 4: AI 학습 시스템 - 데이터 저장소
학습 데이터, 피처, 모델, 성과 등 모든 데이터의 저장 및 관리
"""

import os
import json
import joblib
import sqlite3
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from dataclasses import asdict

# 학습 인터페이스 import (새로운 아키텍처)
try:
    from core.interfaces.learning import (
        LearningData, FeatureSet, ModelPrediction, 
        PerformanceMetrics, PatternResult, OptimizationResult
    )
    from core.learning.config.settings import get_learning_config
    from core.learning.utils.logging import get_learning_logger
    LEARNING_INTERFACES_AVAILABLE = True
except ImportError:
    LEARNING_INTERFACES_AVAILABLE = False


class DataStorageError(Exception):
    """데이터 저장소 관련 예외"""
    pass


class LearningDataStorage:
    """
    AI 학습 시스템 데이터 저장소
    SQLite 기반 구조화된 데이터 저장 + 파일 기반 대용량 데이터 저장
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        데이터 저장소 초기화
        
        Args:
            storage_path: 저장소 기본 경로
        """
        self.config = get_learning_config() if LEARNING_INTERFACES_AVAILABLE else None
        self.logger = get_learning_logger(__name__) if LEARNING_INTERFACES_AVAILABLE else None
        
        # 저장소 경로 설정
        if storage_path:
            self.storage_path = Path(storage_path)
        elif self.config:
            self.storage_path = Path(self.config.data.data_dir)
        else:
            self.storage_path = Path("data/learning")
        
        # 디렉토리 구조 생성
        self._create_directory_structure()
        
        # 데이터베이스 초기화
        self._initialize_database()
    
    def _create_directory_structure(self):
        """디렉토리 구조 생성"""
        directories = [
            self.storage_path,
            self.storage_path / "raw_data",          # 원시 데이터
            self.storage_path / "processed_data",    # 전처리된 데이터
            self.storage_path / "features",          # 피처 데이터
            self.storage_path / "models",            # 모델 파일
            self.storage_path / "predictions",       # 예측 결과
            self.storage_path / "performance",       # 성과 데이터
            self.storage_path / "patterns",          # 패턴 데이터
            self.storage_path / "optimization",      # 최적화 결과
            self.storage_path / "backtest",          # 백테스트 결과
            self.storage_path / "metadata",          # 메타데이터
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _initialize_database(self):
        """SQLite 데이터베이스 초기화"""
        self.db_path = self.storage_path / "learning_data.db"
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            
            # 학습 데이터 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS learning_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    phase1_file_path TEXT,
                    phase2_file_path TEXT,
                    actual_performance TEXT,
                    market_condition TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(stock_code, date)
                )
            ''')
            
            # 피처 데이터 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feature_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    feature_file_path TEXT NOT NULL,
                    target_value REAL,
                    feature_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(stock_code, date)
                )
            ''')
            
            # 모델 정보 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    version TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    hyperparameters TEXT,
                    training_date TEXT,
                    performance_metrics TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(model_name, version)
                )
            ''')
            
            # 예측 결과 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    prediction_date TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prediction_value REAL NOT NULL,
                    confidence REAL NOT NULL,
                    probability REAL,
                    actual_result REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 인덱스 생성
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_predictions_stock_date 
                ON predictions(stock_code, prediction_date)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_predictions_date 
                ON predictions(prediction_date)
            ''')
            
            # 성과 지표 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    accuracy REAL NOT NULL,
                    precision_score REAL NOT NULL,
                    recall_score REAL NOT NULL,
                    f1_score REAL NOT NULL,
                    auc_score REAL,
                    sharpe_ratio REAL,
                    max_drawdown REAL,
                    win_rate REAL,
                    avg_return REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, model_name)
                )
            ''')
            
            # 패턴 데이터 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    occurrence_count INTEGER NOT NULL,
                    success_rate REAL NOT NULL,
                    avg_return REAL NOT NULL,
                    pattern_data_path TEXT NOT NULL,
                    market_conditions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 최적화 결과 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS optimization_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parameter_name TEXT NOT NULL,
                    best_value TEXT NOT NULL,
                    best_score REAL NOT NULL,
                    optimization_method TEXT NOT NULL,
                    elapsed_time REAL NOT NULL,
                    result_file_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    # === 학습 데이터 관리 ===
    def save_learning_data(self, learning_data: 'LearningData') -> bool:
        """학습 데이터 저장"""
        try:
            # 파일 경로 생성
            date_str = learning_data.date.replace('-', '')
            phase1_file = self.storage_path / "raw_data" / f"phase1_{learning_data.stock_code}_{date_str}.json"
            phase2_file = self.storage_path / "raw_data" / f"phase2_{learning_data.stock_code}_{date_str}.json"
            
            # Phase 1,2 데이터 파일 저장
            with open(phase1_file, 'w', encoding='utf-8') as f:
                json.dump(learning_data.phase1_data, f, ensure_ascii=False, indent=2)
            
            with open(phase2_file, 'w', encoding='utf-8') as f:
                json.dump(learning_data.phase2_data, f, ensure_ascii=False, indent=2)
            
            # 데이터베이스에 메타데이터 저장
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO learning_data 
                    (stock_code, stock_name, date, phase1_file_path, phase2_file_path, 
                     actual_performance, market_condition)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    learning_data.stock_code,
                    learning_data.stock_name,
                    learning_data.date,
                    str(phase1_file),
                    str(phase2_file),
                    json.dumps(learning_data.actual_performance) if learning_data.actual_performance else None,
                    learning_data.market_condition
                ))
                conn.commit()
            
            if self.logger:
                self.logger.info(f"학습 데이터 저장 완료: {learning_data.stock_code} - {learning_data.date}")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"학습 데이터 저장 실패: {e}", exc_info=True)
            raise DataStorageError(f"학습 데이터 저장 실패: {e}")
    
    def load_learning_data(self, stock_code: str, date: str) -> Union['LearningData', Dict[str, Any], None]:
        """학습 데이터 로드"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT stock_code, stock_name, date, phase1_file_path, phase2_file_path, 
                           actual_performance, market_condition
                    FROM learning_data 
                    WHERE stock_code = ? AND date = ?
                ''', (stock_code, date))
                
                result = cursor.fetchone()
                if not result:
                    return None
                
                # 파일에서 데이터 로드
                with open(result[3], 'r', encoding='utf-8') as f:
                    phase1_data = json.load(f)
                
                with open(result[4], 'r', encoding='utf-8') as f:
                    phase2_data = json.load(f)
                
                # LearningData 객체 생성
                if LEARNING_INTERFACES_AVAILABLE:
                    return LearningData(
                        stock_code=result[0],
                        stock_name=result[1],
                        date=result[2],
                        phase1_data=phase1_data,
                        phase2_data=phase2_data,
                        actual_performance=json.loads(result[5]) if result[5] else None,
                        market_condition=result[6]
                    )
                else:
                    return {
                        'stock_code': result[0],
                        'stock_name': result[1],
                        'date': result[2],
                        'phase1_data': phase1_data,
                        'phase2_data': phase2_data,
                        'actual_performance': json.loads(result[5]) if result[5] else None,
                        'market_condition': result[6]
                    }
                    
        except Exception as e:
            if self.logger:
                self.logger.error(f"학습 데이터 로드 실패: {e}", exc_info=True)
            return None
    
    def get_learning_data_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """날짜 범위로 학습 데이터 조회"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT stock_code, stock_name, date, phase1_file_path, phase2_file_path, 
                           actual_performance, market_condition
                    FROM learning_data 
                    WHERE date >= ? AND date <= ?
                    ORDER BY date, stock_code
                ''', (start_date, end_date))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'stock_code': row[0],
                        'stock_name': row[1],
                        'date': row[2],
                        'phase1_file_path': row[3],
                        'phase2_file_path': row[4],
                        'actual_performance': json.loads(row[5]) if row[5] else None,
                        'market_condition': row[6]
                    })
                
                return results
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"학습 데이터 조회 실패: {e}", exc_info=True)
            return []
    
    # === 피처 데이터 관리 ===
    def save_feature_set(self, feature_set: 'FeatureSet') -> bool:
        """피처 셋 저장"""
        try:
            # 피처 파일 경로 생성
            date_str = feature_set.date.replace('-', '')
            feature_file = self.storage_path / "features" / f"features_{feature_set.stock_code}_{date_str}.json"
            
            # 피처 데이터 저장
            feature_data = {
                'features': feature_set.features,
                'target': feature_set.target,
                'feature_importance': feature_set.feature_importance,
                'feature_category': feature_set.feature_category,
                'metadata': feature_set.metadata
            }
            
            with open(feature_file, 'w', encoding='utf-8') as f:
                json.dump(feature_data, f, ensure_ascii=False, indent=2)
            
            # 데이터베이스에 메타데이터 저장
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO feature_data 
                    (stock_code, date, feature_file_path, target_value, feature_count)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    feature_set.stock_code,
                    feature_set.date,
                    str(feature_file),
                    feature_set.target,
                    len(feature_set.features)
                ))
                conn.commit()
            
            if self.logger:
                self.logger.info(f"피처 셋 저장 완료: {feature_set.stock_code} - {feature_set.date}")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"피처 셋 저장 실패: {e}", exc_info=True)
            raise DataStorageError(f"피처 셋 저장 실패: {e}")
    
    # === 모델 관리 ===
    def save_model(self, model: Any, model_name: str, model_type: str, version: str,
                  hyperparameters: Dict, performance_metrics: Dict) -> bool:
        """모델 저장"""
        try:
            # 모델 파일 경로 생성 (.joblib 확장자 사용)
            model_file = self.storage_path / "models" / f"{model_name}_{version}.joblib"

            # 모델 객체 저장 (joblib 사용, compress=3으로 압축)
            joblib.dump(model, str(model_file), compress=3)
            
            # 데이터베이스에 메타데이터 저장
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO models 
                    (model_name, model_type, version, file_path, hyperparameters, 
                     training_date, performance_metrics)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    model_name,
                    model_type,
                    version,
                    str(model_file),
                    json.dumps(hyperparameters),
                    datetime.now().strftime('%Y-%m-%d'),
                    json.dumps(performance_metrics)
                ))
                conn.commit()
            
            if self.logger:
                self.logger.info(f"모델 저장 완료: {model_name} v{version}")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"모델 저장 실패: {e}", exc_info=True)
            raise DataStorageError(f"모델 저장 실패: {e}")
    
    def load_model(self, model_name: str, version: Optional[str] = None) -> Optional[Any]:
        """모델 로드"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                if version:
                    cursor.execute('''
                        SELECT file_path FROM models 
                        WHERE model_name = ? AND version = ?
                    ''', (model_name, version))
                else:
                    cursor.execute('''
                        SELECT file_path FROM models 
                        WHERE model_name = ? AND is_active = 1
                        ORDER BY created_at DESC LIMIT 1
                    ''', (model_name,))
                
                result = cursor.fetchone()
                if not result:
                    return None

                # 모델 객체 로드 (joblib 사용)
                model = joblib.load(result[0])

                return model

        except Exception as e:
            if self.logger:
                self.logger.error(f"모델 로드 실패: {e}", exc_info=True)
            return None
    
    # === 성과 지표 관리 ===
    def save_performance_metrics(self, metrics: 'PerformanceMetrics', model_name: str) -> bool:
        """성과 지표 저장"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO performance_metrics 
                    (date, model_name, accuracy, precision_score, recall_score, f1_score, 
                     auc_score, sharpe_ratio, max_drawdown, win_rate, avg_return)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metrics.date,
                    model_name,
                    metrics.accuracy,
                    metrics.precision,
                    metrics.recall,
                    metrics.f1_score,
                    metrics.auc_score,
                    metrics.sharpe_ratio,
                    metrics.max_drawdown,
                    metrics.win_rate,
                    metrics.avg_return
                ))
                conn.commit()
            
            if self.logger:
                self.logger.info(f"성과 지표 저장 완료: {model_name} - {metrics.date}")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"성과 지표 저장 실패: {e}", exc_info=True)
            raise DataStorageError(f"성과 지표 저장 실패: {e}")
    
    def get_performance_history(self, model_name: str, days: int = 30) -> List[Dict]:
        """성과 이력 조회"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT date, accuracy, precision_score, recall_score, f1_score, 
                           auc_score, sharpe_ratio, max_drawdown, win_rate, avg_return
                    FROM performance_metrics 
                    WHERE model_name = ?
                    ORDER BY date DESC
                    LIMIT ?
                ''', (model_name, days))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'date': row[0],
                        'accuracy': row[1],
                        'precision': row[2],
                        'recall': row[3],
                        'f1_score': row[4],
                        'auc_score': row[5],
                        'sharpe_ratio': row[6],
                        'max_drawdown': row[7],
                        'win_rate': row[8],
                        'avg_return': row[9]
                    })
                
                return results
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"성과 이력 조회 실패: {e}", exc_info=True)
            return []
    
    # === 데이터 정리 및 유지보수 ===
    def cleanup_old_data(self, days: int = 90) -> bool:
        """오래된 데이터 정리"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # 오래된 예측 결과 삭제
                cursor.execute('''
                    DELETE FROM predictions 
                    WHERE prediction_date < ?
                ''', (cutoff_date,))
                
                # 오래된 성과 지표 삭제 (최근 것은 유지)
                cursor.execute('''
                    DELETE FROM performance_metrics 
                    WHERE date < ? AND date NOT IN (
                        SELECT date FROM performance_metrics 
                        WHERE model_name = performance_metrics.model_name
                        ORDER BY date DESC LIMIT 30
                    )
                ''', (cutoff_date,))
                
                conn.commit()
            
            if self.logger:
                self.logger.info(f"오래된 데이터 정리 완료: {cutoff_date} 이전 데이터")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"데이터 정리 실패: {e}", exc_info=True)
            return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """저장소 통계 조회"""
        try:
            stats = {}
            
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # 각 테이블 레코드 수
                tables = ['learning_data', 'feature_data', 'models', 'predictions', 
                         'performance_metrics', 'patterns', 'optimization_results']
                
                for table in tables:
                    cursor.execute(f'SELECT COUNT(*) FROM {table}')
                    stats[f'{table}_count'] = cursor.fetchone()[0]
                
                # 디스크 사용량
                stats['db_size_bytes'] = os.path.getsize(self.db_path)
                stats['total_files'] = sum(len(files) for _, _, files in os.walk(self.storage_path))
                
            return stats
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"저장소 통계 조회 실패: {e}", exc_info=True)
            return {}


# 전역 저장소 인스턴스
_storage_instance = None


def get_learning_storage() -> LearningDataStorage:
    """학습 데이터 저장소 인스턴스 반환"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = LearningDataStorage()
    return _storage_instance 