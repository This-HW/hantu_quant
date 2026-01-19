"""
선물 헤징 시스템 (P3-3)

KOSPI200 선물을 이용한 포트폴리오 헤지

Features:
- 포트폴리오 베타 계산
- 헤지 비율 자동 계산
- 선물 계약수 산출
- 자동 헤지 오픈/클로즈

Usage:
    hedger = FuturesHedger(kis_api)

    # 포트폴리오 분석
    beta = hedger.calculate_portfolio_beta(portfolio, market_data)

    # 헤지 신호
    signal = hedger.get_hedge_signal(portfolio_value, market_condition)

    # 헤지 실행
    if signal.should_hedge:
        hedger.open_hedge(signal)
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# KOSPI200 선물 상수
KOSPI200_FUTURES_MULTIPLIER = 250000  # 1포인트당 25만원
KOSPI200_TICK_SIZE = 0.05  # 틱 크기
MARGIN_RATE = 0.15  # 증거금율 (15%)


class MarketCondition(Enum):
    """시장 상황"""
    BULLISH = "bullish"  # 상승장
    NEUTRAL = "neutral"  # 보합
    BEARISH = "bearish"  # 하락장
    CRISIS = "crisis"  # 급락장


class HedgeAction(Enum):
    """헤지 행동"""
    OPEN = "open"  # 헤지 시작
    CLOSE = "close"  # 헤지 청산
    INCREASE = "increase"  # 헤지 확대
    DECREASE = "decrease"  # 헤지 축소
    HOLD = "hold"  # 유지


@dataclass
class HedgeConfig:
    """헤지 설정"""
    # 헤지 트리거
    max_portfolio_loss: float = 0.03  # 3% 손실시 헤지 시작
    vix_threshold: float = 25.0  # VIX 25 이상시 헤지
    beta_threshold: float = 1.0  # 베타 1.0 이상시 헤지 고려

    # 헤지 비율
    min_hedge_ratio: float = 0.3  # 최소 30%
    max_hedge_ratio: float = 1.0  # 최대 100%
    target_hedge_ratio: float = 0.5  # 기본 50%

    # 시장 상황별 헤지 비율
    hedge_ratios_by_condition: Dict[str, float] = field(default_factory=lambda: {
        'bullish': 0.0,  # 상승장: 헤지 안함
        'neutral': 0.3,  # 보합: 30%
        'bearish': 0.5,  # 하락장: 50%
        'crisis': 1.0,  # 급락장: 100%
    })

    # 청산 조건
    profit_close_threshold: float = 0.02  # 2% 수익시 헤지 청산 고려
    loss_close_threshold: float = 0.05  # 5% 손실시 헤지 청산 (손절)

    # 거래 비용
    commission_rate: float = 0.00015  # 수수료 0.015%
    slippage_ticks: int = 2  # 슬리피지 2틱


@dataclass
class HedgePosition:
    """헤지 포지션"""
    contracts: int  # 계약 수 (음수 = 매도)
    entry_price: float  # 진입가
    entry_date: datetime
    margin_required: float  # 필요 증거금
    current_price: float = 0.0
    unrealized_pnl: float = 0.0

    @property
    def position_value(self) -> float:
        """포지션 가치"""
        return abs(self.contracts) * self.current_price * KOSPI200_FUTURES_MULTIPLIER

    @property
    def is_short(self) -> bool:
        """매도 포지션 여부"""
        return self.contracts < 0

    def update_price(self, price: float):
        """가격 업데이트"""
        self.current_price = price
        price_diff = price - self.entry_price
        # 매수(+): 가격상승=수익, 매도(-): 가격하락=수익
        self.unrealized_pnl = self.contracts * price_diff * KOSPI200_FUTURES_MULTIPLIER

    def to_dict(self) -> Dict:
        return {
            'contracts': self.contracts,
            'entry_price': self.entry_price,
            'entry_date': self.entry_date.isoformat(),
            'margin_required': self.margin_required,
            'current_price': self.current_price,
            'unrealized_pnl': self.unrealized_pnl,
            'position_value': self.position_value,
            'is_short': self.is_short,
        }


@dataclass
class HedgeSignal:
    """헤지 신호"""
    action: HedgeAction
    contracts: int  # 매매할 계약 수
    target_hedge_ratio: float
    reason: str
    market_condition: MarketCondition
    confidence: float = 0.0

    @property
    def should_hedge(self) -> bool:
        """헤지 필요 여부"""
        return self.action in [HedgeAction.OPEN, HedgeAction.INCREASE]

    def to_dict(self) -> Dict:
        return {
            'action': self.action.value,
            'contracts': self.contracts,
            'target_hedge_ratio': self.target_hedge_ratio,
            'reason': self.reason,
            'market_condition': self.market_condition.value,
            'confidence': self.confidence,
            'should_hedge': self.should_hedge,
        }


@dataclass
class PortfolioBeta:
    """포트폴리오 베타"""
    portfolio_beta: float
    stock_betas: Dict[str, float]
    r_squared: float  # 결정계수
    calculation_date: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'portfolio_beta': self.portfolio_beta,
            'stock_betas': self.stock_betas,
            'r_squared': self.r_squared,
            'calculation_date': self.calculation_date.isoformat(),
        }


class FuturesHedger:
    """KOSPI200 선물 헤저

    Usage:
        hedger = FuturesHedger()

        # 베타 계산
        beta = hedger.calculate_portfolio_beta(portfolio, market_df)

        # 헤지 신호 확인
        signal = hedger.get_hedge_signal(portfolio_value, volatility, current_loss)

        # 헤지 계약수 계산
        contracts = hedger.calculate_hedge_contracts(
            portfolio_value=100_000_000,
            portfolio_beta=1.2,
            futures_price=350.0,
            hedge_ratio=0.5
        )
    """

    def __init__(
        self,
        config: Optional[HedgeConfig] = None,
        kis_api: Optional[Any] = None,
    ):
        """초기화

        Args:
            config: 헤지 설정
            kis_api: KIS API 클라이언트 (선물 주문용)
        """
        self.config = config or HedgeConfig()
        self.kis_api = kis_api
        self.current_position: Optional[HedgePosition] = None
        self.trade_history: List[Dict] = []

        logger.info("FuturesHedger 초기화 완료")

    def calculate_stock_beta(
        self,
        stock_returns: pd.Series,
        market_returns: pd.Series,
    ) -> Tuple[float, float]:
        """개별 종목 베타 계산

        Args:
            stock_returns: 종목 수익률 시리즈
            market_returns: 시장 수익률 시리즈

        Returns:
            (베타, R-squared)
        """
        # 공통 인덱스
        common_idx = stock_returns.index.intersection(market_returns.index)
        stock_r = stock_returns.loc[common_idx]
        market_r = market_returns.loc[common_idx]

        if len(common_idx) < 20:
            logger.warning("데이터가 부족합니다 (최소 20일 필요)")
            return 1.0, 0.0

        # 베타 = Cov(stock, market) / Var(market)
        covariance = np.cov(stock_r, market_r)[0, 1]
        market_variance = np.var(market_r)

        if market_variance == 0:
            return 1.0, 0.0

        beta = covariance / market_variance

        # R-squared
        correlation = np.corrcoef(stock_r, market_r)[0, 1]
        r_squared = correlation ** 2

        return float(beta), float(r_squared)

    def calculate_portfolio_beta(
        self,
        portfolio: Dict[str, Dict],
        stock_data: Dict[str, pd.DataFrame],
        market_data: pd.DataFrame,
        lookback_days: int = 60,
    ) -> PortfolioBeta:
        """포트폴리오 베타 계산

        Args:
            portfolio: 포트폴리오 {'종목코드': {'value': 금액, 'weight': 비중}}
            stock_data: 종목별 가격 데이터
            market_data: KOSPI200 지수 데이터
            lookback_days: 분석 기간

        Returns:
            PortfolioBeta
        """
        # 시장 수익률
        market_returns = market_data['close'].pct_change().dropna().tail(lookback_days)

        stock_betas = {}
        weighted_beta = 0.0
        total_r_squared = 0.0

        for stock_code, position in portfolio.items():
            weight = position.get('weight', 0)

            if stock_code not in stock_data:
                # 데이터 없으면 베타 1 가정
                stock_betas[stock_code] = 1.0
                weighted_beta += weight * 1.0
                continue

            stock_df = stock_data[stock_code]
            stock_returns = stock_df['close'].pct_change().dropna().tail(lookback_days)

            beta, r_sq = self.calculate_stock_beta(stock_returns, market_returns)
            stock_betas[stock_code] = beta
            weighted_beta += weight * beta
            total_r_squared += weight * r_sq

        return PortfolioBeta(
            portfolio_beta=weighted_beta,
            stock_betas=stock_betas,
            r_squared=total_r_squared,
        )

    def detect_market_condition(
        self,
        market_data: pd.DataFrame,
        vix: Optional[float] = None,
    ) -> MarketCondition:
        """시장 상황 감지

        Args:
            market_data: KOSPI200 데이터
            vix: VIX 지수 (없으면 변동성으로 대체)

        Returns:
            MarketCondition
        """
        if len(market_data) < 20:
            return MarketCondition.NEUTRAL

        # 최근 수익률
        returns_5d = (market_data['close'].iloc[-1] / market_data['close'].iloc[-5] - 1)
        returns_20d = (market_data['close'].iloc[-1] / market_data['close'].iloc[-20] - 1)

        # 변동성 (연율화)
        daily_vol = market_data['close'].pct_change().tail(20).std()
        annualized_vol = daily_vol * np.sqrt(252) * 100

        # VIX 대용
        if vix is None:
            vix = annualized_vol * 1.5  # 근사값

        # 시장 상황 판단
        if returns_5d < -0.05 or vix > 35:
            return MarketCondition.CRISIS
        elif returns_20d < -0.03 or vix > 25:
            return MarketCondition.BEARISH
        elif returns_20d > 0.03 and vix < 15:
            return MarketCondition.BULLISH
        else:
            return MarketCondition.NEUTRAL

    def get_hedge_signal(
        self,
        portfolio_value: float,
        portfolio_beta: float,
        market_data: pd.DataFrame,
        current_loss: float = 0.0,
        vix: Optional[float] = None,
    ) -> HedgeSignal:
        """헤지 신호 생성

        Args:
            portfolio_value: 포트폴리오 가치
            portfolio_beta: 포트폴리오 베타
            market_data: KOSPI200 데이터
            current_loss: 현재 손실률 (음수)
            vix: VIX 지수

        Returns:
            HedgeSignal
        """
        market_condition = self.detect_market_condition(market_data, vix)
        futures_price = market_data['close'].iloc[-1]

        # 시장 상황별 목표 헤지 비율
        target_ratio = self.config.hedge_ratios_by_condition.get(
            market_condition.value,
            self.config.target_hedge_ratio
        )

        # 손실이 크면 헤지 비율 증가
        if current_loss < -self.config.max_portfolio_loss:
            target_ratio = min(target_ratio + 0.2, self.config.max_hedge_ratio)

        # 베타가 높으면 헤지 비율 조정
        if portfolio_beta > self.config.beta_threshold:
            target_ratio = min(target_ratio * portfolio_beta, self.config.max_hedge_ratio)

        # 현재 헤지 포지션
        current_contracts = self.current_position.contracts if self.current_position else 0
        current_hedge_ratio = self._calculate_current_hedge_ratio(
            portfolio_value, portfolio_beta, futures_price, current_contracts
        )

        # 필요한 계약 수
        target_contracts = self.calculate_hedge_contracts(
            portfolio_value, portfolio_beta, futures_price, target_ratio
        )
        contracts_diff = target_contracts - abs(current_contracts)

        # 행동 결정
        if current_contracts == 0 and target_ratio > 0:
            action = HedgeAction.OPEN
            reason = f"시장 상황 {market_condition.value}, 헤지 시작"
        elif target_ratio == 0 and current_contracts != 0:
            action = HedgeAction.CLOSE
            reason = "상승장 진입, 헤지 청산"
            contracts_diff = -abs(current_contracts)
        elif contracts_diff > 0:
            action = HedgeAction.INCREASE
            reason = f"헤지 비율 확대 {current_hedge_ratio:.1%} → {target_ratio:.1%}"
        elif contracts_diff < 0:
            action = HedgeAction.DECREASE
            reason = f"헤지 비율 축소 {current_hedge_ratio:.1%} → {target_ratio:.1%}"
        else:
            action = HedgeAction.HOLD
            reason = "현재 헤지 비율 유지"
            contracts_diff = 0

        confidence = self._calculate_confidence(market_condition, current_loss, vix)

        return HedgeSignal(
            action=action,
            contracts=contracts_diff,
            target_hedge_ratio=target_ratio,
            reason=reason,
            market_condition=market_condition,
            confidence=confidence,
        )

    def _calculate_current_hedge_ratio(
        self,
        portfolio_value: float,
        portfolio_beta: float,
        futures_price: float,
        contracts: int,
    ) -> float:
        """현재 헤지 비율 계산"""
        if portfolio_value == 0:
            return 0.0

        hedge_value = abs(contracts) * futures_price * KOSPI200_FUTURES_MULTIPLIER
        beta_adjusted_portfolio = portfolio_value * portfolio_beta

        return hedge_value / beta_adjusted_portfolio if beta_adjusted_portfolio > 0 else 0.0

    def _calculate_confidence(
        self,
        condition: MarketCondition,
        loss: float,
        vix: Optional[float],
    ) -> float:
        """신호 신뢰도 계산"""
        confidence = 0.5

        # 시장 상황별 기본 신뢰도
        condition_confidence = {
            MarketCondition.CRISIS: 0.9,
            MarketCondition.BEARISH: 0.7,
            MarketCondition.NEUTRAL: 0.5,
            MarketCondition.BULLISH: 0.6,
        }
        confidence = condition_confidence.get(condition, 0.5)

        # 손실이 클수록 신뢰도 증가
        if loss < -0.05:
            confidence += 0.2

        # VIX가 높을수록 신뢰도 증가
        if vix and vix > 30:
            confidence += 0.1

        return min(confidence, 1.0)

    def calculate_hedge_contracts(
        self,
        portfolio_value: float,
        portfolio_beta: float,
        futures_price: float,
        hedge_ratio: float = 1.0,
    ) -> int:
        """필요한 선물 계약 수 계산

        Args:
            portfolio_value: 포트폴리오 가치 (원)
            portfolio_beta: 포트폴리오 베타
            futures_price: 선물 가격 (포인트)
            hedge_ratio: 헤지 비율 (0-1)

        Returns:
            계약 수 (항상 양수, 매도 포지션)
        """
        # 헤지 금액 = 포트폴리오 × 베타 × 헤지비율
        hedge_amount = portfolio_value * portfolio_beta * hedge_ratio

        # 1계약 가치
        contract_value = futures_price * KOSPI200_FUTURES_MULTIPLIER

        # 필요 계약 수 (반올림)
        contracts = int(round(hedge_amount / contract_value))

        return max(contracts, 0)

    def calculate_margin_required(
        self,
        contracts: int,
        futures_price: float,
    ) -> float:
        """필요 증거금 계산

        Args:
            contracts: 계약 수
            futures_price: 선물 가격

        Returns:
            필요 증거금 (원)
        """
        contract_value = abs(contracts) * futures_price * KOSPI200_FUTURES_MULTIPLIER
        return contract_value * MARGIN_RATE

    def open_hedge(
        self,
        signal: HedgeSignal,
        futures_price: float,
    ) -> Optional[HedgePosition]:
        """헤지 포지션 오픈

        Args:
            signal: 헤지 신호
            futures_price: 현재 선물 가격

        Returns:
            HedgePosition or None
        """
        if not signal.should_hedge:
            logger.warning("헤지 신호가 아닙니다")
            return None

        contracts = -abs(signal.contracts)  # 매도 포지션
        margin = self.calculate_margin_required(contracts, futures_price)

        # 실제 주문 (KIS API 연동)
        if self.kis_api:
            try:
                # 실제 API 호출 (구현 필요)
                # order_result = self.kis_api.futures_order(...)
                pass
            except Exception as e:
                logger.error(f"선물 주문 실패: {e}", exc_info=True)
                return None

        position = HedgePosition(
            contracts=contracts,
            entry_price=futures_price,
            entry_date=datetime.now(),
            margin_required=margin,
            current_price=futures_price,
        )

        self.current_position = position
        self.trade_history.append({
            'action': 'open',
            'contracts': contracts,
            'price': futures_price,
            'datetime': datetime.now().isoformat(),
            'reason': signal.reason,
        })

        logger.info(
            f"헤지 오픈: {abs(contracts)}계약 매도 @ {futures_price}, "
            f"증거금: {margin:,.0f}원"
        )

        return position

    def close_hedge(
        self,
        futures_price: float,
        reason: str = "수동 청산",
    ) -> Optional[float]:
        """헤지 포지션 청산

        Args:
            futures_price: 현재 선물 가격
            reason: 청산 사유

        Returns:
            실현 손익 (원)
        """
        if not self.current_position:
            logger.warning("청산할 포지션이 없습니다")
            return None

        pos = self.current_position
        pos.update_price(futures_price)
        realized_pnl = pos.unrealized_pnl

        # 거래 비용 차감
        trade_cost = abs(pos.contracts) * futures_price * KOSPI200_FUTURES_MULTIPLIER * self.config.commission_rate
        realized_pnl -= trade_cost

        # 실제 청산 주문
        if self.kis_api:
            try:
                # 실제 API 호출 (구현 필요)
                # order_result = self.kis_api.futures_order(...)
                pass
            except Exception as e:
                logger.error(f"선물 청산 실패: {e}", exc_info=True)
                return None

        self.trade_history.append({
            'action': 'close',
            'contracts': -pos.contracts,
            'entry_price': pos.entry_price,
            'exit_price': futures_price,
            'realized_pnl': realized_pnl,
            'datetime': datetime.now().isoformat(),
            'reason': reason,
        })

        logger.info(
            f"헤지 청산: {abs(pos.contracts)}계약 @ {futures_price}, "
            f"진입가: {pos.entry_price}, 실현손익: {realized_pnl:,.0f}원"
        )

        self.current_position = None

        return realized_pnl

    def adjust_hedge(
        self,
        signal: HedgeSignal,
        futures_price: float,
    ) -> Optional[int]:
        """헤지 조정

        Args:
            signal: 헤지 신호
            futures_price: 현재 선물 가격

        Returns:
            조정된 계약 수
        """
        if not self.current_position:
            return self.open_hedge(signal, futures_price).contracts if signal.should_hedge else None

        if signal.action == HedgeAction.CLOSE:
            self.close_hedge(futures_price, signal.reason)
            return 0

        if signal.action in [HedgeAction.INCREASE, HedgeAction.DECREASE]:
            adjust_contracts = signal.contracts

            # 기존 포지션 업데이트
            new_contracts = self.current_position.contracts + (-abs(adjust_contracts) if signal.action == HedgeAction.INCREASE else abs(adjust_contracts))

            # 평균 단가 조정 (추가 매도시)
            if signal.action == HedgeAction.INCREASE:
                old_value = abs(self.current_position.contracts) * self.current_position.entry_price
                new_value = abs(adjust_contracts) * futures_price
                total_contracts = abs(new_contracts)
                if total_contracts > 0:
                    self.current_position.entry_price = (old_value + new_value) / total_contracts

            self.current_position.contracts = new_contracts
            self.current_position.margin_required = self.calculate_margin_required(
                new_contracts, futures_price
            )

            self.trade_history.append({
                'action': signal.action.value,
                'contracts': adjust_contracts,
                'price': futures_price,
                'datetime': datetime.now().isoformat(),
                'reason': signal.reason,
            })

            logger.info(f"헤지 조정: {adjust_contracts}계약, 총 {new_contracts}계약")

            return new_contracts

        return self.current_position.contracts

    def get_hedge_stats(self) -> Dict[str, Any]:
        """헤지 통계"""
        total_trades = len(self.trade_history)
        closed_trades = [t for t in self.trade_history if t['action'] == 'close']

        total_pnl = sum(t.get('realized_pnl', 0) for t in closed_trades)
        wins = sum(1 for t in closed_trades if t.get('realized_pnl', 0) > 0)
        losses = len(closed_trades) - wins

        return {
            'total_trades': total_trades,
            'closed_trades': len(closed_trades),
            'total_pnl': total_pnl,
            'win_count': wins,
            'loss_count': losses,
            'win_rate': wins / len(closed_trades) if closed_trades else 0.0,
            'current_position': self.current_position.to_dict() if self.current_position else None,
        }

    def update_position_price(self, futures_price: float):
        """포지션 가격 업데이트"""
        if self.current_position:
            self.current_position.update_price(futures_price)


def create_sample_portfolio() -> Dict[str, Dict]:
    """테스트용 샘플 포트폴리오"""
    return {
        '005930': {'value': 30_000_000, 'weight': 0.3},  # 삼성전자
        '000660': {'value': 20_000_000, 'weight': 0.2},  # SK하이닉스
        '035420': {'value': 15_000_000, 'weight': 0.15},  # NAVER
        '051910': {'value': 15_000_000, 'weight': 0.15},  # LG화학
        '006400': {'value': 20_000_000, 'weight': 0.2},  # 삼성SDI
    }


def create_sample_market_data(days: int = 100) -> pd.DataFrame:
    """테스트용 샘플 시장 데이터"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    price = 350.0
    prices = []
    for _ in range(days):
        price *= (1 + np.random.randn() * 0.015)
        prices.append(price)

    return pd.DataFrame({
        'open': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'close': prices,
        'volume': np.random.randint(50000, 200000, days),
    }, index=dates)
