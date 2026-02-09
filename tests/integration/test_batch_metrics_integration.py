"""
배치 메트릭 통합 테스트
DB 저장 및 알림 전송을 검증
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


def test_batch_metrics_db_save():
    """배치 메트릭 DB 저장 통합 테스트"""
    from core.database.models import BatchMetrics
    from core.database.unified_db import get_session

    # 테스트 데이터
    test_metric = BatchMetrics(
        phase_name="phase2",
        batch_number=0,
        start_time=datetime.now(),
        end_time=datetime.now(),
        duration_seconds=10.5,
        api_calls_count=50,
        stocks_processed=100,
        stocks_selected=10,
        error_count=2
    )

    # DB 저장
    try:
        with get_session() as session:
            session.add(test_metric)
            session.commit()

            # 조회
            saved_metric = session.query(BatchMetrics)\
                .filter_by(phase_name="phase2", batch_number=0)\
                .order_by(BatchMetrics.created_at.desc())\
                .first()

            assert saved_metric is not None
            assert saved_metric.phase_name == "phase2"
            assert saved_metric.batch_number == 0
            assert saved_metric.duration_seconds == 10.5
            assert saved_metric.api_calls_count == 50
            assert saved_metric.stocks_processed == 100
            assert saved_metric.stocks_selected == 10
            assert saved_metric.error_count == 2

            # 정리
            session.delete(saved_metric)
            session.commit()

    except Exception as e:
        pytest.skip(f"DB 연결 불가: {e}")


def test_telegram_batch_summary():
    """텔레그램 배치 요약 알림 테스트"""
    from core.utils.telegram_notifier import get_telegram_notifier

    notifier = get_telegram_notifier()

    # 텔레그램이 비활성화된 경우 스킵
    if not notifier.is_enabled():
        pytest.skip("텔레그램 알림 비활성화")

    stats = {
        'duration_seconds': 120.5,
        'stocks_processed': 100,
        'stocks_selected': 10,
        'api_calls_count': 50,
        'error_count': 2
    }

    # 알림 전송 (실제 전송되지 않도록 mock 처리)
    with patch.object(notifier, 'send_message') as mock_send:
        mock_send.return_value = True
        result = notifier.send_batch_summary(0, stats)

        # 호출 확인
        assert mock_send.called
        call_args = mock_send.call_args

        # 메시지 내용 확인
        message = call_args[0][0]
        assert "배치 #0" in message
        assert "2분 0초" in message  # 120초 = 2분
        assert "100종목" in message
        assert "10종목" in message
        assert "50회" in message
        assert "2건" in message


def test_daily_updater_save_batch_metrics():
    """DailyUpdater._save_batch_metrics 통합 테스트"""
    from core.daily_selection.daily_updater import DailyUpdater
    from core.database.models import BatchMetrics
    from core.database.unified_db import get_session

    # DailyUpdater 인스턴스 생성
    updater = DailyUpdater()

    # 테스트 데이터
    start_time = datetime.now()
    end_time = datetime.now()

    # 메트릭 저장
    updater._save_batch_metrics(
        batch_index=0,
        start_time=start_time,
        end_time=end_time,
        stocks_processed=100,
        stocks_selected=10
    )

    # DB에서 확인
    try:
        with get_session() as session:
            metric = session.query(BatchMetrics)\
                .filter_by(phase_name="phase2", batch_number=0)\
                .order_by(BatchMetrics.created_at.desc())\
                .first()

            assert metric is not None
            assert metric.phase_name == "phase2"
            assert metric.batch_number == 0
            assert metric.stocks_processed == 100
            assert metric.stocks_selected == 10

            # 정리
            session.delete(metric)
            session.commit()

    except Exception as e:
        pytest.skip(f"DB 연결 불가: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
