"""
Select command - Daily selection (Phase 2).

Usage:
    hantu select [OPTIONS]
"""

import os
import sys
import click

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.command()
@click.option('--parallel', '-p', type=int, default=4, help='Number of parallel workers.')
@click.option('--analyze', '-a', is_flag=True, help='Run analysis mode (detailed output).')
@click.option('--show', '-s', is_flag=True, help='Show current daily selection.')
@click.option('--criteria', '-c', is_flag=True, help='Show selection criteria.')
@click.pass_context
def select(ctx: click.Context, parallel: int, analyze: bool, show: bool, criteria: bool) -> None:
    """Run daily stock selection (Phase 2).

    \b
    Examples:
        hantu select              Run daily selection
        hantu select -p 8         Run with 8 parallel workers
        hantu select --analyze    Run with detailed analysis
        hantu select --show       Show current selections
        hantu select --criteria   Show selection criteria
    """
    try:
        if show:
            _show_selections()
            return

        if criteria:
            _show_criteria()
            return

        # Run selection
        _run_selection(parallel, analyze, ctx.obj.get('debug', False))

    except Exception as e:
        click.echo(f"Selection failed: {e}", err=True)
        if ctx.obj.get('debug'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _run_selection(parallel: int, analyze: bool, debug: bool) -> None:
    """Execute daily selection."""
    from workflows.phase2_daily_selection import Phase2CLI

    click.echo(f"Starting daily selection with {parallel} workers...")
    click.echo()

    cli = Phase2CLI(p_parallel_workers=parallel)

    if analyze:
        result = cli.run_analysis()
    else:
        result = cli.run_update()

    if result:
        click.echo()
        click.echo("Daily selection completed successfully.")
        click.echo(f"Candidates evaluated: {result.get('evaluated_count', 0)}")
        click.echo(f"Stocks selected: {result.get('selected_count', 0)}")
        click.echo(f"Processing time: {result.get('duration_seconds', 0):.1f}s")

        # Show top selections
        selections = result.get('selections', [])
        if selections:
            click.echo()
            click.echo("=== Today's Top Selections ===")
            click.echo(f"{'Code':<10} {'Name':<20} {'Score':>8} {'Signal':<10}")
            click.echo("-" * 55)

            for stock in selections[:5]:
                click.echo(
                    f"{stock.get('code', 'N/A'):<10} "
                    f"{stock.get('name', 'N/A')[:18]:<20} "
                    f"{stock.get('score', 0):>8.1f} "
                    f"{stock.get('signal', 'N/A'):<10}"
                )
    else:
        click.echo("Selection completed with no results.")


def _show_selections() -> None:
    """Display current daily selections."""
    from core.daily_selection.daily_updater import DailyUpdater

    updater = DailyUpdater()
    selections = updater.get_today_selections()

    click.echo()
    if not selections:
        click.echo("No selections for today.")
        return

    click.echo(f"=== Today's Selections ({len(selections)} stocks) ===")
    click.echo(f"{'Code':<10} {'Name':<20} {'Score':>8} {'Signal':<10} {'Reason':<20}")
    click.echo("-" * 75)

    for stock in selections:
        click.echo(
            f"{stock.get('code', 'N/A'):<10} "
            f"{stock.get('name', 'N/A')[:18]:<20} "
            f"{stock.get('score', 0):>8.1f} "
            f"{stock.get('signal', 'N/A'):<10} "
            f"{stock.get('reason', 'N/A')[:18]:<20}"
        )

    click.echo()


def _show_criteria() -> None:
    """Display selection criteria."""
    from datetime import datetime
    from core.daily_selection.selection_criteria import SelectionCriteria, MarketCondition

    criteria = SelectionCriteria(
        name="Default Criteria",
        description="기본 선정 기준",
        market_condition=MarketCondition.SIDEWAYS,
        created_date=datetime.now().strftime('%Y-%m-%d')
    )
    config = criteria.to_dict()

    click.echo()
    click.echo("=== Selection Criteria ===")
    click.echo()

    for category, settings in config.items():
        click.echo(f"[{category}]")
        if isinstance(settings, dict):
            for key, value in settings.items():
                click.echo(f"  {key}: {value}")
        else:
            click.echo(f"  {settings}")
        click.echo()
