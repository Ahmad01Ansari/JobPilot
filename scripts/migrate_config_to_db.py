#!/usr/bin/env python3
"""JobPilot Configuration & Application History Migration CLI.

Migrates legacy JSON configurations (profile.json), Python config modules
(search.py, questions.py, settings.py), and historical CSV logs into SQLite.

Usage:
    python migrate_config_to_db.py [--dry-run] [--validate] [--verbose]
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.service import init_db
from app.db.session import SessionLocal, create_db_engine, engine as default_engine
from app.services.migration_service import MigrationService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate JobPilot legacy configurations and history into SQLite database."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without committing changes to database",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run parity validation between database and configuration",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Display detailed migration logs",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Optional custom SQLite database URL override",
    )
    args = parser.parse_args()

    print("=" * 65)
    print("JOBPILOT: CONFIGURATION TO DATABASE MIGRATION ENGINE")
    print("=" * 65)

    if args.dry_run:
        print(">>> MODE: DRY-RUN (no database records will be saved) <<<\n")

    # 1. Initialize schema
    if args.db_url:
        active_engine = create_db_engine(args.db_url)
        from sqlalchemy.orm import sessionmaker

        session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=active_engine,
            future=True,
        )
    else:
        active_engine = default_engine
        session_factory = SessionLocal

    success, err = init_db(active_engine)
    if not success:
        print(f"[-] Database schema initialization failed: {err}")
        return 1

    service = MigrationService(
        session_factory=session_factory,
        project_root=str(ROOT_DIR),
    )

    if args.validate and not args.dry_run:
        print("[*] Running Parity Validation against existing Database...")
        with session_factory() as session:
            from app.repositories.user_repository import UserRepository

            user = UserRepository(session).get_primary_user()
            if not user:
                print("[-] Error: No primary user found in database to validate against.")
                return 1
            val = service.validate_migration(session, user.id)
            print("-" * 65)
            print(f"Validation Status : {'PASSED' if val.is_valid else 'FAILED'}")
            print(f"Checked Fields    : {val.checked_fields}")
            print(f"Passed Fields     : {val.passed_fields}")
            print(f"Mismatches        : {len(val.mismatches)}")
            if val.mismatches:
                print("\nDiscrepancies Found:")
                for m in val.mismatches:
                    print(f"  - {m}")
            print("=" * 65)
            return 0 if val.is_valid else 1

    print("[*] Starting configuration and history migration...")
    try:
        report = service.run_full_migration(dry_run=args.dry_run)
    except Exception as exc:
        print(f"[-] Migration aborted with error: {exc}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

    print("\n" + "=" * 65)
    print("MIGRATION EXECUTION SUMMARY")
    print("=" * 65)
    print(f"Dry Run Mode            : {report.dry_run}")
    print(f"Candidate User Migrated : {'Yes' if report.user_migrated else 'No'}")
    print(f"Profiles Migrated       : {'Yes' if report.profiles_migrated else 'No'}")
    print(f"Resumes Discovered      : {report.resumes_count}")
    print(f"Platforms Registered    : {report.platforms_count}")
    print(f"Platform Accounts Saved : {report.platform_accounts_count}")
    print(f"Q&A Entries Seeded      : {report.qna_entries_count}")
    print(f"Settings Preserved      : {report.settings_count}")
    print(f"Jobs Imported (CSVs)    : {report.jobs_imported}")
    print(f"Applications Imported   : {report.applications_imported}")
    print(f"Companies Created       : {report.companies_created}")

    if report.validation:
        print("-" * 65)
        print(f"Parity Validation       : {'PASSED (100% Match)' if report.validation.is_valid else 'MISMATCH'}")
        if not report.validation.is_valid:
            for m in report.validation.mismatches:
                print(f"  [!] {m}")

    print("=" * 65)
    if report.success or (report.dry_run and not report.errors):
        print("[+] Migration completed successfully.")
        return 0
    else:
        print("[-] Migration completed with errors.")
        for err in report.errors:
            print(f"  - {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
