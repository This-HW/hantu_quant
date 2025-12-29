"""
Screen command - Stock screening (Phase 1).

Usage:
    hantu screen [OPTIONS]
"""

import os
import sys
import click

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.command()
@click.option('--parallel', '-p', type=int, default=4, help='Number of parallel workers.')
@click.option('--list', 'show_list', is_flag=True, help='Show current watchlist.')
@click.option('--add', 'add_code', type=str, help='Add stock to watchlist.')
@click.option('--remove', 'remove_code', type=str, help='Remove stock from watchlist.')
@click.pass_context
def screen(ctx: click.Context, parallel: int, show_list: bool, add_code: str, remove_code: str) -> None:
    """Run stock screening (Phase 1).

    \b
    Examples:
        hantu screen              Run screening with default settings
        hantu screen -p 8         Run with 8 parallel workers
        hantu screen --list       Show current watchlist
        hantu screen --add 005930 Add stock to watchlist
    """
    try:
        # Handle mutually exclusive options
        if show_list:
            _show_watchlist()
            return

        if add_code:
            _add_to_watchlist(add_code)
            return

        if remove_code:
            _remove_from_watchlist(remove_code)
            return

        # Run screening
        _run_screening(parallel, ctx.obj.get('debug', False))

    except Exception as e:
        click.echo(f"Screening failed: {e}", err=True)
        if ctx.obj.get('debug'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _run_screening(parallel: int, debug: bool) -> None:
    """Execute stock screening."""
    from workflows.phase1_watchlist import Phase1Workflow

    click.echo(f"Starting stock screening with {parallel} workers...")
    click.echo()

    workflow = Phase1Workflow(p_parallel_workers=parallel)
    result = workflow.run_screening()

    if result:
        click.echo()
        click.echo(f"Screening completed successfully.")
        click.echo(f"Total stocks screened: {result.get('total_screened', 0)}")
        click.echo(f"Stocks added to watchlist: {result.get('added_count', 0)}")
        click.echo(f"Processing time: {result.get('duration_seconds', 0):.1f}s")
    else:
        click.echo("Screening completed with no results.")


def _show_watchlist() -> None:
    """Display current watchlist."""
    from core.watchlist.watchlist_manager import WatchlistManager

    manager = WatchlistManager()
    stocks = manager.get_all()

    click.echo()
    if not stocks:
        click.echo("Watchlist is empty.")
        return

    click.echo(f"=== Watchlist ({len(stocks)} stocks) ===")
    click.echo(f"{'Code':<10} {'Name':<20} {'Score':>8} {'Added':<12}")
    click.echo("-" * 55)

    for stock in stocks:
        click.echo(
            f"{stock.get('code', 'N/A'):<10} "
            f"{stock.get('name', 'N/A')[:18]:<20} "
            f"{stock.get('score', 0):>8.1f} "
            f"{stock.get('added_at', 'N/A')[:10]:<12}"
        )

    click.echo()


def _add_to_watchlist(code: str) -> None:
    """Add stock to watchlist."""
    from core.watchlist.watchlist_manager import WatchlistManager

    manager = WatchlistManager()
    success = manager.add(code)

    if success:
        click.echo(f"Stock {code} added to watchlist.")
    else:
        click.echo(f"Failed to add stock {code} to watchlist.", err=True)


def _remove_from_watchlist(code: str) -> None:
    """Remove stock from watchlist."""
    from core.watchlist.watchlist_manager import WatchlistManager

    manager = WatchlistManager()
    success = manager.remove(code)

    if success:
        click.echo(f"Stock {code} removed from watchlist.")
    else:
        click.echo(f"Failed to remove stock {code} from watchlist.", err=True)
