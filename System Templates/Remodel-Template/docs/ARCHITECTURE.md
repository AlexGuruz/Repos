# Architecture Overview

This document describes the high-level architecture and design patterns used in this template.

## Design Principles

1. **Generic and Reusable** - No domain-specific logic or identifiers
2. **Configuration-Driven** - Behavior controlled via environment variables and config files
3. **Multi-Schema Support** - Flexible database architecture (single-schema or multi-schema)
4. **Testable** - Clear separation of concerns for easy testing

## Core Components

### Configuration Management (`src/yourapp/config/`)

#### Connection Manager
- Unified interface for database connections
- Supports both single-schema (per-entity DBs) and multi-schema (single DB, per-entity schemas) modes
- Automatic schema routing based on entity ID
- Connection pooling support

#### Schema Resolver
- Maps entity IDs to schema names
- Supports shadow schemas for validation/testing
- Backward compatible with single-schema mode

#### SQL Preprocessor
- Runtime SQL preprocessing for multi-schema mode
- Replaces schema references (e.g., `app.` -> `app_entity1.`)
- Manages PostgreSQL search paths

#### Feature Flags
- Environment variable-based feature flags
- Sensible defaults
- Type-safe helpers (bool, int, str, float, csv)

### Common Utilities (`src/yourapp/common/`)

#### Normalization
- Text normalization utilities
- Deterministic string processing
- Useful for data matching and deduplication

#### Telemetry
- Event emission system
- Multiple sinks: stdout, HTTP webhook, or disabled
- Structured JSON output
- Non-blocking (never breaks business logic)

## Database Architecture

### Single-Schema Mode (Default)

Each entity has its own database:

```
app_entity1 (database)
  └── app (schema)
      └── tables...

app_entity2 (database)
  └── app (schema)
      └── tables...
```

**Configuration:**
- Use `dsn_map.json` with per-entity DSNs
- Or set individual `DATABASE_URL_*` environment variables

### Multi-Schema Mode

Single database with per-entity schemas:

```
app_global (database)
  ├── app_entity1 (schema)
  │   └── tables...
  ├── app_entity2 (schema)
  │   └── tables...
  └── public (schema)
      └── shared tables...
```

**Configuration:**
- Set `APP_MULTI_SCHEMA=true`
- Set `APP_GLOBAL_DSN` for the single database
- Set `APP_ENTITY_SCHEMAS` mapping (entity_id:schema_name)

### Shadow Mode

For validation/testing, can use shadow schemas:

```
app_entity1 (schema)
app_entity1_shadow (schema)  # For validation
```

**Configuration:**
- Set `APP_SHADOW_MODE=true`
- Shadow schemas use `_shadow` suffix by default

## Testing Strategy

### Unit Tests
- No external dependencies
- Fast execution
- Test individual functions/classes
- Located in `tests/unit/`

### Integration Tests
- Require database connection
- Test component interactions
- Marked with `@pytest.mark.integration`
- Located in `tests/integration/` (if created)

### Test Configuration
- `tests/conftest.py` - Shared fixtures and setup
- Default test DSNs can be overridden via environment variables
- CI/CD provides PostgreSQL service automatically

## Extension Points

### Adding Workers

Create worker processes in `src/yourapp/workers/`:

```python
from yourapp.config.connection_manager import get_connection_context

def process_entity(entity_id: str):
    with get_connection_context(entity_id) as conn:
        # Your processing logic
        pass
```

### Adding Database Utilities

Add database helpers in `src/yourapp/db/`:

```python
from yourapp.config.connection_manager import get_connection_context
from yourapp.config.sql_preprocessor import preprocess_sql

def query_entity_data(entity_id: str, sql: str):
    processed_sql = preprocess_sql(sql, entity_id)
    with get_connection_context(entity_id) as conn:
        # Execute query
        pass
```

### Adding Telemetry

Use the telemetry emitter:

```python
from yourapp.common.telemetry import start_trace, emit

trace_id = start_trace("processor", "entity1")
emit("processor", trace_id, "started", {"entity_id": "entity1"})
# ... do work ...
emit("processor", trace_id, "completed", {"rows_processed": 100})
```

## Configuration Patterns

### Environment Variables

Use the `flags.py` helpers:

```python
from yourapp.config.flags import multi_schema_enabled, max_retry_attempts

if multi_schema_enabled():
    # Multi-schema logic
    pass

retries = max_retry_attempts()
```

### Config Files

Load JSON configs:

```python
import json

with open("config/example.companies.json") as f:
    config = json.load(f)
    entities = config["entities"]
```

## Best Practices

1. **Always use connection context managers** - Ensures proper cleanup
2. **Use SQL preprocessor in multi-schema mode** - Ensures correct schema routing
3. **Emit telemetry for important operations** - Helps with debugging and monitoring
4. **Write tests for new code** - Maintains code quality
5. **Keep configuration external** - Makes deployment easier

## Migration Path

When extending this template:

1. **Rename `yourapp`** to your actual package name
2. **Add your domain logic** in appropriate modules
3. **Configure your database schema** (DDL files if needed)
4. **Add your specific integrations** (APIs, message queues, etc.)
5. **Customize CI/CD** as needed for your deployment

## See Also

- `README.md` - Quick start guide
- `tests/` - Example test patterns
- `.env.example` - Configuration reference
