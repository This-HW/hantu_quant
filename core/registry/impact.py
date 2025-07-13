"""
영향 분석 엔진 구현

이 모듈은 모듈 변경 시 시스템에 미치는 영향을 분석하는 기능을 제공합니다.
"""

import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from collections import defaultdict
from enum import Enum

from .interfaces import IImpactAnalyzer, IModuleRegistry, IDependencyAnalyzer
from .exceptions import ModuleNotFoundError, ImpactAnalysisError

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """변경 타입 정의"""
    VERSION_UPGRADE = "version_upgrade"
    VERSION_DOWNGRADE = "version_downgrade"
    INTERFACE_CHANGE = "interface_change"
    DEPENDENCY_CHANGE = "dependency_change"
    CONFIGURATION_CHANGE = "configuration_change"
    IMPLEMENTATION_CHANGE = "implementation_change"
    REMOVAL = "removal"
    ADDITION = "addition"
    STATUS_CHANGE = "status_change"


class ImpactLevel(Enum):
    """영향 수준 정의"""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ImpactAnalyzer(IImpactAnalyzer):
    """영향 분석 엔진 구현 클래스"""
    
    def __init__(self, registry: IModuleRegistry, dependency_analyzer: IDependencyAnalyzer):
        """초기화"""
        self._registry = registry
        self._dependency_analyzer = dependency_analyzer
        
        # 변경 타입별 영향 가중치
        self._impact_weights = {
            ChangeType.VERSION_UPGRADE: 0.3,
            ChangeType.VERSION_DOWNGRADE: 0.5,
            ChangeType.INTERFACE_CHANGE: 0.8,
            ChangeType.DEPENDENCY_CHANGE: 0.6,
            ChangeType.CONFIGURATION_CHANGE: 0.2,
            ChangeType.IMPLEMENTATION_CHANGE: 0.4,
            ChangeType.REMOVAL: 1.0,
            ChangeType.ADDITION: 0.1,
            ChangeType.STATUS_CHANGE: 0.3
        }
        
        logger.info("ImpactAnalyzer initialized")
    
    def analyze_impact(self, module_name: str, change_type: str) -> Dict[str, Any]:
        """영향 분석"""
        try:
            # 모듈 존재 확인
            module = self._registry.get_module(module_name)
            if not module:
                raise ModuleNotFoundError(module_name)
            
            # 변경 타입 파싱
            try:
                change_enum = ChangeType(change_type)
            except ValueError:
                raise ImpactAnalysisError(f"Invalid change type: {change_type}", module_name, change_type)
            
            # 영향 분석 수행
            analysis = self._perform_impact_analysis(module_name, change_enum)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze impact for '{module_name}': {e}")
            raise
    
    def get_dependent_modules(self, module_name: str) -> List[str]:
        """의존 모듈 목록 (해당 모듈을 의존하는 모듈들)"""
        try:
            return self._dependency_analyzer.get_reverse_dependencies(module_name)
        except Exception as e:
            logger.error(f"Failed to get dependent modules for '{module_name}': {e}")
            raise
    
    def get_affected_modules(self, module_name: str, change_type: str) -> List[str]:
        """영향 받는 모듈 목록"""
        try:
            # 변경 타입 파싱
            try:
                change_enum = ChangeType(change_type)
            except ValueError:
                raise ImpactAnalysisError(f"Invalid change type: {change_type}", module_name, change_type)
            
            # 영향 받는 모듈 수집
            affected_modules = set()
            
            # 직접 의존하는 모듈들
            direct_dependents = self.get_dependent_modules(module_name)
            affected_modules.update(direct_dependents)
            
            # 변경 타입에 따른 추가 영향 모듈 수집
            if change_enum in [ChangeType.INTERFACE_CHANGE, ChangeType.REMOVAL]:
                # 인터페이스 변경이나 제거 시 더 넓은 영향
                for dependent in direct_dependents:
                    indirect_dependents = self.get_dependent_modules(dependent)
                    affected_modules.update(indirect_dependents)
            
            return list(affected_modules)
            
        except Exception as e:
            logger.error(f"Failed to get affected modules for '{module_name}': {e}")
            raise
    
    def calculate_change_impact(self, module_name: str, change_type: str) -> float:
        """변경 영향도 계산 (0.0 ~ 1.0)"""
        try:
            # 변경 타입 파싱
            try:
                change_enum = ChangeType(change_type)
            except ValueError:
                raise ImpactAnalysisError(f"Invalid change type: {change_type}", module_name, change_type)
            
            # 기본 영향도 (변경 타입 기반)
            base_impact = self._impact_weights.get(change_enum, 0.5)
            
            # 의존성 기반 영향도 계산
            dependent_modules = self.get_dependent_modules(module_name)
            dependency_impact = len(dependent_modules) * 0.1
            
            # 모듈 타입 기반 영향도 조정
            module = self._registry.get_module(module_name)
            type_multiplier = self._get_type_multiplier(module.module_type)
            
            # 최종 영향도 계산
            total_impact = min(1.0, base_impact + dependency_impact * type_multiplier)
            
            return total_impact
            
        except Exception as e:
            logger.error(f"Failed to calculate change impact for '{module_name}': {e}")
            raise
    
    def generate_impact_report(self, module_name: str, change_type: str) -> Dict[str, Any]:
        """영향 분석 보고서 생성"""
        try:
            # 기본 영향 분석
            impact_analysis = self.analyze_impact(module_name, change_type)
            
            # 영향 받는 모듈들
            affected_modules = self.get_affected_modules(module_name, change_type)
            
            # 영향도 계산
            impact_score = self.calculate_change_impact(module_name, change_type)
            
            # 위험도 계산
            risk_score = self.calculate_risk_score(module_name, change_type)
            
            # 호환성 문제 예측
            breaking_changes = self.predict_breaking_changes(module_name, change_type)
            
            # 권장 사항 생성
            recommendations = self._generate_recommendations(module_name, change_type, impact_score, risk_score)
            
            report = {
                "module_name": module_name,
                "change_type": change_type,
                "impact_score": impact_score,
                "risk_score": risk_score,
                "impact_level": self._get_impact_level(impact_score),
                "affected_modules": affected_modules,
                "affected_count": len(affected_modules),
                "breaking_changes": breaking_changes,
                "recommendations": recommendations,
                "detailed_analysis": impact_analysis,
                "timestamp": self._get_current_timestamp()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate impact report for '{module_name}': {e}")
            raise
    
    def predict_breaking_changes(self, module_name: str, change_type: str) -> List[str]:
        """호환성 문제 예측"""
        try:
            # 변경 타입 파싱
            try:
                change_enum = ChangeType(change_type)
            except ValueError:
                raise ImpactAnalysisError(f"Invalid change type: {change_type}", module_name, change_type)
            
            breaking_changes = []
            
            # 변경 타입별 호환성 문제 예측
            if change_enum == ChangeType.INTERFACE_CHANGE:
                breaking_changes.extend(self._predict_interface_breaking_changes(module_name))
            elif change_enum == ChangeType.VERSION_DOWNGRADE:
                breaking_changes.extend(self._predict_version_breaking_changes(module_name))
            elif change_enum == ChangeType.DEPENDENCY_CHANGE:
                breaking_changes.extend(self._predict_dependency_breaking_changes(module_name))
            elif change_enum == ChangeType.REMOVAL:
                breaking_changes.extend(self._predict_removal_breaking_changes(module_name))
            
            return breaking_changes
            
        except Exception as e:
            logger.error(f"Failed to predict breaking changes for '{module_name}': {e}")
            raise
    
    def calculate_risk_score(self, module_name: str, change_type: str) -> float:
        """변경 위험도 계산 (0.0 ~ 1.0)"""
        try:
            # 변경 타입 파싱
            try:
                change_enum = ChangeType(change_type)
            except ValueError:
                raise ImpactAnalysisError(f"Invalid change type: {change_type}", module_name, change_type)
            
            # 기본 위험도 (변경 타입 기반)
            base_risk = self._get_base_risk(change_enum)
            
            # 의존성 기반 위험도
            dependent_count = len(self.get_dependent_modules(module_name))
            dependency_risk = min(0.5, dependent_count * 0.05)
            
            # 모듈 중요도 기반 위험도
            module = self._registry.get_module(module_name)
            importance_risk = self._get_importance_risk(module)
            
            # 순환 의존성 위험도
            cycles = self._dependency_analyzer.detect_circular_dependencies()
            circular_risk = 0.0
            for cycle in cycles:
                if module_name in cycle:
                    circular_risk = 0.3
                    break
            
            # 최종 위험도 계산
            total_risk = min(1.0, base_risk + dependency_risk + importance_risk + circular_risk)
            
            return total_risk
            
        except Exception as e:
            logger.error(f"Failed to calculate risk score for '{module_name}': {e}")
            raise
    
    def get_impact_statistics(self) -> Dict[str, Any]:
        """영향 분석 통계 정보"""
        try:
            stats = {
                "total_modules": 0,
                "critical_modules": 0,
                "high_impact_modules": 0,
                "modules_with_dependents": 0,
                "average_dependents": 0.0,
                "max_dependents": 0,
                "circular_dependencies": 0,
                "impact_distribution": defaultdict(int)
            }
            
            modules = self._registry.list_modules()
            stats["total_modules"] = len(modules)
            
            dependent_counts = []
            for module in modules:
                dependents = self.get_dependent_modules(module.name)
                dependent_count = len(dependents)
                dependent_counts.append(dependent_count)
                
                if dependent_count > 0:
                    stats["modules_with_dependents"] += 1
                
                stats["max_dependents"] = max(stats["max_dependents"], dependent_count)
                
                # 영향도 분포 계산
                impact_score = self.calculate_change_impact(module.name, ChangeType.INTERFACE_CHANGE.value)
                impact_level = self._get_impact_level(impact_score)
                stats["impact_distribution"][impact_level.name] += 1
                
                if impact_level == ImpactLevel.CRITICAL:
                    stats["critical_modules"] += 1
                elif impact_level == ImpactLevel.HIGH:
                    stats["high_impact_modules"] += 1
            
            # 평균 의존 모듈 수
            if dependent_counts:
                stats["average_dependents"] = sum(dependent_counts) / len(dependent_counts)
            
            # 순환 의존성 수
            cycles = self._dependency_analyzer.detect_circular_dependencies()
            stats["circular_dependencies"] = len(cycles)
            
            return dict(stats)
            
        except Exception as e:
            logger.error(f"Failed to get impact statistics: {e}")
            raise
    
    def _perform_impact_analysis(self, module_name: str, change_type: ChangeType) -> Dict[str, Any]:
        """영향 분석 수행"""
        module = self._registry.get_module(module_name)
        
        analysis = {
            "module_name": module_name,
            "change_type": change_type.value,
            "direct_dependents": [],
            "indirect_dependents": [],
            "affected_interfaces": [],
            "affected_services": [],
            "impact_propagation": [],
            "estimated_downtime": 0,
            "recovery_complexity": "low"
        }
        
        # 직접 의존 모듈 분석
        direct_dependents = self.get_dependent_modules(module_name)
        analysis["direct_dependents"] = direct_dependents
        
        # 간접 의존 모듈 분석
        indirect_dependents = set()
        for dependent in direct_dependents:
            indirect_dependents.update(self.get_dependent_modules(dependent))
        indirect_dependents -= set(direct_dependents)
        analysis["indirect_dependents"] = list(indirect_dependents)
        
        # 영향 받는 인터페이스 분석
        for interface in module.provided_interfaces:
            analysis["affected_interfaces"].append({
                "name": interface.name,
                "version": str(interface.version),
                "impact": self._analyze_interface_impact(interface.name, change_type)
            })
        
        # 영향 전파 경로 분석
        analysis["impact_propagation"] = self._analyze_impact_propagation(module_name)
        
        # 다운타임 추정
        analysis["estimated_downtime"] = self._estimate_downtime(module_name, change_type)
        
        # 복구 복잡도 평가
        analysis["recovery_complexity"] = self._assess_recovery_complexity(module_name, change_type)
        
        return analysis
    
    def _get_type_multiplier(self, module_type) -> float:
        """모듈 타입 기반 영향도 배수"""
        multipliers = {
            "core": 1.5,
            "plugin": 1.0,
            "workflow": 1.2,
            "external": 0.8,
            "common": 1.3
        }
        return multipliers.get(module_type.value, 1.0)
    
    def _get_impact_level(self, impact_score: float) -> ImpactLevel:
        """영향도 점수를 레벨로 변환"""
        if impact_score >= 0.8:
            return ImpactLevel.CRITICAL
        elif impact_score >= 0.6:
            return ImpactLevel.HIGH
        elif impact_score >= 0.4:
            return ImpactLevel.MEDIUM
        elif impact_score >= 0.2:
            return ImpactLevel.LOW
        else:
            return ImpactLevel.NONE
    
    def _get_base_risk(self, change_type: ChangeType) -> float:
        """변경 타입 기반 기본 위험도"""
        risk_levels = {
            ChangeType.REMOVAL: 0.9,
            ChangeType.INTERFACE_CHANGE: 0.8,
            ChangeType.VERSION_DOWNGRADE: 0.7,
            ChangeType.DEPENDENCY_CHANGE: 0.6,
            ChangeType.IMPLEMENTATION_CHANGE: 0.4,
            ChangeType.VERSION_UPGRADE: 0.3,
            ChangeType.STATUS_CHANGE: 0.3,
            ChangeType.CONFIGURATION_CHANGE: 0.2,
            ChangeType.ADDITION: 0.1
        }
        return risk_levels.get(change_type, 0.5)
    
    def _get_importance_risk(self, module) -> float:
        """모듈 중요도 기반 위험도"""
        # 코어 모듈은 높은 중요도
        if module.module_type.value == "core":
            return 0.3
        elif module.module_type.value == "workflow":
            return 0.2
        elif module.module_type.value == "common":
            return 0.2
        else:
            return 0.1
    
    def _predict_interface_breaking_changes(self, module_name: str) -> List[str]:
        """인터페이스 변경 시 호환성 문제 예측"""
        breaking_changes = []
        
        # 인터페이스를 사용하는 모듈들 확인
        dependents = self.get_dependent_modules(module_name)
        for dependent in dependents:
            dependent_module = self._registry.get_module(dependent)
            if dependent_module:
                for usage in dependent_module.used_interfaces:
                    breaking_changes.append(
                        f"Module '{dependent}' uses interface '{usage.interface_name}' "
                        f"which may be affected by changes in '{module_name}'"
                    )
        
        return breaking_changes
    
    def _predict_version_breaking_changes(self, module_name: str) -> List[str]:
        """버전 변경 시 호환성 문제 예측"""
        breaking_changes = []
        
        dependents = self.get_dependent_modules(module_name)
        for dependent in dependents:
            dependent_module = self._registry.get_module(dependent)
            if dependent_module:
                for dep in dependent_module.dependencies:
                    if dep.module_name == module_name and dep.version_constraint:
                        breaking_changes.append(
                            f"Module '{dependent}' has version constraint '{dep.version_constraint}' "
                            f"for '{module_name}' which may be violated"
                        )
        
        return breaking_changes
    
    def _predict_dependency_breaking_changes(self, module_name: str) -> List[str]:
        """의존성 변경 시 호환성 문제 예측"""
        breaking_changes = []
        
        module = self._registry.get_module(module_name)
        for dep in module.dependencies:
            if not dep.optional:
                breaking_changes.append(
                    f"Required dependency '{dep.module_name}' change may affect '{module_name}'"
                )
        
        return breaking_changes
    
    def _predict_removal_breaking_changes(self, module_name: str) -> List[str]:
        """모듈 제거 시 호환성 문제 예측"""
        breaking_changes = []
        
        dependents = self.get_dependent_modules(module_name)
        for dependent in dependents:
            breaking_changes.append(
                f"Module '{dependent}' depends on '{module_name}' which will be removed"
            )
        
        return breaking_changes
    
    def _analyze_interface_impact(self, interface_name: str, change_type: ChangeType) -> str:
        """인터페이스 영향 분석"""
        if change_type == ChangeType.INTERFACE_CHANGE:
            return "high"
        elif change_type == ChangeType.REMOVAL:
            return "critical"
        elif change_type in [ChangeType.VERSION_UPGRADE, ChangeType.VERSION_DOWNGRADE]:
            return "medium"
        else:
            return "low"
    
    def _analyze_impact_propagation(self, module_name: str) -> List[Dict[str, Any]]:
        """영향 전파 경로 분석"""
        propagation = []
        
        # 1단계: 직접 의존 모듈들
        direct_dependents = self.get_dependent_modules(module_name)
        for dependent in direct_dependents:
            propagation.append({
                "level": 1,
                "module": dependent,
                "impact": "direct"
            })
        
        # 2단계: 간접 의존 모듈들
        for dependent in direct_dependents:
            indirect_dependents = self.get_dependent_modules(dependent)
            for indirect_dependent in indirect_dependents:
                propagation.append({
                    "level": 2,
                    "module": indirect_dependent,
                    "impact": "indirect",
                    "via": dependent
                })
        
        return propagation
    
    def _estimate_downtime(self, module_name: str, change_type: ChangeType) -> int:
        """다운타임 추정 (분 단위)"""
        base_downtime = {
            ChangeType.ADDITION: 0,
            ChangeType.CONFIGURATION_CHANGE: 5,
            ChangeType.IMPLEMENTATION_CHANGE: 10,
            ChangeType.VERSION_UPGRADE: 15,
            ChangeType.STATUS_CHANGE: 20,
            ChangeType.DEPENDENCY_CHANGE: 30,
            ChangeType.VERSION_DOWNGRADE: 45,
            ChangeType.INTERFACE_CHANGE: 60,
            ChangeType.REMOVAL: 120
        }
        
        downtime = base_downtime.get(change_type, 30)
        
        # 의존 모듈 수에 따른 추가 다운타임
        dependent_count = len(self.get_dependent_modules(module_name))
        downtime += dependent_count * 5
        
        return downtime
    
    def _assess_recovery_complexity(self, module_name: str, change_type: ChangeType) -> str:
        """복구 복잡도 평가"""
        if change_type == ChangeType.REMOVAL:
            return "critical"
        elif change_type in [ChangeType.INTERFACE_CHANGE, ChangeType.VERSION_DOWNGRADE]:
            return "high"
        elif change_type in [ChangeType.DEPENDENCY_CHANGE, ChangeType.VERSION_UPGRADE]:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(self, module_name: str, change_type: str, 
                                impact_score: float, risk_score: float) -> List[str]:
        """권장 사항 생성"""
        recommendations = []
        
        if impact_score >= 0.8:
            recommendations.append("고영향 변경으로 인한 시스템 전체 테스트 필요")
            recommendations.append("단계별 롤아웃 계획 수립 권장")
        
        if risk_score >= 0.7:
            recommendations.append("백업 및 롤백 계획 필수")
            recommendations.append("모니터링 강화 필요")
        
        dependents = self.get_dependent_modules(module_name)
        if len(dependents) > 5:
            recommendations.append("다수의 의존 모듈로 인한 점진적 배포 권장")
        
        if change_type == ChangeType.INTERFACE_CHANGE.value:
            recommendations.append("인터페이스 변경에 따른 호환성 테스트 필수")
        
        return recommendations
    
    def _get_current_timestamp(self) -> str:
        """현재 타임스탬프 반환"""
        import datetime
        return datetime.datetime.now().isoformat()
    
    def __str__(self) -> str:
        """문자열 표현"""
        return f"ImpactAnalyzer(registry={self._registry})"
    
    def __repr__(self) -> str:
        """상세 문자열 표현"""
        return f"ImpactAnalyzer(registry={self._registry}, dependency_analyzer={self._dependency_analyzer})" 