"""
시장 지표 수집기

Task C.1.1: MarketIndicatorCollector 클래스 생성
Task C.1.2: 주요 지수 데이터 수집 (KOSPI, KOSDAQ)
Task C.1.3: 시장 폭 지표 계산
Task C.1.4: 변동성 지표 계산
"""

import json
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class MarketIndicators:
    """시장 지표 데이터"""
    # 수집 시점
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 주요 지수 (C.1.2)
    kospi_price: float = 0.0              # KOSPI 현재가
    kospi_change: float = 0.0             # KOSPI 전일 대비 변동률
    kospi_5d_return: float = 0.0          # 5일 수익률
    kospi_20d_return: float = 0.0         # 20일 수익률
    kospi_60d_return: float = 0.0         # 60일 수익률

    kosdaq_price: float = 0.0             # KOSDAQ 현재가
    kosdaq_change: float = 0.0            # KOSDAQ 전일 대비 변동률
    kosdaq_20d_return: float = 0.0        # 20일 수익률

    # 이동평균 대비 위치
    kospi_vs_ma20: float = 0.0            # 20일 이평 대비 (%)
    kospi_vs_ma60: float = 0.0            # 60일 이평 대비 (%)
    kospi_vs_ma200: float = 0.0           # 200일 이평 대비 (%)

    # 시장 폭 지표 (C.1.3)
    advance_count: int = 0                # 상승 종목 수
    decline_count: int = 0                # 하락 종목 수
    unchanged_count: int = 0              # 보합 종목 수
    advance_decline_ratio: float = 1.0    # 등락비

    new_high_count: int = 0               # 52주 신고가 종목 수
    new_low_count: int = 0                # 52주 신저가 종목 수
    new_high_low_ratio: float = 1.0       # 신고/신저 비율

    above_ma20_ratio: float = 0.5         # 20일선 위 종목 비율
    above_ma60_ratio: float = 0.5         # 60일선 위 종목 비율
    above_ma200_ratio: float = 0.5        # 200일선 위 종목 비율

    # 거래량 지표
    volume_ratio: float = 1.0             # 평균 대비 거래량 비율
    volume_ma20_ratio: float = 1.0        # 20일 평균 대비

    # 변동성 지표 (C.1.4)
    market_volatility: float = 0.0        # 시장 변동성 (20일)
    avg_stock_volatility: float = 0.0     # 평균 개별 종목 변동성
    volatility_percentile: float = 50.0   # 변동성 백분위 (과거 대비)

    # 투자심리 지표
    fear_greed_score: float = 50.0        # 공포-탐욕 점수 (0~100)
    put_call_ratio: float = 1.0           # 풋콜 비율

    # 외국인/기관 동향
    foreign_net_buy: float = 0.0          # 외국인 순매수 (억원)
    institution_net_buy: float = 0.0      # 기관 순매수 (억원)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketIndicators':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class MarketIndicatorCollector:
    """시장 지표 수집기"""

    # 캐시 유효 시간 (초)
    CACHE_TTL_SECONDS = 3600  # 1시간

    def __init__(self,
                 data_dir: str = "data/market",
                 use_cache: bool = True):
        """
        초기화

        Args:
            data_dir: 데이터 저장 디렉토리
            use_cache: 캐시 사용 여부
        """
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._use_cache = use_cache
        self._cache: Optional[MarketIndicators] = None
        self._cache_time: Optional[datetime] = None

        # API 클라이언트 (실제 구현에서는 KIS API 사용)
        self._api_client = None

        logger.info("MarketIndicatorCollector 초기화 완료")

    def collect(self, force_refresh: bool = False) -> MarketIndicators:
        """
        시장 지표 수집 (C.1.1)

        Args:
            force_refresh: 캐시 무시하고 새로 수집

        Returns:
            수집된 시장 지표
        """
        # 캐시 확인
        if not force_refresh and self._is_cache_valid():
            logger.debug("캐시된 시장 지표 반환")
            return self._cache

        try:
            indicators = MarketIndicators()

            # 1. 주요 지수 수집 (C.1.2)
            self._collect_index_data(indicators)

            # 2. 시장 폭 지표 계산 (C.1.3)
            self._collect_market_breadth(indicators)

            # 3. 변동성 지표 계산 (C.1.4)
            self._collect_volatility(indicators)

            # 4. 기타 지표 수집
            self._collect_sentiment_indicators(indicators)

            # 캐시 업데이트
            self._cache = indicators
            self._cache_time = datetime.now()

            # 파일 저장
            self._save_indicators(indicators)

            logger.info("시장 지표 수집 완료")
            return indicators

        except Exception as e:
            logger.error(f"시장 지표 수집 오류: {e}")
            # 실패 시 캐시 또는 기본값 반환
            if self._cache:
                return self._cache
            return MarketIndicators()

    def _collect_index_data(self, indicators: MarketIndicators):
        """주요 지수 데이터 수집 (C.1.2)"""
        try:
            # 실제 구현에서는 KIS API 사용
            # 여기서는 저장된 데이터 또는 더미 데이터 사용

            index_data = self._load_index_data()

            if index_data:
                indicators.kospi_price = index_data.get('kospi_price', 2500.0)
                indicators.kospi_change = index_data.get('kospi_change', 0.0)
                indicators.kospi_5d_return = index_data.get('kospi_5d_return', 0.0)
                indicators.kospi_20d_return = index_data.get('kospi_20d_return', 0.0)
                indicators.kospi_60d_return = index_data.get('kospi_60d_return', 0.0)

                indicators.kosdaq_price = index_data.get('kosdaq_price', 800.0)
                indicators.kosdaq_change = index_data.get('kosdaq_change', 0.0)
                indicators.kosdaq_20d_return = index_data.get('kosdaq_20d_return', 0.0)

                indicators.kospi_vs_ma20 = index_data.get('kospi_vs_ma20', 0.0)
                indicators.kospi_vs_ma60 = index_data.get('kospi_vs_ma60', 0.0)
                indicators.kospi_vs_ma200 = index_data.get('kospi_vs_ma200', 0.0)
            else:
                # API 호출 또는 기본값
                self._fetch_index_from_api(indicators)

        except Exception as e:
            logger.warning(f"지수 데이터 수집 오류: {e}")

    def _collect_market_breadth(self, indicators: MarketIndicators):
        """시장 폭 지표 계산 (C.1.3)"""
        try:
            breadth_data = self._load_breadth_data()

            if breadth_data:
                indicators.advance_count = breadth_data.get('advance_count', 0)
                indicators.decline_count = breadth_data.get('decline_count', 0)
                indicators.unchanged_count = breadth_data.get('unchanged_count', 0)

                # 등락비 계산
                if indicators.decline_count > 0:
                    indicators.advance_decline_ratio = indicators.advance_count / indicators.decline_count
                else:
                    indicators.advance_decline_ratio = float(indicators.advance_count) if indicators.advance_count > 0 else 1.0

                indicators.new_high_count = breadth_data.get('new_high_count', 0)
                indicators.new_low_count = breadth_data.get('new_low_count', 0)

                # 신고/신저 비율
                if indicators.new_low_count > 0:
                    indicators.new_high_low_ratio = indicators.new_high_count / indicators.new_low_count
                else:
                    indicators.new_high_low_ratio = float(indicators.new_high_count) if indicators.new_high_count > 0 else 1.0

                indicators.above_ma20_ratio = breadth_data.get('above_ma20_ratio', 0.5)
                indicators.above_ma60_ratio = breadth_data.get('above_ma60_ratio', 0.5)
                indicators.above_ma200_ratio = breadth_data.get('above_ma200_ratio', 0.5)

                indicators.volume_ratio = breadth_data.get('volume_ratio', 1.0)
                indicators.volume_ma20_ratio = breadth_data.get('volume_ma20_ratio', 1.0)
            else:
                self._calculate_breadth_from_stocks(indicators)

        except Exception as e:
            logger.warning(f"시장 폭 지표 계산 오류: {e}")

    def _collect_volatility(self, indicators: MarketIndicators):
        """변동성 지표 계산 (C.1.4)"""
        try:
            volatility_data = self._load_volatility_data()

            if volatility_data:
                indicators.market_volatility = volatility_data.get('market_volatility', 0.15)
                indicators.avg_stock_volatility = volatility_data.get('avg_stock_volatility', 0.25)
                indicators.volatility_percentile = volatility_data.get('volatility_percentile', 50.0)
            else:
                self._calculate_volatility_from_prices(indicators)

        except Exception as e:
            logger.warning(f"변동성 지표 계산 오류: {e}")

    def _collect_sentiment_indicators(self, indicators: MarketIndicators):
        """투자심리 지표 수집"""
        try:
            sentiment_data = self._load_sentiment_data()

            if sentiment_data:
                indicators.fear_greed_score = sentiment_data.get('fear_greed_score', 50.0)
                indicators.put_call_ratio = sentiment_data.get('put_call_ratio', 1.0)
                indicators.foreign_net_buy = sentiment_data.get('foreign_net_buy', 0.0)
                indicators.institution_net_buy = sentiment_data.get('institution_net_buy', 0.0)
            else:
                # 기본값 사용
                indicators.fear_greed_score = self._estimate_fear_greed(indicators)

        except Exception as e:
            logger.warning(f"투자심리 지표 수집 오류: {e}")

    def _estimate_fear_greed(self, indicators: MarketIndicators) -> float:
        """공포-탐욕 지수 추정"""
        score = 50.0  # 중립 시작

        # 지수 수익률 반영
        if indicators.kospi_20d_return > 0.05:
            score += 15
        elif indicators.kospi_20d_return < -0.05:
            score -= 15

        # 등락비 반영
        if indicators.advance_decline_ratio > 1.5:
            score += 10
        elif indicators.advance_decline_ratio < 0.67:
            score -= 10

        # 200일선 위 종목 비율 반영
        if indicators.above_ma200_ratio > 0.6:
            score += 10
        elif indicators.above_ma200_ratio < 0.4:
            score -= 10

        # 변동성 반영 (높으면 공포)
        if indicators.market_volatility > 0.25:
            score -= 10
        elif indicators.market_volatility < 0.1:
            score += 5

        return max(0, min(100, score))

    def _is_cache_valid(self) -> bool:
        """캐시 유효성 확인"""
        if not self._use_cache or not self._cache or not self._cache_time:
            return False

        elapsed = (datetime.now() - self._cache_time).total_seconds()
        return elapsed < self.CACHE_TTL_SECONDS

    def _load_index_data(self) -> Optional[Dict[str, Any]]:
        """저장된 지수 데이터 로드"""
        index_file = self._data_dir / "index_data.json"

        try:
            if index_file.exists():
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 1일 이내 데이터만 유효
                    if 'updated_at' in data:
                        updated = datetime.fromisoformat(data['updated_at'])
                        if (datetime.now() - updated).days < 1:
                            return data
        except Exception as e:
            logger.warning(f"지수 데이터 로드 오류: {e}")

        return None

    def _load_breadth_data(self) -> Optional[Dict[str, Any]]:
        """저장된 시장 폭 데이터 로드"""
        breadth_file = self._data_dir / "breadth_data.json"

        try:
            if breadth_file.exists():
                with open(breadth_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass

        return None

    def _load_volatility_data(self) -> Optional[Dict[str, Any]]:
        """저장된 변동성 데이터 로드"""
        volatility_file = self._data_dir / "volatility_data.json"

        try:
            if volatility_file.exists():
                with open(volatility_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass

        return None

    def _load_sentiment_data(self) -> Optional[Dict[str, Any]]:
        """저장된 심리 지표 데이터 로드"""
        sentiment_file = self._data_dir / "sentiment_data.json"

        try:
            if sentiment_file.exists():
                with open(sentiment_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass

        return None

    def _fetch_index_from_api(self, indicators: MarketIndicators):
        """API에서 지수 데이터 가져오기 (실제 구현 필요)"""
        # TODO: KIS API 연동
        # 현재는 기본값 유지
        pass

    def _calculate_breadth_from_stocks(self, indicators: MarketIndicators):
        """개별 종목 데이터에서 시장 폭 계산"""
        # TODO: 실제 종목 데이터 분석
        pass

    def _calculate_volatility_from_prices(self, indicators: MarketIndicators):
        """가격 데이터에서 변동성 계산"""
        # 기본값 설정
        indicators.market_volatility = 0.15
        indicators.avg_stock_volatility = 0.25
        indicators.volatility_percentile = 50.0

    def _save_indicators(self, indicators: MarketIndicators):
        """지표 저장"""
        indicators_file = self._data_dir / f"indicators_{datetime.now().strftime('%Y%m%d')}.json"

        try:
            with open(indicators_file, 'w', encoding='utf-8') as f:
                json.dump(indicators.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"지표 저장 오류: {e}")

    def update_index_data(self, data: Dict[str, Any]):
        """지수 데이터 업데이트 (외부에서 주입)"""
        data['updated_at'] = datetime.now().isoformat()
        index_file = self._data_dir / "index_data.json"

        try:
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("지수 데이터 업데이트")
        except Exception as e:
            logger.error(f"지수 데이터 업데이트 오류: {e}")

    def update_breadth_data(self, data: Dict[str, Any]):
        """시장 폭 데이터 업데이트"""
        breadth_file = self._data_dir / "breadth_data.json"

        try:
            with open(breadth_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"시장 폭 데이터 업데이트 오류: {e}")

    def get_historical_indicators(self, days: int = 30) -> List[MarketIndicators]:
        """과거 지표 조회"""
        historical = []

        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime('%Y%m%d')
            indicators_file = self._data_dir / f"indicators_{date_str}.json"

            try:
                if indicators_file.exists():
                    with open(indicators_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        historical.append(MarketIndicators.from_dict(data))
            except Exception:
                continue

        return historical


# 싱글톤 인스턴스
_collector_instance: Optional[MarketIndicatorCollector] = None


def get_market_indicator_collector() -> MarketIndicatorCollector:
    """MarketIndicatorCollector 싱글톤 인스턴스 반환"""
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = MarketIndicatorCollector()
    return _collector_instance
