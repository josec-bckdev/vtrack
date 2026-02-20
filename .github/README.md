# GitHub Actions CI/CD Configuration

This directory contains the automated workflows for VTrack's continuous integration and deployment pipeline.

## Workflows

### 1. Tests (`tests.yml`)

**Triggers:** Push to main/develop, Pull Requests  
**Duration:** ~3-5 minutes

**What it does:**
- Sets up Python 3.12 environment
- Spins up PostgreSQL and Redis test services
- Installs all dependencies
- Runs main application tests (27+ tests)
- Runs microservice tests (notification-sender, alert-processor)
- Generates code coverage report
- Uploads coverage to Codecov

**Services:**
- PostgreSQL 16 (test database)
- Redis 7 (message queue)

**Status:** [![Tests](https://github.com/josec-bckdev/vtrack/workflows/Tests/badge.svg)](https://github.com/josec-bckdev/vtrack/actions/workflows/tests.yml)

---

### 2. Docker Build (`docker-build.yml`)

**Triggers:** Push to main/develop, Pull Requests  
**Duration:** ~5-8 minutes

**What it does:**
- Validates docker-compose.yml syntax
- Builds all Docker images in parallel
- Tests docker-compose orchestration
- Verifies service health checks
- Tests API availability
- Validates microservice images

**Validates:**
- Main API service
- Alert Processor
- Notification Sender
- PostgreSQL
- Redis

**Status:** [![Docker Build](https://github.com/josec-bckdev/vtrack/workflows/Docker%20Build/badge.svg)](https://github.com/josec-bckdev/vtrack/actions/workflows/docker-build.yml)

---

### 3. Code Quality (`linting.yml`)

**Triggers:** Push to main/develop, Pull Requests  
**Duration:** ~2-3 minutes

**What it does:**
- Code formatting check (Black)
- Import sorting check (isort)
- Linting (flake8)
- Security scanning (Bandit)
- Dependency vulnerability check (Safety)
- Type checking (mypy)
- Markdown link validation

**Tools:**
- **Black** - Code formatter
- **isort** - Import organizer  
- **flake8** - Style guide enforcement
- **mypy** - Static type checker
- **Bandit** - Security linter
- **Safety** - Dependency scanner

**Status:** [![Code Quality](https://github.com/josec-bckdev/vtrack/workflows/Code%20Quality/badge.svg)](https://github.com/josec-bckdev/vtrack/actions/workflows/linting.yml)

---

## How to Use

### Local Testing Before Push

```bash
# Run tests locally
pytest app/tests/ -v

# Check code formatting
black --check app/ microservices/

# Run linter
flake8 app/ microservices/

# Type check
mypy app/ --ignore-missing-imports

# Test Docker build
docker-compose build
```

### Viewing Results

1. **Push your code:**
   ```bash
   git push origin your-branch
   ```

2. **Check status:**
   - Visit: `https://github.com/josec-bckdev/vtrack/actions`
   - See all workflow runs and their status
   - Click any workflow for detailed logs

3. **Pull Request checks:**
   - All workflows must pass before merge
   - Green checkmarks = ready to merge
   - Red X = needs fixing

### Troubleshooting Failed Workflows

**Tests failing:**
```bash
# View the specific test that failed in Actions tab
# Run locally with same environment:
docker-compose up -d db redis
export DATABASE_URL=postgresql://test_user:test_password@localhost:5432/test_db
export REDIS_URL=redis://localhost:6379/0
pytest app/tests/ -v
```

**Docker build failing:**
```bash
# Test locally:
docker-compose build
docker-compose up -d
docker-compose ps  # Check health
```

**Linting failing:**
```bash
# Auto-fix formatting:
black app/ microservices/
isort app/ microservices/

# Check what's wrong:
flake8 app/ microservices/
```

## Configuration Files

- **tests.yml** - Main test suite
- **docker-build.yml** - Docker validation
- **linting.yml** - Code quality checks
- **markdown-link-check-config.json** - Link checker config

## Environment Variables (CI)

The following variables are automatically set in workflows:

```yaml
DATABASE_URL: postgresql://test_user:test_password@localhost:5432/test_db
REDIS_URL: redis://localhost:6379/0
TESTING: "1"
TELEGRAM_BOT_TOKEN: "test_token_for_ci"
TELEGRAM_CHAT_ID: "12345"
```

## Adding New Workflows

1. Create new file: `.github/workflows/your-workflow.yml`
2. Define triggers, jobs, and steps
3. Test locally if possible
4. Push and verify in Actions tab

Example structure:
```yaml
name: Your Workflow

on:
  push:
    branches: [main]

jobs:
  your-job:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Your step
        run: echo "Hello"
```

## Badges for README

```markdown
[![Tests](https://github.com/josec-bckdev/vtrack/workflows/Tests/badge.svg)](https://github.com/josec-bckdev/vtrack/actions/workflows/tests.yml)
[![Docker Build](https://github.com/josec-bckdev/vtrack/workflows/Docker%20Build/badge.svg)](https://github.com/josec-bckdev/vtrack/actions/workflows/docker-build.yml)
[![Code Quality](https://github.com/josec-bckdev/vtrack/workflows/Code%20Quality/badge.svg)](https://github.com/josec-bckdev/vtrack/actions/workflows/linting.yml)
```

## Best Practices

✅ **Keep workflows fast** - Use caching, parallel jobs  
✅ **Fail fast** - Catch errors early  
✅ **Clear job names** - Easy to understand what failed  
✅ **Informative logs** - Help debug failures  
✅ **Use matrix builds** - Test multiple versions/services  

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Action Marketplace](https://github.com/marketplace?type=actions)

---

**Maintained by:** VTrack Team  
**Last Updated:** February 2026
