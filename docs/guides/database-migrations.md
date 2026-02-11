# Alembic Database Migrations Guide

## Overview

Alembic is now configured for managing database schema changes in VTRACK. This guide explains how to apply migrations to your PostgreSQL database.

---

## ✅ Configuration Complete

Alembic has been configured with:

1. **[alembic.ini](alembic.ini)** - Main configuration file
   - Database URL: `postgresql://user:password@localhost/dbname` (default-placeholder)
   - Override with `DATABASE_URL` environment variable

2. **[alembic/env.py](alembic/env.py)** - Migration environment
   - Imports `app.models.Base` for model metadata
   - Uses `DATABASE_URL` environment variable if available
   - Supports both online and offline migration modes

3. **First Migration Created**: [alembic/versions/ab927e2e840d_initial_migration.py](alembic/versions/ab927e2e840d_initial_migration.py)
   - Makes `position_ts` nullable
   - Makes `route_status_ts` nullable
   - Makes `student_status_ts` nullable

4. **Docker Integration**: Modified for Alembic support
   - **[requirements.txt](requirements.txt)** - Added `alembic` package
   - **[Dockerfile](Dockerfile)** - Copies alembic/ directory and alembic.ini
   - **[docker-compose.yml](docker-compose.yml)** - Mounts alembic files for live development

---

## 🐳 Docker Configuration

### What Was Changed

To make Alembic work inside your Docker containers, the following changes were made:

#### 1. [requirements.txt](requirements.txt)
```diff
# Database
sqlalchemy
psycopg2-binary
+alembic
```

#### 2. [docker-compose.yml](docker-compose.yml)
```diff
volumes:
+ - ./alembic.ini:/app/alembic.ini:ro
+  - ./alembic:/app/alembic:ro
  - ./app:/app/app:ro
```

**Why mount these files?**
- Changes to migrations are immediately available without rebuilding
- You can create new migrations and they persist on your host machine
- Enables live development workflow

#### 3. [Dockerfile](Dockerfile)
```diff
# Copy the application code into the container
COPY app/ /app/app/

+# Copy Alembic migration files
+COPY alembic/ /app/alembic/
+COPY alembic.ini /app/alembic.ini
```

**Why copy these files?**
- Ensures migrations are included in production builds
- Makes the image self-contained

### Environment Variables

The `DATABASE_URL` from your `.env` file is automatically used by Alembic through the configuration in [alembic/env.py](alembic/env.py).

---

## 🎬 Migration Helper Script

A convenience script [migrate.sh](migrate.sh) has been created to simplify common migration tasks:

```bash
# Make the script executable (already done)
chmod +x migrate.sh

# Apply all pending migrations (safest way)
./migrate.sh upgrade

# Check current migration version
./migrate.sh current

# Create a backup before migrating
./migrate.sh backup

# Show detailed status
./migrate.sh status

# See all available commands
./migrate.sh help
```

**Recommended workflow:**
```bash
# 1. Always backup first!
./migrate.sh backup

# 2. Check current state
./migrate.sh current

# 3. Apply migrations
./migrate.sh upgrade

# 4. Verify success
./migrate.sh status
```

The script handles all the Docker commands for you and includes helpful color output and error checking.

---

## 🚀 Applying Migrations

### Option 1: Using Docker Compose (Recommended for Production)

Your app container is named `fastapi_api` and already has DATABASE_URL configured.

#### First Time Setup (After Adding Alembic)

```bash
# Rebuild the container to install Alembic
docker-compose build api

# Restart the container
docker-compose up -d api
```

#### Running Migrations

```bash
# If containers are running:
docker-compose exec api alembic upgrade head

# If containers are stopped, use run:
docker-compose run --rm api alembic upgrade head

# Check current migration version:
docker-compose exec api alembic current

# View migration history:
docker-compose exec api alembic history
```

#### Complete Migration Workflow

```bash
# 1. Ensure database is running and healthy
docker-compose ps

# 2. Check current migration status
docker-compose exec api alembic current

# 3. Apply pending migrations
docker-compose exec api alembic upgrade head

# 4. Verify migration was applied
docker-compose exec api alembic current
# Should show: 4906ead73111 (head)

# 5. Restart the API to ensure it picks up changes
docker-compose restart api
```

### Option 2: Local Development

If you have PostgreSQL running locally:

```bash
# Set the DATABASE_URL environment variable
export DATABASE_URL="postgresql://user:password@localhost:5432/app_db"

# Apply all pending migrations
alembic upgrade head
```

### Option 3: Using Docker Exec

If your containers are running:

```bash
# Find the app container name
docker ps

# Run migration inside the container
docker exec -it vtrack-app-1 alembic upgrade head
```

---

## 📊 Migration Commands Reference

### Check Current Version

```bash
# Show current migration version
alembic current

# Show migration history
alembic history --verbose
```

### Apply Migrations

```bash
# Upgrade to latest version
alembic upgrade head

# Upgrade by 1 version
alembic upgrade +1

# Upgrade to specific revision
alembic upgrade 4906ead73111
```

### Rollback Migrations

