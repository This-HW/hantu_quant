#!/usr/bin/env python3
"""
C단계: 멀티 팩터 스코어링 테스트
7개 팩터를 결합하여 종합 점수 계산 및 상위 종목 선정
"""

import sys
import json
from pathlib import Path
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.scoring import get_multi_factor_scorer
from core.workflow import get_workflow_state_manager, WorkflowStage, WorkflowStatus


def test_stage_c_multi_factor_scoring():
    """C단계 멀티 팩터 스코어링 테스트"""

    print("\n" + "=" * 80)
    print("C단계: 멀티 팩터 스코어링 테스트")
    print("=" * 80)

    state_manager = get_workflow_state_manager()

    # Step 1: A단계 결과 로드
    print("\n[Step 1] A단계 선정 결과 로드...")
    selection_file = project_root / "data" / "daily_selection" / "stage_a_filtered_selection.json"

    if not selection_file.exists():
        print(f"❌ A단계 결과 파일이 없습니다: {selection_file}")
        return False

    with open(selection_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    selected_stocks = data.get("selected_stocks", [])
    print(f"✅ A단계 선정 종목: {len(selected_stocks)}개")

    if len(selected_stocks) == 0:
        print("❌ 선정 종목이 없습니다")
        return False

    # 진행 상태 저장
    state_manager.save_checkpoint(
        stage=WorkflowStage.STAGE_C,
        status=WorkflowStatus.IN_PROGRESS,
        progress=25.0,
        current_step="A단계 결과 로드",
        total_steps=4,
        completed_steps=[],
        metadata={"description": "멀티 팩터 스코어링", "stock_count": len(selected_stocks)}
    )

    # Step 2: 멀티 팩터 스코어링 실행
    print("\n[Step 2] 멀티 팩터 스코어링 실행...")
    scorer = get_multi_factor_scorer()

    try:
        factor_scores = scorer.calculate_multi_factor_scores(selected_stocks)

        if not factor_scores:
            print("❌ 스코어링 결과가 없습니다")
            return False

        print(f"✅ 멀티 팩터 스코어링 완료: {len(factor_scores)}개 종목")

        # 통계 정보
        composite_scores = [f.composite_score for f in factor_scores]
        print(f"\n   종합 점수 통계:")
        print(f"   • 평균: {np.mean(composite_scores):.1f}")
        print(f"   • 최대: {np.max(composite_scores):.1f}")
        print(f"   • 최소: {np.min(composite_scores):.1f}")
        print(f"   • 표준편차: {np.std(composite_scores):.1f}")

        # 상위 5개 종목
        print(f"\n   상위 5개 종목:")
        for i, fs in enumerate(factor_scores[:5], 1):
            print(f"   {i}. {fs.stock_name:12s} - 종합: {fs.composite_score:.1f}, "
                  f"모멘텀: {fs.momentum_score:.1f}, 밸류: {fs.value_score:.1f}, "
                  f"퀄리티: {fs.quality_score:.1f}")

    except Exception as e:
        print(f"❌ 멀티 팩터 스코어링 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

    state_manager.save_checkpoint(
        stage=WorkflowStage.STAGE_C,
        status=WorkflowStatus.IN_PROGRESS,
        progress=50.0,
        current_step="멀티 팩터 스코어링",
        total_steps=4,
        completed_steps=["A단계 결과 로드"],
        metadata={
            "description": "멀티 팩터 스코어링",
            "avg_score": np.mean(composite_scores),
            "max_score": np.max(composite_scores)
        }
    )

    # Step 3: 상위 종목 필터링
    print("\n[Step 3] 상위 종목 필터링 (상위 70%)...")

    try:
        # 상위 70% 필터링
        filtered_scores = scorer.filter_by_percentile(factor_scores, percentile=70)
        print(f"✅ 필터링 완료: {len(filtered_scores)}개 종목 선정")

        # 선정된 종목 정보
        print(f"\n   선정 종목:")
        for i, fs in enumerate(filtered_scores, 1):
            print(f"   {i:2d}. {fs.stock_name:12s} ({fs.stock_code}) - 종합: {fs.composite_score:.1f}")

    except Exception as e:
        print(f"❌ 필터링 실패: {e}")
        return False

    state_manager.save_checkpoint(
        stage=WorkflowStage.STAGE_C,
        status=WorkflowStatus.IN_PROGRESS,
        progress=75.0,
        current_step="상위 종목 필터링",
        total_steps=4,
        completed_steps=["A단계 결과 로드", "멀티 팩터 스코어링"],
        metadata={
            "description": "멀티 팩터 스코어링",
            "filtered_count": len(filtered_scores),
            "filter_threshold": 70
        }
    )

    # Step 4: 결과 저장
    print("\n[Step 4] 결과 저장...")

    result_data = {
        "test_stage": "C",
        "test_date": data.get("test_date"),
        "scoring_method": "multi_factor",
        "factor_weights": scorer.factor_weights,
        "results": {
            "total_stocks": len(factor_scores),
            "filtered_stocks": len(filtered_scores),
            "avg_score": float(np.mean(composite_scores)),
            "max_score": float(np.max(composite_scores)),
            "min_score": float(np.min(composite_scores))
        },
        "factor_scores": [
            {
                "stock_code": fs.stock_code,
                "stock_name": fs.stock_name,
                "composite_score": fs.composite_score,
                "momentum_score": fs.momentum_score,
                "value_score": fs.value_score,
                "quality_score": fs.quality_score,
                "volume_score": fs.volume_score,
                "volatility_score": fs.volatility_score,
                "technical_score": fs.technical_score,
                "market_strength_score": fs.market_strength_score
            }
            for fs in filtered_scores
        ],
        "original_stocks": selected_stocks
    }

    output_file = project_root / "data" / "daily_selection" / "stage_c_multi_factor_scores.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 결과 저장: {output_file}")

    # 완료 상태 저장
    state_manager.save_checkpoint(
        stage=WorkflowStage.STAGE_C,
        status=WorkflowStatus.COMPLETED,
        progress=100.0,
        current_step="완료",
        total_steps=4,
        completed_steps=["A단계 결과 로드", "멀티 팩터 스코어링", "상위 종목 필터링", "결과 저장"],
        metadata={
            "description": "멀티 팩터 스코어링",
            "total_stocks": len(factor_scores),
            "filtered_stocks": len(filtered_scores),
            "avg_score": float(np.mean(composite_scores)),
            "top_stock": filtered_scores[0].stock_name if filtered_scores else "N/A",
            "top_score": filtered_scores[0].composite_score if filtered_scores else 0.0
        }
    )

    print("\n" + "=" * 80)
    print(f"✅ C단계 완료!")
    print(f"   • 입력: {len(selected_stocks)}개 종목")
    print(f"   • 출력: {len(filtered_scores)}개 종목")
    print(f"   • 평균 점수: {np.mean(composite_scores):.1f}")
    print(f"   • 최고 종목: {filtered_scores[0].stock_name} ({filtered_scores[0].composite_score:.1f}점)")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = test_stage_c_multi_factor_scoring()
    sys.exit(0 if success else 1)
