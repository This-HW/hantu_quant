"""
Phase 4: AI 학습 시스템 - 인터페이스 정의
AI 학습 시스템의 모든 인터페이스를 정의
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from enum import Enum


class ModelType(Enum):
    """모델 타입 열거형"""
    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"
    ENSEMBLE = "ensemble"
    NEURAL_NETWORK = "neural_network"


class LearningPhase(Enum):
    """학습 단계 열거형"""
    DATA_COLLECTION = "data_collection"
    FEATURE_ENGINEERING = "feature_engineering"
    MODEL_TRAINING = "model_training"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    PATTERN_LEARNING = "pattern_learning"
    OPTIMIZATION = "optimization"
    BACKTESTING = "backtesting"
    DEPLOYMENT = "deployment"


@dataclass
class LearningData:
    """학습 데이터 클래스"""
    stock_code: str
    stock_name: str
    date: str
    phase1_data: Dict[str, Any]  # Phase 1 스크리닝 데이터
    phase2_data: Dict[str, Any]  # Phase 2 가격 분석 데이터
    actual_performance: Optional[Dict[str, float]] = None  # 실제 성과
    market_condition: Optional[str] = None  # 시장 상황
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class FeatureSet:
    """피처 셋 클래스"""
    stock_code: str
    date: str
    features: Dict[str, float]  # 피처 딕셔너리
    target: Optional[float] = None  # 타겟 값
    feature_importance: Optional[Dict[str, float]] = None  # 피처 중요도
    feature_category: Optional[Dict[str, str]] = None  # 피처 카테고리
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelPrediction:
    """모델 예측 결과 클래스"""
    stock_code: str
    stock_name: str
    prediction_date: str
    prediction: float  # 예측 값
    confidence: float  # 신뢰도
    probability: Optional[float] = None  # 확률 (분류 모델)
    model_type: ModelType = ModelType.ENSEMBLE
    features_used: Optional[List[str]] = None  # 사용된 피처 목록
    explanation: Optional[Dict[str, Any]] = None  # 예측 설명
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PerformanceMetrics:
    """성과 지표 클래스"""
    date: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    auc_score: Optional[float] = None
    mse: Optional[float] = None  # 회귀 모델용
    mae: Optional[float] = None  # 회귀 모델용
    sharpe_ratio: Optional[float] = None  # 트레이딩 성과
    max_drawdown: Optional[float] = None  # 최대 손실
    win_rate: Optional[float] = None  # 승률
    avg_return: Optional[float] = None  # 평균 수익률
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PatternResult:
    """패턴 분석 결과 클래스"""
    pattern_type: str
    confidence: float
    occurrence_count: int
    success_rate: float
    avg_return: float
    pattern_data: Dict[str, Any]
    market_conditions: List[str]
    recommendations: List[str]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class OptimizationResult:
    """최적화 결과 클래스"""
    parameter_name: str
    best_value: Any
    best_score: float
    optimization_history: List[Dict]
    search_space: Dict[str, Any]
    optimization_method: str
    elapsed_time: float
    metadata: Optional[Dict[str, Any]] = None


class ILearningDataCollector(ABC):
    """학습 데이터 수집 인터페이스"""
    
    @abstractmethod
    def collect_historical_data(self, stock_codes: List[str], 
                               start_date: str, end_date: str) -> List[LearningData]:
        """
        과거 데이터 수집
        
        Args:
            stock_codes: 주식 코드 목록
            start_date: 시작 날짜
            end_date: 종료 날짜
            
        Returns:
            학습 데이터 목록
        """
        pass
    
    @abstractmethod
    def collect_phase1_results(self, date: str) -> List[Dict]:
        """Phase 1 결과 수집"""
        pass
    
    @abstractmethod
    def collect_phase2_results(self, date: str) -> List[Dict]:
        """Phase 2 결과 수집"""
        pass
    
    @abstractmethod
    def collect_actual_performance(self, stock_codes: List[str], 
                                 start_date: str, end_date: str) -> Dict[str, Dict]:
        """실제 성과 수집"""
        pass
    
    @abstractmethod
    def validate_data_quality(self, data: List[LearningData]) -> Dict[str, Any]:
        """데이터 품질 검증"""
        pass


class IFeatureEngineer(ABC):
    """피처 엔지니어링 인터페이스"""
    
    @abstractmethod
    def extract_features(self, learning_data: LearningData) -> FeatureSet:
        """
        피처 추출
        
        Args:
            learning_data: 학습 데이터
            
        Returns:
            피처 셋
        """
        pass
    
    @abstractmethod
    def extract_slope_features(self, price_data: Dict) -> Dict[str, float]:
        """기울기 피처 추출"""
        pass
    
    @abstractmethod
    def extract_volume_features(self, volume_data: Dict) -> Dict[str, float]:
        """볼륨 피처 추출"""
        pass
    
    @abstractmethod
    def select_features(self, feature_sets: List[FeatureSet], 
                       method: str = "importance") -> List[str]:
        """피처 선택"""
        pass
    
    @abstractmethod
    def calculate_feature_importance(self, feature_sets: List[FeatureSet], 
                                   target_column: str) -> Dict[str, float]:
        """피처 중요도 계산"""
        pass
    
    @abstractmethod
    def normalize_features(self, feature_sets: List[FeatureSet]) -> List[FeatureSet]:
        """피처 정규화"""
        pass


class IModelTrainer(ABC):
    """모델 훈련 인터페이스"""
    
    @abstractmethod
    def train_model(self, feature_sets: List[FeatureSet], 
                   model_type: ModelType, 
                   hyperparameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        모델 훈련
        
        Args:
            feature_sets: 피처 셋 목록
            model_type: 모델 타입
            hyperparameters: 하이퍼파라미터
            
        Returns:
            훈련된 모델 정보
        """
        pass
    
    @abstractmethod
    def predict(self, model: Any, feature_sets: List[FeatureSet]) -> List[ModelPrediction]:
        """모델 예측"""
        pass
    
    @abstractmethod
    def evaluate_model(self, model: Any, test_data: List[FeatureSet]) -> PerformanceMetrics:
        """모델 평가"""
        pass
    
    @abstractmethod
    def save_model(self, model: Any, model_path: str) -> bool:
        """모델 저장"""
        pass
    
    @abstractmethod
    def load_model(self, model_path: str) -> Any:
        """모델 로드"""
        pass
    
    @abstractmethod
    def cross_validate(self, feature_sets: List[FeatureSet], 
                      model_type: ModelType, 
                      cv_folds: int = 5) -> List[PerformanceMetrics]:
        """교차 검증"""
        pass


