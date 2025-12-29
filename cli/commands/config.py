"""
Config command - Configuration management.

Usage:
    hantu config [SUBCOMMAND]

Subcommands:
    check       Validate configuration
    show        Show current configuration (masked)
"""

import os
import sys
import click

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.group(invoke_without_command=True)
@click.pass_context
def config(ctx: click.Context) -> None:
    """Configuration management.

    \b
    Examples:
        hantu config check       Validate all configuration
        hantu config show        Show current configuration
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@config.command('check')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed validation results.')
@click.pass_context
def config_check(ctx: click.Context, verbose: bool) -> None:
    """Validate configuration files and environment variables."""
    try:
        from core.config.loader import ConfigLoader

        loader = ConfigLoader()
        result = loader.validate()

        click.echo()
        click.echo("=== Configuration Validation ===")
        click.echo()

        all_valid = True

        for category, status in result.items():
            is_valid = status.get('valid', False)
            icon = click.style("✓", fg='green') if is_valid else click.style("✗", fg='red')
            click.echo(f"{icon} {category}")

            if not is_valid:
                all_valid = False
                for error in status.get('errors', []):
                    click.echo(f"    - {error}")

            if verbose and status.get('warnings'):
                for warning in status['warnings']:
                    click.echo(f"    ! {click.style(warning, fg='yellow')}")

        click.echo()

        if all_valid:
            click.echo(click.style("All configuration is valid.", fg='green'))
            sys.exit(0)
        else:
            click.echo(click.style("Configuration validation failed.", fg='red'))
            sys.exit(1)

    except Exception as e:
        click.echo(f"Configuration check failed: {e}", err=True)
        if ctx.obj.get('debug'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


@config.command('show')
@click.option('--unmask', is_flag=True, help='Show unmasked values (dangerous!).')
@click.pass_context
def config_show(ctx: click.Context, unmask: bool) -> None:
    """Show current configuration (credentials masked by default)."""
    try:
        from core.config.loader import ConfigLoader

        loader = ConfigLoader()
        config_data = loader.get_display_config(mask_credentials=not unmask)

        click.echo()
        click.echo("=== Current Configuration ===")
        click.echo()

        for section, values in config_data.items():
            click.echo(f"[{section}]")
            if isinstance(values, dict):
                for key, value in values.items():
                    click.echo(f"  {key}: {value}")
            else:
                click.echo(f"  {values}")
            click.echo()

        if not unmask:
            click.echo(click.style("Note: Credentials are masked. Use --unmask to reveal.", fg='yellow'))

    except Exception as e:
        click.echo(f"Failed to load configuration: {e}", err=True)
        if ctx.obj.get('debug'):
            import traceback
            traceback.print_exc()
        sys.exit(1)
