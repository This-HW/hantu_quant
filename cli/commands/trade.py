"""
Trade command - Trading operations.

Usage:
    hantu trade [SUBCOMMAND]

Subcommands:
    start       Start auto trading
    stop        Stop auto trading
    balance     Check account balance
    positions   Show current positions
"""

import os
import sys
import click

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.group(invoke_without_command=True)
@click.pass_context
def trade(ctx: click.Context) -> None:
    """Trading operations.

    \b
    Examples:
        hantu trade balance      Check account balance
        hantu trade positions    Show current positions
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@trade.command('balance')
@click.pass_context
def trade_balance(ctx: click.Context) -> None:
    """Check account balance."""
    try:
        from core.api.kis_api import KISAPI

        api = KISAPI()
        balance = api.get_balance()

        click.echo()
        click.echo("=== Account Balance ===")
        click.echo(f"Deposit:       {balance.get('deposit', 0):>15,} KRW")
        click.echo(f"Total Value:   {balance.get('total_eval_amount', 0):>15,} KRW")
        click.echo(f"P/L:           {balance.get('total_eval_profit_loss', 0):>15,} KRW")
        click.echo(f"Net Worth:     {balance.get('net_worth', 0):>15,} KRW")
        click.echo()

    except Exception as e:
        click.echo(f"Failed to fetch balance: {e}", err=True)
        if ctx.obj.get('debug'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


@trade.command('positions')
@click.pass_context
def trade_positions(ctx: click.Context) -> None:
    """Show current positions."""
    try:
        from core.api.kis_api import KISAPI

        api = KISAPI()
        balance = api.get_balance()
        positions = balance.get('positions', {})

        click.echo()
        if not positions:
            click.echo("No positions currently held.")
            return

        click.echo("=== Current Positions ===")
        click.echo(f"{'Code':<10} {'Qty':>10} {'Avg Price':>12} {'Current':>12} {'P/L':>15}")
        click.echo("-" * 65)

        for code, pos in positions.items():
            pl = pos.get('eval_profit_loss', 0)
            pl_color = 'green' if pl >= 0 else 'red'
            click.echo(
                f"{code:<10} "
                f"{pos.get('quantity', 0):>10,} "
                f"{pos.get('avg_price', 0):>12,} "
                f"{pos.get('current_price', 0):>12,} "
                f"{click.style(f'{pl:>15,}', fg=pl_color)}"
            )

        click.echo()

    except Exception as e:
        click.echo(f"Failed to fetch positions: {e}", err=True)
        if ctx.obj.get('debug'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


@trade.command('find')
@click.option('--limit', '-n', type=int, default=10, help='Maximum number of stocks to show.')
@click.pass_context
def trade_find(ctx: click.Context, limit: int) -> None:
    """Find candidate stocks based on momentum strategy."""
    try:
        from core.api.kis_api import KISAPI
        from core.strategy.momentum import MomentumStrategy

        api = KISAPI()
        strategy = MomentumStrategy(api)
        stocks = strategy.find_candidates()

        click.echo()
        if not stocks:
            click.echo("No candidate stocks found.")
            return

        click.echo("=== Candidate Stocks ===")
        click.echo(f"{'Code':<10} {'Name':<20} {'Price':>12} {'Volume':>12} {'Score':>8}")
        click.echo("-" * 70)

        for stock in stocks[:limit]:
            click.echo(
                f"{stock['code']:<10} "
                f"{stock.get('name', 'N/A')[:18]:<20} "
                f"{stock.get('price', 0):>12,} "
                f"{stock.get('volume', 0):>12,} "
                f"{stock.get('momentum_score', 0):>8.1f}"
            )

        if len(stocks) > limit:
            click.echo(f"\n... and {len(stocks) - limit} more stocks")

        click.echo()

    except Exception as e:
        click.echo(f"Failed to find stocks: {e}", err=True)
        if ctx.obj.get('debug'):
            import traceback
            traceback.print_exc()
        sys.exit(1)
