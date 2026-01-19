"""
통합 데이터베이스 유틸리티

모든 모듈에서 SQLAlchemy 기반의 통합 데이터베이스에 접근할 수 있도록 제공합니다.
SQLite와 PostgreSQL 모두 지원합니다.
"""

from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Generator
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from core.utils.log_utils import get_logger
from .session import DatabaseSession
from .models import (
    Base, FeedbackData, ModelPerformanceHistory,
    ScreeningResult, SelectionResult
)

logger = get_logger(__name__)

# 싱글톤 인스턴스
_db_session: Optional[DatabaseSession] = None


def get_db() -> DatabaseSession:
    """통합 데이터베이스 세션 인스턴스 반환"""
    global _db_session
    if _db_session is None:
        _db_session = DatabaseSession()
        logger.info("통합 데이터베이스 세션 초기화 완료")
    return _db_session


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    데이터베이스 세션 컨텍스트 매니저

    Usage:
        with get_session() as session:
            session.query(FeedbackData).all()
    """
    db = get_db()
    with db.get_session() as session:
        yield session


def ensure_tables_exist():
    """모든 테이블이 존재하는지 확인하고 없으면 생성"""
    db = get_db()
    try:
        Base.metadata.create_all(db.engine)
        logger.info("모든 테이블 확인/생성 완료")
    except SQLAlchemyError as e:
        logger.error(f"테이블 생성 오류: {e}", exc_info=True)
        raise


# ============================================================
# FeedbackData CRUD 함수
# ============================================================

def save_feedback(
    prediction_id: str,
    stock_code: str,
    prediction_date: date,
    predicted_probability: float,
    predicted_class: int,
    model_name: str,
    factor_scores: Optional[str] = None
) -> bool:
    """피드백 데이터 저장"""
    try:
        with get_session() as session:
            # 기존 데이터 확인
            existing = session.query(FeedbackData).filter_by(
                prediction_id=prediction_id
            ).first()

            if existing:
                # 업데이트
                existing.predicted_probability = predicted_probability
                existing.predicted_class = predicted_class
                existing.factor_scores = factor_scores
                existing.updated_at = datetime.now()
            else:
                # 신규 생성
                feedback = FeedbackData(
                    prediction_id=prediction_id,
                    stock_code=stock_code,
                    prediction_date=prediction_date,
                    predicted_probability=predicted_probability,
                    predicted_class=predicted_class,
                    model_name=model_name,
                    factor_scores=factor_scores
                )
                session.add(feedback)

            return True
    except SQLAlchemyError as e:
        logger.error(f"피드백 저장 오류: {e}", exc_info=True)
        return False


def update_feedback_result(
    prediction_id: str,
    actual_return_7d: float,
    actual_class: int
) -> bool:
    """피드백 실제 결과 업데이트"""
    try:
        with get_session() as session:
            feedback = session.query(FeedbackData).filter_by(
                prediction_id=prediction_id
            ).first()

            if feedback:
                feedback.actual_return_7d = actual_return_7d
                feedback.actual_class = actual_class
                feedback.prediction_error = feedback.predicted_probability - (1 if actual_class == 1 else 0)
                feedback.absolute_error = abs(feedback.prediction_error)
                feedback.feedback_date = date.today()
                feedback.is_processed = 1
                feedback.updated_at = datetime.now()
                return True

            logger.warning(f"피드백 데이터 없음: {prediction_id}")
            return False
    except SQLAlchemyError as e:
        logger.error(f"피드백 결과 업데이트 오류: {e}", exc_info=True)
        return False


def get_recent_feedback(days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
    """최근 피드백 데이터 조회"""
    try:
        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=days)

        with get_session() as session:
            feedbacks = session.query(FeedbackData).filter(
                FeedbackData.prediction_date >= cutoff_date
            ).order_by(FeedbackData.prediction_date.desc()).limit(limit).all()

            return [fb.to_dict() for fb in feedbacks]
    except SQLAlchemyError as e:
        logger.error(f"피드백 조회 오류: {e}", exc_info=True)
        return []


def get_unprocessed_feedback() -> List[Dict[str, Any]]:
    """미처리 피드백 조회"""
    try:
        with get_session() as session:
            feedbacks = session.query(FeedbackData).filter(
                FeedbackData.is_processed == 0
            ).all()

            return [fb.to_dict() for fb in feedbacks]
    except SQLAlchemyError as e:
        logger.error(f"미처리 피드백 조회 오류: {e}", exc_info=True)
        return []


# ============================================================
# ScreeningResult CRUD 함수
# ============================================================

def save_screening_result(
    screening_date: date,
    stock_code: str,
    stock_name: str,
    total_score: float,
    fundamental_score: float = None,
    technical_score: float = None,
    momentum_score: float = None,
    passed: bool = False,
    roe: float = None,
    per: float = None,
    pbr: float = None,
    debt_ratio: float = None
) -> bool:
    """스크리닝 결과 저장"""
    try:
        with get_session() as session:
            result = ScreeningResult(
                screening_date=screening_date,
                stock_code=stock_code,
                stock_name=stock_name,
                total_score=total_score,
                fundamental_score=fundamental_score,
                technical_score=technical_score,
                momentum_score=momentum_score,
                passed=1 if passed else 0,
                roe=roe,
                per=per,
                pbr=pbr,
                debt_ratio=debt_ratio
            )
            session.add(result)
            return True
    except SQLAlchemyError as e:
        logger.error(f"스크리닝 결과 저장 오류: {e}", exc_info=True)
        return False


def get_screening_results(target_date: date) -> List[Dict[str, Any]]:
    """특정 날짜 스크리닝 결과 조회"""
    try:
        with get_session() as session:
            results = session.query(ScreeningResult).filter(
                ScreeningResult.screening_date == target_date
            ).all()

            return [{
                'stock_code': r.stock_code,
                'stock_name': r.stock_name,
                'total_score': r.total_score,
                'fundamental_score': r.fundamental_score,
                'technical_score': r.technical_score,
                'momentum_score': r.momentum_score,
                'passed': bool(r.passed),
                'roe': r.roe,
                'per': r.per,
                'pbr': r.pbr,
                'debt_ratio': r.debt_ratio,
            } for r in results]
    except SQLAlchemyError as e:
        logger.error(f"스크리닝 결과 조회 오류: {e}", exc_info=True)
        return []


# ============================================================
# SelectionResult CRUD 함수
# ============================================================

def save_selection_result(
    selection_date: date,
    stock_code: str,
    stock_name: str,
    total_score: float,
    entry_price: float,
    target_price: float,
    stop_loss: float,
    expected_return: float,
    confidence: float,
    signal: str = 'buy',
    selection_reason: str = None,
    market_condition: str = None,
    technical_score: float = None,
    volume_score: float = None,
    pattern_score: float = None,
    risk_score: float = None
) -> bool:
    """선정 결과 저장"""
    try:
        with get_session() as session:
            result = SelectionResult(
                selection_date=selection_date,
                stock_code=stock_code,
                stock_name=stock_name,
                total_score=total_score,
                technical_score=technical_score,
                volume_score=volume_score,
                pattern_score=pattern_score,
                risk_score=risk_score,
                entry_price=entry_price,
                target_price=target_price,
                stop_loss=stop_loss,
                expected_return=expected_return,
                confidence=confidence,
                signal=signal,
                selection_reason=selection_reason,
                market_condition=market_condition
            )
            session.add(result)
            return True
    except SQLAlchemyError as e:
        logger.error(f"선정 결과 저장 오류: {e}", exc_info=True)
        return False


def get_selection_results(target_date: date) -> List[Dict[str, Any]]:
    """특정 날짜 선정 결과 조회"""
    try:
        with get_session() as session:
            results = session.query(SelectionResult).filter(
                SelectionResult.selection_date == target_date
            ).order_by(SelectionResult.total_score.desc()).all()

            return [{
                'stock_code': r.stock_code,
                'stock_name': r.stock_name,
                'total_score': r.total_score,
                'entry_price': r.entry_price,
                'target_price': r.target_price,
                'stop_loss': r.stop_loss,
                'expected_return': r.expected_return,
                'confidence': r.confidence,
                'signal': r.signal,
                'selection_reason': r.selection_reason,
                'market_condition': r.market_condition,
            } for r in results]
    except SQLAlchemyError as e:
        logger.error(f"선정 결과 조회 오류: {e}", exc_info=True)
        return []


def update_selection_actual_return(
    selection_date: date,
    stock_code: str,
    actual_return_7d: float
) -> bool:
    """선정 결과 실제 수익률 업데이트"""
    try:
        with get_session() as session:
            result = session.query(SelectionResult).filter(
                SelectionResult.selection_date == selection_date,
                SelectionResult.stock_code == stock_code
            ).first()

            if result:
                result.actual_return_7d = actual_return_7d
                result.is_success = 1 if actual_return_7d > 0 else 0
                result.updated_at = datetime.now()
                return True

            logger.warning(f"선정 결과 없음: {selection_date} - {stock_code}")
            return False
    except SQLAlchemyError as e:
        logger.error(f"선정 결과 업데이트 오류: {e}", exc_info=True)
        return False


# ============================================================
# ModelPerformanceHistory CRUD 함수
# ============================================================

def save_model_performance(
    model_name: str,
    evaluation_date: date,
    accuracy: float,
    precision_score: float = None,
    recall_score: float = None,
    f1_score: float = None,
    auc_score: float = None,
    feedback_count: int = None
) -> bool:
    """모델 성능 저장"""
    try:
        with get_session() as session:
            perf = ModelPerformanceHistory(
                model_name=model_name,
                evaluation_date=evaluation_date,
                accuracy=accuracy,
                precision_score=precision_score,
                recall_score=recall_score,
                f1_score=f1_score,
                auc_score=auc_score,
                feedback_count=feedback_count
            )
            session.add(perf)
            return True
    except SQLAlchemyError as e:
        logger.error(f"모델 성능 저장 오류: {e}", exc_info=True)
        return False


def get_model_performance_history(
    model_name: str,
    days: int = 30
) -> List[Dict[str, Any]]:
    """모델 성능 히스토리 조회"""
    try:
        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=days)

        with get_session() as session:
            history = session.query(ModelPerformanceHistory).filter(
                ModelPerformanceHistory.model_name == model_name,
                ModelPerformanceHistory.evaluation_date >= cutoff_date
            ).order_by(ModelPerformanceHistory.evaluation_date.desc()).all()

            return [{
                'model_name': h.model_name,
                'evaluation_date': h.evaluation_date.isoformat() if h.evaluation_date else None,
                'accuracy': h.accuracy,
                'precision_score': h.precision_score,
                'recall_score': h.recall_score,
                'f1_score': h.f1_score,
                'auc_score': h.auc_score,
                'feedback_count': h.feedback_count,
            } for h in history]
    except SQLAlchemyError as e:
        logger.error(f"모델 성능 히스토리 조회 오류: {e}", exc_info=True)
        return []


# ============================================================
# 통계 및 분석 함수
# ============================================================

def get_model_accuracy(model_name: str, days: int = 30) -> Optional[float]:
    """모델 정확도 계산"""
    try:
        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=days)

        with get_session() as session:
            feedbacks = session.query(FeedbackData).filter(
                FeedbackData.model_name == model_name,
                FeedbackData.prediction_date >= cutoff_date,
                FeedbackData.is_processed == 1
            ).all()

            if not feedbacks:
                return None

            correct = sum(1 for f in feedbacks if f.predicted_class == f.actual_class)
            return correct / len(feedbacks)
    except SQLAlchemyError as e:
        logger.error(f"정확도 계산 오류: {e}", exc_info=True)
        return None


def get_feedback_stats(days: int = 30) -> Dict[str, Any]:
    """피드백 통계"""
    try:
        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=days)

        with get_session() as session:
            total = session.query(FeedbackData).filter(
                FeedbackData.prediction_date >= cutoff_date
            ).count()

            processed = session.query(FeedbackData).filter(
                FeedbackData.prediction_date >= cutoff_date,
                FeedbackData.is_processed == 1
            ).count()

            correct = session.query(FeedbackData).filter(
                FeedbackData.prediction_date >= cutoff_date,
                FeedbackData.is_processed == 1,
                FeedbackData.predicted_class == FeedbackData.actual_class
            ).count()

            return {
                'total_predictions': total,
                'processed': processed,
                'correct': correct,
                'accuracy': correct / processed if processed > 0 else 0,
                'pending': total - processed,
            }
    except SQLAlchemyError as e:
        logger.error(f"피드백 통계 오류: {e}", exc_info=True)
        return {}
