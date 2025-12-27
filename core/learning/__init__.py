"""
Phase 4: AI 학습 시스템 메인 모듈
새로운 아키텍처 기반 AI 학습 시스템 구현
"""

from .config.settings import LearningConfig
from .utils.logging import get_learning_logger

# 학습 시스템 모듈
from .trade_logger import (
    TradeLogger,
    TradeLog,
    Trade,
    TradeContext,
    EntryContext,
    ExitContext,
    TradeLabels,
    ExitReason,
    MarketRegime,
)
from .performance_pattern_analyzer import (
    PerformancePatternAnalyzer,
    PatternAnalysis,
    WinningConditions,
    LosingConditions,
    OptimalRange,
)
from .failure_analyzer import (
    FailureAnalyzer,
    FailureAnalysis,
    FailureType,
    FailureTypeAnalysis,
    Improvement,
    CommonMistake,
)
from .lstm_learner import (
    LSTMContinuousLearner,
    LearnerConfig,
    RetrainDecision,
    RetrainResult,
    RetrainUrgency,
    ModelMetrics,
)
from .scheduler import (
    LearningScheduler,
    SchedulerRunner,
    ScheduledTask,
    TaskResult,
    TaskPriority,
    TaskStatus,
)
from .tracker import (
    LearningTracker,
    LearningRecord,
    LearningType,
    LearningEffectivenessReport,
    TypeEffectiveness,
)
from .safety import (
    LearningSafetyManager,
    OverfitPrevention,
    ModelRollback,
    SafetyConfig,
    ValidationResult,
    ValidationCheck,
    RollbackDecision,
    LearningResult,
)

__version__ = "2.0.0"
__author__ = "HantuQuant"
__description__ = "Phase 4 AI 학습 시스템 - 지속 학습 및 안전장치 포함"

# 메인 로거 설정
logger = get_learning_logger(__name__)

# 모듈 카테고리 정의
MODULE_CATEGORIES = {
    'data': '데이터 수집 및 전처리',
    'features': '피처 엔지니어링',
    'models': '머신러닝 모델',
    'rl': '강화학습',
    'analysis': '성과 및 패턴 분석',
    'optimization': '최적화 및 백테스트',
    'config': '설정 관리',
    'utils': '유틸리티',
    'learning': '지속 학습 시스템',
    'safety': '학습 안전장치',
}

# 플러그인 카테고리 등록
PLUGIN_CATEGORY = "learning"

logger.info(f"Phase 4 AI 학습 시스템 v{__version__} 초기화 완료")

# ML 자동 트리거 시스템 export (B단계 자동 시작용)
__all__ = [
    # Config
    'LearningConfig',
    'get_learning_logger',
    'MODULE_CATEGORIES',
    'PLUGIN_CATEGORY',
    # Trade Logging
    'TradeLogger',
    'TradeLog',
    'Trade',
    'TradeContext',
    'EntryContext',
    'ExitContext',
    'TradeLabels',
    'ExitReason',
    'MarketRegime',
    # Performance Analysis
    'PerformancePatternAnalyzer',
    'PatternAnalysis',
    'WinningConditions',
    'LosingConditions',
    'OptimalRange',
    # Failure Analysis
    'FailureAnalyzer',
    'FailureAnalysis',
    'FailureType',
    'FailureTypeAnalysis',
    'Improvement',
    'CommonMistake',
    # LSTM Learning
    'LSTMContinuousLearner',
    'LearnerConfig',
    'RetrainDecision',
    'RetrainResult',
    'RetrainUrgency',
    'ModelMetrics',
    # Scheduler
    'LearningScheduler',
    'SchedulerRunner',
    'ScheduledTask',
    'TaskResult',
    'TaskPriority',
    'TaskStatus',
    # Tracker
    'LearningTracker',
    'LearningRecord',
    'LearningType',
    'LearningEffectivenessReport',
    'TypeEffectiveness',
    # Safety
    'LearningSafetyManager',
    'OverfitPrevention',
    'ModelRollback',
    'SafetyConfig',
    'ValidationResult',
    'ValidationCheck',
    'RollbackDecision',
    'LearningResult',
]

# Auto ML Trigger는 독립적으로 import 가능
# from core.learning.auto_ml_trigger import get_auto_ml_trigger 