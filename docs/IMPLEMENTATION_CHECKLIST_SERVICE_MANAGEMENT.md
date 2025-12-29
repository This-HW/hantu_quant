# Implementation Phase Checklist
## Service Entry Point Consolidation

**Reference Document**: `TECHNICAL_REVIEW_SERVICE_MANAGEMENT.md`
**Created**: 2025-12-29

---

## Feature 1: Unified Service Management System

### Story 1.1: Unified CLI Entry Point

#### Task 1.1.1: Create `hantu` CLI command structure
- [ ] **Implementation**
  - [ ] Create `cli/` directory structure
  - [ ] Implement `cli/main.py` with Click/Typer
  - [ ] Define command group hierarchy
  - [ ] Add `--version` and `--help` flags
- [ ] **Testing**
  - [ ] Unit tests for CLI parsing
  - [ ] Feature test: `hantu --help` returns valid output
  - [ ] Feature test: `hantu --version` returns correct version
- [ ] **Security Review**: N/A
- [ ] **Performance Check**: Startup time < 1s for CLI help

#### Task 1.1.2: Implement service subcommands
- [ ] **Implementation**
  - [ ] `hantu start [service]` command
  - [ ] `hantu stop [service]` command
  - [ ] `hantu status` command
  - [ ] Service name validation
  - [ ] Error handling for invalid services
- [ ] **Testing**
  - [ ] Unit tests for each subcommand
  - [ ] Integration test: start → status → stop flow
  - [ ] Integration test: invalid service name handling
- [ ] **Security Review**: N/A
- [ ] **Performance Check**: Service start time < 5s

#### Task 1.1.3: Migrate existing commands
- [ ] **Implementation**
  - [ ] `hantu trade` → `main.py` commands
  - [ ] `hantu screen` → `phase1_watchlist.py` commands
  - [ ] `hantu select` → `phase2_daily_selection.py` commands
  - [ ] Backward compatibility wrappers (optional)
- [ ] **Testing**
  - [ ] Integration test: `hantu trade balance` matches `python main.py balance`
  - [ ] Integration test: `hantu screen` matches `python workflows/phase1_watchlist.py screen`
  - [ ] Integration test: `hantu select` matches `python workflows/phase2_daily_selection.py update`
- [ ] **Security Review**: N/A
- [ ] **Performance Check**: Same performance as original commands

---

### Story 1.2: Process Manager

#### Task 1.2.1: Design process registry
- [ ] **Implementation**
  - [ ] Create `core/process/registry.py`
  - [ ] Define `ProcessRegistry` class
  - [ ] Implement PID file management
  - [ ] Implement status tracking
  - [ ] Create `~/.hantu/run/` directory management
- [ ] **Testing**
  - [ ] Unit tests for ProcessRegistry methods
  - [ ] Story test: register → get_status → unregister flow
  - [ ] Story test: multiple service registration
  - [ ] Story test: orphan PID detection
- [ ] **Security Review**
  - [ ] PID file permissions (0600)
  - [ ] Directory permissions (0700)
  - [ ] No sensitive data in PID files
- [ ] **Performance Check**: N/A

#### Task 1.2.2: Implement graceful shutdown
- [ ] **Implementation**
  - [ ] Add SIGTERM handler to scheduler
  - [ ] Add SIGINT handler to scheduler
  - [ ] Add SIGTERM handler to API server
  - [ ] Implement cleanup routines
  - [ ] Add timeout for graceful shutdown (30s default)
- [ ] **Testing**
  - [ ] Integration test: SIGTERM triggers graceful shutdown
  - [ ] Integration test: SIGINT triggers graceful shutdown
  - [ ] Integration test: Cleanup completes within timeout
  - [ ] Integration test: PID file removed on shutdown
- [ ] **Security Review**: N/A
- [ ] **Performance Check**: Shutdown completes < 30s

#### Task 1.2.3: Health check integration
- [ ] **Implementation**
  - [ ] Define `HealthCheckable` interface
  - [ ] Implement health check for scheduler
  - [ ] Implement health check for API server
  - [ ] Add `hantu health` command
  - [ ] Add `/health` endpoint to API (if not exists)
- [ ] **Testing**
  - [ ] Integration test: `hantu health` returns valid JSON
  - [ ] Integration test: Health status reflects actual service state
  - [ ] Integration test: Unhealthy service detection
- [ ] **Security Review**: N/A
- [ ] **Performance Check**: Health check < 1s

---

### Story 1.3: Configuration Consolidation

#### Task 1.3.1: Create unified config loader
- [ ] **Implementation**
  - [ ] Create `core/config/loader.py`
  - [ ] Implement `ConfigLoader` class
  - [ ] Load order: .env → yaml → json → env override
  - [ ] Credential masking in `__repr__`
  - [ ] Singleton pattern for config instance
- [ ] **Testing**
  - [ ] Unit tests for load order
  - [ ] Story test: Missing config file handling
  - [ ] Story test: Environment variable override
  - [ ] Story test: Credential masking in logs