```bash
# Downgrade by 1 version
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade 4906ead73111

# Downgrade to base (removes all migrations)
alembic downgrade base
```

### Creating New Migrations

```bash
# Create a new empty migration
alembic revision -m "description of changes"

# Create migration with autogenerate (requires DB connection)
alembic revision --autogenerate -m "description of changes"
```

---

## 🔍 What This Migration Does

### Upgrade (Apply Migration)

The migration changes the `route_data_entry` table to make three timestamp fields nullable:

```sql
ALTER TABLE route_data_entry
  ALTER COLUMN position_ts DROP NOT NULL;

ALTER TABLE route_data_entry
  ALTER COLUMN route_status_ts DROP NOT NULL;

ALTER TABLE route_data_entry
  ALTER COLUMN student_status_ts DROP NOT NULL;
```

### Why This Change?

The external API (`rutasljrj.net`) sometimes returns invalid timestamps like `'0000-00-00 00:00:00'` which our parser converts to `None`. The database schema needs to allow NULL values to match the application logic.

**Files changed to support this:**
- [app/models.py:58-62](app/models.py#L58-L62) - Made Pydantic fields nullable
- [app/scraper_async.py](app/scraper_async.py) - Parser returns None for invalid dates
- [app/data_server.py:21-36](app/data_server.py#L21-L36) - Timezone handling for nullable timestamps

### Downgrade (Rollback Migration)

The downgrade makes the fields NOT NULL again:

```sql
ALTER TABLE route_data_entry
  ALTER COLUMN position_ts SET NOT NULL;

ALTER TABLE route_data_entry
  ALTER COLUMN route_status_ts SET NOT NULL;

ALTER TABLE route_data_entry
  ALTER COLUMN student_status_ts SET NOT NULL;
```

**⚠️ Warning:** Downgrading will fail if any rows have NULL values in these columns!

---

## 🎯 Quick Start Checklist

To apply the migration to your production database:

- [ ] **Backup your database** (always!)
  ```bash
  docker-compose exec db pg_dump -U user app_db > backup_$(date +%Y%m%d).sql
  ```

- [ ] **Check current migration status**
  ```bash
  docker-compose exec app alembic current
  ```

- [ ] **Review the migration file**
  - Check [alembic/versions/4906ead73111_make_timestamp_fields_nullable.py](alembic/versions/4906ead73111_make_timestamp_fields_nullable.py)

- [ ] **Apply the migration**
  ```bash
  docker-compose exec app alembic upgrade head
  ```

- [ ] **Verify the migration**
  ```bash
  docker-compose exec app alembic current
  # Should show: 4906ead73111 (head)
  ```

- [ ] **Test the application**
  - Start collecting data: `POST /collect/start`
  - Check for errors in logs
  - Verify data is being saved correctly

---

## 🐛 Troubleshooting

### Error: "could not translate host name 'db' to address"

**Problem:** Alembic can't connect to PostgreSQL container.

**Solutions:**
- Ensure database container is running: `docker-compose ps`
- Use `docker-compose exec app alembic ...` to run inside the container
- Check `DATABASE_URL` environment variable

### Error: "Can't locate revision identified by '...'"

**Problem:** Alembic version table is out of sync.

**Solutions:**
```bash
# Check current version
alembic current

# Stamp the database with the current version
alembic stamp head

# Or start fresh (destructive!)
alembic stamp base
alembic upgrade head
```

### Error: "Target database is not up to date"

**Problem:** Database has changes not tracked by Alembic.

**Solutions:**
- This is the first migration, so the database might have been created manually
- Option 1: Stamp the database as being at base, then upgrade:
  ```bash
  alembic stamp base
  alembic upgrade head
  ```
- Option 2: If tables were created by `Base.metadata.create_all()`, you may need to manually adjust the schema or recreate the database

### Migration Fails with "column ... does not exist"

**Problem:** Database schema doesn't match the model metadata.

**Solutions:**
- Check what tables exist: `docker-compose exec db psql -U user -d app_db -c "\d"`
- If starting fresh, drop all tables and let Alembic create them:
  ```sql
  -- WARNING: This deletes all data!
  DROP TABLE IF EXISTS route_data_entry CASCADE;
  DROP TABLE IF EXISTS collection_metadata CASCADE;
  ```
- Then run: `alembic upgrade head`

### Error: `psycopg2.errors.DuplicateTable: relation "route_data" already exists`

**Problem:** After running `docker-compose down` and then `docker-compose up`, the migration fails because:
- The database volume persists (containers/services stop, but data remains)
- Alembic's version history table (`alembic_version`) is out of sync with the actual database
- When migrations try to re-run, they attempt to create tables that already exist

**When This Happens:**
```
migrate_job | Running upgrade ab927e2e840d -> c3f9a4b2e6f7, Create initial tables
migrate_job | sqlalchemy.exc.ProgrammingError: (psycopg2.errors.DuplicateTable) 
             relation "route_data" already exists
```

**Solutions:**

**Option 1: Quick Fix (Recommended for Development)**
Stamp the database to match the current head revision without re-running migrations:
```bash
# Mark the database as being at the latest migration version
docker-compose run --rm migrate alembic stamp head

# Then restart the migration service
docker-compose up -d migrate
```

**Option 2: Clean Slate (Destructive)**
If you want to start fresh with a clean database:
```bash
# Remove all containers, volumes, and data
docker-compose down -v

# Recreate everything from scratch
docker-compose up -d

# Data in the database will be gone, but migrations will apply cleanly
```

**Option 3: Keep Data But Reset Alembic**
If you want to keep existing data but reset the migration history:
```bash
# Connect to the database
docker-compose exec db psql -U user -d app_db

# Inside psql, reset the alembic version table:
\c app_db
DELETE FROM alembic_version;
\q

# Then stamp to the current head
docker-compose run --rm migrate alembic stamp head
```

**Why This Happens:**
- The `docker-compose.yml` uses named volumes by default, so data persists across container restarts
- Alembic tracks which migrations have been applied in the `alembic_version` table
- If the database has tables but the `alembic_version` table doesn't reflect this, Alembic tries to re-apply migrations
- This causes "already exists" errors for tables that are already there

**Prevention Tips:**
- Use `docker-compose down -v` to remove volumes if doing a full reset
- Use `alembic stamp head` after major database changes to sync Alembic's tracking
- Keep database backups before running migrations

---

## 📚 Best Practices

### Before Creating Migrations

1. **Always review autogenerated migrations** - Alembic sometimes generates extra operations
2. **Test migrations on a copy of production data** before applying to production
3. **Write descriptive migration messages** - Future you will thank you!

### When Applying Migrations

1. **Always backup the database first**
2. **Apply migrations during low-traffic periods**
3. **Have a rollback plan ready**
4. **Monitor application logs** after migration

### Migration Workflow

```bash
# 1. Make model changes in app/models.py
vim app/models.py

# 2. Create migration (requires DB connection for autogenerate)
alembic revision --autogenerate -m "add new field"

# 3. Review the generated migration
cat alembic/versions/XXXXX_add_new_field.py

# 4. Edit if necessary
vim alembic/versions/XXXXX_add_new_field.py

# 5. Test migration on dev database
alembic upgrade head

# 6. Test downgrade works
alembic downgrade -1
alembic upgrade head

# 7. Commit to git
git add alembic/versions/XXXXX_add_new_field.py
git commit -m "Add migration: add new field"

# 8. Apply to production
# (with backup and monitoring!)
```

---

## 🔗 Related Files

- **[alembic.ini](alembic.ini)** - Alembic configuration
- **[alembic/env.py](alembic/env.py)** - Migration environment setup
- **[app/models.py](app/models.py)** - SQLAlchemy models (source of truth)
- **[app/database.py](app/database.py)** - Database connection setup
- **[TEST_SUITE_SUMMARY.md](../archive/test-suite-summary.md)** - Testing documentation

---

## 🎯 Quick Reference: Docker + Alembic Commands

### Initial Setup
```bash
# Build container with Alembic
docker-compose build api

# Start all services
docker-compose up -d
```

### Apply Migrations
```bash
# Apply all pending migrations
docker-compose exec api alembic upgrade head

# Apply one migration at a time
docker-compose exec api alembic upgrade +1
```

### Check Status
```bash
# Show current version
docker-compose exec api alembic current

# Show migration history
docker-compose exec api alembic history --verbose

# Show pending migrations
docker-compose exec api alembic heads
```

### Rollback Migrations
```bash
# Rollback one version
docker-compose exec api alembic downgrade -1

# Rollback to specific version
docker-compose exec api alembic downgrade 4906ead73111

# Rollback all migrations
docker-compose exec api alembic downgrade base
```

### Create New Migrations
```bash
# Create empty migration
docker-compose exec api alembic revision -m "description"

# Create migration with autogenerate (detects changes)
docker-compose exec api alembic revision --autogenerate -m "description"
```

### Database Operations
```bash
# Backup database before migration
docker-compose exec db pg_dump -U user app_db > backup_$(date +%Y%m%d).sql

# Restore database from backup
docker-compose exec -T db psql -U user app_db < backup_20260205.sql

# Connect to database
docker-compose exec db psql -U user -d app_db

# Check database tables
docker-compose exec db psql -U user -d app_db -c "\dt"
```

### Container Management
```bash
# View logs
docker-compose logs -f api

# Restart API after migration
docker-compose restart api

# Rebuild and restart (if Dockerfile changed)
docker-compose up -d --build api

# Stop all services
docker-compose down

# Remove all data (⚠️ destructive!)
docker-compose down -v
```

### Debugging
```bash
# Open shell in running container
docker-compose exec api bash

# Run Python in container
docker-compose exec api python

# Check if alembic is installed
docker-compose exec api pip show alembic

# Check environment variables
docker-compose exec api env | grep DATABASE_URL
```

---

## 📖 Additional Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

---

**Last Updated:** 2026-02-05
**Migration Version:** ab927e2e840d
**Status:** ✅ Ready to apply
**Container Name:** `fastapi_api`