class IPerformanceAnalyzer(ABC):
    """성과 분석 인터페이스"""
    
    @abstractmethod
    def analyze_daily_performance(self, predictions: List[ModelPrediction], 
                                 actual_results: List[Dict]) -> PerformanceMetrics:
        """
        일일 성과 분석
        
        Args:
            predictions: 예측 결과 목록
            actual_results: 실제 결과 목록
            
        Returns:
            성과 지표
        """
        pass
    
    @abstractmethod
    def calculate_trading_metrics(self, predictions: List[ModelPrediction], 
                                 actual_returns: List[float]) -> Dict[str, float]:
        """트레이딩 지표 계산"""
        pass
    
    @abstractmethod
    def analyze_prediction_accuracy(self, predictions: List[ModelPrediction], 
                                   actual_values: List[float]) -> Dict[str, float]:
        """예측 정확도 분석"""
        pass
    
    @abstractmethod
    def generate_performance_report(self, metrics: List[PerformanceMetrics]) -> str:
        """성과 보고서 생성"""
        pass
    
    @abstractmethod
    def track_model_drift(self, recent_metrics: List[PerformanceMetrics], 
                         baseline_metrics: PerformanceMetrics) -> Dict[str, Any]:
        """모델 드리프트 추적"""
        pass


class IPatternLearner(ABC):
    """패턴 학습 인터페이스"""
    
    @abstractmethod
    def learn_success_patterns(self, successful_predictions: List[ModelPrediction], 
                              feature_sets: List[FeatureSet]) -> List[PatternResult]:
        """
        성공 패턴 학습
        
        Args:
            successful_predictions: 성공한 예측 목록
            feature_sets: 피처 셋 목록
            
        Returns:
            패턴 결과 목록
        """
        pass
    
    @abstractmethod
    def learn_failure_patterns(self, failed_predictions: List[ModelPrediction], 
                              feature_sets: List[FeatureSet]) -> List[PatternResult]:
        """실패 패턴 학습"""
        pass
    
    @abstractmethod
    def detect_market_regime_patterns(self, historical_data: List[LearningData]) -> List[PatternResult]:
        """시장 상황 패턴 감지"""
        pass
    
    @abstractmethod
    def apply_pattern_filter(self, predictions: List[ModelPrediction], 
                           patterns: List[PatternResult]) -> List[ModelPrediction]:
        """패턴 필터 적용"""
        pass
    
    @abstractmethod
    def update_pattern_database(self, new_patterns: List[PatternResult]) -> bool:
        """패턴 데이터베이스 업데이트"""
        pass


