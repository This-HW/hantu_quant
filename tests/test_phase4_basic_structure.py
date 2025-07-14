"""
Phase 4 AI 학습 시스템 기본 구조 테스트 (TODO 2.1)
"""

import unittest
import os
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPhase4BasicStructure(unittest.TestCase):
    """Phase 4 AI 학습 시스템 기본 구조 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.learning_path = Path("core/learning")
    
    def test_directory_structure(self):
        """디렉토리 구조 확인"""
        # 기본 디렉토리 존재 확인
        self.assertTrue(self.learning_path.exists(), "core/learning 디렉토리가 존재하지 않음")
        
        # 서브 디렉토리 존재 확인
        subdirs = ['data', 'features', 'models', 'analysis', 'optimization', 'config', 'utils']
        for subdir in subdirs:
            subdir_path = self.learning_path / subdir
            self.assertTrue(subdir_path.exists(), f"{subdir} 디렉토리가 존재하지 않음")
            
            # __init__.py 파일 존재 확인
            init_file = subdir_path / "__init__.py"
            self.assertTrue(init_file.exists(), f"{subdir}/__init__.py 파일이 존재하지 않음")
    
    def test_config_system(self):
        """설정 시스템 확인"""
        try:
            from core.learning.config.settings import LearningConfig, get_learning_config
            
            # 설정 인스턴스 생성 확인
            config = LearningConfig()
            self.assertIsNotNone(config)
            
            # 기본 설정 값 확인
            self.assertEqual(config.version, "1.0.0")
            self.assertEqual(config.n_jobs, 4)
            self.assertEqual(config.target_accuracy, 0.90)
            
            # 전역 설정 함수 확인
            global_config = get_learning_config()
            self.assertIsNotNone(global_config)
            
        except ImportError as e:
            self.fail(f"설정 시스템 import 실패: {e}")
    
    def test_logging_system(self):
        """로깅 시스템 확인"""
        try:
            from core.learning.utils.logging import get_learning_logger, log_learning_event
            
            # 로거 생성 확인
            logger = get_learning_logger("test")
            self.assertIsNotNone(logger)
            
            # 로그 이벤트 함수 확인
            log_learning_event("test", "테스트 메시지", "test_module")
            
        except ImportError as e:
            self.fail(f"로깅 시스템 import 실패: {e}")
    
    def test_learning_interfaces(self):
        """AI 학습 인터페이스 확인"""
        try:
            from core.interfaces.learning import (
                ILearningDataCollector, IFeatureEngineer, IModelTrainer,
                IPerformanceAnalyzer, IPatternLearner, IParameterOptimizer,
                IBacktestAutomation, ILearningEngine,
                LearningData, FeatureSet, ModelPrediction, PerformanceMetrics,
                PatternResult, OptimizationResult, ModelType, LearningPhase
            )
            
            # 인터페이스 클래스 확인
            interfaces = [
                ILearningDataCollector, IFeatureEngineer, IModelTrainer,
                IPerformanceAnalyzer, IPatternLearner, IParameterOptimizer,
                IBacktestAutomation, ILearningEngine
            ]
            
            for interface in interfaces:
                self.assertTrue(hasattr(interface, '__abstractmethods__'), 
                              f"{interface.__name__}가 ABC 인터페이스가 아님")
            
            # 데이터 클래스 확인
            data_classes = [
                LearningData, FeatureSet, ModelPrediction, PerformanceMetrics,
                PatternResult, OptimizationResult
            ]
            
            for data_class in data_classes:
                self.assertTrue(hasattr(data_class, '__dataclass_fields__'), 
                              f"{data_class.__name__}가 데이터클래스가 아님")
            
            # 열거형 확인
            self.assertTrue(hasattr(ModelType, 'RANDOM_FOREST'), "ModelType 열거형 확인 실패")
            self.assertTrue(hasattr(LearningPhase, 'DATA_COLLECTION'), "LearningPhase 열거형 확인 실패")
            
        except ImportError as e:
            self.fail(f"학습 인터페이스 import 실패: {e}")
    
    def test_interfaces_integration(self):
        """인터페이스 통합 확인"""
        try:
            from core.interfaces import (
                ILearningDataCollector, IFeatureEngineer, IModelTrainer,
                LearningData, FeatureSet, ModelPrediction, ModelType
            )
            
            # 통합된 인터페이스 import 확인
            self.assertIsNotNone(ILearningDataCollector)
            self.assertIsNotNone(IFeatureEngineer)
            self.assertIsNotNone(IModelTrainer)
            self.assertIsNotNone(LearningData)
            self.assertIsNotNone(FeatureSet)
            self.assertIsNotNone(ModelPrediction)
            self.assertIsNotNone(ModelType)
            
        except ImportError as e:
            self.fail(f"통합 인터페이스 import 실패: {e}")
    
    def test_data_storage_system(self):
        """데이터 저장소 시스템 확인"""
        try:
            from core.learning.data.storage import LearningDataStorage, get_learning_storage
            
            # 데이터 저장소 클래스 확인
            self.assertTrue(hasattr(LearningDataStorage, 'save_learning_data'))
            self.assertTrue(hasattr(LearningDataStorage, 'load_learning_data'))
            self.assertTrue(hasattr(LearningDataStorage, 'save_feature_set'))
            self.assertTrue(hasattr(LearningDataStorage, 'save_model'))
            self.assertTrue(hasattr(LearningDataStorage, 'save_performance_metrics'))
            
            # 전역 저장소 함수 확인
            storage = get_learning_storage()
            self.assertIsNotNone(storage)
            
        except ImportError as e:
            self.fail(f"데이터 저장소 시스템 import 실패: {e}")
    
    def test_learning_module_initialization(self):
        """학습 모듈 초기화 확인"""
        try:
            import core.learning
            
            # 모듈 버전 확인
            self.assertEqual(core.learning.__version__, "1.0.0")
            self.assertEqual(core.learning.__author__, "HantuQuant")
            
            # 모듈 카테고리 확인
            self.assertIn('data', core.learning.MODULE_CATEGORIES)
            self.assertIn('features', core.learning.MODULE_CATEGORIES)
            self.assertIn('models', core.learning.MODULE_CATEGORIES)
            self.assertIn('analysis', core.learning.MODULE_CATEGORIES)
            self.assertIn('optimization', core.learning.MODULE_CATEGORIES)
            
            # 플러그인 카테고리 확인
            self.assertEqual(core.learning.PLUGIN_CATEGORY, "learning")
            
        except ImportError as e:
            self.fail(f"학습 모듈 초기화 실패: {e}")


if __name__ == '__main__':
    unittest.main() 