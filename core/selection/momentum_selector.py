"""
모멘텀 기반 종목 선정 엔진
30년 퀀트 경험 기반 - 단순하고 견고한 시스템

핵심 원리:
1. 유동성 필터 (Hard) - 슬리피지 방지
2. 모멘텀 스코어 (Soft) - 상대 순위 기반 선정
3. 섹터 분산 - 집중 리스크 방지
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from core.utils.log_utils import get_logger
from core.selection.quant_config import (
    get_quant_config, QuantConfig, MarketRegime
)

logger = get_logger(__name__)


@dataclass
class MomentumScore:
    """모멘텀 스코어 결과"""
    stock_code: str
    stock_name: str
    sector: str

    # 모멘텀 점수 구성요소
    relative_return: float          # 시장 대비 초과수익률 (%)
    volume_surge: float             # 거래량 서지 (배수)
    price_strength: float           # 가격 위치 강도 (0-1)

    # 종합 점수
    momentum_score: float           # 종합 모멘텀 점수
    percentile_rank: float          # 백분위 순위 (0-100)

    # 기초 데이터
    current_price: float
    return_20d: float               # 20일 수익률 (%)
    market_cap: float               # 시가총액
    avg_trading_value: float        # 평균 거래대금

    # 메타 정보
    analysis_date: str
    passed_liquidity: bool

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SelectionResult:
    """
    선정 결과 - 기존 DailySelectionLegacy와 호환
    trading_engine에서 사용하는 필드 포함
    """
    stock_code: str
    stock_name: str
    selection_date: str
    selection_reason: str

    # 점수 (기존 호환)
    price_attractiveness: float     # = momentum_score (매핑)
    technical_score: float          # = relative_return (매핑)
    volume_score: float             # = volume_surge * 20 (매핑)
    risk_score: float               # = 100 - momentum_score (매핑)
    confidence: float               # = percentile_rank / 100 (매핑)

    # 가격 정보
    entry_price: float
    target_price: float
    stop_loss: float
    expected_return: float

    # 포지션 정보
    position_size: float            # 포트폴리오 비중 (0-1)
    position_amount: float          # 투자 금액

    # 기타 정보
    sector: str
    market_cap: float
    priority: int
    technical_signals: List[str]

    # 학습용 필드
    predicted_class: int = 1
    model_name: str = "momentum_v1"

    # ATR 기반 정보 (신규)
    atr_value: float = 0.0
    daily_volatility: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


class MomentumSelector:
    """
    모멘텀 기반 종목 선정기

    사용법:
        selector = MomentumSelector()
        results = selector.select_stocks(watchlist_stocks, market_data)
    """

    def __init__(
        self,
        config: Optional[QuantConfig] = None,
        api_client=None  # API 인스턴스 주입 (Rate Limit 공유용)
    ):
        """
        초기화

        Args:
            config: 퀀트 설정 (None이면 기본값 사용)
            api_client: KIS API 클라이언트 (None이면 내부 생성)
        """
        self.config = config or get_quant_config()
        self.logger = logger
        self._api = api_client  # 외부 주입 또는 None (지연 로딩)

        # 캐시
        self._market_return_cache: Dict[str, float] = {}
        self._price_data_cache: Dict[str, pd.DataFrame] = {}

    @property
    def api(self):
        """API 클라이언트 지연 로딩"""
        if self._api is None:
            from core.api.kis_api import KISAPI
            self._api = KISAPI()
        return self._api

    def select_stocks(
        self,
        watchlist: List[Dict],
        total_capital: float,
        market_return_20d: Optional[float] = None
    ) -> List[SelectionResult]:
        """
        종목 선정 메인 함수

        Args:
            watchlist: 감시 리스트 종목들 (Phase 1 결과)
                각 항목: {stock_code, stock_name, sector, ...}
            total_capital: 총 투자 자본금
            market_return_20d: 시장(KOSPI) 20일 수익률 (없으면 자동 조회)

        Returns:
            List[SelectionResult]: 선정된 종목 리스트
        """
        try:
            self.logger.info(f"=== 모멘텀 기반 종목 선정 시작 ({len(watchlist)}개) ===")

            # 1. 시장 수익률 조회 (레짐 판단용)
            if market_return_20d is None:
                market_return_20d = self._get_market_return()
            self._update_market_regime(market_return_20d)

            # 2. 유동성 필터 적용
            liquid_stocks = self._apply_liquidity_filter(watchlist)
            self.logger.info(f"유동성 필터 통과: {len(liquid_stocks)}개")

            if not liquid_stocks:
                self.logger.warning("유동성 필터를 통과한 종목이 없습니다")
                return []

            # 3. 모멘텀 스코어 계산
            scored_stocks = self._calculate_momentum_scores(
                liquid_stocks, market_return_20d
            )
            self.logger.info(f"모멘텀 스코어 계산 완료: {len(scored_stocks)}개")

            # 4. 상위 N% 선정 + 섹터 분산
            selected = self._select_top_stocks(scored_stocks)
            self.logger.info(f"최종 선정: {len(selected)}개")

            # 5. SelectionResult로 변환 (포지션 사이징 포함)
            results = self._create_selection_results(selected, total_capital)

            self.logger.info(f"=== 종목 선정 완료: {len(results)}개 ===")
            return results

        except Exception as e:
            self.logger.error(f"종목 선정 실패: {e}", exc_info=True)
            return []

    def _apply_liquidity_filter(self, watchlist: List[Dict]) -> List[Dict]:
        """
        유동성 필터 적용 (Hard Filter)

        통과 조건 (모두 충족):
        - 일평균 거래대금 >= 5억원
        - 시가총액 >= 500억원
        - 주가 >= 1,000원
        """
        liq = self.config.liquidity
        passed = []

        for stock in watchlist:
            try:
                # 기존 데이터에서 추출 (Phase 1에서 이미 조회된 데이터)
                trading_value = stock.get('avg_trading_value', 0) or stock.get('acml_tr_pbmn', 0)
                market_cap = stock.get('market_cap', 0) or stock.get('hts_avls', 0)
                current_price = stock.get('current_price', 0) or stock.get('stck_prpr', 0)

                # 거래대금이 없으면 거래량 * 현재가로 추정
                if trading_value == 0 and current_price > 0:
                    volume = stock.get('volume', 0) or stock.get('acml_vol', 0)
                    trading_value = volume * current_price

                # 시가총액이 억 단위로 저장된 경우 변환
                if 0 < market_cap < 1_000_000:
                    market_cap = market_cap * 100_000_000  # 억 → 원

                # 필터 적용
                if (trading_value >= liq.min_trading_value and
                    market_cap >= liq.min_market_cap and
                    current_price >= liq.min_price):

                    stock['_trading_value'] = trading_value
                    stock['_market_cap'] = market_cap
                    stock['_current_price'] = current_price
                    passed.append(stock)

            except Exception as e:
                self.logger.debug(f"유동성 필터 오류 ({stock.get('stock_code')}): {e}")
                continue

        return passed

    def _calculate_momentum_scores(
        self,
        stocks: List[Dict],
        market_return: float
    ) -> List[MomentumScore]:
        """
        모멘텀 스코어 계산

        스코어 구성:
        - 상대 수익률 (50%): 시장 대비 초과수익률
        - 거래량 서지 (30%): 단기/장기 거래량 비율
        - 가격 강도 (20%): 최근 가격 위치
        """
        scores = []

        for stock in stocks:
            try:
                score = self._calculate_single_momentum(stock, market_return)
                if score:
                    scores.append(score)
            except Exception as e:
                self.logger.debug(f"모멘텀 계산 오류 ({stock.get('stock_code')}): {e}")
                continue

        # 백분위 순위 계산
        if scores:
            momentum_values = [s.momentum_score for s in scores]
            for score in scores:
                rank = sum(1 for v in momentum_values if v <= score.momentum_score)
                score.percentile_rank = (rank / len(scores)) * 100

        return scores

    def _calculate_single_momentum(
        self,
        stock: Dict,
        market_return: float
    ) -> Optional[MomentumScore]:
        """단일 종목 모멘텀 스코어 계산"""
        mom = self.config.momentum
        stock_code = stock.get('stock_code', '')

        # 일봉 데이터 조회 (캐시 활용)
        df = self._get_price_data(stock_code)
        if df is None or len(df) < mom.return_period:
            return None

        # 1. 수익률 계산
        return_20d = self._calculate_return(df, mom.return_period)
        relative_return = return_20d - market_return

        # 2. 거래량 서지 계산
        volume_surge = self._calculate_volume_surge(
            df, mom.volume_short_period, mom.volume_long_period
        )

        # 3. 가격 강도 계산 (최근 고점 대비 위치)
        price_strength = self._calculate_price_strength(df)

        # 4. 종합 점수 (가중 평균)
        momentum_score = (
            relative_return * mom.relative_return_weight +
            min(volume_surge * 20, 40) * mom.volume_surge_weight +  # 최대 40점
            price_strength * 100 * mom.price_strength_weight
        )

        return MomentumScore(
            stock_code=stock_code,
            stock_name=stock.get('stock_name', ''),
            sector=stock.get('sector', ''),
            relative_return=round(relative_return, 2),
            volume_surge=round(volume_surge, 2),
            price_strength=round(price_strength, 3),
            momentum_score=round(momentum_score, 2),
            percentile_rank=0,  # 나중에 계산
            current_price=stock.get('_current_price', 0),
            return_20d=round(return_20d, 2),
            market_cap=stock.get('_market_cap', 0),
            avg_trading_value=stock.get('_trading_value', 0),
            analysis_date=datetime.now().isoformat(),
            passed_liquidity=True
        )

    def _get_price_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """일봉 데이터 조회 (캐시 활용)"""
        if stock_code in self._price_data_cache:
            return self._price_data_cache[stock_code]

        try:
            df = self.api.get_daily_chart(stock_code, period_days=60)
            if df is not None and len(df) > 0:
                self._price_data_cache[stock_code] = df
            return df
        except Exception as e:
            self.logger.debug(f"일봉 조회 실패 ({stock_code}): {e}")
            return None

    def _calculate_return(self, df: pd.DataFrame, period: int) -> float:
        """수익률 계산"""
        if len(df) < period:
            return 0.0

        current = df['close'].iloc[-1]
        past = df['close'].iloc[-period]

        if past > 0:
            return ((current / past) - 1) * 100
        return 0.0

    def _calculate_volume_surge(
        self,
        df: pd.DataFrame,
        short_period: int,
        long_period: int
    ) -> float:
        """거래량 서지 계산 (단기/장기 비율)"""
        if len(df) < long_period:
            return 1.0

        short_avg = df['volume'].tail(short_period).mean()
        long_avg = df['volume'].tail(long_period).mean()

        if long_avg > 0:
            return short_avg / long_avg
        return 1.0

    def _calculate_price_strength(self, df: pd.DataFrame) -> float:
        """
        가격 강도 계산
        현재가가 최근 고점 대비 어느 위치인지 (0-1)
        """
        if len(df) < 20:
            return 0.5

        current = df['close'].iloc[-1]
        high_20d = df['high'].tail(20).max()
        low_20d = df['low'].tail(20).min()

        price_range = high_20d - low_20d
        if price_range > 0:
            return (current - low_20d) / price_range
        return 0.5

    def _select_top_stocks(self, scores: List[MomentumScore]) -> List[MomentumScore]:
        """
        상위 종목 선정 + 섹터 분산

        1. 모멘텀 점수 순 정렬
        2. 상위 N% 필터
        3. 섹터별 제한 적용
        """
        mom = self.config.momentum
        adjusted = self.config.get_adjusted_config()
        max_stocks = adjusted.get('max_stocks', mom.max_stocks)

        # 점수 순 정렬
        sorted_scores = sorted(scores, key=lambda x: x.momentum_score, reverse=True)

        # 상위 N% 필터
        cutoff_idx = max(1, int(len(sorted_scores) * mom.top_percentile))
        top_candidates = sorted_scores[:cutoff_idx]

        # 섹터별 제한 적용
        selected = []
        sector_count: Dict[str, int] = {}

        for score in top_candidates:
            sector = score.sector or "기타"
            current_count = sector_count.get(sector, 0)

            if current_count < mom.sector_limit:
                selected.append(score)
                sector_count[sector] = current_count + 1

                if len(selected) >= max_stocks:
                    break

        return selected

    def _create_selection_results(
        self,
        selected: List[MomentumScore],
        total_capital: float
    ) -> List[SelectionResult]:
        """
        SelectionResult 변환 (포지션 사이징 포함)
        기존 DailySelectionLegacy와 호환되는 형식
        """
        from core.selection.position_sizer import PositionSizer

        # API 인스턴스 공유 (Rate Limit 효율화)
        sizer = PositionSizer(self.config, api_client=self._api)
        results = []

        for i, score in enumerate(selected):
            try:
                # 포지션 사이징
                sizing = sizer.calculate_position(
                    stock_code=score.stock_code,
                    current_price=score.current_price,
                    total_capital=total_capital,
                    price_data=self._price_data_cache.get(score.stock_code)
                )

                # SelectionResult 생성
                result = SelectionResult(
                    stock_code=score.stock_code,
                    stock_name=score.stock_name,
                    selection_date=datetime.now().strftime("%Y-%m-%d"),
                    selection_reason=self._generate_reason(score),

                    # 점수 매핑 (기존 호환)
                    price_attractiveness=score.momentum_score,
                    technical_score=score.relative_return + 50,  # 0-100 스케일
                    volume_score=min(score.volume_surge * 30, 100),
                    risk_score=max(0, 100 - score.momentum_score),
                    confidence=score.percentile_rank / 100,

                    # 가격 정보
                    entry_price=score.current_price,
                    target_price=sizing.target_price,
                    stop_loss=sizing.stop_loss,
                    expected_return=sizing.expected_return,

                    # 포지션 정보
                    position_size=sizing.weight,
                    position_amount=sizing.amount,

                    # 기타 정보
                    sector=score.sector,
                    market_cap=score.market_cap,
                    priority=i + 1,
                    technical_signals=self._generate_signals(score),

                    # ATR 정보
                    atr_value=sizing.atr_value,
                    daily_volatility=sizing.daily_volatility
                )

                results.append(result)

            except Exception as e:
                self.logger.warning(f"SelectionResult 생성 실패 ({score.stock_code}): {e}")
                continue

        return results

    def _generate_reason(self, score: MomentumScore) -> str:
        """선정 이유 생성"""
        reasons = []

        if score.relative_return > 5:
            reasons.append(f"시장대비 +{score.relative_return:.1f}%")
        if score.volume_surge > 1.5:
            reasons.append(f"거래량 {score.volume_surge:.1f}배 증가")
        if score.price_strength > 0.7:
            reasons.append("상승 추세")
        if score.percentile_rank > 90:
            reasons.append("모멘텀 상위 10%")

        return ", ".join(reasons) if reasons else "모멘텀 점수 우수"

    def _generate_signals(self, score: MomentumScore) -> List[str]:
        """기술적 신호 생성 (기존 호환)"""
        signals = []

        if score.relative_return > 0:
            signals.append("MOMENTUM_POSITIVE")
        if score.volume_surge > 1.5:
            signals.append("VOLUME_SURGE")
        if score.price_strength > 0.7:
            signals.append("PRICE_STRENGTH")
        if score.percentile_rank > 80:
            signals.append("TOP_PERCENTILE")

        return signals

    def _get_market_return(self) -> float:
        """시장(KOSPI) 20일 수익률 조회"""
        cache_key = datetime.now().strftime("%Y%m%d")

        if cache_key in self._market_return_cache:
            return self._market_return_cache[cache_key]

        try:
            # KOSPI ETF (KODEX 200) 또는 인덱스 조회
            df = self.api.get_daily_chart("069500", period_days=30)  # KODEX 200
            if df is not None and len(df) >= 20:
                return_20d = self._calculate_return(df, 20)
                self._market_return_cache[cache_key] = return_20d
                return return_20d
        except Exception as e:
            self.logger.warning(f"시장 수익률 조회 실패: {e}")

        return 0.0

    def _update_market_regime(self, market_return: float):
        """시장 레짐 업데이트"""
        regime = self.config.regime

        if market_return > regime.bull_threshold * 100:
            self.config.current_regime = MarketRegime.BULL
        elif market_return < regime.bear_threshold * 100:
            self.config.current_regime = MarketRegime.BEAR
        else:
            self.config.current_regime = MarketRegime.SIDEWAYS

        self.logger.info(f"시장 레짐: {self.config.current_regime.value} (수익률: {market_return:.2f}%)")

    def clear_cache(self):
        """캐시 초기화"""
        self._price_data_cache.clear()
        self._market_return_cache.clear()
