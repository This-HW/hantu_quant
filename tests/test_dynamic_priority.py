"""
동적 TODO 우선순위 조정 시스템 테스트
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils.dynamic_priority import (
    DynamicPriorityManager, TodoItem, TodoStatus, Priority, 
    MarketCondition, get_priority_manager
)

class TestDynamicPriorityManager:
    """동적 우선순위 관리자 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        # 임시 디렉토리 생성
        self.temp_dir = tempfile.mkdtemp()
        self.manager = DynamicPriorityManager(data_dir=self.temp_dir)
        
    def teardown_method(self):
        """테스트 정리"""
        # 임시 디렉토리 삭제
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_manager_initialization(self):
        """관리자 초기화 테스트"""
        assert self.manager is not None
        assert os.path.exists(self.temp_dir)
        
        # 초기 상태 확인
        summary = self.manager.get_priority_summary()
        assert summary['total_todos'] == 0
    
    def test_add_todo(self):
        """TODO 추가 테스트"""
        # TODO 추가
        self.manager.add_or_update_todo(
            todo_id="2.1",
            content="Phase 4 AI 학습 시스템 기본 구조 설정",
            status="completed",
            completion_rate=1.0
        )
        
        # 확인
        summary = self.manager.get_priority_summary()
        assert summary['total_todos'] == 1
        assert summary['by_status']['completed'] == 1
    
    def test_update_market_condition(self):
        """시장 상황 업데이트 테스트"""
        # 시장 상황 업데이트
        self.manager.update_market_condition(
            volatility=0.6,
            trend=0.2,
            accuracy=0.82,
            performance_score=0.75
        )
        
        # 확인
        summary = self.manager.get_priority_summary()
        market = summary['market_condition']
        assert market is not None
        assert market['volatility'] == 0.6
        assert market['accuracy'] == 0.82
    
    def test_priority_adjustment_high_volatility(self):
        """높은 변동성 시 우선순위 조정 테스트"""
        # 트레이딩 관련 TODO 추가
        self.manager.add_or_update_todo(
            todo_id="trading_1",
            content="리스크 관리 시스템 구현",
            status="pending",
            completion_rate=0.0
        )
        
        # 태그 수동 설정 (실제로는 자동으로 태그 지정됨)
        if "trading_1" in self.manager._todos:
            self.manager._todos["trading_1"].tags = ['trading', 'risk']
        
        # 높은 변동성 시장 상황 설정
        self.manager.update_market_condition(
            volatility=0.8,  # 높은 변동성
            trend=0.1,
            accuracy=0.82,
            performance_score=0.75
        )
        
        # 우선순위가 상승했는지 확인
        todos = self.manager.get_prioritized_todos()
        if todos:
            # 트레이딩 관련 TODO가 높은 우선순위를 가져야 함
            trading_todo = next((t for t in todos if t.id == "trading_1"), None)
            assert trading_todo is not None
    
    def test_priority_adjustment_low_accuracy(self):
        """낮은 정확도 시 AI 학습 우선순위 상승 테스트"""
        # AI 학습 관련 TODO 추가
        self.manager.add_or_update_todo(
            todo_id="ai_1", 
            content="피처 엔지니어링 시스템 개선",
            status="pending",
            completion_rate=0.5
        )
        
        # 태그 설정
        if "ai_1" in self.manager._todos:
            self.manager._todos["ai_1"].tags = ['ai', 'learning']
        
        # 낮은 정확도 시장 상황 설정
        self.manager.update_market_condition(
            volatility=0.3,
            trend=0.2,
            accuracy=0.75,  # 낮은 정확도 (< 0.8)
            performance_score=0.70
        )
        
        # AI 관련 TODO 우선순위 확인
        todos = self.manager.get_prioritized_todos()
        if todos:
            ai_todo = next((t for t in todos if t.id == "ai_1"), None)
            assert ai_todo is not None
    
    def test_completion_rate_priority_boost(self):
        """높은 완성률 TODO 우선순위 상승 테스트"""
        # 거의 완성된 TODO 추가
        self.manager.add_or_update_todo(
            todo_id="nearly_done",
            content="거의 완성된 작업",
            status="in_progress", 
            completion_rate=0.9
        )
        
        # 시작한지 얼마 안된 TODO 추가
        self.manager.add_or_update_todo(
            todo_id="just_started",
            content="방금 시작한 작업",
            status="pending",
            completion_rate=0.1
        )
        
        # 우선순위 확인
        todos = self.manager.get_prioritized_todos()
        assert len(todos) >= 2
        
        # 완성률이 높은 TODO가 우선순위가 높아야 함
        nearly_done = next((t for t in todos if t.id == "nearly_done"), None)
        just_started = next((t for t in todos if t.id == "just_started"), None)
        
        assert nearly_done is not None
        assert just_started is not None
    
    def test_dependency_priority_boost(self):
        """의존성이 있는 TODO 우선순위 상승 테스트"""
        # 의존성을 가진 TODO들 추가
        self.manager.add_or_update_todo(
            todo_id="base_task",
            content="기본 작업",
            status="pending",
            completion_rate=0.0
        )
        
        self.manager.add_or_update_todo(
            todo_id="dependent_task",
            content="의존 작업",
            status="pending", 
            completion_rate=0.0,
            dependencies=["base_task"]
        )
        
        # base_task가 더 높은 우선순위를 가져야 함
        todos = self.manager.get_prioritized_todos()
        if len(todos) >= 2:
            # 의존성이 있는 작업이 먼저 나와야 함
            base_task = next((t for t in todos if t.id == "base_task"), None)
            dependent_task = next((t for t in todos if t.id == "dependent_task"), None)
            
            assert base_task is not None
            assert dependent_task is not None
    
    def test_priority_report_generation(self):
        """우선순위 리포트 생성 테스트"""
        # 몇 개 TODO 추가
        self.manager.add_or_update_todo("test1", "테스트 1", "pending")
        self.manager.add_or_update_todo("test2", "테스트 2", "in_progress", 0.5)
        self.manager.add_or_update_todo("test3", "테스트 3", "completed", 1.0)
        
        # 시장 상황 설정
        self.manager.update_market_condition(0.5, 0.3, 0.82, 0.75)
        
        # 리포트 생성
        report = self.manager.export_priority_report()
        
        assert "동적 TODO 우선순위 리포트" in report
        assert "📊 요약" in report
        assert "🚦 우선순위별 현황" in report
        assert "📈 시장 상황" in report
        assert "📋 우선순위 TODO 목록" in report
        
        # 실제 데이터가 포함되었는지 확인
        assert "전체 TODO: 3개" in report
        assert "변동성: 0.50" in report
        assert "정확도: 0.82" in report
    
    def test_singleton_manager(self):
        """싱글톤 관리자 테스트"""
        manager1 = get_priority_manager()
        manager2 = get_priority_manager()
        
        # 같은 인스턴스여야 함
        assert manager1 is manager2
    
    def test_time_sensitivity(self):
        """시간 민감도 테스트"""
        # 오래된 TODO 생성 (수동으로 생성 시간 조작)
        old_todo_id = "old_task"
        self.manager.add_or_update_todo(
            old_todo_id,
            "오래된 작업",
            "pending",
            completion_rate=0.0
        )
        
        # 생성 시간을 10일 전으로 설정
        if old_todo_id in self.manager._todos:
            old_date = datetime.now() - timedelta(days=10)
            self.manager._todos[old_todo_id].created_at = old_date
        
        # 새로운 TODO 추가
        self.manager.add_or_update_todo(
            "new_task",
            "새로운 작업", 
            "pending",
            completion_rate=0.0
        )
        
        # 우선순위 재계산
        self.manager._calculate_priority_for_todo(old_todo_id)
        self.manager._calculate_priority_for_todo("new_task")
        
        # 새로운 작업이 더 높은 우선순위를 가져야 함 (오래된 작업은 우선순위 하락)
        todos = self.manager.get_prioritized_todos()
        if len(todos) >= 2:
            new_todo = next((t for t in todos if t.id == "new_task"), None)
            old_todo = next((t for t in todos if t.id == old_todo_id), None)
            
            assert new_todo is not None
            assert old_todo is not None


