"""
향상된 주식 스크리닝 시스템
새로운 지표들 (VWAP, ADX, MFI, Ichimoku, Pattern Recognition, A/D Line) 통합
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from core.utils.log_utils import get_logger
from core.watchlist.stock_screener import StockScreener
from core.api.rest_client import KISRestClient

# 새로운 지표들 import
from hantu_common.indicators.vwap import VWAP
from hantu_common.indicators.adx import ADX
from hantu_common.indicators.mfi import MFI
from hantu_common.indicators.ichimoku import Ichimoku
from hantu_common.indicators.pattern_recognition import PatternRecognition
from hantu_common.indicators.accumulation_distribution import AccumulationDistribution

logger = get_logger(__name__)


class EnhancedScreener(StockScreener):
    """향상된 스크리닝 시스템"""

    def __init__(self):
        """초기화"""
        super().__init__()
        self.rest_client = KISRestClient()
        logger.info("향상된 스크리너 초기화 완료")

    def calculate_enhanced_indicators(self, stock_code: str,
                                     period: int = 60) -> Optional[Dict[str, Any]]:
        """
        향상된 지표 계산

        Args:
            stock_code: 종목 코드
            period: 데이터 기간

        Returns:
            향상된 지표 데이터
        """
        try:
            # 가격 데이터 가져오기
            try:
                df = self.rest_client.fetch_price_data(stock_code, count=period)
            except:
                # 대체 방법으로 시도
                df = None
            if df is None or len(df) < 30:
                return None

            indicators = {}

            # 1. VWAP 계산
            try:
                vwap_data = VWAP.calculate(
                    df['close'], df['volume'],
                    df['high'], df['low']
                )
                vwap_signals = VWAP.get_trade_signals(df)

                indicators['vwap'] = {
                    'current_vwap': vwap_data.iloc[-1] if len(vwap_data) > 0 else None,
                    'price_vs_vwap': ((df['close'].iloc[-1] - vwap_data.iloc[-1]) /
                                     vwap_data.iloc[-1] * 100) if len(vwap_data) > 0 else 0,
                    'above_vwap': df['close'].iloc[-1] > vwap_data.iloc[-1] if len(vwap_data) > 0 else False,
                    'buy_signal': vwap_signals['buy_signal'].iloc[-1] if len(vwap_signals) > 0 else 0
                }
            except Exception as e:
                logger.warning(f"VWAP 계산 실패 ({stock_code}): {e}")
                indicators['vwap'] = None

            # 2. ADX 계산
            try:
                adx_data = ADX.calculate(df['high'], df['low'], df['close'])
                adx_signals = ADX.get_trade_signals(df)

                indicators['adx'] = {
                    'adx_value': adx_data['adx'].iloc[-1] if len(adx_data['adx']) > 0 else None,
                    'plus_di': adx_data['plus_di'].iloc[-1] if len(adx_data['plus_di']) > 0 else None,
                    'minus_di': adx_data['minus_di'].iloc[-1] if len(adx_data['minus_di']) > 0 else None,
                    'trend_strength': ADX.analyze_trend_strength(
                        adx_data['adx'].iloc[-1]) if len(adx_data['adx']) > 0 else 'no_trend',
                    'trend_direction': ADX.get_trend_direction(
                        adx_data['plus_di'].iloc[-1],
                        adx_data['minus_di'].iloc[-1]
                    ) if len(adx_data['plus_di']) > 0 else 'neutral'
                }
            except Exception as e:
                logger.warning(f"ADX 계산 실패 ({stock_code}): {e}")
                indicators['adx'] = None

            # 3. MFI 계산
            try:
                mfi_value = MFI.calculate(df['high'], df['low'], df['close'], df['volume'])
                mfi_signals = MFI.get_trade_signals(df)

                indicators['mfi'] = {
                    'mfi_value': mfi_value.iloc[-1] if len(mfi_value) > 0 else None,
                    'mfi_level': MFI.analyze_level(mfi_value.iloc[-1]) if len(mfi_value) > 0 else 'neutral',
                    'divergence': mfi_signals['divergence'].iloc[-1] if len(mfi_signals) > 0 else 0,
                    'buy_signal': mfi_signals['buy_signal'].iloc[-1] if len(mfi_signals) > 0 else 0
                }
            except Exception as e:
                logger.warning(f"MFI 계산 실패 ({stock_code}): {e}")
                indicators['mfi'] = None

            # 4. Ichimoku 계산
            try:
                ichimoku_data = Ichimoku.calculate(df['high'], df['low'], df['close'])
                ichimoku_signals = Ichimoku.get_trade_signals(df)

                indicators['ichimoku'] = {
                    'cloud_position': ichimoku_signals['cloud_position'].iloc[-1] if len(ichimoku_signals) > 0 else 'unknown',
                    'cloud_trend': ichimoku_signals['cloud_trend'].iloc[-1] if len(ichimoku_signals) > 0 else 'unknown',
                    'signal_strength': ichimoku_signals['signal_strength'].iloc[-1] if len(ichimoku_signals) > 0 else 0,
                    'tk_cross': ichimoku_signals['tk_cross'].iloc[-1] if len(ichimoku_signals) > 0 else 0
                }
            except Exception as e:
                logger.warning(f"Ichimoku 계산 실패 ({stock_code}): {e}")
                indicators['ichimoku'] = None

            # 5. Pattern Recognition
            try:
                pattern_signals = PatternRecognition.get_pattern_signals(df)

                indicators['patterns'] = {
                    'pattern_score': pattern_signals['pattern_score'].iloc[-1] if len(pattern_signals) > 0 else 0,
                    'breakout': pattern_signals['breakout'].iloc[-1] if len(pattern_signals) > 0 else 0,
                    'bullish_engulfing': pattern_signals['bullish_engulfing'].iloc[-1] if len(pattern_signals) > 0 else 0,
                    'morning_star': pattern_signals['morning_star'].iloc[-1] if len(pattern_signals) > 0 else 0
                }

                # 지지/저항선
                sr_levels = PatternRecognition.detect_support_resistance(df['close'])
                indicators['patterns']['support_levels'] = sr_levels.get('support', [])
                indicators['patterns']['resistance_levels'] = sr_levels.get('resistance', [])

            except Exception as e:
                logger.warning(f"Pattern Recognition 실패 ({stock_code}): {e}")
                indicators['patterns'] = None

            # 6. A/D Line 계산
            try:
                ad_signals = AccumulationDistribution.get_trade_signals(df)

                indicators['ad_line'] = {
                    'ad_value': ad_signals['ad_line'].iloc[-1] if len(ad_signals) > 0 else None,
                    'chaikin_osc': ad_signals['chaikin_osc'].iloc[-1] if len(ad_signals) > 0 else None,
                    'accumulation_phase': ad_signals['accumulation_phase'].iloc[-1] if len(ad_signals) > 0 else 'unknown',
                    'divergence': ad_signals['divergence'].iloc[-1] if len(ad_signals) > 0 else 0
                }
            except Exception as e:
                logger.warning(f"A/D Line 계산 실패 ({stock_code}): {e}")
                indicators['ad_line'] = None

            return indicators

        except Exception as e:
            logger.error(f"향상된 지표 계산 실패 ({stock_code}): {e}", exc_info=True)
            return None

    def enhanced_screening(self, stock_code: str, stock_name: str,
                          stock_data: Dict) -> Optional[Dict[str, Any]]:
        """
        향상된 스크리닝 수행

        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            stock_data: 기본 데이터

        Returns:
            스크리닝 결과
        """
        try:
            # 기본 스크리닝 수행
            basic_result = self.perform_screening(stock_code, stock_name, stock_data)
            if not basic_result:
                return None

            # 향상된 지표 계산
            enhanced_indicators = self.calculate_enhanced_indicators(stock_code)
            if not enhanced_indicators:
                return basic_result

            # 향상된 점수 계산
            enhanced_score = self.calculate_enhanced_score(enhanced_indicators)

            # 결과 통합
            result = {
                **basic_result,
                'enhanced_indicators': enhanced_indicators,
                'enhanced_score': enhanced_score,
                'total_score': (basic_result.get('total_score', 0) * 0.6 +
                              enhanced_score * 0.4)  # 기본 60%, 향상 40%
            }

            # 매매 신호 종합
            result['composite_signal'] = self.get_composite_signal(
                basic_result, enhanced_indicators
            )

            return result

        except Exception as e:
            logger.error(f"향상된 스크리닝 실패 ({stock_code}): {e}", exc_info=True)
            return None

    def calculate_enhanced_score(self, indicators: Dict[str, Any]) -> float:
        """
        향상된 지표 점수 계산

        Args:
            indicators: 지표 데이터

        Returns:
            향상된 점수 (0-100)
        """
        score = 0
        max_score = 0

        # VWAP 점수 (20점)
        if indicators.get('vwap'):
            max_score += 20
            if indicators['vwap'].get('above_vwap'):
                score += 10
            if indicators['vwap'].get('buy_signal') == 1:
                score += 10

        # ADX 점수 (20점)
        if indicators.get('adx'):
            max_score += 20
            trend = indicators['adx'].get('trend_strength', 'no_trend')
            if trend in ['strong_trend', 'very_strong_trend']:
                score += 10
            if indicators['adx'].get('trend_direction') == 'bullish':
                score += 10

        # MFI 점수 (15점)
        if indicators.get('mfi'):
            max_score += 15
            level = indicators['mfi'].get('mfi_level', 'neutral')
            if level == 'oversold':
                score += 10
            elif level == 'extreme_oversold':
                score += 15
            if indicators['mfi'].get('divergence') == 1:
                score += 5

        # Ichimoku 점수 (20점)
        if indicators.get('ichimoku'):
            max_score += 20
            if indicators['ichimoku'].get('cloud_position') == 'above_cloud':
                score += 10
            if indicators['ichimoku'].get('signal_strength', 0) > 2:
                score += 10

        # Pattern 점수 (15점)
        if indicators.get('patterns'):
            max_score += 15
            pattern_score = indicators['patterns'].get('pattern_score', 0)
            score += min(pattern_score * 5, 15)

        # A/D Line 점수 (10점)
        if indicators.get('ad_line'):
            max_score += 10
            phase = indicators['ad_line'].get('accumulation_phase', 'unknown')
            if phase == 'strong_accumulation':
                score += 10
            elif phase == 'hidden_accumulation':
                score += 7

        # 정규화 (0-100)
        if max_score > 0:
            normalized_score = (score / max_score) * 100
        else:
            normalized_score = 0

        return normalized_score

    def get_composite_signal(self, basic_result: Dict,
                           enhanced_indicators: Dict) -> str:
        """
        종합 매매 신호 생성

        Args:
            basic_result: 기본 스크리닝 결과
            enhanced_indicators: 향상된 지표

        Returns:
            종합 신호
        """
        buy_signals = 0
        sell_signals = 0

        # 기본 신호
        if basic_result.get('signals', {}).get('buy_signal'):
            buy_signals += 2

        # VWAP 신호
        if enhanced_indicators.get('vwap', {}).get('above_vwap'):
            buy_signals += 1

        # ADX 신호
        if enhanced_indicators.get('adx', {}).get('trend_direction') == 'bullish':
            buy_signals += 1

        # MFI 신호
        mfi_level = enhanced_indicators.get('mfi', {}).get('mfi_level')
        if mfi_level in ['oversold', 'extreme_oversold']:
            buy_signals += 1
        elif mfi_level in ['overbought', 'extreme_overbought']:
            sell_signals += 1

        # Ichimoku 신호
        if enhanced_indicators.get('ichimoku', {}).get('signal_strength', 0) > 2:
            buy_signals += 1
        elif enhanced_indicators.get('ichimoku', {}).get('signal_strength', 0) < -2:
            sell_signals += 1

        # Pattern 신호
        pattern_score = enhanced_indicators.get('patterns', {}).get('pattern_score', 0)
        if pattern_score > 0:
            buy_signals += 1
        elif pattern_score < 0:
            sell_signals += 1

        # A/D Line 신호
        phase = enhanced_indicators.get('ad_line', {}).get('accumulation_phase')
        if phase in ['strong_accumulation', 'hidden_accumulation']:
            buy_signals += 1
        elif phase == 'strong_distribution':
            sell_signals += 1

        # 종합 판단
        if buy_signals >= 5:
            return 'strong_buy'
        elif buy_signals >= 3:
            return 'buy'
        elif sell_signals >= 3:
            return 'sell'
        elif sell_signals >= 2:
            return 'weak_sell'
        else:
            return 'hold'