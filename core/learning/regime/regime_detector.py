"""
시장 레짐 판단 엔진

Task C.2.1: RegimeDetector 클래스 생성
Task C.2.2: 규칙 기반 레짐 판단 로직
Task C.2.3: 레짐 확신도 점수 계산
Task C.2.4: 레짐 전환 감지 및 알림
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

from core.utils.log_utils import get_logger
from core.daily_selection.selection_criteria import MarketCondition
from .market_indicator_collector import MarketIndicators, get_market_indicator_collector

logger = get_logger(__name__)


@dataclass
class RegimeScore:
    """레짐별 점수"""
    regime: MarketCondition
    score: float           # 0 ~ 100
    factors: Dict[str, float]  # 점수 구성 요소

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['regime'] = self.regime.value
        return result


@dataclass
class RegimeResult:
    """레짐 판단 결과"""
    detected_regime: MarketCondition
    confidence: float              # 0 ~ 1 (확신도)
    scores: Dict[str, RegimeScore] # 레짐별 점수
    indicators_used: MarketIndicators
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 레짐 전환 관련
    previous_regime: Optional[MarketCondition] = None
    regime_changed: bool = False
    regime_duration_days: int = 0

    @property
    def regime(self) -> MarketCondition:
        """호환성을 위한 별칭"""
        return self.detected_regime

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'detected_regime': self.detected_regime.value,
            'confidence': self.confidence,
            'scores': {k: v.to_dict() for k, v in self.scores.items()},
            'detected_at': self.detected_at,
            'previous_regime': self.previous_regime.value if self.previous_regime else None,
            'regime_changed': self.regime_changed,
            'regime_duration_days': self.regime_duration_days
        }
        return result


class RegimeDetector:
    """시장 레짐 탐지기"""

    # 레짐별 판단 기준 임계값
    THRESHOLDS = {
        'bull_strong': 0.70,      # 강한 상승장
        'bull_weak': 0.55,        # 약한 상승장
        'bear_strong': 0.70,      # 강한 하락장
        'bear_weak': 0.55,        # 약한 하락장
        'volatile': 0.60,         # 변동성 장
        'sideways': 0.50,         # 횡보장
        'confidence_threshold': 0.3  # 최소 확신도
    }

    def __init__(self,
                 indicator_collector: Optional[Any] = None,
                 state_dir: str = "data/learning/regime"):
        """
        초기화

        Args:
            indicator_collector: 시장 지표 수집기
            state_dir: 상태 저장 디렉토리
        """
        self._collector = indicator_collector or get_market_indicator_collector()
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)

        # 이전 레짐 상태
        self._state = self._load_state()

        logger.info("RegimeDetector 초기화 완료")

    def detect(self, indicators: Optional[MarketIndicators] = None) -> RegimeResult:
        """
        시장 레짐 탐지 (C.2.1)

        Args:
            indicators: 시장 지표 (None이면 자동 수집)

        Returns:
            레짐 판단 결과
        """
        # 지표 수집
        if indicators is None:
            indicators = self._collector.collect()

        # 각 레짐별 점수 계산 (C.2.2)
        scores = self._calculate_all_regime_scores(indicators)

        # 최고 점수 레짐 선택
        best_regime = max(scores.values(), key=lambda x: x.score)
        detected_regime = best_regime.regime

        # 확신도 계산 (C.2.3)
        confidence = self._calculate_confidence(scores)

        # 이전 레짐과 비교 (C.2.4)
        previous_regime = self._state.get('current_regime')
        regime_changed = False
        regime_duration = 0

        if previous_regime:
            previous_regime = MarketCondition(previous_regime)
            if previous_regime != detected_regime:
                regime_changed = True
                self._handle_regime_change(previous_regime, detected_regime, confidence)
            else:
                regime_duration = self._state.get('regime_duration_days', 0) + 1
        else:
            regime_duration = 1

        # 상태 업데이트
        self._update_state(detected_regime, regime_duration)

        result = RegimeResult(
            detected_regime=detected_regime,
            confidence=confidence,
            scores={r.regime.value: r for r in scores.values()},
            indicators_used=indicators,
            previous_regime=previous_regime,
            regime_changed=regime_changed,
            regime_duration_days=regime_duration
        )

        logger.info(f"레짐 탐지: {detected_regime.value} (확신도: {confidence:.2f})")
        return result

    def _calculate_all_regime_scores(self,
                                    indicators: MarketIndicators) -> Dict[MarketCondition, RegimeScore]:
        """모든 레짐에 대한 점수 계산 (C.2.2)"""
        scores = {}

        scores[MarketCondition.BULL_MARKET] = self._calculate_bull_score(indicators)
        scores[MarketCondition.BEAR_MARKET] = self._calculate_bear_score(indicators)
        scores[MarketCondition.SIDEWAYS] = self._calculate_sideways_score(indicators)
        scores[MarketCondition.VOLATILE] = self._calculate_volatile_score(indicators)
        scores[MarketCondition.RECOVERY] = self._calculate_recovery_score(indicators)

        return scores

    def _calculate_bull_score(self, ind: MarketIndicators) -> RegimeScore:
        """상승장 점수 계산"""
        factors = {}
        total_score = 0.0

        # 1. 지수 추세 (30점)
        trend_score = 0.0
        if ind.kospi_20d_return > 0.05:
            trend_score += 15
        elif ind.kospi_20d_return > 0.02:
            trend_score += 10
        elif ind.kospi_20d_return > 0:
            trend_score += 5

        if ind.kospi_60d_return > 0.10:
            trend_score += 15
        elif ind.kospi_60d_return > 0.05:
            trend_score += 10
        elif ind.kospi_60d_return > 0:
            trend_score += 5

        factors['trend'] = trend_score
        total_score += trend_score

        # 2. 이동평균 위치 (25점)
        ma_score = 0.0
        if ind.kospi_vs_ma20 > 0.02:
            ma_score += 10
        elif ind.kospi_vs_ma20 > 0:
            ma_score += 5

        if ind.kospi_vs_ma60 > 0.03:
            ma_score += 8
        elif ind.kospi_vs_ma60 > 0:
            ma_score += 4

        if ind.kospi_vs_ma200 > 0:
            ma_score += 7

        factors['ma_position'] = ma_score
        total_score += ma_score

        # 3. 시장 폭 (25점)
        breadth_score = 0.0
        if ind.advance_decline_ratio > 1.5:
            breadth_score += 10
        elif ind.advance_decline_ratio > 1.2:
            breadth_score += 5

        if ind.above_ma200_ratio > 0.6:
            breadth_score += 8
        elif ind.above_ma200_ratio > 0.5:
            breadth_score += 4

        if ind.new_high_low_ratio > 2:
            breadth_score += 7
        elif ind.new_high_low_ratio > 1:
            breadth_score += 3

        factors['breadth'] = breadth_score
        total_score += breadth_score

        # 4. 투자심리 (20점)
        sentiment_score = 0.0
        if ind.fear_greed_score > 60:
            sentiment_score += 10
        elif ind.fear_greed_score > 50:
            sentiment_score += 5

        if ind.foreign_net_buy > 0:
            sentiment_score += 5
        if ind.institution_net_buy > 0:
            sentiment_score += 5

        factors['sentiment'] = sentiment_score
        total_score += sentiment_score

        return RegimeScore(
            regime=MarketCondition.BULL_MARKET,
            score=total_score,
            factors=factors
        )

    def _calculate_bear_score(self, ind: MarketIndicators) -> RegimeScore:
        """하락장 점수 계산"""
        factors = {}
        total_score = 0.0

        # 1. 지수 추세 (30점)
        trend_score = 0.0
        if ind.kospi_20d_return < -0.05:
            trend_score += 15
        elif ind.kospi_20d_return < -0.02:
            trend_score += 10
        elif ind.kospi_20d_return < 0:
            trend_score += 5

        if ind.kospi_60d_return < -0.10:
            trend_score += 15
        elif ind.kospi_60d_return < -0.05:
            trend_score += 10
        elif ind.kospi_60d_return < 0:
            trend_score += 5

        factors['trend'] = trend_score
        total_score += trend_score

        # 2. 이동평균 위치 (25점)
        ma_score = 0.0
        if ind.kospi_vs_ma20 < -0.02:
            ma_score += 10
        elif ind.kospi_vs_ma20 < 0:
            ma_score += 5

        if ind.kospi_vs_ma60 < -0.03:
            ma_score += 8
        elif ind.kospi_vs_ma60 < 0:
            ma_score += 4

        if ind.kospi_vs_ma200 < 0:
            ma_score += 7

        factors['ma_position'] = ma_score
        total_score += ma_score

        # 3. 시장 폭 (25점)
        breadth_score = 0.0
        if ind.advance_decline_ratio < 0.67:
            breadth_score += 10
        elif ind.advance_decline_ratio < 0.83:
            breadth_score += 5

        if ind.above_ma200_ratio < 0.4:
            breadth_score += 8
        elif ind.above_ma200_ratio < 0.5:
            breadth_score += 4

        if ind.new_high_low_ratio < 0.5:
            breadth_score += 7
        elif ind.new_high_low_ratio < 1:
            breadth_score += 3

        factors['breadth'] = breadth_score
        total_score += breadth_score

        # 4. 투자심리 (20점)
        sentiment_score = 0.0
        if ind.fear_greed_score < 40:
            sentiment_score += 10
        elif ind.fear_greed_score < 50:
            sentiment_score += 5

        if ind.foreign_net_buy < 0:
            sentiment_score += 5
        if ind.institution_net_buy < 0:
            sentiment_score += 5

        factors['sentiment'] = sentiment_score
        total_score += sentiment_score

        return RegimeScore(
            regime=MarketCondition.BEAR_MARKET,
            score=total_score,
            factors=factors
        )

    def _calculate_sideways_score(self, ind: MarketIndicators) -> RegimeScore:
        """횡보장 점수 계산"""
        factors = {}
        total_score = 0.0

        # 1. 지수 변동 범위 (35점)
        range_score = 0.0
        # 20일 수익률이 ±3% 이내
        if abs(ind.kospi_20d_return) < 0.03:
            range_score += 20
        elif abs(ind.kospi_20d_return) < 0.05:
            range_score += 10

        # 60일 수익률이 ±5% 이내
        if abs(ind.kospi_60d_return) < 0.05:
            range_score += 15
        elif abs(ind.kospi_60d_return) < 0.08:
            range_score += 8

        factors['range'] = range_score
        total_score += range_score

        # 2. 변동성 (30점)
        vol_score = 0.0
        if ind.market_volatility < 0.12:
            vol_score += 15
        elif ind.market_volatility < 0.18:
            vol_score += 8

        if ind.volatility_percentile < 40:
            vol_score += 15
        elif ind.volatility_percentile < 60:
            vol_score += 8

        factors['volatility'] = vol_score
        total_score += vol_score

        # 3. 균형 지표 (35점)
        balance_score = 0.0
        # 등락비가 균형 상태
        if 0.8 < ind.advance_decline_ratio < 1.2:
            balance_score += 15
        elif 0.7 < ind.advance_decline_ratio < 1.4:
            balance_score += 8

        # 투자심리 중립
        if 40 < ind.fear_greed_score < 60:
            balance_score += 10

        # 이평선 근처
        if abs(ind.kospi_vs_ma20) < 0.01:
            balance_score += 10
        elif abs(ind.kospi_vs_ma20) < 0.02:
            balance_score += 5

        factors['balance'] = balance_score
        total_score += balance_score

        return RegimeScore(
            regime=MarketCondition.SIDEWAYS,
            score=total_score,
            factors=factors
        )

    def _calculate_volatile_score(self, ind: MarketIndicators) -> RegimeScore:
        """변동성 장 점수 계산"""
        factors = {}
        total_score = 0.0

        # 1. 변동성 지표 (40점)
        vol_score = 0.0
        if ind.market_volatility > 0.25:
            vol_score += 20
        elif ind.market_volatility > 0.20:
            vol_score += 12
        elif ind.market_volatility > 0.15:
            vol_score += 6

        if ind.volatility_percentile > 75:
            vol_score += 20
        elif ind.volatility_percentile > 60:
            vol_score += 12
        elif ind.volatility_percentile > 50:
            vol_score += 6

        factors['volatility'] = vol_score
        total_score += vol_score

        # 2. 일간 변동 (30점)
        daily_score = 0.0
        if abs(ind.kospi_change) > 0.02:
            daily_score += 15
        elif abs(ind.kospi_change) > 0.01:
            daily_score += 8

        # 거래량 급증
        if ind.volume_ratio > 1.5:
            daily_score += 15
        elif ind.volume_ratio > 1.2:
            daily_score += 8

        factors['daily'] = daily_score
        total_score += daily_score

        # 3. 투자심리 극단 (30점)
        sentiment_score = 0.0
        if ind.fear_greed_score < 25 or ind.fear_greed_score > 75:
            sentiment_score += 15
        elif ind.fear_greed_score < 35 or ind.fear_greed_score > 65:
            sentiment_score += 8

        # 풋콜 비율 극단
        if ind.put_call_ratio > 1.3 or ind.put_call_ratio < 0.7:
            sentiment_score += 15
        elif ind.put_call_ratio > 1.1 or ind.put_call_ratio < 0.9:
            sentiment_score += 8

        factors['sentiment'] = sentiment_score
        total_score += sentiment_score

        return RegimeScore(
            regime=MarketCondition.VOLATILE,
            score=total_score,
            factors=factors
        )

    def _calculate_recovery_score(self, ind: MarketIndicators) -> RegimeScore:
        """회복장 점수 계산"""
        factors = {}
        total_score = 0.0

        # 1. 단기 반등 (35점)
        bounce_score = 0.0
        # 5일 수익률 양수 + 20일 수익률 음수 (저점 반등)
        if ind.kospi_5d_return > 0.02 and ind.kospi_20d_return < 0:
            bounce_score += 20
        elif ind.kospi_5d_return > 0.01 and ind.kospi_20d_return < 0.02:
            bounce_score += 10

        # 이평선 돌파 시도
        if ind.kospi_vs_ma20 > -0.01 and ind.kospi_vs_ma60 < 0:
            bounce_score += 15
        elif ind.kospi_vs_ma20 > -0.02:
            bounce_score += 8

        factors['bounce'] = bounce_score
        total_score += bounce_score

        # 2. 시장 폭 개선 (35점)
        breadth_score = 0.0
        # 등락비 개선 (1 이상)
        if ind.advance_decline_ratio > 1.2:
            breadth_score += 15
        elif ind.advance_decline_ratio > 1.0:
            breadth_score += 8

        # 200일선 위 종목 증가
        if 0.35 < ind.above_ma200_ratio < 0.55:
            breadth_score += 10  # 회복 중간 단계
        elif ind.above_ma200_ratio > 0.55:
            breadth_score += 5

        # 신고/신저 비율 개선
        if ind.new_high_low_ratio > 0.8 and ind.new_high_low_ratio < 1.5:
            breadth_score += 10

        factors['breadth'] = breadth_score
        total_score += breadth_score

        # 3. 거래량 증가 (30점)
        volume_score = 0.0
        if ind.volume_ratio > 1.3:
            volume_score += 15
        elif ind.volume_ratio > 1.1:
            volume_score += 8

        # 투자심리 회복
        if 35 < ind.fear_greed_score < 55:
            volume_score += 15
        elif 30 < ind.fear_greed_score < 60:
            volume_score += 8

        factors['volume'] = volume_score
        total_score += volume_score

        return RegimeScore(
            regime=MarketCondition.RECOVERY,
            score=total_score,
            factors=factors
        )

    def _calculate_confidence(self,
                             scores: Dict[MarketCondition, RegimeScore]) -> float:
        """
        확신도 계산 (C.2.3)

        점수 차이가 클수록 높은 확신도
        """
        sorted_scores = sorted(scores.values(), key=lambda x: x.score, reverse=True)

        if len(sorted_scores) < 2:
            return 0.5

        best_score = sorted_scores[0].score
        second_score = sorted_scores[1].score

        # 최대 점수 대비 1위와 2위 차이
        max_possible = 100.0
        score_gap = best_score - second_score

        # 확신도 = (1위 점수 / 최대) * (1위-2위 차이 보정)
        base_confidence = best_score / max_possible
        gap_factor = min(1.0, score_gap / 30.0)  # 30점 차이면 100% 확신

        confidence = base_confidence * 0.5 + gap_factor * 0.5
        return min(1.0, max(0.0, confidence))

    def _handle_regime_change(self,
                              previous: MarketCondition,
                              current: MarketCondition,
                              confidence: float):
        """
        레짐 전환 처리 (C.2.4)
        """
        logger.info(f"레짐 전환 감지: {previous.value} → {current.value} (확신도: {confidence:.2f})")

        # 알림 발송 (선택적)
        if confidence > 0.5:
            self._send_regime_change_notification(previous, current, confidence)

        # 전환 이력 저장
        self._save_regime_change_history(previous, current, confidence)

    def _send_regime_change_notification(self,
                                         previous: MarketCondition,
                                         current: MarketCondition,
                                         confidence: float):
        """레짐 전환 알림"""
        try:
            from core.utils.telegram_notifier import get_telegram_notifier

            notifier = get_telegram_notifier()
            message = f"""
