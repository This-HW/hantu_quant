"""
설정 관련 인터페이스 정의

이 모듈은 설정 시스템을 위한 인터페이스들을 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ConfigSection:
    """설정 섹션"""
    name: str
    settings: Dict[str, Any]
    description: str = ""
    is_sensitive: bool = False  # 민감한 정보 여부 (API 키 등)


@dataclass
class APICredentials:
    """API 자격증명"""
    app_key: str
    app_secret: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires: Optional[datetime] = None
    is_mock: bool = False


@dataclass
class TradingSettings:
    """거래 설정"""
    trade_amount: float
    max_stocks: int
    max_trades_per_day: int
    max_trades_per_stock: int
    market_start_time: str
    market_end_time: str
    stop_loss_rate: float
    target_profit_rate: float
    risk_level: str  # LOW, MEDIUM, HIGH


@dataclass
class ScreeningSettings:
    """스크리닝 설정"""
    fundamental_criteria: Dict[str, float]
    technical_criteria: Dict[str, float]
    momentum_criteria: Dict[str, float]
    min_market_cap: float
    min_volume: int
    exclude_sectors: List[str]


class IConfigProvider(ABC):
    """설정 제공자 인터페이스"""
    
    @abstractmethod
    def get_config(self, section: str, key: str, default: Any = None) -> Any:
        """설정 값 조회"""
        pass
    
    @abstractmethod
    def set_config(self, section: str, key: str, value: Any) -> bool:
        """설정 값 설정"""
        pass
    
    @abstractmethod
    def get_section(self, section: str) -> Optional[ConfigSection]:
        """설정 섹션 조회"""
        pass
    
    @abstractmethod
    def get_all_sections(self) -> List[ConfigSection]:
        """모든 설정 섹션 조회"""
        pass
    
    @abstractmethod
    def reload_config(self) -> bool:
        """설정 재로드"""
        pass
    
    @abstractmethod
    def save_config(self) -> bool:
        """설정 저장"""
        pass
    
    @abstractmethod
    def validate_config(self) -> Dict[str, List[str]]:
        """설정 유효성 검증"""
        pass


class IAPIConfig(ABC):
    """API 설정 인터페이스"""
    
    @abstractmethod
    def get_credentials(self, environment: str = "prod") -> APICredentials:
        """API 자격증명 조회"""
        pass
    
    @abstractmethod
    def set_credentials(self, credentials: APICredentials, environment: str = "prod") -> bool:
        """API 자격증명 설정"""
        pass
    
    @abstractmethod
    def get_base_url(self, environment: str = "prod") -> str:
        """Base URL 조회"""
        pass
    
    @abstractmethod
    def get_websocket_url(self, environment: str = "prod") -> str:
        """WebSocket URL 조회"""
        pass
    
    @abstractmethod
    def get_rate_limits(self) -> Dict[str, int]:
        """Rate limit 설정 조회"""
        pass
    
    @abstractmethod
    def get_timeout_settings(self) -> Dict[str, int]:
        """타임아웃 설정 조회"""
        pass
    
    @abstractmethod
    def is_mock_mode(self) -> bool:
        """모의 모드 여부 확인"""
        pass
    
    @abstractmethod
    def get_supported_environments(self) -> List[str]:
        """지원되는 환경 목록 조회"""
        pass


class ITradingConfig(ABC):
    """거래 설정 인터페이스"""
    
    @abstractmethod
    def get_trading_settings(self) -> TradingSettings:
        """거래 설정 조회"""
        pass
    
    @abstractmethod
    def set_trading_settings(self, settings: TradingSettings) -> bool:
        """거래 설정 설정"""
        pass
    
    @abstractmethod
    def get_risk_settings(self) -> Dict[str, float]:
        """리스크 설정 조회"""
        pass
    
    @abstractmethod
    def set_risk_settings(self, settings: Dict[str, float]) -> bool:
        """리스크 설정 설정"""
        pass
    
    @abstractmethod
    def get_strategy_settings(self, strategy_name: str) -> Dict[str, Any]:
        """전략 설정 조회"""
        pass
    
    @abstractmethod
    def set_strategy_settings(self, strategy_name: str, settings: Dict[str, Any]) -> bool:
        """전략 설정 설정"""
        pass
    
    @abstractmethod
    def get_market_hours(self) -> Dict[str, str]:
        """시장 운영 시간 조회"""
        pass
    
    @abstractmethod
    def is_trading_allowed(self) -> bool:
        """거래 허용 여부 확인"""
        pass


class IScreeningConfig(ABC):
    """스크리닝 설정 인터페이스"""
    
    @abstractmethod
    def get_screening_settings(self) -> ScreeningSettings:
        """스크리닝 설정 조회"""
        pass
    
    @abstractmethod
    def set_screening_settings(self, settings: ScreeningSettings) -> bool:
        """스크리닝 설정 설정"""
        pass
    
    @abstractmethod
    def get_fundamental_criteria(self) -> Dict[str, float]:
        """재무 스크리닝 기준 조회"""
        pass
    
    @abstractmethod
    def set_fundamental_criteria(self, criteria: Dict[str, float]) -> bool:
        """재무 스크리닝 기준 설정"""
        pass
    
    @abstractmethod
    def get_technical_criteria(self) -> Dict[str, float]:
        """기술적 스크리닝 기준 조회"""
        pass
    
    @abstractmethod
    def set_technical_criteria(self, criteria: Dict[str, float]) -> bool:
        """기술적 스크리닝 기준 설정"""
        pass
    
    @abstractmethod
    def get_exclusion_rules(self) -> Dict[str, List[str]]:
        """제외 규칙 조회"""
        pass
    
    @abstractmethod
    def set_exclusion_rules(self, rules: Dict[str, List[str]]) -> bool:
        """제외 규칙 설정"""
        pass


class IEnvironmentConfig(ABC):
    """환경 설정 인터페이스"""
    
    @abstractmethod
    def get_current_environment(self) -> str:
        """현재 환경 조회"""
        pass
    
    @abstractmethod
    def set_environment(self, environment: str) -> bool:
        """환경 설정"""
        pass
    
    @abstractmethod
    def get_environment_config(self, environment: str) -> Dict[str, Any]:
        """환경별 설정 조회"""
        pass
    
    @abstractmethod
    def is_production(self) -> bool:
        """운영 환경 여부 확인"""
        pass
    
    @abstractmethod
    def is_development(self) -> bool:
        """개발 환경 여부 확인"""
        pass
    
    @abstractmethod
    def is_testing(self) -> bool:
        """테스트 환경 여부 확인"""
        pass


class ISecurityConfig(ABC):
    """보안 설정 인터페이스"""
    
    @abstractmethod
    def encrypt_sensitive_data(self, data: str) -> str:
        """민감 데이터 암호화"""
        pass
    
    @abstractmethod
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """민감 데이터 복호화"""
        pass
    
    @abstractmethod
    def mask_sensitive_data(self, data: str) -> str:
        """민감 데이터 마스킹"""
        pass
    
    @abstractmethod
    def validate_api_key(self, api_key: str) -> bool:
        """API 키 유효성 검증"""
        pass
    
    @abstractmethod
    def get_encryption_key(self) -> str:
        """암호화 키 조회"""
        pass
    
    @abstractmethod
    def rotate_encryption_key(self) -> bool:
        """암호화 키 회전"""
        pass


class ILoggingConfig(ABC):
    """로깅 설정 인터페이스"""
    
    @abstractmethod
    def get_log_level(self) -> str:
        """로그 레벨 조회"""
        pass
    
    @abstractmethod
    def set_log_level(self, level: str) -> bool:
        """로그 레벨 설정"""
        pass
    
    @abstractmethod
    def get_log_format(self) -> str:
        """로그 포맷 조회"""
        pass
    
    @abstractmethod
    def get_log_file_path(self) -> str:
        """로그 파일 경로 조회"""
        pass
    
    @abstractmethod
    def should_log_sensitive_data(self) -> bool:
        """민감 데이터 로깅 여부 확인"""
        pass
    
    @abstractmethod
    def get_log_retention_days(self) -> int:
        """로그 보존 기간 조회"""
        pass 