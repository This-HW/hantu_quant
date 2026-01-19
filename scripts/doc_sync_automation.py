#!/usr/bin/env python3
"""
문서 동기화 자동화 시스템
TODO 완료 시 관련 문서들을 자동으로 업데이트합니다.
"""

import os
import re
import json
import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TodoUpdate:
    """TODO 업데이트 정보"""
    todo_id: str
    status: str  # completed, in_progress, pending
    completion_date: Optional[str] = None
    description: str = ""


@dataclass
class DocumentMapping:
    """문서 매핑 정보"""
    file_path: str
    update_patterns: List[str]
    dependencies: List[str]


class DocumentSynchronizer:
    """문서 동기화 자동화 클래스"""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.today = datetime.date.today().strftime("%Y-%m-%d")
        
        # 문서 매핑 정의
        self.document_mappings = {
            "project_summary": DocumentMapping(
                file_path="PROJECT_SUMMARY.md",
                update_patterns=[
                    r"## 현재 진행 상황.*?(?=##|$)",
                    r"### 완료된 단계.*?(?=###|##|$)",
                    r"### 다음 단계.*?(?=###|##|$)"
                ],
                dependencies=["todo_status", "phase_completion"]
            ),
            "roadmap": DocumentMapping(
                file_path="ROADMAP.md",
                update_patterns=[
                    r"## 현재 단계.*?(?=##|$)",
                    r"### 진행 상황.*?(?=###|##|$)"
                ],
                dependencies=["todo_status", "phase_status"]
            ),
            "status_report": DocumentMapping(
                file_path="STATUS_REPORT.md",
                update_patterns=[
                    r"## 개발 진행 상황.*?(?=##|$)",
                    r"## 성과 지표.*?(?=##|$)"
                ],
                dependencies=["todo_status", "metrics"]
            ),
            "project_status_rule": DocumentMapping(
                file_path=".cursor/rules/project-status.mdc",
                update_patterns=[
                    r"### 개발 진행 상황.*?(?=###|##|$)",
                    r"### ✅ 완료된.*?(?=###|##|$)",
                    r"### 🚀 다음 단계.*?(?=###|##|$)"
                ],
                dependencies=["todo_status"]
            ),
            "implementation_checklist": DocumentMapping(
                file_path=".cursor/rules/implementation_checklist.md",
                update_patterns=[
                    r"### ✅ 완료된.*?(?=###|##|$)",
                    r"### 🚀 다음 단계.*?(?=###|##|$)"
                ],
                dependencies=["todo_status"]
            )
        }
        
        # TODO 상태 매핑
        self.todo_phases = {
            "1.9": "모듈 아키텍처",
            "1.10": "플러그인 시스템", 
            "1.11": "모듈 레지스트리",
            "1.12": "패키지 관리",
            "1.13": "모듈 리팩토링",
            "2.1": "AI 학습 기본구조",
            "2.2": "데이터 수집",
            "2.3": "피처 엔지니어링",
            "2.4": "성과 분석",
            "2.5": "패턴 학습",
            "2.6": "파라미터 최적화",
            "2.7": "백테스트 자동화",
            "2.8": "AI 모델 통합"
        }

    def detect_todo_completion(self, git_diff: Optional[str] = None) -> List[TodoUpdate]:
        """Git diff 또는 파일 변경을 통해 TODO 완료를 감지"""
        completed_todos = []
        
        # TODO 리스트 파일에서 상태 확인
        if os.path.exists("todos.json"):
            with open("todos.json", "r", encoding="utf-8") as f:
                todos = json.load(f)
                
            for todo in todos:
                if todo.get("status") == "completed":
                    completed_todos.append(TodoUpdate(
                        todo_id=todo["id"],
                        status="completed",
                        completion_date=self.today,
                        description=todo.get("content", "")
                    ))
        
        return completed_todos

    def update_project_summary(self, completed_todos: List[TodoUpdate]) -> bool:
        """PROJECT_SUMMARY.md 업데이트"""
        file_path = self.workspace_root / "PROJECT_SUMMARY.md"
        if not file_path.exists():
            return False
            
        content = file_path.read_text(encoding="utf-8")
        
        # 완료된 TODO 개수 계산
        completed_count = len([t for t in completed_todos if t.status == "completed"])
        
        # 현재 진행 상황 업데이트
        current_status = self._get_current_status_text(completed_todos)
        
        # 정규식으로 섹션 찾아서 업데이트
        pattern = r"(## 현재 진행 상황.*?)(### 완료된 단계.*?)(### 다음 단계.*?)(?=###|##|$)"
        replacement = f"\\1{current_status}\\3"
        
        updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        if updated_content != content:
            file_path.write_text(updated_content, encoding="utf-8")
            return True
            
        return False

    def update_implementation_checklist(self, completed_todos: List[TodoUpdate]) -> bool:
        """implementation_checklist.md 업데이트"""
        file_path = self.workspace_root / ".cursor/rules/implementation_checklist.md"
        if not file_path.exists():
            return False
            
        content = file_path.read_text(encoding="utf-8")
        
        # 완료된 TODO들을 체크박스로 변경
        for todo in completed_todos:
            if todo.status == "completed":
                # [ ] → [x] 변경
                pattern = rf"- \[ \] TODO {todo.todo_id}:"
                replacement = rf"- [x] TODO {todo.todo_id}:"
                content = re.sub(pattern, replacement, content)
        
        # 섹션 재구성 (완료된 것들을 "완료된" 섹션으로 이동)
        content = self._reorganize_checklist_sections(content, completed_todos)
        
        file_path.write_text(content, encoding="utf-8")
        return True

    def update_project_status_rule(self, completed_todos: List[TodoUpdate]) -> bool:
        """project-status.mdc 규칙 파일 업데이트"""
        file_path = self.workspace_root / ".cursor/rules/project-status.mdc"
        if not file_path.exists():
            return False
            
        content = file_path.read_text(encoding="utf-8")
        
        # 개발 진행 상황 업데이트
        status_text = self._get_status_rule_text(completed_todos)
        
        # 정규식으로 섹션 업데이트
        pattern = r"(### 개발 진행 상황.*?)(?=###|##)"
        replacement = f"{status_text}"
        
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        file_path.write_text(content, encoding="utf-8")
        return True

    def create_history_record(self, completed_todos: List[TodoUpdate]) -> bool:
        """작업 히스토리 기록 생성"""
        history_dir = self.workspace_root / ".ai/history"
        history_dir.mkdir(parents=True, exist_ok=True)
        
        # 가장 최근 완료된 TODO를 기준으로 파일명 생성
        if completed_todos:
            latest_todo = max(completed_todos, key=lambda x: x.todo_id)
            filename = f"{self.today}_todo_{latest_todo.todo_id}_completion.md"
        else:
            filename = f"{self.today}_system_update.md"
            
        history_file = history_dir / filename
        
        # 히스토리 내용 생성
        history_content = self._generate_history_content(completed_todos)
        
        history_file.write_text(history_content, encoding="utf-8")
        return True

    def sync_all_documents(self, todo_updates: Optional[List[TodoUpdate]] = None) -> Dict[str, bool]:
        """모든 관련 문서 동기화"""
        if todo_updates is None:
            todo_updates = self.detect_todo_completion()
            
        results = {}
        
        # 각 문서 업데이트
        results["project_summary"] = self.update_project_summary(todo_updates)
        results["implementation_checklist"] = self.update_implementation_checklist(todo_updates)
        results["project_status_rule"] = self.update_project_status_rule(todo_updates)
        results["history_record"] = self.create_history_record(todo_updates)
        
        # ROADMAP.md와 STATUS_REPORT.md도 필요시 업데이트
        results["roadmap"] = self._update_roadmap(todo_updates)
        results["status_report"] = self._update_status_report(todo_updates)
        
        return results

    def _get_current_status_text(self, completed_todos: List[TodoUpdate]) -> str:
        """현재 상태 텍스트 생성"""
        completed_ids = [t.todo_id for t in completed_todos if t.status == "completed"]
        
        if any(id.startswith("1.") for id in completed_ids):
            return """
### 완료된 단계
- ✅ Phase 1: 감시 리스트 구축 시스템 (100% 완료)
- ✅ Phase 2: 일일 매매 주식 선정 시스템 (100% 완료)  
- ✅ 모듈 아키텍처 시스템: TODO 1.9-1.13 (100% 완료)
  - 인터페이스 기반 설계, 플러그인 시스템, 모듈 레지스트리
  - 패키지 관리 시스템, Phase 1,2 모듈 리팩토링

### 현재 우선순위
- 🚀 **다음 단계**: Phase 4 AI 학습 시스템 (TODO 2.1-2.8)
- 📋 **장기 계획**: Phase 5 → Phase 3 순서
"""
        return ""

    def _get_status_rule_text(self, completed_todos: List[TodoUpdate]) -> str:
        """규칙 파일용 상태 텍스트 생성"""
        return """### 개발 진행 상황
- **완료된 단계**: Phase 1 (감시 리스트), Phase 2 (일일 선정), 모듈 아키텍처 시스템 (TODO 1.9-1.13)
- **현재 우선순위**: Phase 4 (AI 학습 시스템) → Phase 5 → Phase 3
- **TODO 현황**: 1.9-1.13 모두 완료, 2.x 시리즈 시작 준비 완료
- **다음 작업**: Phase 4 AI 학습 시스템 (TODO 2.1-2.8) 시작

"""

    def _reorganize_checklist_sections(self, content: str, completed_todos: List[TodoUpdate]) -> str:
        """체크리스트 섹션 재구성"""
        # 완료된 TODO들을 완료된 섹션으로 이동
        # 이 부분은 더 정교한 로직이 필요하지만 기본 구조만 제공
        return content

    def _update_roadmap(self, todo_updates: List[TodoUpdate]) -> bool:
        """ROADMAP.md 업데이트"""
        # 구현 필요
        return False

    def _update_status_report(self, todo_updates: List[TodoUpdate]) -> bool:
        """STATUS_REPORT.md 업데이트"""
        # 구현 필요
        return False

    def _generate_history_content(self, completed_todos: List[TodoUpdate]) -> str:
        """히스토리 내용 생성"""
        content = f"""# 문서 동기화 자동 업데이트 - {self.today}

## 완료된 TODO 목록
"""
        for todo in completed_todos:
            content += f"- TODO {todo.todo_id}: {todo.description}\n"
            
        content += f"""
## 업데이트된 문서
- PROJECT_SUMMARY.md
- .cursor/rules/project-status.mdc  
- .cursor/rules/implementation_checklist.md
- ROADMAP.md (필요시)
- STATUS_REPORT.md (필요시)

## 자동 동기화 시스템
이 업데이트는 문서 동기화 자동화 시스템에 의해 생성되었습니다.
"""
        return content


def main():
    """메인 실행 함수"""
    synchronizer = DocumentSynchronizer()
    
    # TODO 완료 감지 및 문서 동기화
    results = synchronizer.sync_all_documents()
    
    print("문서 동기화 완료:")
    for doc, success in results.items():
        status = "✅ 성공" if success else "⚠️ 스킵"
        print(f"  {doc}: {status}")


if __name__ == "__main__":
    main() 