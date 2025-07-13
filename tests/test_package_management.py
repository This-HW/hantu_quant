"""
패키지 관리 시스템 통합 테스트

TODO 1.12: 패키지 관리 시스템 구현 테스트
"""

import unittest
import tempfile
import shutil
import json
from pathlib import Path
import zipfile

from core.packages import (
    PackageManager, PackageInfo, SemanticVersion, PackageType,
    PackageDependency, PackageEntryPoint, create_package_info,
    build_package, install_package, uninstall_package,
    PackageError, PackageNotFoundError, InvalidPackageError
)


class TestPackageManagement(unittest.TestCase):
    """패키지 관리 시스템 통합 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        # 임시 작업 디렉토리 생성
        self.temp_dir = Path(tempfile.mkdtemp())
        self.workspace = self.temp_dir / "workspace"
        self.test_source = self.temp_dir / "test_source"
        self.output_dir = self.temp_dir / "output"
        
        # 디렉토리 생성
        self.workspace.mkdir(parents=True)
        self.test_source.mkdir(parents=True)
        self.output_dir.mkdir(parents=True)
        
        # 테스트용 모듈 생성
        self._create_test_module()
        
        # 패키지 관리자 생성
        self.manager = PackageManager(self.workspace)
        self.manager.initialize()
    
    def tearDown(self):
        """테스트 정리"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_module(self):
        """테스트용 모듈 생성"""
        # __init__.py 파일
        init_file = self.test_source / "__init__.py"
        init_file.write_text('''
"""테스트 모듈"""

__version__ = "1.0.0"
__author__ = "Test Author"

from .main import TestClass

__all__ = ["TestClass"]
''', encoding='utf-8')
        
        # main.py 파일
        main_file = self.test_source / "main.py"
        main_file.write_text('''
"""메인 모듈"""

class TestClass:
    """테스트 클래스"""
    
    def __init__(self, name: str = "test"):
        self.name = name
    
    def greet(self) -> str:
        """인사 메시지 반환"""
        return f"Hello from {self.name}!"
    
    def get_version(self) -> str:
        """버전 정보 반환"""
        return "1.0.0"


def test_function() -> str:
    """테스트 함수"""
    return "Test function executed"
''', encoding='utf-8')
        
        # utils.py 파일
        utils_file = self.test_source / "utils.py"
        utils_file.write_text('''
"""유틸리티 모듈"""

def utility_function(x: int, y: int) -> int:
    """유틸리티 함수"""
    return x + y

class UtilityClass:
    """유틸리티 클래스"""
    
    @staticmethod
    def format_message(msg: str) -> str:
        return f"[UTIL] {msg}"
''', encoding='utf-8')
    
    def test_package_info_creation(self):
        """패키지 정보 생성 테스트"""
        # 기본 패키지 정보 생성
        package_info = create_package_info(
            name="test-package",
            version="1.0.0",
            package_type="module",
            description="Test package for unit testing",
            author="Test Author"
        )
        
        self.assertEqual(package_info.name, "test-package")
        self.assertEqual(str(package_info.version), "1.0.0")
        self.assertEqual(package_info.package_type, PackageType.MODULE)
        self.assertEqual(package_info.description, "Test package for unit testing")
        self.assertEqual(package_info.author, "Test Author")
    
    def test_semantic_version(self):
        """시맨틱 버전 테스트"""
        # 기본 버전
        version1 = SemanticVersion(1, 0, 0)
        self.assertEqual(str(version1), "1.0.0")
        
        # Pre-release 버전
        version2 = SemanticVersion(1, 0, 0, "alpha.1")
        self.assertEqual(str(version2), "1.0.0-alpha.1")
        
        # Build 메타데이터 포함
        version3 = SemanticVersion(1, 0, 0, None, "20250117")
        self.assertEqual(str(version3), "1.0.0+20250117")
        
        # 버전 비교
        self.assertTrue(version1 > SemanticVersion(0, 9, 9))
        self.assertTrue(version1 < SemanticVersion(1, 0, 1))
        self.assertTrue(version1.is_compatible_with(SemanticVersion(1, 1, 0)))
        self.assertFalse(version1.is_compatible_with(SemanticVersion(2, 0, 0)))
    
    def test_package_dependencies(self):
        """패키지 의존성 테스트"""
        # 의존성 생성
        dep1 = PackageDependency(
            name="core-interfaces",
            version_constraint=">=1.0.0",
            optional=False,
            description="Core interface definitions"
        )
        
        dep2 = PackageDependency(
            name="data-models", 
            version_constraint="==1.2.0",
            optional=True,
            description="Data model definitions"
        )
        
        # 패키지 정보에 의존성 추가
        package_info = PackageInfo(
            _name="test-package",
            _version=SemanticVersion(1, 0, 0),
            _package_type=PackageType.MODULE,
            _dependencies=[dep1, dep2]
        )
        
        self.assertEqual(len(package_info.dependencies), 2)
        self.assertTrue(package_info.has_dependency("core-interfaces"))
        self.assertTrue(package_info.has_dependency("data-models"))
        self.assertFalse(package_info.has_dependency("non-existent"))
    
    def test_package_entry_points(self):
        """패키지 엔트리 포인트 테스트"""
        # 엔트리 포인트 생성
        ep1 = PackageEntryPoint(
            name="test_class",
            module_path="test_module.main",
            class_name="TestClass",
            description="Main test class"
        )
        
        ep2 = PackageEntryPoint(
            name="test_function",
            module_path="test_module.main",
            function_name="test_function",
            description="Test function"
        )
        
        # 임포트 경로 확인
        self.assertEqual(ep1.get_import_path(), "test_module.main:TestClass")
        self.assertEqual(ep2.get_import_path(), "test_module.main:test_function")
        
        # 패키지 정보에 엔트리 포인트 추가
        package_info = PackageInfo(
            _name="test-package",
            _version=SemanticVersion(1, 0, 0),
            _package_type=PackageType.MODULE,
            _entry_points=[ep1, ep2]
        )
        
        self.assertEqual(len(package_info.entry_points), 2)
        self.assertTrue(package_info.has_entry_point("test_class"))
        self.assertTrue(package_info.has_entry_point("test_function"))
    
    def test_package_building(self):
        """패키지 빌드 테스트"""
        # 패키지 정보 생성
        package_info = create_package_info(
            name="test-module",
            version="1.0.0",
            package_type="module",
            description="Test module for building",
            author="Test Author"
        )
        
        # 엔트리 포인트 추가
        entry_point = PackageEntryPoint(
            name="test_class",
            module_path="main",
            class_name="TestClass"
        )
        package_info.add_entry_point(entry_point)
        
        # 패키지 빌드
        package_path = self.manager.build_package(
            self.test_source,
            self.output_dir,
            package_info
        )
        
        # 빌드 결과 확인
        self.assertTrue(package_path.exists())
        self.assertEqual(package_path.name, "test-module-1.0.0.hqp")
        
        # 패키지 파일 내용 확인
        with zipfile.ZipFile(package_path, 'r') as zf:
            file_list = zf.namelist()
            
            # 필수 파일들 확인
            self.assertIn('manifest.json', file_list)
            self.assertIn('dependencies.json', file_list)
            self.assertIn('build_info.json', file_list)
            
            # 모듈 파일들 확인
            self.assertIn('module/__init__.py', file_list)
            self.assertIn('module/main.py', file_list)
            self.assertIn('module/utils.py', file_list)
            
            # 매니페스트 내용 확인
            manifest_data = json.loads(zf.read('manifest.json').decode('utf-8'))
            self.assertEqual(manifest_data['package']['name'], 'test-module')
            self.assertEqual(manifest_data['package']['version']['major'], 1)
            self.assertEqual(manifest_data['package']['version']['minor'], 0)
            self.assertEqual(manifest_data['package']['version']['patch'], 0)
    
    def test_package_repository(self):
        """패키지 저장소 테스트"""
        # 패키지 빌드
        package_info = create_package_info("test-repo-package", "1.0.0")
        package_path = self.manager.build_package(
            self.test_source,
            self.output_dir,
            package_info
        )
        
        # 저장소에 패키지 저장
        success = self.manager.publish_package(package_path)
        self.assertTrue(success)
        
        # 저장소에서 패키지 조회
        stored_info = self.manager.repository.get_package_info("test-repo-package")
        self.assertIsNotNone(stored_info)
        self.assertEqual(stored_info.name, "test-repo-package")
        
        # 패키지 존재 여부 확인
        exists = self.manager.repository.package_exists("test-repo-package")
        self.assertTrue(exists)
        
        # 패키지 목록 조회
        packages = self.manager.repository.list_packages()
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0].name, "test-repo-package")
    
    def test_package_installation(self):
        """패키지 설치 테스트"""
        # 패키지 빌드 및 퍼블리시
        package_info = create_package_info("test-install-package", "1.0.0")
        package_path = self.manager.build_package(
            self.test_source,
            self.output_dir,
            package_info
        )
        self.manager.publish_package(package_path)
        
        # 패키지 설치
        success = self.manager.install_package("test-install-package", "1.0.0")
        self.assertTrue(success)
        
        # 설치 확인
        is_installed = self.manager.installer.is_package_installed("test-install-package")
        self.assertTrue(is_installed)
        
        # 설치된 패키지 목록 확인
        installed_packages = self.manager.list_installed_packages()
        self.assertEqual(len(installed_packages), 1)
        self.assertEqual(installed_packages[0].name, "test-install-package")
        
        # 설치된 파일 확인
        install_location = self.manager.install_path / "test-install-package"
        self.assertTrue(install_location.exists())
        self.assertTrue((install_location / "__init__.py").exists())
        self.assertTrue((install_location / "main.py").exists())
    
    def test_package_uninstallation(self):
        """패키지 제거 테스트"""
        # 패키지 설치
        package_info = create_package_info("test-uninstall-package", "1.0.0")
        package_path = self.manager.build_package(
            self.test_source,
            self.output_dir,
            package_info
        )
        self.manager.publish_package(package_path)
        self.manager.install_package("test-uninstall-package", "1.0.0")
        
        # 설치 확인
        self.assertTrue(self.manager.installer.is_package_installed("test-uninstall-package"))
        
        # 패키지 제거
        success = self.manager.uninstall_package("test-uninstall-package")
        self.assertTrue(success)
        
        # 제거 확인
        is_installed = self.manager.installer.is_package_installed("test-uninstall-package")
        self.assertFalse(is_installed)
        
        # 설치된 패키지 목록 확인
        installed_packages = self.manager.list_installed_packages()
        self.assertEqual(len(installed_packages), 0)
        
        # 설치 디렉토리 제거 확인
        install_location = self.manager.install_path / "test-uninstall-package"
        self.assertFalse(install_location.exists())
    
    def test_package_update(self):
        """패키지 업데이트 테스트"""
        # 버전 1.0.0 패키지 설치
        package_info_v1 = create_package_info("test-update-package", "1.0.0")
        package_path_v1 = self.manager.build_package(
            self.test_source,
            self.output_dir,
            package_info_v1
        )
        self.manager.publish_package(package_path_v1)
        self.manager.install_package("test-update-package", "1.0.0")
        
        # 버전 1.1.0 패키지 생성 및 퍼블리시
        package_info_v2 = create_package_info("test-update-package", "1.1.0")
        package_path_v2 = self.manager.build_package(
            self.test_source,
            self.output_dir,
            package_info_v2
        )
        self.manager.publish_package(package_path_v2)
        
        # 패키지 업데이트
        success = self.manager.update_package("test-update-package", "1.1.0")
        self.assertTrue(success)
        
        # 업데이트 확인
        installed_packages = self.manager.list_installed_packages()
        self.assertEqual(len(installed_packages), 1)
        updated_package = installed_packages[0]
        self.assertEqual(str(updated_package.version), "1.1.0")
    
    def test_dependency_resolution(self):
        """의존성 해결 테스트"""
        # 의존성이 있는 패키지 생성
        # 먼저 의존성 패키지 생성
        dep_package_info = create_package_info("dependency-package", "1.0.0")
        dep_package_path = self.manager.build_package(
            self.test_source,
            self.output_dir,
            dep_package_info
        )
        self.manager.publish_package(dep_package_path)
        
        # 메인 패키지 생성 (의존성 포함)
        main_package_info = create_package_info("main-package", "1.0.0")
        dependency = PackageDependency(
            name="dependency-package",
            version_constraint=">=1.0.0"
        )
        main_package_info.add_dependency(dependency)
        
        main_package_path = self.manager.build_package(
            self.test_source,
            self.output_dir,
            main_package_info
        )
        self.manager.publish_package(main_package_path)
        
        # 메인 패키지 설치 (의존성 자동 해결)
        success = self.manager.install_package("main-package", "1.0.0")
        self.assertTrue(success)
        
        # 의존성 패키지도 설치되었는지 확인
        installed_packages = self.manager.list_installed_packages()
        package_names = [pkg.name for pkg in installed_packages]
        
        self.assertIn("main-package", package_names)
        self.assertIn("dependency-package", package_names)
    
    def test_package_search(self):
        """패키지 검색 테스트"""
        # 여러 패키지 생성
        packages = [
            ("search-test-alpha", "1.0.0"),
            ("search-test-beta", "1.0.0"),
            ("other-package", "1.0.0")
        ]
        
        for name, version in packages:
            package_info = create_package_info(name, version)
            package_path = self.manager.build_package(
                self.test_source,
                self.output_dir,
                package_info
            )
            self.manager.publish_package(package_path)
        
        # 검색 테스트
        search_results = self.manager.search_packages("search-test")
        self.assertEqual(len(search_results), 2)
        
        result_names = [pkg.name for pkg in search_results]
        self.assertIn("search-test-alpha", result_names)
        self.assertIn("search-test-beta", result_names)
        self.assertNotIn("other-package", result_names)
    
    def test_package_statistics(self):
        """패키지 통계 테스트"""
        # 패키지 생성 및 설치
        package_info = create_package_info("stats-test-package", "1.0.0")
        package_path = self.manager.build_package(
            self.test_source,
            self.output_dir,
            package_info
        )
        self.manager.publish_package(package_path)
        self.manager.install_package("stats-test-package", "1.0.0")
        
        # 통계 정보 조회
        stats = self.manager.get_package_statistics()
        
        # 통계 구조 확인
        self.assertIn('repository', stats)
        self.assertIn('installed', stats)
        self.assertIn('workspace_path', stats)
        
        # 저장소 통계 확인
        repo_stats = stats['repository']
        self.assertEqual(repo_stats['total_packages'], 1)
        
        # 설치된 패키지 통계 확인
        installed_stats = stats['installed']
        self.assertEqual(installed_stats['total_packages'], 1)
    
    def test_error_handling(self):
        """오류 처리 테스트"""
        # 존재하지 않는 패키지 설치 시도
        with self.assertRaises(PackageNotFoundError):
            self.manager.install_package("non-existent-package", "1.0.0")
        
        # 설치되지 않은 패키지 제거 시도
        with self.assertRaises(Exception):  # PackageNotInstalledError 예상
            self.manager.uninstall_package("non-existent-package")
        
        # 잘못된 소스 경로로 빌드 시도
        non_existent_path = self.temp_dir / "non-existent"
        with self.assertRaises(Exception):  # PackageBuildError 예상
            self.manager.build_package(
                non_existent_path,
                self.output_dir
            )
    
    def test_full_workflow(self):
        """전체 워크플로우 테스트"""
        # 1. 패키지 정보 생성
        package_info = create_package_info(
            name="workflow-test-package",
            version="1.0.0",
            package_type="module",
            description="Complete workflow test package",
            author="Test Workflow"
        )
        
        # 2. 엔트리 포인트 추가
        entry_point = PackageEntryPoint(
            name="workflow_test",
            module_path="main",
            class_name="TestClass",
            description="Workflow test entry point"
        )
        package_info.add_entry_point(entry_point)
        
        # 3. 패키지 빌드
        package_path = self.manager.build_package(
            self.test_source,
            self.output_dir,
            package_info
        )
        self.assertTrue(package_path.exists())
        
        # 4. 저장소에 퍼블리시
        success = self.manager.publish_package(package_path)
        self.assertTrue(success)
        
        # 5. 패키지 설치
        success = self.manager.install_package("workflow-test-package", "1.0.0")
        self.assertTrue(success)
        
        # 6. 설치 확인
        is_installed = self.manager.installer.is_package_installed("workflow-test-package")
        self.assertTrue(is_installed)
        
        # 7. 패키지 검색
        search_results = self.manager.search_packages("workflow-test")
        self.assertEqual(len(search_results), 1)
        
        # 8. 통계 확인
        stats = self.manager.get_package_statistics()
        self.assertEqual(stats['repository']['total_packages'], 1)
        self.assertEqual(stats['installed']['total_packages'], 1)
        
        # 9. 패키지 제거
        success = self.manager.uninstall_package("workflow-test-package")
        self.assertTrue(success)
        
        # 10. 제거 확인
        is_installed = self.manager.installer.is_package_installed("workflow-test-package")
        self.assertFalse(is_installed)
        
        # 11. 정리 작업
        self.manager.cleanup()


if __name__ == '__main__':
    unittest.main(verbosity=2) 