📊 시장 레짐 전환 감지

🔄 {previous.value} → {current.value}
📈 확신도: {confidence:.1%}
⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}

전략 자동 조정이 적용됩니다.
"""
            notifier.send_message(message, priority="high")
            logger.info("레짐 전환 알림 발송")

        except Exception as e:
            logger.warning(f"레짐 전환 알림 발송 실패: {e}")

    def _save_regime_change_history(self,
                                   previous: MarketCondition,
                                   current: MarketCondition,
                                   confidence: float):
        """레짐 전환 이력 저장"""
        history_file = self._state_dir / "regime_change_history.json"

        try:
            history = []
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)

            history.append({
                'timestamp': datetime.now().isoformat(),
                'previous_regime': previous.value,
                'current_regime': current.value,
                'confidence': confidence
            })

            # 최근 100개만 유지
            history = history[-100:]

            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"레짐 전환 이력 저장 실패: {e}", exc_info=True)

    def _update_state(self, regime: MarketCondition, duration: int):
        """상태 업데이트"""
        self._state['current_regime'] = regime.value
        self._state['regime_duration_days'] = duration
        self._state['last_detected'] = datetime.now().isoformat()
        self._save_state()

    def _load_state(self) -> Dict[str, Any]:
        """상태 로드"""
        state_file = self._state_dir / "detector_state.json"

        try:
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"레짐 상태 로드 실패: {e}", exc_info=True)

        return {}

    def _save_state(self):
        """상태 저장"""
        state_file = self._state_dir / "detector_state.json"

        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"레짐 상태 저장 실패: {e}", exc_info=True)

    def get_current_regime(self) -> Optional[MarketCondition]:
        """현재 레짐 조회"""
        regime_value = self._state.get('current_regime')
        if regime_value:
            return MarketCondition(regime_value)
        return None

    def get_regime_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """레짐 전환 이력 조회"""
        history_file = self._state_dir / "regime_change_history.json"

        try:
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    return history[-limit:]
        except Exception:
            pass

        return []


# 싱글톤 인스턴스
_detector_instance: Optional[RegimeDetector] = None


def get_regime_detector() -> RegimeDetector:
    """RegimeDetector 싱글톤 인스턴스 반환"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = RegimeDetector()
    return _detector_instance
