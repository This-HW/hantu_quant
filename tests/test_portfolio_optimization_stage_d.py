#!/usr/bin/env python3
"""
D단계: 포트폴리오 최적화 테스트
리스크 패리티 vs 샤프 비율 최적화 비교
"""

import sys
import json
from pathlib import Path
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.portfolio import get_risk_parity_optimizer, get_sharpe_optimizer  # noqa: E402
from core.workflow import get_workflow_state_manager, WorkflowStage, WorkflowStatus  # noqa: E402


def test_stage_d_portfolio_optimization():
    """D단계 포트폴리오 최적화 테스트"""

    print("\n" + "=" * 80)
    print("D단계: 포트폴리오 최적화 테스트")
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
        stage=WorkflowStage.STAGE_D,
        status=WorkflowStatus.IN_PROGRESS,
        progress=25.0,
        current_step="A단계 결과 로드",
        total_steps=4,
        completed_steps=[],
        metadata={"description": "포트폴리오 최적화", "stock_count": len(selected_stocks)}
    )

    # Step 2: 리스크 패리티 최적화
    print("\n[Step 2] 리스크 패리티 최적화 실행...")
    risk_parity_optimizer = get_risk_parity_optimizer()

    try:
        rp_result = risk_parity_optimizer.optimize(selected_stocks)
        print("✅ 리스크 패리티 최적화 완료")
        print(f"   • 기대 수익률: {rp_result.expected_return:.2%}")
        print(f"   • 예상 변동성: {rp_result.expected_volatility:.2%}")
        print(f"   • 샤프 비율: {rp_result.sharpe_ratio:.2f}")
        print(f"   • 최대 가중치: {max(rp_result.weights):.2%}")
        print(f"   • 최소 가중치: {min(rp_result.weights):.2%}")

        # 상위 5개 가중치 종목
        print("\n   상위 5개 가중치 종목:")
        sorted_indices = np.argsort(rp_result.weights)[::-1][:5]
        for idx in sorted_indices:
            print(f"   - {selected_stocks[idx]['stock_name']:12s}: {rp_result.weights[idx]:.2%}")

    except Exception as e:
        print(f"❌ 리스크 패리티 최적화 실패: {e}")
        return False

    state_manager.save_checkpoint(
        stage=WorkflowStage.STAGE_D,
        status=WorkflowStatus.IN_PROGRESS,
        progress=50.0,
        current_step="리스크 패리티 최적화",
        total_steps=4,
        completed_steps=["A단계 결과 로드"],
        metadata={
            "description": "포트폴리오 최적화",
            "rp_sharpe": rp_result.sharpe_ratio,
            "rp_return": rp_result.expected_return,
            "rp_volatility": rp_result.expected_volatility
        }
    )

    # Step 3: 샤프 비율 최적화
    print("\n[Step 3] 샤프 비율 최적화 실행...")
    sharpe_optimizer = get_sharpe_optimizer()

    try:
        sharpe_result = sharpe_optimizer.optimize(selected_stocks)
        print("✅ 샤프 비율 최적화 완료")
        print(f"   • 기대 수익률: {sharpe_result.expected_return:.2%}")
        print(f"   • 예상 변동성: {sharpe_result.expected_volatility:.2%}")
        print(f"   • 샤프 비율: {sharpe_result.sharpe_ratio:.2f}")
        print(f"   • 최대 가중치: {max(sharpe_result.weights):.2%}")
        print(f"   • 최소 가중치: {min(sharpe_result.weights):.2%}")

        # 상위 5개 가중치 종목
        print("\n   상위 5개 가중치 종목:")
        sorted_indices = np.argsort(sharpe_result.weights)[::-1][:5]
        for idx in sorted_indices:
            print(f"   - {selected_stocks[idx]['stock_name']:12s}: {sharpe_result.weights[idx]:.2%}")

    except Exception as e:
        print(f"❌ 샤프 비율 최적화 실패: {e}")
        return False

    state_manager.save_checkpoint(
        stage=WorkflowStage.STAGE_D,
        status=WorkflowStatus.IN_PROGRESS,
        progress=75.0,
        current_step="샤프 비율 최적화",
        total_steps=4,
        completed_steps=["A단계 결과 로드", "리스크 패리티 최적화"],
        metadata={
            "description": "포트폴리오 최적화",
            "rp_sharpe": rp_result.sharpe_ratio,
            "sharpe_sharpe": sharpe_result.sharpe_ratio,
            "comparison": "샤프 비율 최적화가 더 우수" if sharpe_result.sharpe_ratio > rp_result.sharpe_ratio else "리스크 패리티가 더 우수"
        }
    )

    # Step 4: 결과 비교 및 저장
    print("\n[Step 4] 결과 비교...")
    print(f"\n{'지표':<20} {'리스크 패리티':>15} {'샤프 최적화':>15} {'차이':>15}")
    print("-" * 70)
    print(f"{'기대 수익률':<20} {rp_result.expected_return:>14.2%} {sharpe_result.expected_return:>14.2%} {sharpe_result.expected_return - rp_result.expected_return:>14.2%}")
    print(f"{'예상 변동성':<20} {rp_result.expected_volatility:>14.2%} {sharpe_result.expected_volatility:>14.2%} {sharpe_result.expected_volatility - rp_result.expected_volatility:>14.2%}")
    print(f"{'샤프 비율':<20} {rp_result.sharpe_ratio:>14.2f} {sharpe_result.sharpe_ratio:>14.2f} {sharpe_result.sharpe_ratio - rp_result.sharpe_ratio:>14.2f}")

    # 최고 성과 선택
    best_method = "sharpe" if sharpe_result.sharpe_ratio > rp_result.sharpe_ratio else "risk_parity"
    best_result = sharpe_result if best_method == "sharpe" else rp_result

    print(f"\n🏆 최고 성과: {best_method.upper()} (샤프 비율: {best_result.sharpe_ratio:.2f})")

    # 결과 저장
    result_data = {
        "test_stage": "D",
        "test_date": data.get("test_date"),
        "optimization_methods": {
            "risk_parity": {
                "expected_return": rp_result.expected_return,
                "expected_volatility": rp_result.expected_volatility,
                "sharpe_ratio": rp_result.sharpe_ratio,
                "weights": rp_result.weights,
                "stock_codes": rp_result.stock_codes
            },
            "max_sharpe": {
                "expected_return": sharpe_result.expected_return,
                "expected_volatility": sharpe_result.expected_volatility,
                "sharpe_ratio": sharpe_result.sharpe_ratio,
                "weights": sharpe_result.weights,
                "stock_codes": sharpe_result.stock_codes
            }
        },
        "best_method": best_method,
        "selected_stocks": selected_stocks
    }

    output_file = project_root / "data" / "daily_selection" / "stage_d_optimized_portfolio.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"\n💾 결과 저장: {output_file}")

    # 완료 상태 저장
    state_manager.save_checkpoint(
        stage=WorkflowStage.STAGE_D,
        status=WorkflowStatus.COMPLETED,
        progress=100.0,
        current_step="완료",
        total_steps=4,
        completed_steps=["A단계 결과 로드", "리스크 패리티 최적화", "샤프 비율 최적화", "결과 비교 및 저장"],
        metadata={
            "description": "포트폴리오 최적화",
            "best_method": best_method,
            "best_sharpe": best_result.sharpe_ratio,
            "best_return": best_result.expected_return,
            "best_volatility": best_result.expected_volatility,
            "stock_count": len(selected_stocks)
        }
    )

    print("\n" + "=" * 80)
    print("✅ D단계 완료!")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = test_stage_d_portfolio_optimization()
    sys.exit(0 if success else 1)
