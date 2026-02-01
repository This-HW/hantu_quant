"""
Monitor command - Real-time trading monitoring.

Usage:
    hantu monitor [TARGET] [OPTIONS]
"""

import os
import sys
import time
import click
from datetime import datetime
from typing import Dict, Any, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.command()
@click.argument('target', type=click.Choice(['all', 'positions', 'circuit', 'trades']), default='all', required=False)
@click.option('--live', is_flag=True, help='실시간 모니터링 (5초 간격)')
@click.option('--interval', default=5, type=int, help='새로고침 간격 (초)')
@click.option('--json', 'as_json', is_flag=True, help='JSON 출력')
@click.pass_context
def monitor(ctx: click.Context, target: str, live: bool, interval: int, as_json: bool) -> None:
    """실시간 매매 모니터링.

    \b
    Examples:
        hantu monitor             현재 상황 1회 출력
        hantu monitor --live      실시간 모니터링 (5초 간격)
        hantu monitor --json      JSON 출력
        hantu monitor positions   포지션만 출력
        hantu monitor circuit     서킷브레이커 상태만
        hantu monitor trades      오늘 거래 내역만
    """
    try:
        if as_json:
            # JSON 모드는 1회만 출력
            data = _collect_monitor_data(target)
            import json
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))
            return

        # 일반 출력 모드
        if live:
            _monitor_live(target, interval)
        else:
            _monitor_once(target)

    except KeyboardInterrupt:
        click.echo("\n\n모니터링을 종료합니다.")
        sys.exit(0)
    except Exception as e:
        click.echo(f"모니터링 실패: {e}", err=True)
        if ctx.obj and ctx.obj.get('debug'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _monitor_live(target: str, interval: int) -> None:
    """실시간 모니터링 (지속적 새로고침)"""
    click.echo("실시간 모니터링 시작 (Ctrl+C로 종료)")
    click.echo(f"새로고침 간격: {interval}초\n")

    try:
        while True:
            # 터미널 클리어 (크로스 플랫폼)
            if os.name == 'nt':
                os.system('cls')
            else:
                os.system('clear')

            _monitor_once(target)

            # 대기
            time.sleep(interval)

    except KeyboardInterrupt:
        raise


def _monitor_once(target: str) -> None:
    """1회 모니터링 출력"""
    data = _collect_monitor_data(target)

    # 헤더
    _print_header()

    # 타겟별 출력
    if target in ['all', 'positions']:
        _print_positions(data['positions'])

    if target in ['all', 'circuit']:
        _print_circuit_breaker(data['circuit_breaker'])

    if target in ['all', 'trades']:
        _print_daily_trades(data['daily_trades'])

    # 푸터
    _print_footer()


def _collect_monitor_data(target: str) -> Dict[str, Any]:
    """모니터링 데이터 수집"""
    data = {
        'timestamp': datetime.now().isoformat(),
        'positions': [],
        'circuit_breaker': {},
        'daily_trades': {},
    }

    # 포지션 정보
    if target in ['all', 'positions']:
        data['positions'] = _get_positions()

    # 서킷브레이커 상태
    if target in ['all', 'circuit']:
        data['circuit_breaker'] = _get_circuit_breaker_status()

    # 오늘 거래 통계
    if target in ['all', 'trades']:
        data['daily_trades'] = _get_daily_trades()

    return data


def _get_positions() -> List[Dict[str, Any]]:
    """현재 포지션 조회"""
    try:
        from core.api.kis_api import KISAPI

        api = KISAPI()
        balance = api.get_balance()

        if not balance or not balance.get('positions'):
            return []

        positions = []
        for code, pos in balance['positions'].items():
            if pos.get('quantity', 0) > 0:
                avg_price = pos.get('avg_price', 0)
                current_price = pos.get('current_price', 0)
                quantity = pos.get('quantity', 0)
                pnl = (current_price - avg_price) * quantity
                pnl_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0.0

                positions.append({
                    'stock_code': code,
                    'stock_name': pos.get('stock_name', code),
                    'quantity': quantity,
                    'avg_price': avg_price,
                    'current_price': current_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                })

        return positions

    except Exception as e:
        from core.utils.log_utils import get_logger
        logger = get_logger(__name__)
        logger.error(f"포지션 조회 실패: {e}", exc_info=True)
        return []


def _get_circuit_breaker_status() -> Dict[str, Any]:
    """서킷브레이커 상태 조회"""
    try:
        from core.risk.drawdown.circuit_breaker import CircuitBreaker
        from core.risk.drawdown.drawdown_monitor import DrawdownMonitor

        monitor = DrawdownMonitor()
        breaker = CircuitBreaker()

        # 현재 드로다운 상태 계산
        drawdown_status = monitor.calculate_current_drawdown()

        # 서킷브레이커 체크
        breaker_status = breaker.check(drawdown_status)

        return {
            'state': breaker_status.state.value,
            'trigger_reason': breaker_status.trigger_reason,
            'can_trade': breaker_status.can_trade,
            'current_stage': breaker_status.current_stage,
            'position_reduction': breaker_status.position_reduction,
            'daily_drawdown': drawdown_status.daily_drawdown,
            'weekly_drawdown': drawdown_status.weekly_drawdown,
            'current_drawdown': drawdown_status.current_drawdown,
            'alert_level': drawdown_status.alert_level.value,
        }

    except Exception as e:
        from core.utils.log_utils import get_logger
        logger = get_logger(__name__)
        logger.error(f"서킷브레이커 상태 조회 실패: {e}", exc_info=True)
        return {
            'state': 'unknown',
            'trigger_reason': '',
            'can_trade': True,
            'current_stage': 0,
            'position_reduction': 0.0,
            'daily_drawdown': 0.0,
            'weekly_drawdown': 0.0,
            'current_drawdown': 0.0,
            'alert_level': 'normal',
        }


def _get_daily_trades() -> Dict[str, Any]:
    """오늘 거래 통계 조회"""
    try:
        from core.trading.trade_journal import TradeJournal

        journal = TradeJournal()
        summary = journal.compute_daily_summary()

        return {
            'total_trades': summary.get('total_trades', 0),
            'buy_count': _count_side_trades(summary.get('details', []), 'buy'),
            'sell_count': _count_side_trades(summary.get('details', []), 'sell'),
            'realized_pnl': summary.get('realized_pnl', 0),
            'win_rate': summary.get('win_rate', 0),
            'wins': int(summary.get('total_trades', 0) * summary.get('win_rate', 0)),
            'losses': int(summary.get('total_trades', 0) * (1 - summary.get('win_rate', 0))),
        }

    except Exception as e:
        from core.utils.log_utils import get_logger
        logger = get_logger(__name__)
        logger.error(f"거래 통계 조회 실패: {e}", exc_info=True)
        return {
            'total_trades': 0,
            'buy_count': 0,
            'sell_count': 0,
            'realized_pnl': 0,
            'win_rate': 0.0,
            'wins': 0,
            'losses': 0,
        }


def _count_side_trades(details: List[Dict], side: str) -> int:
    """특정 side 거래 횟수 계산"""
    # details는 매수-매도 짝이므로, sell_count = len(details)
    # buy_count = len(details) (각 거래는 buy + sell 쌍)
    # 여기서는 단순히 total_trades로 반환
    return len(details)


def _print_header() -> None:
    """헤더 출력"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    click.echo("=" * 80)
    click.echo(f"{'Hantu Quant Monitor':^80}")
    click.echo(f"{now:^80}")
    click.echo("=" * 80)
    click.echo()


def _print_footer() -> None:
    """푸터 출력"""
    click.echo("=" * 80)


def _print_positions(positions: List[Dict[str, Any]]) -> None:
    """포지션 현황 출력"""
    click.echo("[포지션 현황]")

    if not positions:
        click.echo("  보유 종목이 없습니다.")
        click.echo()
        return

    # 테이블 헤더
    click.echo(f"{'종목코드':<10} {'종목명':<12} {'수량':>8} {'평균단가':>12} {'현재가':>12} {'손익':>15}")
    click.echo("-" * 80)

    # 포지션 출력
    total_pnl = 0.0
    for pos in positions:
        code = pos['stock_code']
        name = _truncate_name(pos['stock_name'], 10)
        qty = pos['quantity']
        avg_price = pos['avg_price']
        current_price = pos['current_price']
        pnl = pos['pnl']
        pnl_pct = pos['pnl_pct']

        total_pnl += pnl

        # 손익 색상
        if pnl > 0:
            pnl_str = click.style(f"+{pnl:,.0f}원 ({pnl_pct:+.2f}%)", fg='green')
        elif pnl < 0:
            pnl_str = click.style(f"{pnl:,.0f}원 ({pnl_pct:+.2f}%)", fg='red')
        else:
            pnl_str = f"{pnl:,.0f}원 (0.00%)"

        click.echo(
            f"{code:<10} {name:<12} {qty:>8,} {avg_price:>12,} {current_price:>12,} {pnl_str}"
        )

    # 총계
    click.echo("-" * 80)
    total_pnl_str = click.style(f"+{total_pnl:,.0f}원", fg='green') if total_pnl > 0 else click.style(f"{total_pnl:,.0f}원", fg='red') if total_pnl < 0 else f"{total_pnl:,.0f}원"
    click.echo(f"{'총 평가손익:':<60} {total_pnl_str}")
    click.echo()


def _print_circuit_breaker(cb_status: Dict[str, Any]) -> None:
    """서킷브레이커 상태 출력"""
    click.echo("[서킷 브레이커]")

    state = cb_status.get('state', 'unknown')
    can_trade = cb_status.get('can_trade', True)
    stage = cb_status.get('current_stage', 0)
    reduction = cb_status.get('position_reduction', 0.0)
    reason = cb_status.get('trigger_reason', '')

    # 상태 표시
    if state == 'active':
        state_icon = click.style("●", fg='green')
        state_text = "ACTIVE (정상 거래)"
    elif state == 'triggered':
        state_icon = click.style("●", fg='yellow')
        state_text = f"TRIGGERED (Stage {stage})"
    elif state == 'cooldown':
        state_icon = click.style("●", fg='red')
        state_text = f"COOLDOWN (Stage {stage})"
    else:
        state_icon = click.style("○", fg='white')
        state_text = "UNKNOWN"

    click.echo(f"  {state_icon} 상태: {state_text}")

    if reason:
        click.echo(f"  발동 사유: {reason}")

    if stage > 0:
        click.echo(f"  포지션 축소: {reduction * 100:.0f}%")

    # 드로다운 정보
    daily_dd = cb_status.get('daily_drawdown', 0.0)
    weekly_dd = cb_status.get('weekly_drawdown', 0.0)
    current_dd = cb_status.get('current_drawdown', 0.0)

    click.echo(f"  일간 손실: {daily_dd:.2%}")
    click.echo(f"  주간 손실: {weekly_dd:.2%}")
    click.echo(f"  현재 낙폭: {current_dd:.2%}")

    # 거래 가능 여부
    if can_trade:
        click.echo(f"  거래 가능: {click.style('예', fg='green')}")
    else:
        click.echo(f"  거래 가능: {click.style('아니오 (거래 중단)', fg='red')}")

    click.echo()


def _print_daily_trades(trades: Dict[str, Any]) -> None:
    """오늘 거래 통계 출력"""
    click.echo("[오늘 거래]")

    total = trades.get('total_trades', 0)
    buy_count = trades.get('buy_count', 0)
    sell_count = trades.get('sell_count', 0)
    pnl = trades.get('realized_pnl', 0)
    win_rate = trades.get('win_rate', 0.0)
    wins = trades.get('wins', 0)
    losses = trades.get('losses', 0)

    # 손익 색상
    if pnl > 0:
        pnl_str = click.style(f"+{pnl:,.0f}원", fg='green')
        pnl_pct_str = click.style(f"(수익)", fg='green')
    elif pnl < 0:
        pnl_str = click.style(f"{pnl:,.0f}원", fg='red')
        pnl_pct_str = click.style(f"(손실)", fg='red')
    else:
        pnl_str = f"{pnl:,.0f}원"
        pnl_pct_str = "(무변동)"

    click.echo(f"  총 거래: {total}건 (승: {wins}건, 패: {losses}건)")
    click.echo(f"  실현 손익: {pnl_str} {pnl_pct_str}")
    click.echo(f"  승률: {win_rate * 100:.1f}%")
    click.echo()


def _truncate_name(name: str, max_len: int) -> str:
    """종목명 길이 제한 (한글 고려)"""
    if not name:
        return ""

    # 한글은 2바이트, 영문은 1바이트로 계산
    byte_len = 0
    truncated = []
    for char in name:
        char_len = 2 if ord(char) > 127 else 1
        if byte_len + char_len > max_len:
            break
        truncated.append(char)
        byte_len += char_len

    result = ''.join(truncated)
    if len(result) < len(name):
        result = result[:-1] + "…"

    return result
