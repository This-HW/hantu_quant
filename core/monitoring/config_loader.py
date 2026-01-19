"""
모니터링 설정 로더

Feature 3.1: 모니터링 설정 외부화
- T-3.1.1: SystemMonitor 임계값 설정 파일화
- T-3.1.2: 환경별 임계값 프로필 지원
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "config/monitoring_config.yaml"


@dataclass
class ThresholdConfig:
    """임계값 설정"""
    warning: float = 0
    error: float = 0
    critical: float = 0


@dataclass
class ResourceThresholds:
    """리소스 임계값"""
    cpu: ThresholdConfig = field(default_factory=lambda: ThresholdConfig(70, 80, 90))
    memory: ThresholdConfig = field(default_factory=lambda: ThresholdConfig(75, 85, 95))
    disk: ThresholdConfig = field(default_factory=lambda: ThresholdConfig(80, 90, 95))


@dataclass
class APIThresholds:
    """API 임계값"""
    error_rate: ThresholdConfig = field(default_factory=lambda: ThresholdConfig(5, 10, 20))
    latency_ms: ThresholdConfig = field(default_factory=lambda: ThresholdConfig(1000, 3000, 5000))
    rate_limit: ThresholdConfig = field(default_factory=lambda: ThresholdConfig(70, 85, 95))


@dataclass
class TradingThresholds:
    """트레이딩 임계값"""
    drawdown_percent: ThresholdConfig = field(default_factory=lambda: ThresholdConfig(3, 7, 15))
    daily_loss_percent: ThresholdConfig = field(default_factory=lambda: ThresholdConfig(2, 5, 10))
    position_limit: ThresholdConfig = field(default_factory=lambda: ThresholdConfig(80, 90, 100))


@dataclass
class MonitoringIntervals:
    """모니터링 간격 (초)"""
    system_check: int = 60
    api_health: int = 30
    trading_status: int = 10
    anomaly_detection: int = 300


@dataclass
class AlertingConfig:
    """알림 설정"""
    cooldown_minutes: int = 5
    max_alerts_per_hour: int = 20
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"


@dataclass
class MonitoringConfig:
    """통합 모니터링 설정"""
    thresholds: ResourceThresholds = field(default_factory=ResourceThresholds)
    api: APIThresholds = field(default_factory=APIThresholds)
    trading: TradingThresholds = field(default_factory=TradingThresholds)
    intervals: MonitoringIntervals = field(default_factory=MonitoringIntervals)
    alerting: AlertingConfig = field(default_factory=AlertingConfig)
    profile: str = "default"


class MonitoringConfigLoader:
    """
    모니터링 설정 로더

    YAML 파일에서 환경별 설정을 로드합니다.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._config: Optional[MonitoringConfig] = None
        self._raw_config: Optional[Dict[str, Any]] = None

    def load(self, profile: Optional[str] = None) -> MonitoringConfig:
        """
        설정 로드

        Args:
            profile: 환경 프로필 (development, staging, production)
                     None이면 HANTU_ENV 환경변수 또는 default 사용

        Returns:
            MonitoringConfig 인스턴스
        """
        # 프로필 결정
        profile = profile or os.getenv("HANTU_ENV", "default")

        # YAML 파일 로드
        self._raw_config = self._load_yaml()

        if self._raw_config is None:
            logger.warning("Config file not found, using defaults")
            self._config = MonitoringConfig(profile=profile)
            return self._config

        # 기본 설정 로드
        default_config = self._raw_config.get("default", {})

        # 프로필 설정 병합
        profile_config = self._raw_config.get(profile, {})
        merged_config = self._deep_merge(default_config, profile_config)

        # MonitoringConfig 객체 생성
        self._config = self._build_config(merged_config, profile)

        logger.info(f"Monitoring config loaded with profile: {profile}")
        return self._config

    def _load_yaml(self) -> Optional[Dict[str, Any]]:
        """YAML 파일 로드"""
        if not HAS_YAML:
            logger.warning("PyYAML not installed")
            return None

        if not os.path.exists(self._config_path):
            return None

        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}", exc_info=True)
            return None

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """딕셔너리 깊은 병합"""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _build_config(self, data: Dict[str, Any], profile: str) -> MonitoringConfig:
        """설정 객체 빌드"""
        thresholds_data = data.get("thresholds", {})
        api_data = data.get("api", {})
        trading_data = data.get("trading", {})
        intervals_data = data.get("intervals", {})
        alerting_data = data.get("alerting", {})

        return MonitoringConfig(
            thresholds=ResourceThresholds(
                cpu=self._build_threshold(thresholds_data.get("cpu", {})),
                memory=self._build_threshold(thresholds_data.get("memory", {})),
                disk=self._build_threshold(thresholds_data.get("disk", {})),
            ),
            api=APIThresholds(
                error_rate=self._build_threshold(api_data.get("error_rate", {})),
                latency_ms=self._build_threshold(api_data.get("latency_ms", {})),
                rate_limit=self._build_threshold(api_data.get("rate_limit", {})),
            ),
            trading=TradingThresholds(
                drawdown_percent=self._build_threshold(trading_data.get("drawdown_percent", {})),
                daily_loss_percent=self._build_threshold(trading_data.get("daily_loss_percent", {})),
                position_limit=self._build_threshold(trading_data.get("position_limit", {})),
            ),
            intervals=MonitoringIntervals(
                system_check=intervals_data.get("system_check", 60),
                api_health=intervals_data.get("api_health", 30),
                trading_status=intervals_data.get("trading_status", 10),
                anomaly_detection=intervals_data.get("anomaly_detection", 300),
            ),
            alerting=AlertingConfig(
                cooldown_minutes=alerting_data.get("cooldown_minutes", 5),
                max_alerts_per_hour=alerting_data.get("max_alerts_per_hour", 20),
                quiet_hours_enabled=alerting_data.get("quiet_hours", {}).get("enabled", False),
                quiet_hours_start=alerting_data.get("quiet_hours", {}).get("start", "22:00"),
                quiet_hours_end=alerting_data.get("quiet_hours", {}).get("end", "08:00"),
            ),
            profile=profile,
        )

    def _build_threshold(self, data: Dict[str, float]) -> ThresholdConfig:
        """ThresholdConfig 빌드"""
        return ThresholdConfig(
            warning=data.get("warning", 0),
            error=data.get("error", 0),
            critical=data.get("critical", 0),
        )

    def get_config(self) -> MonitoringConfig:
        """캐시된 설정 반환"""
        if self._config is None:
            self.load()
        return self._config

    def get_threshold(self, category: str, metric: str) -> ThresholdConfig:
        """
        특정 임계값 조회

        Args:
            category: 카테고리 (cpu, memory, disk, error_rate, etc.)
            metric: 메트릭 이름

        Returns:
            ThresholdConfig
        """
        config = self.get_config()

        # 리소스 임계값
        if hasattr(config.thresholds, category):
            return getattr(config.thresholds, category)

        # API 임계값
        if hasattr(config.api, category):
            return getattr(config.api, category)

        # 트레이딩 임계값
        if hasattr(config.trading, category):
            return getattr(config.trading, category)

        return ThresholdConfig()


# 글로벌 인스턴스
_config_loader: Optional[MonitoringConfigLoader] = None


def get_monitoring_config(
    config_path: Optional[str] = None,
    profile: Optional[str] = None,
) -> MonitoringConfig:
    """
    모니터링 설정 가져오기

    Args:
        config_path: 설정 파일 경로
        profile: 환경 프로필

    Returns:
        MonitoringConfig 인스턴스
    """
    global _config_loader

    if _config_loader is None or config_path is not None:
        _config_loader = MonitoringConfigLoader(config_path)

    return _config_loader.load(profile)


def reload_monitoring_config(profile: Optional[str] = None) -> MonitoringConfig:
    """설정 다시 로드"""
    global _config_loader
    _config_loader = MonitoringConfigLoader()
    return _config_loader.load(profile)
