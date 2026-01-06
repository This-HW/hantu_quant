# -*- coding: utf-8 -*-
"""
투자자 수급 분석기 (P1-3)

기능:
- 외국인/기관 순매수 분석
- 투자자별 매매 동향 추적
- 수급 기반 매매 신호 생성

외국인/기관 순매수 = 상승 확률 높음
양방향 순매수 = strong_buy 신호
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from ..utils.log_utils import get_logger

logger = get_logger(__name__)


class InvestorSignal(Enum):
    """투자자 수급 신호"""
    STRONG_BUY = "strong_buy"    # 외국인 + 기관 모두 순매수
    BUY = "buy"                   # 외국인 또는 기관 순매수
    NEUTRAL = "neutral"           # 중립
    SELL = "sell"                 # 외국인 또는 기관 순매도
    STRONG_SELL = "strong_sell"   # 외국인 + 기관 모두 순매도


class InvestorType(Enum):
    """투자자 유형"""
    FOREIGN = "foreign"      # 외국인
    INSTITUTION = "inst"     # 기관
    INDIVIDUAL = "individual"  # 개인
    PROGRAM = "program"      # 프로그램 매매


@dataclass
class InvestorTrend:
    """투자자 동향"""
    investor_type: InvestorType
    net_buy: int  # 순매수량 (음수면 순매도)
    buy_volume: int = 0
    sell_volume: int = 0
    trend: str = "neutral"  # buying, selling, neutral

    @property
    def is_buying(self) -> bool:
        return self.net_buy > 0

    @property
    def is_selling(self) -> bool:
        return self.net_buy < 0


@dataclass
class InvestorFlowResult:
    """투자자 수급 분석 결과"""
    stock_code: str
    foreign: InvestorTrend
    institution: InvestorTrend
    individual: InvestorTrend
    signal: InvestorSignal
    confidence: float  # 0.0 ~ 1.0
    net_buy_total: int = 0  # 외국인 + 기관 합산
    analysis_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """딕셔너리 변환"""
        return {
            "stock_code": self.stock_code,
            "foreign_net_buy": self.foreign.net_buy,
            "foreign_trend": self.foreign.trend,
            "institution_net_buy": self.institution.net_buy,
            "institution_trend": self.institution.trend,
            "individual_net_buy": self.individual.net_buy,
            "individual_trend": self.individual.trend,
            "signal": self.signal.value,
            "confidence": self.confidence,
            "net_buy_total": self.net_buy_total,
            "analysis_date": self.analysis_date,
            "timestamp": self.timestamp,
        }


class InvestorFlowAnalyzer:
    """투자자 수급 분석기

    외국인/기관 순매수 동향을 분석하여 매매 신호를 생성합니다.

    신호 기준:
    - strong_buy: 외국인 + 기관 모두 순매수
    - buy: 외국인 또는 기관 순매수
    - neutral: 혼조 또는 거래량 미미
    - sell: 외국인 또는 기관 순매도
    - strong_sell: 외국인 + 기관 모두 순매도
    """

    # 순매수 임계값 (주)
    FOREIGN_BUY_THRESHOLD = 1_000_000    # 외국인 100만주 이상
    FOREIGN_SELL_THRESHOLD = -1_000_000
    INST_BUY_THRESHOLD = 500_000         # 기관 50만주 이상
    INST_SELL_THRESHOLD = -500_000

    # 소형주 임계값 (더 낮은 기준)
    SMALL_FOREIGN_BUY_THRESHOLD = 100_000
    SMALL_FOREIGN_SELL_THRESHOLD = -100_000
    SMALL_INST_BUY_THRESHOLD = 50_000
    SMALL_INST_SELL_THRESHOLD = -50_000

    def __init__(
        self,
        kis_api=None,
        foreign_threshold: int = 1_000_000,
        inst_threshold: int = 500_000,
        use_small_cap_threshold: bool = False,
    ):
        """초기화

        Args:
            kis_api: KIS REST API 클라이언트
            foreign_threshold: 외국인 순매수 임계값 (주)
            inst_threshold: 기관 순매수 임계값 (주)
            use_small_cap_threshold: 소형주 임계값 사용 여부
        """
        self.kis_api = kis_api
        self.foreign_threshold = foreign_threshold
        self.inst_threshold = inst_threshold
        self.use_small_cap_threshold = use_small_cap_threshold

        # 소형주 임계값 적용
        if use_small_cap_threshold:
            self.foreign_threshold = self.SMALL_FOREIGN_BUY_THRESHOLD
            self.inst_threshold = self.SMALL_INST_BUY_THRESHOLD

        # 캐시
        self._cache: Dict[str, InvestorFlowResult] = {}

        logger.info(
            f"InvestorFlowAnalyzer 초기화 - "
            f"외국인 임계값: {self.foreign_threshold:,}주, "
            f"기관 임계값: {self.inst_threshold:,}주"
        )

    def set_kis_api(self, kis_api):
        """KIS API 클라이언트 설정"""
        self.kis_api = kis_api

    def analyze(self, stock_code: str) -> Optional[InvestorFlowResult]:
        """종목의 투자자 수급 분석

        Args:
            stock_code: 종목 코드

        Returns:
            InvestorFlowResult 또는 None (실패 시)
        """
        if not self.kis_api:
            logger.error("KIS API 클라이언트가 설정되지 않았습니다")
            return None

        try:
            # API 호출
            data = self.kis_api.get_investor_flow(stock_code)
            if not data:
                logger.warning(f"투자자 수급 데이터 없음: {stock_code}")
                return None

            return self.analyze_from_data(stock_code, data)

        except Exception as e:
            logger.error(f"투자자 수급 분석 오류 ({stock_code}): {e}", exc_info=True)
            return None

    def analyze_from_data(
        self,
        stock_code: str,
        data: Dict
    ) -> InvestorFlowResult:
        """데이터로부터 투자자 수급 분석

        Args:
            stock_code: 종목 코드
            data: KIS API 응답 데이터

        Returns:
            InvestorFlowResult 분석 결과
        """
        # 투자자별 순매수량 추출
        foreign_net = self._parse_int(data.get('frgn_ntby_qty', 0))
        inst_net = self._parse_int(data.get('orgn_ntby_qty', 0))
        individual_net = self._parse_int(data.get('prsn_ntby_qty', 0))

        # 매수/매도 수량 추출 (있는 경우)
        foreign_buy = self._parse_int(data.get('frgn_seln_vol', 0))
        foreign_sell = self._parse_int(data.get('frgn_shnu_vol', 0))
        inst_buy = self._parse_int(data.get('orgn_seln_vol', 0))
        inst_sell = self._parse_int(data.get('orgn_shnu_vol', 0))

        # 투자자별 동향 객체 생성
        foreign = self._create_trend(InvestorType.FOREIGN, foreign_net, foreign_buy, foreign_sell)
        institution = self._create_trend(InvestorType.INSTITUTION, inst_net, inst_buy, inst_sell)
        individual = self._create_trend(InvestorType.INDIVIDUAL, individual_net, 0, 0)

        # 신호 및 신뢰도 계산
        signal, confidence = self._calculate_signal(foreign, institution)

        result = InvestorFlowResult(
            stock_code=stock_code,
            foreign=foreign,
            institution=institution,
            individual=individual,
            signal=signal,
            confidence=confidence,
            net_buy_total=foreign_net + inst_net,
        )

        # 캐시 업데이트
        self._cache[stock_code] = result

        logger.debug(
            f"투자자 수급 분석 - {stock_code}: "
            f"외국인 {foreign_net:+,}, 기관 {inst_net:+,}, "
            f"신호 {signal.value}"
        )

        return result

    def analyze_multi_day(
        self,
        stock_code: str,
        days: int = 5
    ) -> Optional[InvestorFlowResult]:
        """다일간 누적 수급 분석

        Args:
            stock_code: 종목 코드
            days: 분석 기간 (일)

        Returns:
            InvestorFlowResult 또는 None
        """
        if not self.kis_api:
            logger.error("KIS API 클라이언트가 설정되지 않았습니다")
            return None

        try:
            # 여러 날짜 데이터 수집 (API에 따라 구현)
            # 현재는 단일일 데이터만 지원하므로 로그만 출력
            logger.info(f"{days}일 누적 수급 분석 요청: {stock_code}")
            return self.analyze(stock_code)

        except Exception as e:
            logger.error(f"다일간 수급 분석 오류 ({stock_code}): {e}", exc_info=True)
            return None

    def _create_trend(
        self,
        investor_type: InvestorType,
        net_buy: int,
        buy_vol: int = 0,
        sell_vol: int = 0
    ) -> InvestorTrend:
        """투자자 동향 객체 생성"""
        # 동향 결정
        if investor_type == InvestorType.FOREIGN:
            threshold = self.foreign_threshold
        else:
            threshold = self.inst_threshold

        if net_buy > threshold:
            trend = "buying"
        elif net_buy < -threshold:
            trend = "selling"
        else:
            trend = "neutral"

        return InvestorTrend(
            investor_type=investor_type,
            net_buy=net_buy,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            trend=trend,
        )

    def _calculate_signal(
        self,
        foreign: InvestorTrend,
        institution: InvestorTrend
    ) -> Tuple[InvestorSignal, float]:
        """신호 및 신뢰도 계산

        Args:
            foreign: 외국인 동향
            institution: 기관 동향

        Returns:
            (신호, 신뢰도) 튜플
        """
        foreign_buying = foreign.trend == "buying"
        foreign_selling = foreign.trend == "selling"
        inst_buying = institution.trend == "buying"
        inst_selling = institution.trend == "selling"

        # 신호 결정
        if foreign_buying and inst_buying:
            signal = InvestorSignal.STRONG_BUY
            confidence = 0.8 + min(
                (abs(foreign.net_buy) / (self.foreign_threshold * 5) +
                 abs(institution.net_buy) / (self.inst_threshold * 5)) / 2,
                0.2
            )

        elif foreign_selling and inst_selling:
            signal = InvestorSignal.STRONG_SELL
            confidence = 0.8 + min(
                (abs(foreign.net_buy) / (self.foreign_threshold * 5) +
                 abs(institution.net_buy) / (self.inst_threshold * 5)) / 2,
                0.2
            )

        elif foreign_buying or inst_buying:
            signal = InvestorSignal.BUY
            # 외국인이 더 중요
            if foreign_buying:
                confidence = 0.5 + min(abs(foreign.net_buy) / (self.foreign_threshold * 3), 0.3)
            else:
                confidence = 0.4 + min(abs(institution.net_buy) / (self.inst_threshold * 3), 0.3)

        elif foreign_selling or inst_selling:
            signal = InvestorSignal.SELL
            if foreign_selling:
                confidence = 0.5 + min(abs(foreign.net_buy) / (self.foreign_threshold * 3), 0.3)
            else:
                confidence = 0.4 + min(abs(institution.net_buy) / (self.inst_threshold * 3), 0.3)

        else:
            signal = InvestorSignal.NEUTRAL
            # 중립일 때 신뢰도는 수급량이 적을수록 높음
            confidence = max(
                1 - (abs(foreign.net_buy) + abs(institution.net_buy)) /
                (self.foreign_threshold + self.inst_threshold),
                0.3
            )

        return signal, round(min(confidence, 1.0), 3)

    def _parse_int(self, value) -> int:
        """값을 정수로 변환"""
        try:
            if value is None:
                return 0
            return int(value)
        except (ValueError, TypeError):
            return 0

    # ========== 캐시 관리 ==========

    def get_cached_result(self, stock_code: str) -> Optional[InvestorFlowResult]:
        """캐시된 결과 조회"""
        return self._cache.get(stock_code)

    def get_all_cached_results(self) -> Dict[str, InvestorFlowResult]:
        """모든 캐시 결과 조회"""
        return self._cache.copy()

    def clear_cache(self):
        """캐시 초기화"""
        self._cache.clear()

    # ========== 유틸리티 ==========

    def get_strong_buy_stocks(self) -> List[str]:
        """strong_buy 신호 종목 조회"""
        return [
            code for code, result in self._cache.items()
            if result.signal == InvestorSignal.STRONG_BUY
        ]

    def get_strong_sell_stocks(self) -> List[str]:
        """strong_sell 신호 종목 조회"""
        return [
            code for code, result in self._cache.items()
            if result.signal == InvestorSignal.STRONG_SELL
        ]

    def get_signal_summary(self) -> Dict[str, int]:
        """신호별 통계"""
        summary = {signal.value: 0 for signal in InvestorSignal}

        for result in self._cache.values():
            summary[result.signal.value] += 1

        return summary


# 편의 함수
def analyze_investor_flow(
    stock_code: str,
    data: Dict,
    foreign_threshold: int = 1_000_000,
    inst_threshold: int = 500_000,
) -> InvestorFlowResult:
    """투자자 수급 분석 편의 함수

    Args:
        stock_code: 종목 코드
        data: KIS API 응답 데이터
        foreign_threshold: 외국인 순매수 임계값
        inst_threshold: 기관 순매수 임계값

    Returns:
        InvestorFlowResult 분석 결과
    """
    analyzer = InvestorFlowAnalyzer(
        foreign_threshold=foreign_threshold,
        inst_threshold=inst_threshold,
    )
    return analyzer.analyze_from_data(stock_code, data)
