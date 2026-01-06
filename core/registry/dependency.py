"""
의존성 분석 엔진 구현

이 모듈은 모듈 간의 의존성을 분석하고 관리하는 기능을 제공합니다.
"""

import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict, deque
import networkx as nx

from .interfaces import IDependencyAnalyzer, IModuleRegistry, ModuleStatus
from .exceptions import (
    CircularDependencyError, UnresolvedDependencyError, 
    ModuleNotFoundError, DependencyError
)

logger = logging.getLogger(__name__)


class DependencyAnalyzer(IDependencyAnalyzer):
    """의존성 분석 엔진 구현 클래스"""
    
    def __init__(self, registry: IModuleRegistry):
        """초기화"""
        self._registry = registry
        self._dependency_cache: Dict[str, Dict[str, Any]] = {}
        self._circular_cache: Optional[List[List[str]]] = None
        self._graph_cache: Optional[nx.DiGraph] = None
        self._cache_dirty = True
        
        logger.info("DependencyAnalyzer initialized")
    
    def analyze_dependencies(self, module_name: str) -> Dict[str, Any]:
        """의존성 분석"""
        try:
            # 캐시 확인
            if not self._cache_dirty and module_name in self._dependency_cache:
                return self._dependency_cache[module_name]
            
            # 모듈 존재 확인
            module = self._registry.get_module(module_name)
            if not module:
                raise ModuleNotFoundError(module_name)
            
            # 의존성 분석 수행
            analysis = self._perform_dependency_analysis(module_name)
            
            # 캐시 업데이트
            self._dependency_cache[module_name] = analysis
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze dependencies for '{module_name}': {e}", exc_info=True)
            raise
    
    def detect_circular_dependencies(self) -> List[List[str]]:
        """순환 의존성 탐지"""
        try:
            # 캐시 확인
            if not self._cache_dirty and self._circular_cache is not None:
                return self._circular_cache
            
            # 그래프 구축
            graph = self._build_dependency_graph()
            
            # 순환 의존성 탐지
            cycles = self._find_cycles(graph)
            
            # 캐시 업데이트
            self._circular_cache = cycles
            
            return cycles
            
        except Exception as e:
            logger.error(f"Failed to detect circular dependencies: {e}", exc_info=True)
            raise
    
    def resolve_dependency_order(self, modules: List[str]) -> List[str]:
        """의존성 순서 해결 (위상 정렬)"""
        try:
            # 서브그래프 생성
            subgraph = self._build_subgraph(modules)
            
            # 위상 정렬 수행
            try:
                return list(nx.topological_sort(subgraph))
            except nx.NetworkXError as e:
                # 순환 의존성 발견
                cycles = list(nx.simple_cycles(subgraph))
                if cycles:
                    raise CircularDependencyError(cycles[0])
                raise DependencyError(f"Cannot resolve dependency order: {e}")
            
        except Exception as e:
            logger.error(f"Failed to resolve dependency order: {e}", exc_info=True)
            raise
    
    def validate_dependency_versions(self, module_name: str) -> Tuple[bool, List[str]]:
        """의존성 버전 검증"""
        try:
            module = self._registry.get_module(module_name)
            if not module:
                raise ModuleNotFoundError(module_name)
            
            errors = []
            
            # 각 의존성에 대해 버전 검증
            for dependency in module.dependencies:
                dep_name = dependency.module_name
                dep_module = self._registry.get_module(dep_name)
                
                if not dep_module:
                    if not dependency.optional:
                        errors.append(f"Required dependency '{dep_name}' not found")
                    continue
                
                # 버전 호환성 확인
                if not self._is_version_compatible(dependency.version_constraint, 
                                                 dep_module.version):
                    errors.append(
                        f"Incompatible version for '{dep_name}': "
                        f"required {dependency.version_constraint}, "
                        f"available {dep_module.version}"
                    )
            
            return len(errors) == 0, errors
            
        except Exception as e:
            logger.error(f"Failed to validate dependency versions for '{module_name}': {e}", exc_info=True)
            raise
    
    def get_dependency_tree(self, module_name: str) -> Dict[str, Any]:
        """의존성 트리 생성"""
        try:
            module = self._registry.get_module(module_name)
            if not module:
                raise ModuleNotFoundError(module_name)
            
            visited = set()
            
            def build_tree(name: str) -> Dict[str, Any]:
                if name in visited:
                    return {"name": name, "cyclic": True, "dependencies": []}
                
                visited.add(name)
                
                current_module = self._registry.get_module(name)
                if not current_module:
                    return {"name": name, "not_found": True, "dependencies": []}
                
                tree = {
                    "name": name,
                    "version": str(current_module.version),
                    "type": current_module.module_type.value,
                    "status": current_module.status.value,
                    "dependencies": []
                }
                
                for dep in current_module.dependencies:
                    dep_tree = build_tree(dep.module_name)
                    dep_tree["optional"] = dep.optional
                    dep_tree["version_constraint"] = dep.version_constraint
                    tree["dependencies"].append(dep_tree)
                
                visited.remove(name)
                return tree
            
            return build_tree(module_name)
            
        except Exception as e:
            logger.error(f"Failed to build dependency tree for '{module_name}': {e}", exc_info=True)
            raise
    
    def get_reverse_dependencies(self, module_name: str) -> List[str]:
        """역 의존성 조회 (해당 모듈을 의존하는 모듈들)"""
        try:
            reverse_deps = []
            
            # 모든 모듈을 확인하여 역 의존성 찾기
            for module in self._registry.list_modules():
                if module.has_dependency(module_name):
                    reverse_deps.append(module.name)
            
            return reverse_deps
            
        except Exception as e:
            logger.error(f"Failed to get reverse dependencies for '{module_name}': {e}", exc_info=True)
            raise
    
    def calculate_dependency_depth(self, module_name: str) -> int:
        """의존성 깊이 계산"""
        try:
            module = self._registry.get_module(module_name)
            if not module:
                raise ModuleNotFoundError(module_name)
            
            visited = set()
            
            def calculate_depth(name: str) -> int:
                if name in visited:
                    return 0  # 순환 의존성 방지
                
                visited.add(name)
                
                current_module = self._registry.get_module(name)
                if not current_module:
                    return 0
                
                max_depth = 0
                for dep in current_module.dependencies:
                    if not dep.optional:
                        depth = calculate_depth(dep.module_name)
                        max_depth = max(max_depth, depth + 1)
                
                visited.remove(name)
                return max_depth
            
            return calculate_depth(module_name)
            
        except Exception as e:
            logger.error(f"Failed to calculate dependency depth for '{module_name}': {e}", exc_info=True)
            raise
    
    def get_dependency_statistics(self) -> Dict[str, Any]:
        """의존성 통계 정보"""
        try:
            stats = {
                "total_modules": 0,
                "modules_with_dependencies": 0,
                "total_dependencies": 0,
                "optional_dependencies": 0,
                "circular_dependencies": 0,
                "unresolved_dependencies": 0,
                "max_dependency_depth": 0,
                "average_dependency_depth": 0.0,
                "dependency_distribution": defaultdict(int)
            }
            
            modules = self._registry.list_modules()
            stats["total_modules"] = len(modules)
            
            depth_sum = 0
            for module in modules:
                deps = module.dependencies
                if deps:
                    stats["modules_with_dependencies"] += 1
                    stats["total_dependencies"] += len(deps)
                    stats["optional_dependencies"] += sum(1 for d in deps if d.optional)
                    
                    # 의존성 개수별 분포
                    stats["dependency_distribution"][len(deps)] += 1
                    
                    # 깊이 계산
                    depth = self.calculate_dependency_depth(module.name)
                    depth_sum += depth
                    stats["max_dependency_depth"] = max(stats["max_dependency_depth"], depth)
                else:
                    stats["dependency_distribution"][0] += 1
            
            # 평균 깊이 계산
            if stats["total_modules"] > 0:
                stats["average_dependency_depth"] = depth_sum / stats["total_modules"]
            
            # 순환 의존성 개수
            cycles = self.detect_circular_dependencies()
            stats["circular_dependencies"] = len(cycles)
            
            # 해결되지 않은 의존성 개수
            unresolved = 0
            for module in modules:
                for dep in module.dependencies:
                    if not dep.optional and not self._registry.has_module(dep.module_name):
                        unresolved += 1
            stats["unresolved_dependencies"] = unresolved
            
            return dict(stats)
            
        except Exception as e:
            logger.error(f"Failed to get dependency statistics: {e}", exc_info=True)
            raise
    
    def invalidate_cache(self) -> None:
        """캐시 무효화"""
        self._dependency_cache.clear()
        self._circular_cache = None
        self._graph_cache = None
        self._cache_dirty = True
        logger.debug("Dependency cache invalidated")
    
    def _perform_dependency_analysis(self, module_name: str) -> Dict[str, Any]:
        """의존성 분석 수행"""
        module = self._registry.get_module(module_name)
        
        analysis = {
            "module_name": module_name,
            "direct_dependencies": [],
            "all_dependencies": set(),
            "optional_dependencies": [],
            "required_dependencies": [],
            "missing_dependencies": [],
            "circular_dependencies": [],
            "dependency_depth": 0,
            "reverse_dependencies": [],
            "is_leaf": True,
            "is_root": True
        }
        
        # 직접 의존성 분석
        for dep in module.dependencies:
            dep_info = {
                "name": dep.module_name,
                "version_constraint": dep.version_constraint,
                "optional": dep.optional,
                "description": dep.description,
                "exists": self._registry.has_module(dep.module_name)
            }
            
            analysis["direct_dependencies"].append(dep_info)
            analysis["all_dependencies"].add(dep.module_name)
            
            if dep.optional:
                analysis["optional_dependencies"].append(dep.module_name)
            else:
                analysis["required_dependencies"].append(dep.module_name)
            
            if not dep_info["exists"]:
                analysis["missing_dependencies"].append(dep.module_name)
        
        # 전체 의존성 수집 (재귀적)
        visited = set()
        self._collect_all_dependencies(module_name, analysis["all_dependencies"], visited)
        
        # 순환 의존성 확인
        cycles = self.detect_circular_dependencies()
        for cycle in cycles:
            if module_name in cycle:
                analysis["circular_dependencies"].append(cycle)
        
        # 의존성 깊이 계산
        analysis["dependency_depth"] = self.calculate_dependency_depth(module_name)
        
        # 역 의존성 조회
        analysis["reverse_dependencies"] = self.get_reverse_dependencies(module_name)
        
        # 리프/루트 노드 판별
        analysis["is_leaf"] = len(analysis["direct_dependencies"]) == 0
        analysis["is_root"] = len(analysis["reverse_dependencies"]) == 0
        
        return analysis
    
    def _collect_all_dependencies(self, module_name: str, all_deps: Set[str], visited: Set[str]) -> None:
        """모든 의존성 수집 (재귀적)"""
        if module_name in visited:
            return
        
        visited.add(module_name)
        
        module = self._registry.get_module(module_name)
        if not module:
            return
        
        for dep in module.dependencies:
            if dep.module_name not in all_deps:
                all_deps.add(dep.module_name)
                self._collect_all_dependencies(dep.module_name, all_deps, visited)
    
    def _build_dependency_graph(self) -> nx.DiGraph:
        """의존성 그래프 구축"""
        if not self._cache_dirty and self._graph_cache is not None:
            return self._graph_cache
        
        graph = nx.DiGraph()
        
        # 모든 모듈을 노드로 추가
        for module in self._registry.list_modules():
            graph.add_node(module.name)
        
        # 의존성을 엣지로 추가
        for module in self._registry.list_modules():
            for dep in module.dependencies:
                if not dep.optional and self._registry.has_module(dep.module_name):
                    graph.add_edge(module.name, dep.module_name)
        
        self._graph_cache = graph
        return graph
    
    def _build_subgraph(self, modules: List[str]) -> nx.DiGraph:
        """서브그래프 생성"""
        full_graph = self._build_dependency_graph()
        
        # 관련 모듈들을 모두 찾기
        relevant_modules = set(modules)
        
        # 각 모듈의 의존성들도 포함
        for module_name in modules:
            if module_name in full_graph:
                relevant_modules.update(nx.descendants(full_graph, module_name))
        
        # 서브그래프 생성
        return full_graph.subgraph(relevant_modules).copy()
    
    def _find_cycles(self, graph: nx.DiGraph) -> List[List[str]]:
        """순환 의존성 찾기"""
        try:
            cycles = list(nx.simple_cycles(graph))
            return cycles
        except Exception as e:
            logger.error(f"Failed to find cycles: {e}", exc_info=True)
            return []
    
    def _is_version_compatible(self, constraint: Optional[str], version) -> bool:
        """버전 호환성 확인"""
        if not constraint:
            return True
        
        # 간단한 버전 제약 확인
        # 실제 구현에서는 더 정교한 버전 파싱이 필요
        try:
            # 예: ">=1.0.0,<2.0.0" 형태의 제약 조건 처리
            # 여기서는 간단히 항상 True 반환
            return True
        except Exception:
            return False
    
    def get_loading_order(self, modules: List[str]) -> List[str]:
        """모듈 로딩 순서 결정"""
        try:
            # 의존성 순서 해결
            ordered_modules = self.resolve_dependency_order(modules)
            
            # 의존성이 없는 모듈부터 로딩
            return list(reversed(ordered_modules))
            
        except Exception as e:
            logger.error(f"Failed to determine loading order: {e}", exc_info=True)
            raise
    
    def get_unloading_order(self, modules: List[str]) -> List[str]:
        """모듈 언로딩 순서 결정"""
        try:
            # 의존성 순서 해결
            ordered_modules = self.resolve_dependency_order(modules)
            
            # 의존성이 많은 모듈부터 언로딩
            return ordered_modules
            
        except Exception as e:
            logger.error(f"Failed to determine unloading order: {e}", exc_info=True)
            raise
    
    def validate_module_compatibility(self, module_name: str, 
                                    target_modules: List[str]) -> Dict[str, Any]:
        """모듈 호환성 검증"""
        try:
            module = self._registry.get_module(module_name)
            if not module:
                raise ModuleNotFoundError(module_name)
            
            compatibility = {
                "compatible": True,
                "issues": [],
                "warnings": []
            }
            
            # 각 대상 모듈과의 호환성 확인
            for target_name in target_modules:
                target_module = self._registry.get_module(target_name)
                if not target_module:
                    compatibility["issues"].append(f"Target module '{target_name}' not found")
                    compatibility["compatible"] = False
                    continue
                
                # 버전 호환성 확인
                if not module.is_compatible_with(target_module):
                    compatibility["issues"].append(
                        f"Version incompatibility with '{target_name}'"
                    )
                    compatibility["compatible"] = False
                
                # 인터페이스 호환성 확인
                for usage in module.used_interfaces:
                    if not target_module.has_interface(usage.interface_name):
                        if usage.required:
                            compatibility["issues"].append(
                                f"Required interface '{usage.interface_name}' not provided by '{target_name}'"
                            )
                            compatibility["compatible"] = False
                        else:
                            compatibility["warnings"].append(
                                f"Optional interface '{usage.interface_name}' not provided by '{target_name}'"
                            )
            
            return compatibility
            
        except Exception as e:
            logger.error(f"Failed to validate module compatibility: {e}", exc_info=True)
            raise
    
    def __str__(self) -> str:
        """문자열 표현"""
        return f"DependencyAnalyzer(registry={self._registry})"
    
    def __repr__(self) -> str:
        """상세 문자열 표현"""
        return f"DependencyAnalyzer(registry={self._registry}, cache_dirty={self._cache_dirty})" 