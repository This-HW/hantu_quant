#!/usr/bin/env python3
"""
유틸리티 스크립트: 임시 테스트 파일 정리

tests/scratch/ 폴더의 파일을 정리합니다.
- 오래된 파일 경고
- 전체 삭제 옵션
- PR 머지 전 체크

사용법:
  python cleanup-scratch-tests.py [--check | --clean | --force]

옵션:
  --check  : 상태만 확인 (기본값)
  --clean  : 대화형으로 삭제
  --force  : 모두 삭제
"""

import os
import sys
from datetime import datetime

# 공통 유틸리티 import
try:
    from utils import get_project_root, format_size, DEFAULT_SCRATCH_MAX_AGE_DAYS
except ImportError:
    DEFAULT_SCRATCH_MAX_AGE_DAYS = 7

    def get_project_root() -> str:
        """프로젝트 루트 찾기 (fallback)"""
        cwd = os.getcwd()
        while cwd != "/":
            if os.path.exists(os.path.join(cwd, ".git")):
                return cwd
            cwd = os.path.dirname(cwd)
        return os.getcwd()

    def format_size(size: int) -> str:
        """파일 크기 포맷 (fallback)"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


def get_scratch_files(scratch_dir: str) -> list[dict]:
    """scratch 폴더의 파일 목록과 메타데이터"""
    if not os.path.exists(scratch_dir):
        return []

    files = []
    for root, dirs, filenames in os.walk(scratch_dir):
        # .gitkeep 제외
        for filename in filenames:
            if filename == ".gitkeep":
                continue

            file_path = os.path.join(root, filename)
            stat = os.stat(file_path)
            age_days = (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days

            files.append({
                "path": file_path,
                "rel_path": os.path.relpath(file_path, scratch_dir),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "age_days": age_days,
            })

    return sorted(files, key=lambda x: x["age_days"], reverse=True)


def check_scratch(scratch_dir: str, max_age_days: int = 7):
    """scratch 폴더 상태 확인"""
    files = get_scratch_files(scratch_dir)

    if not files:
        print("✅ tests/scratch/ 폴더가 비어있습니다.")
        return True

    print(f"\n📁 tests/scratch/ 파일 목록 ({len(files)}개)\n")
    print(f"{'파일':<40} {'크기':<10} {'경과일':<10} {'상태'}")
    print("-" * 70)

    has_old = False
    for f in files:
        status = ""
        if f["age_days"] > max_age_days:
            status = "⚠️ 삭제 권장"
            has_old = True
        elif f["age_days"] > max_age_days // 2:
            status = "📌 주의"

        print(f"{f['rel_path']:<40} {format_size(f['size']):<10} {f['age_days']}일{'':<6} {status}")

    print()

    if has_old:
        print(f"⚠️ {max_age_days}일 이상 된 파일이 있습니다.")
        print("   PR 머지 전에 정리하세요: python cleanup-scratch-tests.py --clean")
        return False

    return True


def clean_scratch(scratch_dir: str, force: bool = False):
    """scratch 폴더 정리"""
    files = get_scratch_files(scratch_dir)

    if not files:
        print("✅ 정리할 파일이 없습니다.")
        return

    print(f"\n📁 삭제 대상 파일 ({len(files)}개):\n")
    for f in files:
        print(f"  - {f['rel_path']} ({format_size(f['size'])}, {f['age_days']}일)")
    print()

    if force:
        confirm = "y"
    else:
        confirm = input("모두 삭제하시겠습니까? [y/N] ").strip().lower()

    if confirm == "y":
        for f in files:
            os.remove(f["path"])
            print(f"  🗑️ 삭제: {f['rel_path']}")

        # 빈 폴더 정리
        for root, dirs, _ in os.walk(scratch_dir, topdown=False):
            for d in dirs:
                dir_path = os.path.join(root, d)
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)

        print(f"\n✅ {len(files)}개 파일 삭제 완료")
    else:
        print("취소됨")


def main():
    project_root = get_project_root()
    scratch_dir = os.path.join(project_root, "tests", "scratch")

    args = sys.argv[1:]

    if "--force" in args:
        clean_scratch(scratch_dir, force=True)
    elif "--clean" in args:
        clean_scratch(scratch_dir, force=False)
    else:
        # --check (기본값)
        success = check_scratch(scratch_dir)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
