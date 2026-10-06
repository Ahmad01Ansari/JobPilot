# JobPilot — Database & Persistence Rules
**Specialized Guidelines for SQLAlchemy 2.0, Session Lifecycle, and Migrations**
*Reference: [Master Constitution](AI_DEVELOPMENT_RULES.md) §12*

---

## 1. Database Architecture & Dual-Persistence

JobPilot operates with two persistence mechanisms:
1. **Primary Database (`jobpilot.db`):**
   - Managed via **SQLAlchemy 2.0** declarative models located in `app/db/models/`.
   - Stores structured entities: Jobs, Applications, Analytics, Profiles, Settings, and Audit Logs.
2. **Legacy Dual-Sync Tracker (`job_tracker.db` / `applications.csv`):**
   - Managed via `modules/tracker.py`.
   - Maintained for backward compatibility with CLI automation scripts and external analytical exports.
   - **Rule:** When recording job application results, ensure synchronization between `ApplicationRepository` and `modules/tracker.py`.

---

## 2. Session Management & Scoping

All database operations must use the scoped session context manager from `app/db/session.py`:

```python
from app.db.session import session_scope

# Correct Repository Usage:
def create_job(self, job_data: dict) -> JobDTO:
    with session_scope() as session:
        job = JobModel(**job_data)
        session.add(job)
        session.flush()
        # Convert to detached DTO before session closes
        return JobDTO.from_orm(job)
```

### Strict Session Rules:
1. **Never Leave Sessions Dangling:** Always use `with session_scope() as session:` to guarantee automatic commit on success and rollback on exception.
2. **Never Pass Live ORM Instances to UI:** Accessing lazy-loaded attributes on an attached model outside the session scope raises `DetachedInstanceError`. Always convert models to DTOs or plain dataclasses within the repository layer.
3. **No Direct Sessions in UI:** UI views must NEVER import `session_scope` or `SessionLocal`. Persistence requests must route through `app/services/` to `app/repositories/`.

---

## 3. Schema Evolution & Migration Rules

When evolving database models:
1. **Inspect Existing Data:** Review existing columns in `app/db/models/` and check dependent queries in `app/repositories/`.
2. **Backward-Compatible Alterations:**
   - **New Columns:** Must be nullable (`nullable=True`) or provide a explicit default value (`default=...`).
   - **Never Casually Drop or Rename Columns:** Dropping a column breaks historical user data in existing SQLite databases.
3. **Migration Scripts:** Provide a migration script or auto-upgrade handler in `app/db/migrations/` to update user databases without data loss.

---

## 4. Query & Repository Performance

1. **Avoid N+1 Queries:** Use `joinedload()` or `selectinload()` when querying relationships that will be mapped into DTOs.
2. **Indexing:** Add indexes (`index=True`) on frequently filtered columns:
   - `job_id`, `platform`, `status`, `created_at`, `company_name`.
3. **Bulk Operations:** For batch job ingestion, use `session.bulk_insert_mappings()` or `session.execute(insert(...))` rather than committing row-by-row in a loop.
