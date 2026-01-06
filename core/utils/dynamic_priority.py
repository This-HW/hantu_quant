"""
동적 TODO 우선순위 조정 시스템

현재 성과, 시장 상황, 의존성, 사용자 패턴을 분석하여
TODO 우선순위를 동적으로 조정하는 시스템
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np

from ..utils.logging import get_logger

logger = get_logger(__name__)

class Priority(Enum):
    """우선순위 레벨"""
    CRITICAL = 1    # 즉시 실행 필요
    HIGH = 2        # 높은 우선순위  
    MEDIUM = 3      # 보통 우선순위
    LOW = 4         # 낮은 우선순위
    DEFERRED = 5    # 연기됨

class TodoStatus(Enum):
    """TODO 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"

@dataclass
class TodoItem:
    """TODO 아이템"""
    id: str
    content: str
    status: TodoStatus
    priority: Priority
    estimated_hours: float = 0.0
    actual_hours: float = 0.0
    dependencies: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completion_rate: float = 0.0
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

@dataclass
class MarketCondition:
    """시장 상황"""
    volatility: float       # 변동성 (0-1)
    trend: float           # 추세 (-1 to 1, -1=하락, 1=상승)
    accuracy: float        # 현재 정확도 (0-1)
    performance_score: float  # 성과 점수 (0-1)
    last_updated: datetime

@dataclass
class PriorityAdjustment:
    """우선순위 조정 결과"""
    todo_id: str
    old_priority: Priority
    new_priority: Priority
    reason: str
    confidence: float
    adjusted_at: datetime