class IParameterOptimizer(ABC):
    """파라미터 최적화 인터페이스"""
    
    @abstractmethod
    def optimize_hyperparameters(self, feature_sets: List[FeatureSet], 
                               model_type: ModelType, 
                               search_space: Dict[str, Any], 
                               trials: int = 100) -> OptimizationResult:
        """
        하이퍼파라미터 최적화
        
        Args:
            feature_sets: 피처 셋 목록
            model_type: 모델 타입
            search_space: 검색 공간
            trials: 시도 횟수
            
        Returns:
            최적화 결과
        """
        pass
    
    @abstractmethod
    def optimize_feature_selection(self, feature_sets: List[FeatureSet]) -> List[str]:
        """피처 선택 최적화"""
        pass
    
    @abstractmethod
    def optimize_threshold_values(self, predictions: List[ModelPrediction], 
                                 actual_results: List[Dict]) -> Dict[str, float]:
        """임계값 최적화"""
        pass
    
    @abstractmethod
    def dynamic_parameter_adjustment(self, current_performance: PerformanceMetrics, 
                                   baseline_performance: PerformanceMetrics) -> Dict[str, Any]:
        """동적 파라미터 조정"""
        pass


class IBacktestAutomation(ABC):
    """백테스트 자동화 인터페이스"""
    
    @abstractmethod
    def run_backtest(self, model: Any, 
                    start_date: str, end_date: str, 
                    initial_capital: float = 100000000) -> Dict[str, Any]:
        """
        백테스트 실행
        
        Args:
            model: 모델
            start_date: 시작 날짜
            end_date: 종료 날짜
            initial_capital: 초기 자본
            
        Returns:
            백테스트 결과
        """
        pass
    
    @abstractmethod
    def validate_strategy_performance(self, backtest_result: Dict) -> PerformanceMetrics:
        """전략 성과 검증"""
        pass
    
    @abstractmethod
    def generate_backtest_report(self, backtest_result: Dict) -> str:
        """백테스트 보고서 생성"""
        pass
    
    @abstractmethod
    def compare_strategies(self, strategy_results: List[Dict]) -> Dict[str, Any]:
        """전략 비교"""
        pass
    
    @abstractmethod
    def schedule_daily_backtest(self, model: Any) -> bool:
        """일일 백테스트 스케줄링"""
        pass


class ILearningEngine(ABC):
    """학습 엔진 인터페이스"""
    
    @abstractmethod
    def initialize_learning_system(self, config: Dict[str, Any]) -> bool:
        """
        학습 시스템 초기화
        
        Args:
            config: 설정 딕셔너리
            
        Returns:
            초기화 성공 여부
        """
        pass
    
    @abstractmethod
    def run_full_learning_cycle(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """전체 학습 사이클 실행"""
        pass
    
    @abstractmethod
    def update_models(self, new_data: List[LearningData]) -> bool:
        """모델 업데이트"""
        pass
    
    @abstractmethod
    def get_current_predictions(self, stock_codes: List[str]) -> List[ModelPrediction]:
        """현재 예측 결과 조회"""
        pass
    
    @abstractmethod
    def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태 조회"""
        pass
    
    @abstractmethod
    def deploy_model(self, model: Any, model_name: str) -> bool:
        """모델 배포"""
        pass
    
    @abstractmethod
    def rollback_model(self, model_name: str, version: str) -> bool:
        """모델 롤백"""
        pass 