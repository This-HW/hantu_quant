"""
백테스트 자동화 모듈

전략 변경 시 자동으로 백테스트를 실행하고 검증하는 시스템
"""

from .backtest_engine import BacktestEngine, BacktestConfig, BacktestResult
from .validation_system import ValidationSystem, ValidationResult, ValidationCriteria
from .automation_manager import AutomationManager, AutomationConfig, AutomationRule

__all__ = [
    'BacktestEngine',
    'BacktestConfig', 
    'BacktestResult',
    'ValidationSystem',
    'ValidationResult',
    'ValidationCriteria',
    'AutomationManager',
    'AutomationConfig',
    'AutomationRule'
] 