class DynamicPriorityManager:
    """동적 TODO 우선순위 조정 관리자"""
    
    def __init__(self, data_dir: str = "data/priority"):
        """
        초기화
        
        Args:
            data_dir: 데이터 저장 디렉토리
        """
        self._logger = logger
        self._data_dir = data_dir
        self._todos_file = os.path.join(data_dir, "todos.json")
        self._market_file = os.path.join(data_dir, "market_condition.json")
        self._history_file = os.path.join(data_dir, "priority_history.json")
        
        # 디렉토리 생성
        os.makedirs(data_dir, exist_ok=True)
        
        # 우선순위 조정 가중치
        self._weights = {
            'market_volatility': 0.2,
            'current_accuracy': 0.3,
            'dependency_urgency': 0.25,
            'completion_rate': 0.15,
            'time_sensitivity': 0.1
        }
        
        # TODO 목록 및 이력 로드
        self._todos = self._load_todos()
        self._market_condition = self._load_market_condition()
        self._adjustment_history = self._load_adjustment_history()
        
        self._logger.info("동적 우선순위 관리자 초기화 완료")
    
    def _load_todos(self) -> Dict[str, TodoItem]:
        """TODO 목록 로드"""
        try:
            if os.path.exists(self._todos_file):
                with open(self._todos_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                todos = {}
                for todo_data in data:
                    todo = TodoItem(
                        id=todo_data['id'],
                        content=todo_data['content'],
                        status=TodoStatus(todo_data['status']),
                        priority=Priority(todo_data.get('priority', Priority.MEDIUM.value)),
                        estimated_hours=todo_data.get('estimated_hours', 0.0),
                        actual_hours=todo_data.get('actual_hours', 0.0),
                        dependencies=todo_data.get('dependencies', []),
                        tags=todo_data.get('tags', []),
                        created_at=datetime.fromisoformat(todo_data.get('created_at', datetime.now().isoformat())),
                        updated_at=datetime.fromisoformat(todo_data.get('updated_at', datetime.now().isoformat())),
                        completion_rate=todo_data.get('completion_rate', 0.0)
                    )
                    todos[todo.id] = todo
                
                return todos
            return {}
        except Exception as e:
            self._logger.error(f"TODO 목록 로드 실패: {e}", exc_info=True)
            return {}
    
    def _save_todos(self):
        """TODO 목록 저장"""
        try:
            data = []
            for todo in self._todos.values():
                todo_dict = asdict(todo)
                todo_dict['status'] = todo.status.value
                todo_dict['priority'] = todo.priority.value
                todo_dict['created_at'] = todo.created_at.isoformat()
                todo_dict['updated_at'] = todo.updated_at.isoformat()
                data.append(todo_dict)
            
            with open(self._todos_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self._logger.error(f"TODO 목록 저장 실패: {e}", exc_info=True)
    
    def _load_market_condition(self) -> Optional[MarketCondition]:
        """시장 상황 로드"""
        try:
            if os.path.exists(self._market_file):
                with open(self._market_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                return MarketCondition(
                    volatility=data['volatility'],
                    trend=data['trend'],
                    accuracy=data['accuracy'],
                    performance_score=data['performance_score'],
                    last_updated=datetime.fromisoformat(data['last_updated'])
                )
            return None
        except Exception as e:
            self._logger.error(f"시장 상황 로드 실패: {e}", exc_info=True)
            return None
    
    def _save_market_condition(self, condition: MarketCondition):
        """시장 상황 저장"""
        try:
            data = asdict(condition)
            data['last_updated'] = condition.last_updated.isoformat()
            
            with open(self._market_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self._logger.error(f"시장 상황 저장 실패: {e}", exc_info=True)
    
    def _load_adjustment_history(self) -> List[PriorityAdjustment]:
        """우선순위 조정 이력 로드"""
        try:
            if os.path.exists(self._history_file):
                with open(self._history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                history = []
                for adj_data in data:
                    adj = PriorityAdjustment(
                        todo_id=adj_data['todo_id'],
                        old_priority=Priority(adj_data['old_priority']),
                        new_priority=Priority(adj_data['new_priority']),
                        reason=adj_data['reason'],
                        confidence=adj_data['confidence'],
                        adjusted_at=datetime.fromisoformat(adj_data['adjusted_at'])
                    )
                    history.append(adj)
                
                return history
            return []
        except Exception as e:
            self._logger.error(f"조정 이력 로드 실패: {e}", exc_info=True)
            return []
    
    def _save_adjustment_history(self):
        """우선순위 조정 이력 저장"""
        try:
            data = []
            for adj in self._adjustment_history:
                adj_dict = asdict(adj)
                adj_dict['old_priority'] = adj.old_priority.value
                adj_dict['new_priority'] = adj.new_priority.value
                adj_dict['adjusted_at'] = adj.adjusted_at.isoformat()
                data.append(adj_dict)
            
            with open(self._history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self._logger.error(f"조정 이력 저장 실패: {e}", exc_info=True)
    
    def update_market_condition(self, volatility: float, trend: float, 
                              accuracy: float, performance_score: float):
        """시장 상황 업데이트"""
        self._market_condition = MarketCondition(
            volatility=volatility,
            trend=trend,
            accuracy=accuracy,
            performance_score=performance_score,
            last_updated=datetime.now()
        )
        self._save_market_condition(self._market_condition)
        
        # 시장 상황 변화에 따른 우선순위 재조정
        self._trigger_priority_adjustment("market_condition_update")
        
        self._logger.info(f"시장 상황 업데이트: 변동성={volatility:.2f}, 정확도={accuracy:.2f}")
    
    def add_or_update_todo(self, todo_id: str, content: str, status: str, 
                          completion_rate: float = 0.0, dependencies: Optional[List[str]] = None,
                          estimated_hours: float = 0.0):
        """TODO 추가 또는 업데이트"""
        if todo_id in self._todos:
            # 기존 TODO 업데이트
            todo = self._todos[todo_id]
            todo.content = content
            todo.status = TodoStatus(status)
            todo.completion_rate = completion_rate
            todo.updated_at = datetime.now()
            if dependencies:
                todo.dependencies = dependencies
            if estimated_hours > 0:
                todo.estimated_hours = estimated_hours
        else:
            # 새 TODO 추가
            todo = TodoItem(
                id=todo_id,
                content=content,
                status=TodoStatus(status),
                priority=Priority.MEDIUM,  # 기본 우선순위
                estimated_hours=estimated_hours,
                dependencies=dependencies or [],
                completion_rate=completion_rate
            )
            self._todos[todo_id] = todo
        
        self._save_todos()
        
        # 새로운 TODO 추가 시 우선순위 조정
        self._calculate_priority_for_todo(todo_id)
        
        self._logger.info(f"TODO {todo_id} 업데이트: {content[:50]}...")
    
    def _calculate_priority_for_todo(self, todo_id: str) -> Priority:
        """특정 TODO의 우선순위 계산"""
        if todo_id not in self._todos:
            return Priority.MEDIUM
            
        todo = self._todos[todo_id]
        if todo.status in [TodoStatus.COMPLETED, TodoStatus.CANCELLED]:
            return Priority.LOW
        
        # 우선순위 점수 계산 (낮을수록 높은 우선순위)
        score = 0.0
        
        # 1. 시장 변동성 영향
        if self._market_condition and self._market_condition.volatility > 0.7:
            if any(tag in ['trading', 'risk'] for tag in todo.tags):
                score -= 0.3  # 높은 변동성 시 트레이딩 관련 우선순위 상승
        
        # 2. 현재 정확도 영향
        if self._market_condition and self._market_condition.accuracy < 0.8:
            if any(tag in ['ai', 'learning', 'accuracy'] for tag in todo.tags):
                score -= 0.4  # 낮은 정확도 시 AI 학습 관련 우선순위 상승
        
        # 3. 의존성 긴급도
        blocked_dependents = self._count_blocked_dependents(todo_id)
        score -= blocked_dependents * 0.2
        
        # 4. 완성률 고려
        if todo.completion_rate > 0.8:
            score -= 0.3  # 거의 완성된 작업 우선순위 상승
        
        # 5. 시간 민감도
        days_since_created = (datetime.now() - todo.created_at).days
        if days_since_created > 7:
            score += 0.1 * (days_since_created - 7)  # 오래된 작업 우선순위 하락
        
        # 점수를 우선순위로 변환
        if score <= -0.8:
            new_priority = Priority.CRITICAL
        elif score <= -0.4:
            new_priority = Priority.HIGH
        elif score <= 0.2:
            new_priority = Priority.MEDIUM
        elif score <= 0.6:
            new_priority = Priority.LOW
        else:
            new_priority = Priority.DEFERRED
        
        # 우선순위 변경 시 기록
        if todo.priority != new_priority:
            self._record_priority_change(todo_id, todo.priority, new_priority, 
                                       f"계산된 점수: {score:.2f}")
            todo.priority = new_priority
            todo.updated_at = datetime.now()
            self._save_todos()
        
        return new_priority
    
    def _count_blocked_dependents(self, todo_id: str) -> int:
        """이 TODO에 의존하는 블로킹된 TODO 수 계산"""
        count = 0
        for todo in self._todos.values():
            if (todo_id in todo.dependencies and 
                todo.status in [TodoStatus.PENDING, TodoStatus.BLOCKED]):
                count += 1
        return count
    
    def _record_priority_change(self, todo_id: str, old_priority: Priority, 
                              new_priority: Priority, reason: str):
        """우선순위 변경 기록"""
        adjustment = PriorityAdjustment(
            todo_id=todo_id,
            old_priority=old_priority,
            new_priority=new_priority,
            reason=reason,
            confidence=0.8,  # 기본 신뢰도
            adjusted_at=datetime.now()
        )
        
        self._adjustment_history.append(adjustment)
        self._save_adjustment_history()
        
        self._logger.info(f"우선순위 변경: {todo_id} {old_priority.name} → {new_priority.name}")
    
    def _trigger_priority_adjustment(self, trigger_reason: str):
        """우선순위 재조정 트리거"""
        adjusted_count = 0
        
        for todo_id in self._todos.keys():
            old_priority = self._todos[todo_id].priority
            new_priority = self._calculate_priority_for_todo(todo_id)
            
            if old_priority != new_priority:
                adjusted_count += 1
        
        if adjusted_count > 0:
            self._logger.info(f"우선순위 재조정 완료: {adjusted_count}개 TODO 조정됨 (트리거: {trigger_reason})")
    
    def get_prioritized_todos(self, status_filter: Optional[List[TodoStatus]] = None) -> List[TodoItem]:
        """우선순위 순으로 정렬된 TODO 목록 반환"""
        if status_filter is None:
            status_filter = [TodoStatus.PENDING, TodoStatus.IN_PROGRESS]
        
        filtered_todos = [
            todo for todo in self._todos.values() 
            if todo.status in status_filter
        ]
        
        # 우선순위 → 완성률 → 생성일자 순으로 정렬
        filtered_todos.sort(key=lambda x: (
            x.priority.value,
            -x.completion_rate,  # 완성률 높은 순
            x.created_at
        ))
        
        return filtered_todos
    
    def get_priority_summary(self) -> Dict:
        """우선순위 현황 요약"""
        summary = {
            'total_todos': len(self._todos),
            'by_status': {},
            'by_priority': {},
            'market_condition': asdict(self._market_condition) if self._market_condition else None,
            'last_adjustment': None
        }
        
        # 상태별 집계
        for status in TodoStatus:
            count = len([t for t in self._todos.values() if t.status == status])
            summary['by_status'][status.value] = count
        
        # 우선순위별 집계
        for priority in Priority:
            count = len([t for t in self._todos.values() if t.priority == priority])
            summary['by_priority'][priority.name] = count
        
        # 최근 조정 이력
        if self._adjustment_history:
            last_adj = max(self._adjustment_history, key=lambda x: x.adjusted_at)
            summary['last_adjustment'] = {
                'todo_id': last_adj.todo_id,
                'changed_to': last_adj.new_priority.name,
                'reason': last_adj.reason,
                'when': last_adj.adjusted_at.isoformat()
            }
        
        return summary
    
    def export_priority_report(self) -> str:
        """우선순위 현황 리포트 생성"""
        todos = self.get_prioritized_todos()
        summary = self.get_priority_summary()
        
        report = ["# 동적 TODO 우선순위 리포트", ""]
        report.append(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # 요약 정보
        report.append("## 📊 요약")
        report.append(f"- 전체 TODO: {summary['total_todos']}개")
        report.append(f"- 진행 중: {summary['by_status'].get('in_progress', 0)}개")
        report.append(f"- 대기 중: {summary['by_status'].get('pending', 0)}개")
        report.append(f"- 완료: {summary['by_status'].get('completed', 0)}개")
        report.append("")
        
        # 우선순위별 현황
        report.append("## 🚦 우선순위별 현황")
        for priority in Priority:
            count = summary['by_priority'].get(priority.name, 0)
            if count > 0:
                report.append(f"- {priority.name}: {count}개")
        report.append("")
        
        # 시장 상황
        if summary['market_condition']:
            mc = summary['market_condition']
            report.append("## 📈 시장 상황")
            report.append(f"- 변동성: {mc['volatility']:.2f}")
            report.append(f"- 추세: {mc['trend']:.2f}")
            report.append(f"- 정확도: {mc['accuracy']:.2f}")
            report.append(f"- 성과 점수: {mc['performance_score']:.2f}")
            report.append("")
        
        # 우선순위 TODO 목록
        report.append("## 📋 우선순위 TODO 목록")
        for todo in todos[:10]:  # 상위 10개만 표시
            status_emoji = {
                TodoStatus.PENDING: "⏳",
                TodoStatus.IN_PROGRESS: "🔄",
                TodoStatus.COMPLETED: "✅",
                TodoStatus.BLOCKED: "🚫"
            }
            
            priority_emoji = {
                Priority.CRITICAL: "🔴",
                Priority.HIGH: "🟠", 
                Priority.MEDIUM: "🟡",
                Priority.LOW: "🟢",
                Priority.DEFERRED: "⚪"
            }
            
            emoji = f"{priority_emoji[todo.priority]} {status_emoji[todo.status]}"
            report.append(f"{emoji} **{todo.id}**: {todo.content}")
            if todo.completion_rate > 0:
                report.append(f"   완성률: {todo.completion_rate:.1%}")
            report.append("")
        
        return "\n".join(report)

# 전역 인스턴스
_priority_manager = None

def get_priority_manager() -> DynamicPriorityManager:
    """우선순위 관리자 싱글톤 인스턴스 반환"""
    global _priority_manager
    if _priority_manager is None:
        _priority_manager = DynamicPriorityManager()
    return _priority_manager 