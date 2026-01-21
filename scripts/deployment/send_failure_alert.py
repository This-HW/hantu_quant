#!/usr/bin/env python3
"""
배포 실패 알림 전송 스크립트

Usage:
    python3 send_failure_alert.py <consecutive_failures> <commit_sha> <branch> <last_success>
"""
import sys
import os

# Add project root to path
sys.path.insert(0, "/opt/hantu_quant")

from core.utils.telegram_notifier import get_telegram_notifier


def main():
    if len(sys.argv) < 5:
        print(
            "Usage: send_failure_alert.py <failures> <commit> <branch> <last_success>"
        )
        sys.exit(1)

    failures = int(sys.argv[1])
    commit_sha = sys.argv[2]
    branch = sys.argv[3]
    last_success_raw = sys.argv[4]

    # Format last success timestamp
    if last_success_raw == "null" or not last_success_raw:
        last_success = "Never"
    else:
        last_success = last_success_raw.replace("T", " ").replace("Z", " UTC")

    # Send alert
    notifier = get_telegram_notifier()
    success = notifier.send_deployment_failure_alert(
        failures,
        {
            "commit": commit_sha,
            "branch": branch,
            "last_success": last_success,
            "reason": "GitHub Actions deployment: services failed to start",
        },
    )

    if success:
        print(f"✅ Alert sent successfully for {failures} consecutive failures")
        sys.exit(0)
    else:
        print("❌ Failed to send Telegram alert")
        sys.exit(1)


if __name__ == "__main__":
    main()
