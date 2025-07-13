"""
패키지 관리 시스템 예외 클래스

이 모듈은 패키지 관리 시스템에서 발생할 수 있는 다양한 예외들을 정의합니다.
"""

from typing import List, Optional, Any


class PackageError(Exception):
    """패키지 관리 시스템 기본 예외 클래스"""
    
    def __init__(self, message: str, package_name: Optional[str] = None, 
                 package_version: Optional[str] = None):
        super().__init__(message)
        self.package_name = package_name
        self.package_version = package_version
        self.message = message
    
    def __str__(self):
        if self.package_name:
            if self.package_version:
                return f"Package '{self.package_name}' v{self.package_version}: {self.message}"
            return f"Package '{self.package_name}': {self.message}"
        return self.message


class PackageNotFoundError(PackageError):
    """패키지를 찾을 수 없는 예외"""
    
    def __init__(self, package_name: str, version: Optional[str] = None):
        if version:
            message = f"Package '{package_name}' version '{version}' not found"
        else:
            message = f"Package '{package_name}' not found"
        super().__init__(message, package_name, version)


class PackageAlreadyExistsError(PackageError):
    """패키지가 이미 존재하는 예외"""
    
    def __init__(self, package_name: str, version: str):
        super().__init__(
            f"Package '{package_name}' version '{version}' already exists",
            package_name, version
        )


class PackageAlreadyInstalledError(PackageError):
    """패키지가 이미 설치된 예외"""
    
    def __init__(self, package_name: str, version: str):
        super().__init__(
            f"Package '{package_name}' version '{version}' is already installed",
            package_name, version
        )


class PackageNotInstalledError(PackageError):
    """패키지가 설치되지 않은 예외"""
    
    def __init__(self, package_name: str):
        super().__init__(f"Package '{package_name}' is not installed", package_name)


class InvalidPackageError(PackageError):
    """잘못된 패키지 예외"""
    
    def __init__(self, package_name: str, errors: List[str]):
        error_msg = f"Invalid package '{package_name}': {', '.join(errors)}"
        super().__init__(error_msg, package_name)
        self.errors = errors


class PackageCorruptedError(PackageError):
    """패키지 손상 예외"""
    
    def __init__(self, package_name: str, reason: str = "Unknown"):
        super().__init__(f"Package '{package_name}' is corrupted: {reason}", package_name)
        self.reason = reason


class PackageDependencyError(PackageError):
    """패키지 의존성 관련 예외"""
    
    def __init__(self, message: str, package_name: Optional[str] = None,
                 dependency_name: Optional[str] = None):
        super().__init__(message, package_name)
        self.dependency_name = dependency_name


class UnresolvedDependencyError(PackageDependencyError):
    """해결되지 않은 의존성 예외"""
    
    def __init__(self, package_name: str, dependency_name: str, 
                 required_version: Optional[str] = None):
        if required_version:
            message = f"Unresolved dependency: {dependency_name} {required_version}"
        else:
            message = f"Unresolved dependency: {dependency_name}"
        super().__init__(message, package_name, dependency_name)
        self.required_version = required_version


class DependencyConflictError(PackageDependencyError):
    """의존성 충돌 예외"""
    
    def __init__(self, package_name: str, conflicting_packages: List[str]):
        conflict_list = ', '.join(conflicting_packages)
        super().__init__(
            f"Dependency conflict: {conflict_list}",
            package_name
        )
        self.conflicting_packages = conflicting_packages


class CircularDependencyError(PackageDependencyError):
    """순환 의존성 예외"""
    
    def __init__(self, cycle: List[str]):
        cycle_str = " -> ".join(cycle + [cycle[0]])
        super().__init__(f"Circular dependency detected: {cycle_str}")
        self.cycle = cycle


class IncompatibleVersionError(PackageDependencyError):
    """호환되지 않는 버전 예외"""
    
    def __init__(self, package_name: str, dependency_name: str,
                 required_version: str, available_version: str):
        super().__init__(
            f"Incompatible version for {dependency_name}: "
            f"required {required_version}, available {available_version}",
            package_name, dependency_name
        )
        self.required_version = required_version
        self.available_version = available_version


class PackageBuildError(PackageError):
    """패키지 빌드 실패 예외"""
    
    def __init__(self, package_name: str, build_step: str, error: Exception):
        super().__init__(
            f"Build failed at step '{build_step}': {error}",
            package_name
        )
        self.build_step = build_step
        self.original_error = error


class PackageInstallationError(PackageError):
    """패키지 설치 실패 예외"""
    
    def __init__(self, package_name: str, reason: str, original_error: Optional[Exception] = None):
        super().__init__(f"Installation failed: {reason}", package_name)
        self.reason = reason
        self.original_error = original_error


class PackageUninstallationError(PackageError):
    """패키지 제거 실패 예외"""
    
    def __init__(self, package_name: str, reason: str, original_error: Optional[Exception] = None):
        super().__init__(f"Uninstallation failed: {reason}", package_name)
        self.reason = reason
        self.original_error = original_error


