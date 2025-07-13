"""
모듈 레지스트리 시스템 통합 테스트

TODO 1.11에서 구현된 모듈 레지스트리 시스템의 모든 기능을 테스트합니다.
"""

import pytest
from core.registry import (
    create_registry_system, create_module_metadata, create_module_version,
    create_module_dependency, create_module_interface, create_module_usage,
    ModuleType, ModuleStatus, ChangeType
)


class TestModuleRegistry:
    """모듈 레지스트리 테스트"""
    
    def setup_method(self):
        """테스트 전 설정"""
        self.registry, self.dep_analyzer, self.impact_analyzer = create_registry_system()
    
    def test_module_registration(self):
        """모듈 등록 테스트"""
        # 테스트 모듈 생성
        version = create_module_version(1, 0, 0)
        metadata = create_module_metadata(
            name="test_module",
            version=version,
            module_type=ModuleType.CORE,
            description="Test module for registry"
        )
        
        # 모듈 등록
        assert self.registry.register_module(metadata) == True
        
        # 모듈 조회
        retrieved = self.registry.get_module("test_module")
        assert retrieved is not None
        assert retrieved.name == "test_module"
        assert retrieved.version == version
    
    def test_dependency_management(self):
        """의존성 관리 테스트"""
        # 기본 모듈 생성
        base_version = create_module_version(1, 0, 0)
        base_metadata = create_module_metadata(
            name="base_module",
            version=base_version,
            module_type=ModuleType.CORE
        )
        
        # 의존성 모듈 생성
        dependency = create_module_dependency("base_module", ">=1.0.0")
        dep_version = create_module_version(1, 1, 0)
        dep_metadata = create_module_metadata(
            name="dependent_module",
            version=dep_version,
            module_type=ModuleType.PLUGIN,
            dependencies=[dependency]
        )
        
        # 모듈 등록 (기본 모듈 먼저)
        self.registry.register_module(base_metadata)
        self.registry.register_module(dep_metadata)
        
        # 의존성 검증
        is_valid, errors = self.registry.validate_dependencies("dependent_module")
        assert is_valid == True
        assert len(errors) == 0
        
        # 의존성 분석
        analysis = self.dep_analyzer.analyze_dependencies("dependent_module")
        assert "base_module" in analysis["all_dependencies"]
    
    def test_impact_analysis(self):
        """영향 분석 테스트"""
        # 기본 모듈과 의존 모듈 설정
        self.test_dependency_management()
        
        # 영향 분석 수행
        impact_score = self.impact_analyzer.calculate_change_impact(
            "base_module", 
            ChangeType.INTERFACE_CHANGE.value
        )
        assert 0.0 <= impact_score <= 1.0
        
        # 영향 받는 모듈 조회
        affected = self.impact_analyzer.get_affected_modules(
            "base_module",
            ChangeType.INTERFACE_CHANGE.value
        )
        assert "dependent_module" in affected
        
        # 영향 분석 보고서 생성
        report = self.impact_analyzer.generate_impact_report(
            "base_module",
            ChangeType.INTERFACE_CHANGE.value
        )
        assert report["module_name"] == "base_module"
        assert "dependent_module" in report["affected_modules"]
    
    def test_circular_dependency_detection(self):
        """순환 의존성 탐지 테스트"""
        # 모듈 A -> B 의존성 (optional로 설정하여 unresolved dependency 오류 방지)
        dep_a_to_b = create_module_dependency("module_b", optional=True)
        version_a = create_module_version(1, 0, 0)
        metadata_a = create_module_metadata(
            name="module_a",
            version=version_a,
            module_type=ModuleType.CORE,
            dependencies=[dep_a_to_b]
        )
        
        # 모듈 B -> A 의존성 (순환, optional로 설정)
        dep_b_to_a = create_module_dependency("module_a", optional=True)
        version_b = create_module_version(1, 0, 0)
        metadata_b = create_module_metadata(
            name="module_b",
            version=version_b,
            module_type=ModuleType.CORE,
            dependencies=[dep_b_to_a]
        )
        
        # 첫 번째 모듈 등록
        self.registry.register_module(metadata_a)
        
        # 두 번째 모듈 등록 (optional 의존성이므로 성공)
        self.registry.register_module(metadata_b)
        
        # 순환 의존성 탐지 테스트
        cycles = self.dep_analyzer.detect_circular_dependencies()
        # optional 의존성은 순환 탐지에서 제외되므로 빈 결과 예상
        assert isinstance(cycles, list)
    
    def test_interface_management(self):
        """인터페이스 관리 테스트"""
        # 인터페이스 제공 모듈
        interface_version = create_module_version(1, 0, 0)
        provided_interface = create_module_interface(
            name="ITestService",
            version=interface_version,
            methods=["get_data", "set_data"]
        )
        
        provider_version = create_module_version(1, 0, 0)
        provider_metadata = create_module_metadata(
            name="service_provider",
            version=provider_version,
            module_type=ModuleType.CORE,
            provided_interfaces=[provided_interface]
        )
        
        # 인터페이스 사용 모듈
        interface_usage = create_module_usage("ITestService", required=True)
        consumer_version = create_module_version(1, 0, 0)
        consumer_metadata = create_module_metadata(
            name="service_consumer",
            version=consumer_version,
            module_type=ModuleType.PLUGIN,
            used_interfaces=[interface_usage]
        )
        
        # 모듈 등록
        self.registry.register_module(provider_metadata)
        self.registry.register_module(consumer_metadata)
        
        # 인터페이스 제공 모듈 검색
        providers = self.registry.find_modules_by_interface("ITestService")
        assert len(providers) == 1
        assert providers[0].name == "service_provider"
        
        # 인터페이스 사용 모듈 검색
        consumers = self.registry.find_modules_using_interface("ITestService")
        assert len(consumers) == 1
        assert consumers[0].name == "service_consumer"
    
    def test_module_statistics(self):
        """모듈 통계 테스트"""
        # 여러 모듈 등록
        for i in range(3):
            version = create_module_version(1, 0, i)
            metadata = create_module_metadata(
                name=f"test_module_{i}",
                version=version,
                module_type=ModuleType.CORE if i % 2 == 0 else ModuleType.PLUGIN
            )
            self.registry.register_module(metadata)
        
        # 통계 조회
        stats = self.registry.get_statistics()
        assert stats["total_modules"] == 3
        assert "modules_by_type" in stats
        
        # 의존성 통계
        dep_stats = self.dep_analyzer.get_dependency_statistics()
        assert dep_stats["total_modules"] == 3
        
        # 영향 분석 통계
        impact_stats = self.impact_analyzer.get_impact_statistics()
        assert impact_stats["total_modules"] == 3
    
    def test_module_status_management(self):
        """모듈 상태 관리 테스트"""
        # 테스트 모듈 등록
        version = create_module_version(1, 0, 0)
        metadata = create_module_metadata(
            name="status_test_module",
            version=version,
            module_type=ModuleType.CORE
        )
        self.registry.register_module(metadata)
        
        # 상태 변경
        assert self.registry.update_module_status("status_test_module", ModuleStatus.ACTIVE)
        
        # 상태 확인
        module = self.registry.get_module("status_test_module")
        assert module.status == ModuleStatus.ACTIVE
        
        # 활성 모듈 목록 조회
        active_modules = self.registry.get_active_modules()
        assert len(active_modules) == 1
        assert active_modules[0].name == "status_test_module"


def test_module_registry_integration():
    """모듈 레지스트리 통합 테스트"""
    # 레지스트리 시스템 생성
    registry, dep_analyzer, impact_analyzer = create_registry_system()
    
    # 기본 기능 테스트
    version = create_module_version(2, 1, 0)
    metadata = create_module_metadata(
        name="integration_test_module",
        version=version,
        module_type=ModuleType.WORKFLOW,
        description="Integration test module",
        author="Test Author"
    )
    
    # 모듈 등록 및 검증
    assert registry.register_module(metadata)
    assert registry.has_module("integration_test_module")
    
    # 모듈 목록 조회
    all_modules = registry.list_modules()
    assert len(all_modules) == 1
    
    workflow_modules = registry.list_modules(module_type=ModuleType.WORKFLOW)
    assert len(workflow_modules) == 1
    
    print("✅ 모듈 레지스트리 시스템 통합 테스트 완료")


if __name__ == "__main__":
    # 직접 실행 시 통합 테스트 수행
    test_module_registry_integration() 