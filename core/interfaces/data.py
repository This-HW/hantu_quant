"""
데이터 관련 인터페이스 정의

이 모듈은 데이터 저장소와 데이터 모델을 위한 인터페이스들을 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum


class DataType(Enum):
    """데이터 타입"""
    STOCK_INFO = "STOCK_INFO"
    PRICE_DATA = "PRICE_DATA"
    FINANCIAL_DATA = "FINANCIAL_DATA"
    TECHNICAL_DATA = "TECHNICAL_DATA"
    MARKET_DATA = "MARKET_DATA"
    ORDER_DATA = "ORDER_DATA"
    POSITION_DATA = "POSITION_DATA"


@dataclass
class StockInfo:
    """종목 정보"""
    stock_code: str
    stock_name: str
    market: str
    sector: str
    industry: str
    market_cap: float
    listed_date: date
    is_active: bool = True
    updated_at: datetime = None


@dataclass
class PriceData:
    """가격 데이터"""
    stock_code: str
    date: date
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
    trading_value: float
    change_rate: float
    updated_at: datetime = None


@dataclass
class FinancialData:
    """재무 데이터"""
    stock_code: str
    report_date: date
    quarter: str
    revenue: float
    operating_income: float
    net_income: float
    total_assets: float
    total_liabilities: float
    equity: float
    roe: float
    roa: float
    per: float
    pbr: float
    debt_ratio: float
    updated_at: datetime = None


@dataclass
class TechnicalData:
    """기술적 데이터"""
    stock_code: str
    date: date
    rsi: float
    macd: float
    macd_signal: float
    macd_histogram: float
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    bb_upper: float
    bb_middle: float
    bb_lower: float
    volume_ratio: float
    updated_at: datetime = None


class IDataRepository(ABC):
    """데이터 저장소 인터페이스"""
    
    @abstractmethod
    def save(self, data: Any, data_type: DataType) -> bool:
        """데이터 저장"""
        pass
    
    @abstractmethod
    def get(self, key: str, data_type: DataType) -> Optional[Any]:
        """데이터 조회"""
        pass
    
    @abstractmethod
    def update(self, key: str, data: Any, data_type: DataType) -> bool:
        """데이터 업데이트"""
        pass
    
    @abstractmethod
    def delete(self, key: str, data_type: DataType) -> bool:
        """데이터 삭제"""
        pass
    
    @abstractmethod
    def exists(self, key: str, data_type: DataType) -> bool:
        """데이터 존재 여부 확인"""
        pass
    
    @abstractmethod
    def get_all(self, data_type: DataType, filters: Dict[str, Any] = None) -> List[Any]:
        """모든 데이터 조회"""
        pass


class IStockDataRepository(IDataRepository):
    """종목 데이터 저장소 인터페이스"""
    
    @abstractmethod
    def save_stock_info(self, stock_info: StockInfo) -> bool:
        """종목 정보 저장"""
        pass
    
    @abstractmethod
    def get_stock_info(self, stock_code: str) -> Optional[StockInfo]:
        """종목 정보 조회"""
        pass
    
    @abstractmethod
    def get_all_stocks(self, market: str = None, sector: str = None) -> List[StockInfo]:
        """모든 종목 조회"""
        pass
    
    @abstractmethod
    def update_stock_info(self, stock_code: str, stock_info: StockInfo) -> bool:
        """종목 정보 업데이트"""
        pass
    
    @abstractmethod
    def search_stocks(self, query: str, search_type: str = "name") -> List[StockInfo]:
        """종목 검색"""
        pass


class IPriceDataRepository(IDataRepository):
    """가격 데이터 저장소 인터페이스"""
    
    @abstractmethod
    def save_price_data(self, price_data: PriceData) -> bool:
        """가격 데이터 저장"""
        pass
    
    @abstractmethod
    def get_price_data(self, stock_code: str, date: date) -> Optional[PriceData]:
        """가격 데이터 조회"""
        pass
    
    @abstractmethod
    def get_price_history(self, stock_code: str, start_date: date, end_date: date) -> List[PriceData]:
        """가격 히스토리 조회"""
        pass
    
    @abstractmethod
    def get_latest_price(self, stock_code: str) -> Optional[PriceData]:
        """최신 가격 조회"""
        pass
    
    @abstractmethod
    def get_price_dataframe(self, stock_code: str, start_date: date, end_date: date) -> pd.DataFrame:
        """가격 데이터프레임 조회"""
        pass
    
    @abstractmethod
    def bulk_save_price_data(self, price_data_list: List[PriceData]) -> bool:
        """가격 데이터 일괄 저장"""
        pass


class IFinancialDataRepository(IDataRepository):
    """재무 데이터 저장소 인터페이스"""
    
    @abstractmethod
    def save_financial_data(self, financial_data: FinancialData) -> bool:
        """재무 데이터 저장"""
        pass
    
    @abstractmethod
    def get_financial_data(self, stock_code: str, report_date: date) -> Optional[FinancialData]:
        """재무 데이터 조회"""
        pass
    
    @abstractmethod
    def get_financial_history(self, stock_code: str, years: int = 3) -> List[FinancialData]:
        """재무 히스토리 조회"""
        pass
    
    @abstractmethod
    def get_latest_financial_data(self, stock_code: str) -> Optional[FinancialData]:
        """최신 재무 데이터 조회"""
        pass
    
    @abstractmethod
    def get_financial_ratios(self, stock_code: str) -> Dict[str, float]:
        """재무 비율 조회"""
        pass


class ITechnicalDataRepository(IDataRepository):
    """기술적 데이터 저장소 인터페이스"""
    
    @abstractmethod
    def save_technical_data(self, technical_data: TechnicalData) -> bool:
        """기술적 데이터 저장"""
        pass
    
    @abstractmethod
    def get_technical_data(self, stock_code: str, date: date) -> Optional[TechnicalData]:
        """기술적 데이터 조회"""
        pass
    
    @abstractmethod
    def get_technical_history(self, stock_code: str, start_date: date, end_date: date) -> List[TechnicalData]:
        """기술적 데이터 히스토리 조회"""
        pass
    
    @abstractmethod
    def get_latest_technical_data(self, stock_code: str) -> Optional[TechnicalData]:
        """최신 기술적 데이터 조회"""
        pass
    
    @abstractmethod
    def calculate_and_save_indicators(self, stock_code: str, price_data: List[PriceData]) -> bool:
        """지표 계산 및 저장"""
        pass


class IDataCache(ABC):
    """데이터 캐시 인터페이스"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """캐시 조회"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """캐시 설정"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """캐시 삭제"""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """캐시 존재 여부 확인"""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """캐시 전체 삭제"""
        pass
    
    @abstractmethod
    def get_ttl(self, key: str) -> int:
        """캐시 TTL 조회"""
        pass
    
    @abstractmethod
    def set_ttl(self, key: str, ttl: int) -> bool:
        """캐시 TTL 설정"""
        pass


class IDataValidator(ABC):
    """데이터 유효성 검증 인터페이스"""
    
    @abstractmethod
    def validate_stock_info(self, stock_info: StockInfo) -> Tuple[bool, List[str]]:
        """종목 정보 유효성 검증"""
        pass
    
    @abstractmethod
    def validate_price_data(self, price_data: PriceData) -> Tuple[bool, List[str]]:
        """가격 데이터 유효성 검증"""
        pass
    
    @abstractmethod
    def validate_financial_data(self, financial_data: FinancialData) -> Tuple[bool, List[str]]:
        """재무 데이터 유효성 검증"""
        pass
    
    @abstractmethod
    def validate_technical_data(self, technical_data: TechnicalData) -> Tuple[bool, List[str]]:
        """기술적 데이터 유효성 검증"""
        pass
    
    @abstractmethod
    def validate_data_consistency(self, data_list: List[Any]) -> Tuple[bool, List[str]]:
        """데이터 일관성 검증"""
        pass


class IDataTransformer(ABC):
    """데이터 변환 인터페이스"""
    
    @abstractmethod
    def transform_to_dataframe(self, data: List[Any]) -> pd.DataFrame:
        """데이터프레임으로 변환"""
        pass
    
    @abstractmethod
    def transform_from_dataframe(self, df: pd.DataFrame, data_type: DataType) -> List[Any]:
        """데이터프레임에서 변환"""
        pass
    
    @abstractmethod
    def normalize_data(self, data: Any) -> Any:
        """데이터 정규화"""
        pass
    
    @abstractmethod
    def aggregate_data(self, data: List[Any], aggregation_type: str) -> Any:
        """데이터 집계"""
        pass
    
    @abstractmethod
    def filter_data(self, data: List[Any], filters: Dict[str, Any]) -> List[Any]:
        """데이터 필터링"""
        pass


class IDataMigrator(ABC):
    """데이터 마이그레이션 인터페이스"""
    
    @abstractmethod
    def migrate_data(self, source_type: str, target_type: str, data: List[Any]) -> bool:
        """데이터 마이그레이션"""
        pass
    
    @abstractmethod
    def backup_data(self, data_type: DataType, backup_path: str) -> bool:
        """데이터 백업"""
        pass
    
    @abstractmethod
    def restore_data(self, data_type: DataType, backup_path: str) -> bool:
        """데이터 복원"""
        pass
    
    @abstractmethod
    def export_data(self, data_type: DataType, export_path: str, format: str = "csv") -> bool:
        """데이터 내보내기"""
        pass
    
    @abstractmethod
    def import_data(self, data_type: DataType, import_path: str, format: str = "csv") -> bool:
        """데이터 가져오기"""
        pass


class IDataMonitor(ABC):
    """데이터 모니터링 인터페이스"""
    
    @abstractmethod
    def monitor_data_quality(self, data_type: DataType) -> Dict[str, Any]:
        """데이터 품질 모니터링"""
        pass
    
    @abstractmethod
    def check_data_freshness(self, data_type: DataType) -> Dict[str, datetime]:
        """데이터 신선도 확인"""
        pass
    
    @abstractmethod
    def monitor_data_volume(self, data_type: DataType) -> Dict[str, int]:
        """데이터 볼륨 모니터링"""
        pass
    
    @abstractmethod
    def detect_data_anomalies(self, data_type: DataType) -> List[Dict[str, Any]]:
        """데이터 이상 탐지"""
        pass
    
    @abstractmethod
    def generate_data_report(self, data_type: DataType) -> Dict[str, Any]:
        """데이터 보고서 생성"""
        pass 