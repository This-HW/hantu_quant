"""
섹터 분류 및 매핑 모듈

한국 시장의 섹터 분류와 종목-섹터 매핑을 정의합니다.
"""

from enum import Enum
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field


class Sector(Enum):
    """한국 시장 섹터 분류"""
    # 대형 섹터
    SEMICONDUCTOR = "반도체"
    ELECTRONICS = "전자/전기"
    AUTOMOTIVE = "자동차"
    CHEMICAL = "화학"
    STEEL = "철강/금속"
    CONSTRUCTION = "건설"
    SHIPBUILDING = "조선"

    # 금융
    BANK = "은행"
    SECURITIES = "증권"
    INSURANCE = "보험"

    # 소비재
    RETAIL = "유통/소매"
    FOOD = "음식료"
    COSMETICS = "화장품/생활용품"

    # 헬스케어
    PHARMA = "제약"
    BIO = "바이오"
    MEDICAL = "의료기기"

    # 기술/성장
    IT_SOFTWARE = "IT/소프트웨어"
    INTERNET = "인터넷/플랫폼"
    GAME = "게임"
    ENTERTAINMENT = "엔터테인먼트"

    # 에너지/유틸리티
    ENERGY = "에너지"
    UTILITY = "유틸리티"

    # 기타
    TELECOM = "통신"
    TRANSPORT = "운송"
    OTHER = "기타"


# KOSPI 대표 종목 섹터 매핑
KOSPI_SECTORS: Dict[str, Dict] = {
    # 반도체
    "005930": {"name": "삼성전자", "sector": Sector.SEMICONDUCTOR, "weight": 0.25},
    "000660": {"name": "SK하이닉스", "sector": Sector.SEMICONDUCTOR, "weight": 0.08},

    # 전자/전기
    "066570": {"name": "LG전자", "sector": Sector.ELECTRONICS, "weight": 0.02},
    "006400": {"name": "삼성SDI", "sector": Sector.ELECTRONICS, "weight": 0.03},
    "051910": {"name": "LG화학", "sector": Sector.CHEMICAL, "weight": 0.03},

    # 자동차
    "005380": {"name": "현대차", "sector": Sector.AUTOMOTIVE, "weight": 0.04},
    "000270": {"name": "기아", "sector": Sector.AUTOMOTIVE, "weight": 0.03},
    "012330": {"name": "현대모비스", "sector": Sector.AUTOMOTIVE, "weight": 0.02},

    # 화학
    "051900": {"name": "LG생활건강", "sector": Sector.COSMETICS, "weight": 0.01},

    # 철강
    "005490": {"name": "POSCO홀딩스", "sector": Sector.STEEL, "weight": 0.02},

    # 금융
    "105560": {"name": "KB금융", "sector": Sector.BANK, "weight": 0.02},
    "055550": {"name": "신한지주", "sector": Sector.BANK, "weight": 0.02},
    "086790": {"name": "하나금융지주", "sector": Sector.BANK, "weight": 0.01},

    # 통신
    "017670": {"name": "SK텔레콤", "sector": Sector.TELECOM, "weight": 0.01},
    "030200": {"name": "KT", "sector": Sector.TELECOM, "weight": 0.01},

    # 바이오/제약
    "207940": {"name": "삼성바이오로직스", "sector": Sector.BIO, "weight": 0.04},
    "068270": {"name": "셀트리온", "sector": Sector.BIO, "weight": 0.02},

    # 인터넷
    "035720": {"name": "카카오", "sector": Sector.INTERNET, "weight": 0.02},
    "035420": {"name": "NAVER", "sector": Sector.INTERNET, "weight": 0.03},

    # 게임/엔터
    "263750": {"name": "펄어비스", "sector": Sector.GAME, "weight": 0.005},
    "251270": {"name": "넷마블", "sector": Sector.GAME, "weight": 0.005},
    "352820": {"name": "하이브", "sector": Sector.ENTERTAINMENT, "weight": 0.01},

    # 유통
    "004170": {"name": "신세계", "sector": Sector.RETAIL, "weight": 0.005},

    # 건설
    "000720": {"name": "현대건설", "sector": Sector.CONSTRUCTION, "weight": 0.005},

    # 조선
    "009540": {"name": "HD한국조선해양", "sector": Sector.SHIPBUILDING, "weight": 0.01},

    # 에너지
    "096770": {"name": "SK이노베이션", "sector": Sector.ENERGY, "weight": 0.01},
}