class PackageUpdateError(PackageError):
    """패키지 업데이트 실패 예외"""
    
    def __init__(self, package_name: str, from_version: str, to_version: str, 
                 reason: str, original_error: Optional[Exception] = None):
        super().__init__(
            f"Update failed from {from_version} to {to_version}: {reason}",
            package_name
        )
        self.from_version = from_version
        self.to_version = to_version
        self.reason = reason
        self.original_error = original_error


class PackageValidationError(PackageError):
    """패키지 검증 실패 예외"""
    
    def __init__(self, package_name: str, validation_errors: List[str]):
        error_msg = f"Package validation failed: {', '.join(validation_errors)}"
        super().__init__(error_msg, package_name)
        self.validation_errors = validation_errors


class ManifestError(PackageError):
    """매니페스트 관련 예외"""
    
    def __init__(self, message: str, package_name: Optional[str] = None, 
                 manifest_path: Optional[str] = None):
        super().__init__(message, package_name)
        self.manifest_path = manifest_path


class InvalidManifestError(ManifestError):
    """잘못된 매니페스트 예외"""
    
    def __init__(self, package_name: str, errors: List[str], 
                 manifest_path: Optional[str] = None):
        error_msg = f"Invalid manifest: {', '.join(errors)}"
        super().__init__(error_msg, package_name, manifest_path)
        self.errors = errors


class ManifestNotFoundError(ManifestError):
    """매니페스트를 찾을 수 없는 예외"""
    
    def __init__(self, manifest_path: str):
        super().__init__(f"Manifest not found at '{manifest_path}'", None, manifest_path)


class VersionError(PackageError):
    """버전 관련 예외"""
    
    def __init__(self, message: str, version_string: Optional[str] = None):
        super().__init__(message)
        self.version_string = version_string


class InvalidVersionError(VersionError):
    """잘못된 버전 형식 예외"""
    
    def __init__(self, version_string: str):
        super().__init__(f"Invalid version format: '{version_string}'", version_string)


class VersionNotFoundError(VersionError):
    """버전을 찾을 수 없는 예외"""
    
    def __init__(self, package_name: str, version_string: str):
        super().__init__(f"Version '{version_string}' not found for package '{package_name}'")
        self.package_name = package_name


class RepositoryError(PackageError):
    """저장소 관련 예외"""
    
    def __init__(self, message: str, repository_path: Optional[str] = None):
        super().__init__(message)
        self.repository_path = repository_path


class RepositoryNotFoundError(RepositoryError):
    """저장소를 찾을 수 없는 예외"""
    
    def __init__(self, repository_path: str):
        super().__init__(f"Repository not found at '{repository_path}'", repository_path)


class RepositoryCorruptedError(RepositoryError):
    """저장소 손상 예외"""
    
    def __init__(self, repository_path: str, reason: str = "Unknown"):
        super().__init__(f"Repository corrupted: {reason}", repository_path)
        self.reason = reason


class RepositoryLockError(RepositoryError):
    """저장소 락 관련 예외"""
    
    def __init__(self, repository_path: str, operation: str):
        super().__init__(f"Repository locked during operation: {operation}", repository_path)
        self.operation = operation


class DeploymentError(PackageError):
    """배포 관련 예외"""
    
    def __init__(self, message: str, deployment_id: Optional[str] = None,
                 target: Optional[str] = None):
        super().__init__(message)
        self.deployment_id = deployment_id
        self.target = target


class DeploymentFailedError(DeploymentError):
    """배포 실패 예외"""
    
    def __init__(self, package_name: str, target: str, reason: str,
                 deployment_id: Optional[str] = None):
        super().__init__(f"Deployment to '{target}' failed: {reason}", deployment_id, target)
        self.package_name = package_name


class RollbackError(DeploymentError):
    """롤백 실패 예외"""
    
    def __init__(self, deployment_id: str, reason: str):
        super().__init__(f"Rollback failed: {reason}", deployment_id)


class PackageTimeoutError(PackageError):
    """패키지 작업 타임아웃 예외"""
    
    def __init__(self, operation: str, package_name: str, timeout: float):
        super().__init__(
            f"Operation '{operation}' timed out after {timeout} seconds",
            package_name
        )
        self.operation = operation
        self.timeout = timeout


class PackageSecurityError(PackageError):
    """패키지 보안 관련 예외"""
    
    def __init__(self, package_name: str, security_issue: str):
        super().__init__(f"Security issue: {security_issue}", package_name)
        self.security_issue = security_issue


class PackagePermissionError(PackageError):
    """패키지 권한 관련 예외"""
    
    def __init__(self, package_name: str, operation: str, required_permission: str):
        super().__init__(
            f"Permission denied for operation '{operation}': requires '{required_permission}'",
            package_name
        )
        self.operation = operation
        self.required_permission = required_permission


class PackageChecksumError(PackageError):
    """패키지 체크섬 불일치 예외"""
    
    def __init__(self, package_name: str, expected_checksum: str, actual_checksum: str):
        super().__init__(
            f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}",
            package_name
        )
        self.expected_checksum = expected_checksum
        self.actual_checksum = actual_checksum


class PackageIntegrityError(PackageError):
    """패키지 무결성 오류 예외"""
    
    def __init__(self, package_name: str, integrity_issues: List[str]):
        issue_list = ', '.join(integrity_issues)
        super().__init__(f"Integrity check failed: {issue_list}", package_name)
        self.integrity_issues = integrity_issues 