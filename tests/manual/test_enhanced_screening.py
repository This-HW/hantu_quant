#!/usr/bin/env python3
"""
향상된 스크리닝 시스템 테스트
새로운 지표들이 정상 작동하는지 확인
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime
import pandas as pd
import numpy as np


def test_new_indicators():
    """새로운 지표들 개별 테스트"""
    print("=" * 60)
    print("🧪 새로운 지표 테스트")
    print("=" * 60)

    # 테스트용 샘플 데이터 생성
    dates = pd.date_range('2024-01-01', periods=60, freq='D')
    df = pd.DataFrame({
        'date': dates,
        'open': np.random.uniform(50000, 52000, 60),
        'high': np.random.uniform(52000, 53000, 60),
        'low': np.random.uniform(49000, 50000, 60),
        'close': np.random.uniform(50000, 52000, 60),
        'volume': np.random.uniform(1000000, 2000000, 60)
    })
    df.set_index('date', inplace=True)

    # 가격 조정 (현실적인 움직임)
    df['close'] = df['close'].ewm(span=5).mean()
    df['high'] = df[['high', 'close']].max(axis=1) + np.random.uniform(0, 500, 60)
    df['low'] = df[['low', 'close']].min(axis=1) - np.random.uniform(0, 500, 60)

    results = {}

    # 1. VWAP 테스트
    try:
        from hantu_common.indicators.vwap import VWAP
        vwap_value = VWAP.calculate(df['close'], df['volume'], df['high'], df['low'])
        signals = VWAP.get_trade_signals(df)

        results['VWAP'] = {
            'status': '✅ 성공',
            'current_value': f"{vwap_value.iloc[-1]:,.0f}",
            'above_vwap': df['close'].iloc[-1] > vwap_value.iloc[-1],
            'buy_signals': signals['buy_signal'].sum()
        }
        print(f"✅ VWAP: {vwap_value.iloc[-1]:,.0f}원")
    except Exception as e:
        results['VWAP'] = {'status': f'❌ 실패: {e}'}
        print(f"❌ VWAP 테스트 실패: {e}")

    # 2. ADX 테스트
    try:
        from hantu_common.indicators.adx import ADX
        adx_data = ADX.calculate(df['high'], df['low'], df['close'])

        results['ADX'] = {
            'status': '✅ 성공',
            'adx_value': f"{adx_data['adx'].iloc[-1]:.2f}",
            'trend_strength': ADX.analyze_trend_strength(adx_data['adx'].iloc[-1]),
            'trend_direction': ADX.get_trend_direction(
                adx_data['plus_di'].iloc[-1],
                adx_data['minus_di'].iloc[-1]
            )
        }
        print(f"✅ ADX: {adx_data['adx'].iloc[-1]:.2f} ({results['ADX']['trend_strength']})")
    except Exception as e:
        results['ADX'] = {'status': f'❌ 실패: {e}'}
        print(f"❌ ADX 테스트 실패: {e}")

    # 3. MFI 테스트
    try:
        from hantu_common.indicators.mfi import MFI
        mfi_value = MFI.calculate(df['high'], df['low'], df['close'], df['volume'])

        results['MFI'] = {
            'status': '✅ 성공',
            'mfi_value': f"{mfi_value.iloc[-1]:.2f}",
            'level': MFI.analyze_level(mfi_value.iloc[-1])
        }
        print(f"✅ MFI: {mfi_value.iloc[-1]:.2f} ({results['MFI']['level']})")
    except Exception as e:
        results['MFI'] = {'status': f'❌ 실패: {e}'}
        print(f"❌ MFI 테스트 실패: {e}")

    # 4. Ichimoku 테스트
    try:
        from hantu_common.indicators.ichimoku import Ichimoku
        ichimoku_data = Ichimoku.calculate(df['high'], df['low'], df['close'])
        signals = Ichimoku.get_trade_signals(df)

        results['Ichimoku'] = {
            'status': '✅ 성공',
            'tenkan': f"{ichimoku_data['tenkan_sen'].iloc[-1]:,.0f}",
            'kijun': f"{ichimoku_data['kijun_sen'].iloc[-1]:,.0f}",
            'signal_strength': signals['signal_strength'].iloc[-1]
        }
        print(f"✅ Ichimoku: 신호강도 {signals['signal_strength'].iloc[-1]}")
    except Exception as e:
        results['Ichimoku'] = {'status': f'❌ 실패: {e}'}
        print(f"❌ Ichimoku 테스트 실패: {e}")

    # 5. Pattern Recognition 테스트
    try:
        from hantu_common.indicators.pattern_recognition import PatternRecognition
        patterns = PatternRecognition.get_pattern_signals(df)

        results['Patterns'] = {
            'status': '✅ 성공',
            'pattern_score': patterns['pattern_score'].iloc[-1],
            'breakout': patterns['breakout'].iloc[-1],
            'candlestick_patterns': sum([
                patterns['bullish_engulfing'].iloc[-1],
                patterns['morning_star'].iloc[-1],
                patterns['hammer'].iloc[-1]
            ])
        }
        print(f"✅ Pattern Recognition: 패턴점수 {patterns['pattern_score'].iloc[-1]}")
    except Exception as e:
        results['Patterns'] = {'status': f'❌ 실패: {e}'}
        print(f"❌ Pattern Recognition 테스트 실패: {e}")

    # 6. A/D Line 테스트
    try:
        from hantu_common.indicators.accumulation_distribution import AccumulationDistribution
        ad_line = AccumulationDistribution.calculate(
            df['high'], df['low'], df['close'], df['volume']
        )
        signals = AccumulationDistribution.get_trade_signals(df)

        results['AD_Line'] = {
            'status': '✅ 성공',
            'ad_value': f"{ad_line.iloc[-1]:,.0f}",
            'phase': signals['accumulation_phase'].iloc[-1]
        }
        print(f"✅ A/D Line: {signals['accumulation_phase'].iloc[-1]}")
    except Exception as e:
        results['AD_Line'] = {'status': f'❌ 실패: {e}'}
        print(f"❌ A/D Line 테스트 실패: {e}")

    return results


def test_enhanced_screener():
    """향상된 스크리너 테스트"""
    print("\n" + "=" * 60)
    print("🔍 향상된 스크리너 테스트")
    print("=" * 60)

    try:
        from core.watchlist.enhanced_screener import EnhancedScreener

        screener = EnhancedScreener()
        print("✅ 향상된 스크리너 초기화 성공")

        # 테스트 종목들
        test_stocks = [
            ('005930', '삼성전자'),
            ('000660', 'SK하이닉스'),
            ('035720', '카카오')
        ]

        for stock_code, stock_name in test_stocks:
            print(f"\n📊 {stock_name} ({stock_code}) 테스트 중...")

            # 향상된 지표 계산
            indicators = screener.calculate_enhanced_indicators(stock_code, period=30)

            if indicators:
                print(f"  - VWAP: {indicators.get('vwap', {}).get('above_vwap', 'N/A')}")
                print(f"  - ADX: {indicators.get('adx', {}).get('trend_strength', 'N/A')}")
                print(f"  - MFI: {indicators.get('mfi', {}).get('mfi_level', 'N/A')}")
                print(f"  - Ichimoku: {indicators.get('ichimoku', {}).get('cloud_position', 'N/A')}")
                print(f"  - Patterns: {indicators.get('patterns', {}).get('pattern_score', 'N/A')}")
                print(f"  - A/D: {indicators.get('ad_line', {}).get('accumulation_phase', 'N/A')}")

                # 점수 계산
                score = screener.calculate_enhanced_score(indicators)
                print(f"  ⭐ 향상된 점수: {score:.1f}/100")
            else:
                print(f"  ❌ 지표 계산 실패")

        return True

    except Exception as e:
        print(f"❌ 향상된 스크리너 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 테스트 함수"""
    print("🚀 향상된 스크리닝 시스템 테스트 시작")
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 개별 지표 테스트
    indicator_results = test_new_indicators()

    # 2. 통합 스크리너 테스트
    screener_success = test_enhanced_screener()

    # 결과 요약
    print("\n" + "=" * 80)
    print("📊 테스트 결과 요약")
    print("=" * 80)

    success_count = 0
    total_count = len(indicator_results)

    for name, result in indicator_results.items():
        if '✅' in result.get('status', ''):
            success_count += 1
            print(f"✅ {name}: 정상 작동")
        else:
            print(f"❌ {name}: {result.get('status', '실패')}")

    print(f"\n📈 지표 테스트: {success_count}/{total_count} 성공")
    print(f"🔍 통합 스크리너: {'✅ 성공' if screener_success else '❌ 실패'}")

    if success_count == total_count and screener_success:
        print("\n🎉 모든 테스트 통과! 향상된 스크리닝 시스템이 정상 작동합니다.")
    else:
        print("\n⚠️ 일부 테스트가 실패했습니다. 로그를 확인하세요.")

    print(f"\n⏰ 종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()