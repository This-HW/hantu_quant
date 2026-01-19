#!/usr/bin/env python3
"""
A단계: 강화된 선정 기준 테스트
기존 95개 선정 → 강화된 기준 적용 시 몇 개가 되는지 시뮬레이션
"""

import sys
import json
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.daily_selection.daily_updater import FilteringCriteria

def test_stage_a_criteria():
    """A단계 강화된 기준으로 필터링 테스트"""

    print("=" * 80)
    print("A단계: 강화된 선정 기준 테스트")
    print("=" * 80)

    # 1. 기존 선정 결과 로드
    selection_file = project_root / "data" / "daily_selection" / "latest_selection.json"

    if not selection_file.exists():
        print(f"❌ 선정 파일이 없습니다: {selection_file}")
        return

    with open(selection_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    original_stocks = data.get("data", {}).get("selected_stocks", [])
    print(f"\n📊 기존 선정 종목 수: {len(original_stocks)}개")

    # 2. 강화된 기준 로드
    criteria = FilteringCriteria()

    print(f"\n🔧 강화된 기준:")
    print(f"  • 가격 매력도: {criteria.price_attractiveness}점 이상")
    print(f"  • 리스크 점수: {criteria.risk_score_max}점 이하")
    print(f"  • 신뢰도: {criteria.confidence_min} 이상")
    print(f"  • 기술적 점수: {criteria.min_technical_score}점 이상")
    print(f"  • 섹터별 최대: {criteria.sector_limit}개")
    print(f"  • 전체 최대: {criteria.total_limit}개")

    # 3. 필터링 시뮬레이션
    passed_stocks = []
    sector_count = {}
    filtered_reasons = {
        "price_attractiveness": 0,
        "risk_score": 0,
        "confidence": 0,
        "technical_score": 0,
        "sector_limit": 0,
        "total_limit": 0
    }

    for stock in original_stocks:
        # 가격 매력도 체크
        if stock.get("price_attractiveness", 0) < criteria.price_attractiveness:
            filtered_reasons["price_attractiveness"] += 1
            continue

        # 리스크 점수 체크
        if stock.get("risk_score", 100) > criteria.risk_score_max:
            filtered_reasons["risk_score"] += 1
            continue

        # 신뢰도 체크
        if stock.get("confidence", 0) < criteria.confidence_min:
            filtered_reasons["confidence"] += 1
            continue

        # 기술적 점수 체크 (없으면 통과로 가정)
        technical_score = stock.get("technical_score", 100)  # 데이터에 없을 수 있음
        if technical_score < criteria.min_technical_score:
            filtered_reasons["technical_score"] += 1
            continue

        # 섹터별 제한 체크
        sector = stock.get("sector", "기타")
        if sector_count.get(sector, 0) >= criteria.sector_limit:
            filtered_reasons["sector_limit"] += 1
            continue

        # 전체 제한 체크
        if len(passed_stocks) >= criteria.total_limit:
            filtered_reasons["total_limit"] += 1
            break

        # 모든 필터 통과
        passed_stocks.append(stock)
        sector_count[sector] = sector_count.get(sector, 0) + 1

    # 4. 결과 출력
    print(f"\n✅ 강화된 기준 적용 후 선정 종목 수: {len(passed_stocks)}개")
    print(f"   (감소율: {(1 - len(passed_stocks)/len(original_stocks))*100:.1f}%)")

    print(f"\n📉 필터링 사유별 통계:")
    print(f"  • 가격 매력도 미달: {filtered_reasons['price_attractiveness']}개")
    print(f"  • 리스크 점수 초과: {filtered_reasons['risk_score']}개")
    print(f"  • 신뢰도 미달: {filtered_reasons['confidence']}개")
    print(f"  • 기술적 점수 미달: {filtered_reasons['technical_score']}개")
    print(f"  • 섹터 제한 초과: {filtered_reasons['sector_limit']}개")
    print(f"  • 전체 제한 도달: {filtered_reasons['total_limit']}개")

    print(f"\n🏢 섹터별 분포:")
    for sector, count in sorted(sector_count.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {sector}: {count}개 (최대 {criteria.sector_limit}개)")

    print(f"\n🎯 상위 10개 종목:")
    for i, stock in enumerate(passed_stocks[:10], 1):
        print(f"  {i:2d}. {stock['stock_name']:12s} ({stock['stock_code']}) - "
              f"매력도: {stock['price_attractiveness']:.1f}, "
              f"리스크: {stock['risk_score']:.1f}, "
              f"신뢰도: {stock['confidence']:.2f}")

    # 5. 결과 저장
    result_data = {
        "test_stage": "A",
        "test_date": data.get("market_date"),
        "criteria": {
            "price_attractiveness_min": criteria.price_attractiveness,
            "risk_score_max": criteria.risk_score_max,
            "confidence_min": criteria.confidence_min,
            "technical_score_min": criteria.min_technical_score,
            "sector_limit": criteria.sector_limit,
            "total_limit": criteria.total_limit
        },
        "results": {
            "original_count": len(original_stocks),
            "passed_count": len(passed_stocks),
            "reduction_rate": (1 - len(passed_stocks)/len(original_stocks)) * 100,
            "filtered_reasons": filtered_reasons,
            "sector_distribution": sector_count
        },
        "selected_stocks": passed_stocks
    }

    output_file = project_root / "data" / "daily_selection" / "stage_a_filtered_selection.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"\n💾 결과 저장: {output_file}")
    print("\n" + "=" * 80)
    print(f"✅ A단계 테스트 완료: {len(original_stocks)}개 → {len(passed_stocks)}개")
    print("=" * 80)

if __name__ == "__main__":
    test_stage_a_criteria()
