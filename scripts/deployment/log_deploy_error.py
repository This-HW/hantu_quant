#!/usr/bin/env python3
"""
배포 실패 로그를 DB에 저장하는 스크립트

사용법:
    python log_deploy_error.py --service scheduler --message "서비스 시작 실패" --log "journalctl 내용..."
"""

import argparse
import sys
import os
from datetime import datetime

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def log_deploy_error(
    service: str,
    message: str,
    log_content: str = None,
    error_type: str = "DeploymentError",
    context: dict = None
) -> bool:
    """
    배포 실패 로그를 DB에 저장

    Args:
        service: 서비스 이름 (scheduler, api-server, deploy 등)
        message: 에러 메시지
        log_content: journalctl 등의 로그 내용
        error_type: 에러 유형
        context: 추가 컨텍스트 (dict)

    Returns:
        저장 성공 여부
    """
    try:
        from core.database.session import DatabaseSession
        from core.database.models import ErrorLog
        import json

        # 컨텍스트 구성
        ctx = context or {}
        ctx['deploy_time'] = datetime.now().isoformat()
        ctx['hostname'] = os.uname().nodename if hasattr(os, 'uname') else 'unknown'

        # DB 세션
        db = DatabaseSession()
        with db.get_session() as session:
            error_log = ErrorLog(
                timestamp=datetime.now(),
                level='ERROR',
                service=f"deploy-{service}",
                module='deployment',
                function='deploy_to_server',
                message=message,
                error_type=error_type,
                stack_trace=log_content,
                context=json.dumps(ctx, ensure_ascii=False) if ctx else None,
            )
            session.add(error_log)
            session.commit()
            print(f"[OK] 배포 에러 로그 저장 완료 (ID: {error_log.id})")
            return True

    except Exception as e:
        print(f"[WARN] DB 저장 실패: {e}", file=sys.stderr)
        # DB 저장 실패해도 배포 프로세스는 계속 진행
        return False


def send_telegram_alert(service: str, message: str, log_content: str = None) -> bool:
    """
    배포 실패 알림을 텔레그램으로 전송

    Args:
        service: 서비스 이름
        message: 에러 메시지
        log_content: 로그 내용 (축약해서 전송)

    Returns:
        전송 성공 여부
    """
    try:
        from core.utils.telegram_notifier import get_telegram_notifier

        notifier = get_telegram_notifier()
        if not notifier.is_enabled():
            print("[INFO] 텔레그램 알림 비활성화됨")
            return False

        # 로그 축약 (마지막 10줄)
        log_summary = ""
        if log_content:
            lines = log_content.strip().split('\n')
            log_summary = '\n'.join(lines[-10:])[:500]

        alert_message = f"""🚨 *배포 실패 알림*

*서비스*: `{service}`
*시간*: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
*메시지*: {message}

{f'```{log_summary}```' if log_summary else ''}

⚠️ 서버 확인이 필요합니다."""

        success = notifier.send_message(alert_message, "critical")
        if success:
            print("[OK] 텔레그램 알림 전송 완료")
        return success

    except Exception as e:
        print(f"[WARN] 텔레그램 전송 실패: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="배포 실패 로그를 DB에 저장")
    parser.add_argument("--service", required=True, help="서비스 이름 (scheduler, api-server 등)")
    parser.add_argument("--message", required=True, help="에러 메시지")
    parser.add_argument("--log", help="로그 내용 (journalctl 출력 등)")
    parser.add_argument("--error-type", default="DeploymentError", help="에러 유형")
    parser.add_argument("--telegram", action="store_true", help="텔레그램 알림도 전송")
    parser.add_argument("--commit", help="배포된 커밋 SHA")
    parser.add_argument("--branch", help="배포 브랜치")

    args = parser.parse_args()

    # 컨텍스트 구성
    context = {}
    if args.commit:
        context['commit'] = args.commit
    if args.branch:
        context['branch'] = args.branch

    # DB에 저장
    log_deploy_error(
        service=args.service,
        message=args.message,
        log_content=args.log,
        error_type=args.error_type,
        context=context if context else None
    )

    # 텔레그램 알림 (옵션)
    if args.telegram:
        send_telegram_alert(
            service=args.service,
            message=args.message,
            log_content=args.log
        )


if __name__ == "__main__":
    main()