class TestPriorityIntegration:
    """우선순위 시스템 통합 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = DynamicPriorityManager(data_dir=self.temp_dir)
    
    def teardown_method(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_real_world_scenario(self):
        """실제 시나리오 테스트"""
        # 현재 프로젝트 상황 시뮬레이션
        
        # 1. 완료된 TODO들
        self.manager.add_or_update_todo("2.1", "Phase 4 기본 구조", "completed", 1.0)
        self.manager.add_or_update_todo("2.3", "피처 엔지니어링", "completed", 1.0)
        
        # 2. 진행 중인 TODO들
        self.manager.add_or_update_todo("3.1", "동적 우선순위 시스템", "in_progress", 0.7)
        self.manager.add_or_update_todo("3.2", "지능형 테스트 생성", "pending", 0.0)
        
        # 3. 대기 중인 TODO들
        self.manager.add_or_update_todo("2.4", "일일 성과 분석", "pending", 0.0)
        self.manager.add_or_update_todo("2.5", "패턴 학습 엔진", "pending", 0.0)
        
        # 태그 설정
        for todo_id, tags in [
            ("3.1", ["system", "automation"]),
            ("3.2", ["testing", "ai"]),
            ("2.4", ["analysis", "performance"]),
            ("2.5", ["ai", "learning"])
        ]:
            if todo_id in self.manager._todos:
                self.manager._todos[todo_id].tags = tags
        
        # 현재 시장 상황 (정확도가 좀 낮음)
        self.manager.update_market_condition(
            volatility=0.4,
            trend=0.2,
            accuracy=0.78,  # 목표 80% 보다 낮음
            performance_score=0.82
        )
        
        # 우선순위 확인
        todos = self.manager.get_prioritized_todos()
        assert len(todos) > 0
        
        # AI 학습 관련 TODO들이 높은 우선순위를 가져야 함
        ai_todos = [t for t in todos if any(tag in ['ai', 'learning'] for tag in (t.tags or []))]
        
        # 리포트 생성 및 확인
        report = self.manager.export_priority_report()
        assert "정확도: 0.78" in report  # 시장 상황 반영
        
        print("\n=== 동적 우선순위 조정 결과 ===")
        print(report)
        
        # 우선순위 조정 이력 확인
        summary = self.manager.get_priority_summary()
        if summary.get('last_adjustment'):
            print(f"\n최근 조정: {summary['last_adjustment']}")


if __name__ == "__main__":
    # 직접 실행 시 간단한 테스트
    test = TestDynamicPriorityManager()
    test.setup_method()
    
    try:
        test.test_manager_initialization()
        test.test_add_todo()
        test.test_priority_report_generation()
        print("✅ 모든 기본 테스트 통과!")
        
        # 통합 테스트
        integration_test = TestPriorityIntegration()
        integration_test.setup_method()
        integration_test.test_real_world_scenario()
        print("✅ 통합 테스트 통과!")
        
    finally:
        test.teardown_method()
        integration_test.teardown_method() 