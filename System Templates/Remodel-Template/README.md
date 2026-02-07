# Remodel Template

A clean, reusable Python project scaffold for building data processing pipelines and microservices.

## What This Is

This template provides:

- **Generic infrastructure** for Python projects with PostgreSQL
- **Configuration management** utilities (single-schema and multi-schema support)
- **Database connection management** with automatic schema routing
- **Telemetry/observability** helpers (stdout, HTTP webhook)
- **Test infrastructure** with pytest
- **Docker Compose** setup for PostgreSQL (and optional Kafka/Redpanda)
- **CI/CD workflow** for GitHub Actions

## What This Is Not

- **Not a complete application** - it's a starting point
- **Not Kylo-specific** - all Kylo/company identifiers have been removed
- **Not production-ready** - you'll need to add your business logic
- **Not a framework** - it's a collection of utilities and patterns

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Database

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your database settings
```

### 3. Start PostgreSQL (Docker)

```bash
cd docker
docker-compose up -d
```

### 4. Run Tests

```bash
# Unit tests (no database required)
pytest -m "not integration" -q

# Integration tests (requires database)
pytest -m "integration" -q
```

## Project Structure

```
.
├── src/yourapp/          # Your application code
│   ├── config/          # Configuration management
│   ├── common/           # Common utilities
│   ├── db/               # Database utilities (optional)
│   └── workers/          # Worker processes (optional)
├── tests/                # Test suite
├── config/               # Configuration files
│   ├── example.companies.json
│   └── example.dsn_map.json
├── docker/               # Docker Compose files
├── scripts/              # Utility scripts
├── docs/                 # Documentation
└── requirements.txt      # Python dependencies
```

## Configuration

### Single-Schema Mode (Default)

Use per-entity database connections via DSN map:

```json
// config/example.dsn_map.json
{
  "entity1": "postgresql://postgres:postgres@localhost:5432/app_entity1",
  "entity2": "postgresql://postgres:postgres@localhost:5432/app_entity2"
}
```

### Multi-Schema Mode

Use a single database with per-entity schemas:

```bash
APP_MULTI_SCHEMA=true
APP_GLOBAL_DSN=postgresql://postgres:postgres@localhost:5432/app_global
APP_ENTITY_SCHEMAS=entity1:app_entity1,entity2:app_entity2
```

See `.env.example` for all configuration options.

## Development

### Running Tests

```bash
# All tests
pytest -q

# Unit tests only
pytest -m "not integration" -q

# Integration tests only
pytest -m "integration" -q
```

### Adding Your Code

1. Replace `yourapp` with your actual package name
2. Add your business logic in `src/yourapp/`
3. Add tests in `tests/`
4. Update configuration files as needed

## Docker Services

### PostgreSQL

```bash
cd docker
docker-compose up -d pg
```

### Kafka/Redpanda (Optional)

```bash
cd docker
docker-compose -f docker-compose.yml -f docker-compose.kafka.yml up -d
```

## CI/CD

GitHub Actions workflow runs tests on push/PR:

- Sets up Python 3.12
- Starts PostgreSQL service
- Runs unit and integration tests

See `.github/workflows/ci.yml` for details.

## License

This is a template - customize as needed for your project.

## Next Steps

1. Rename `yourapp` to your actual package name
2. Add your business logic
3. Configure your database schema
4. Add your specific integrations
5. Customize CI/CD as needed

See `docs/ARCHITECTURE.md` for more details on the design patterns used.