- [ ] **Security Review**
  - [ ] Credentials not exposed in logs
  - [ ] Credentials not exposed in error messages
  - [ ] Config file permissions checked
- [ ] **Performance Check**: Config load < 100ms

#### Task 1.3.2: Implement config validation
- [ ] **Implementation**
  - [ ] Create JSON Schema for each config type
  - [ ] Implement schema validation in loader
  - [ ] Add `hantu config check` command
  - [ ] Meaningful error messages for validation failures
- [ ] **Testing**
  - [ ] Story test: Valid config passes validation
  - [ ] Story test: Invalid config fails with clear message
  - [ ] Story test: Missing required field detection
  - [ ] Story test: Type mismatch detection
- [ ] **Security Review**
  - [ ] Schema defines required security fields
  - [ ] Validation runs before credential usage
- [ ] **Performance Check**: Validation < 50ms

---

## Feature 2: Logging Consolidation

### Story 2.1: Centralized Logging

#### Task 2.1.1: Implement centralized log manager
- [ ] **Implementation**
  - [ ] Create `core/logging/manager.py`
  - [ ] Single log configuration entry point
  - [ ] Support multiple handlers (file, console, rotating)
  - [ ] Context-aware logger factory
  - [ ] Remove duplicate logging setup from entry points
- [ ] **Testing**
  - [ ] Story test: All services use same log config
  - [ ] Story test: Log rotation works correctly
  - [ ] Story test: Sensitive data filtering
- [ ] **Security Review**: N/A
- [ ] **Performance Check**: Logging overhead < 1ms per log call

#### Task 2.1.2: Add structured logging format
- [ ] **Implementation**
  - [ ] JSON log formatter
  - [ ] Standard fields: timestamp, level, service, message
  - [ ] Optional fields: trace_id, user_id, stock_code
  - [ ] Human-readable console output option
- [ ] **Testing**
  - [ ] Story test: JSON output is valid JSON
  - [ ] Story test: All required fields present
  - [ ] Story test: Console output is readable
- [ ] **Security Review**: N/A
- [ ] **Performance Check**: N/A

---

## Integration Checklist

### Cross-Feature Integration
- [ ] CLI commands use ProcessRegistry
- [ ] CLI commands use ConfigLoader
- [ ] CLI commands use centralized logging
- [ ] ProcessRegistry uses centralized logging
- [ ] ConfigLoader uses centralized logging

### End-to-End Test Scenarios
- [ ] **Scenario 1**: Full system startup
  ```bash
  hantu config check && hantu start all && hantu status
  ```
  - Expected: All services running, status shows healthy

- [ ] **Scenario 2**: Service failure recovery
  - Kill API server process
  - `hantu status` shows unhealthy
  - `hantu start api` restarts successfully

- [ ] **Scenario 3**: Graceful shutdown
  ```bash
  hantu stop all
  ```
  - Expected: All PID files removed, no orphan processes

---

## Security Checklist

- [ ] No credentials in logs (grep test)
- [ ] PID files have correct permissions
- [ ] Config files have correct permissions
- [ ] No hardcoded secrets in code
- [ ] API key validation in API server maintained
- [ ] CORS settings unchanged

---

## Performance Checklist

- [ ] CLI help command < 1s
- [ ] Service start < 5s
- [ ] Config load < 100ms
- [ ] Health check < 1s
- [ ] Graceful shutdown < 30s
- [ ] No memory leak in long-running services (4h test)

---

## Cleanup Checklist

### Temporary Code/Files
- [ ] Remove any TODO comments added during implementation
- [ ] Remove debug print statements
- [ ] Remove temporary test files

### Code Quality
- [ ] All new code passes `black` formatting
- [ ] All new code passes `pylint` (score > 8.0)
- [ ] No unused imports
- [ ] Docstrings for all public functions/classes

---

## Documentation Checklist

- [ ] Update `CLAUDE.md` with new CLI commands
- [ ] Update `docs/USER_GUIDE.md` with new startup instructions
- [ ] Update `README.md` if needed
- [ ] Add `docs/CLI_REFERENCE.md` with full command documentation
- [ ] Update `docs/AUTO_TRADING_GUIDE.md` if affected

---

## Git & PR Checklist

- [ ] All changes committed with clear messages
- [ ] Branch rebased on latest main (if needed)
- [ ] CI/CD tests pass
- [ ] No merge conflicts
- [ ] PR description includes:
  - [ ] Summary of changes
  - [ ] Test plan
  - [ ] Breaking changes (if any)
- [ ] Code review requested
- [ ] All review comments addressed

---

## Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | | | Pending |
| Code Reviewer | | | Pending |
| Security Review | | | Pending |
| Final Approval | | | Pending |

---

**Completion Criteria**:
All checkboxes in this document must be checked before the Implementation Phase is considered complete.

**Note**: This checklist will be updated as implementation progresses. New tasks discovered during implementation should be added to the Technical Review document first, then reflected here.