@dataclass
class SectorInfo:
    """섹터 정보"""
    sector: Sector
    stocks: List[str] = field(default_factory=list)
    total_weight: float = 0.0
    stock_count: int = 0


class SectorMap:
    """
    섹터 매핑 관리자

    종목과 섹터 간의 매핑을 관리합니다.
    """

    def __init__(self, custom_mapping: Optional[Dict[str, Dict]] = None):
        """
        Args:
            custom_mapping: 사용자 정의 종목-섹터 매핑
        """
        self._mapping = custom_mapping or KOSPI_SECTORS
        self._sector_stocks: Dict[Sector, List[str]] = {}
        self._build_sector_index()

    def _build_sector_index(self):
        """섹터별 종목 인덱스 구축"""
        self._sector_stocks = {sector: [] for sector in Sector}

        for stock_code, info in self._mapping.items():
            sector = info.get('sector', Sector.OTHER)
            self._sector_stocks[sector].append(stock_code)

    def get_sector(self, stock_code: str) -> Sector:
        """종목의 섹터 조회"""
        info = self._mapping.get(stock_code)
        return info['sector'] if info else Sector.OTHER

    def get_stocks_in_sector(self, sector: Sector) -> List[str]:
        """섹터의 종목 리스트 조회"""
        return self._sector_stocks.get(sector, [])

    def get_sector_info(self, sector: Sector) -> SectorInfo:
        """섹터 상세 정보 조회"""
        stocks = self.get_stocks_in_sector(sector)
        total_weight = sum(
            self._mapping.get(code, {}).get('weight', 0)
            for code in stocks
        )

        return SectorInfo(
            sector=sector,
            stocks=stocks,
            total_weight=total_weight,
            stock_count=len(stocks)
        )

    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """종목 정보 조회"""
        return self._mapping.get(stock_code)

    def get_all_sectors(self) -> List[Sector]:
        """모든 섹터 조회"""
        return [s for s in Sector if self._sector_stocks.get(s)]

    def get_active_sectors(self) -> List[Sector]:
        """활성 섹터 조회 (종목이 있는 섹터만)"""
        return [s for s in Sector if len(self._sector_stocks.get(s, [])) > 0]

    def add_stock(
        self,
        stock_code: str,
        name: str,
        sector: Sector,
        weight: float = 0.0
    ):
        """종목 추가"""
        self._mapping[stock_code] = {
            'name': name,
            'sector': sector,
            'weight': weight
        }
        self._sector_stocks[sector].append(stock_code)

    def remove_stock(self, stock_code: str):
        """종목 제거"""
        if stock_code in self._mapping:
            sector = self._mapping[stock_code]['sector']
            del self._mapping[stock_code]
            if stock_code in self._sector_stocks[sector]:
                self._sector_stocks[sector].remove(stock_code)

    def get_sector_weights(self) -> Dict[Sector, float]:
        """섹터별 시가총액 가중치"""
        weights = {}
        for sector in self.get_active_sectors():
            stocks = self.get_stocks_in_sector(sector)
            weight = sum(
                self._mapping.get(code, {}).get('weight', 0)
                for code in stocks
            )
            weights[sector] = weight
        return weights

    def filter_by_sectors(
        self,
        sectors: List[Sector]
    ) -> Dict[str, Dict]:
        """특정 섹터의 종목만 필터링"""
        result = {}
        for code, info in self._mapping.items():
            if info.get('sector') in sectors:
                result[code] = info
        return result

    def get_sector_statistics(self) -> Dict[str, any]:
        """섹터 통계"""
        stats = {
            'total_stocks': len(self._mapping),
            'total_sectors': len(self.get_active_sectors()),
            'sectors': {}
        }

        for sector in self.get_active_sectors():
            info = self.get_sector_info(sector)
            stats['sectors'][sector.value] = {
                'stock_count': info.stock_count,
                'total_weight': info.total_weight,
                'stocks': [self._mapping[s]['name'] for s in info.stocks[:5]]
            }

        return stats
