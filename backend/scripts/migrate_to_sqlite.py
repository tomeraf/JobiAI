"""
PostgreSQL to SQLite Migration Script

Exports data from PostgreSQL and imports into SQLite database.

Usage:
    # Export from PostgreSQL
    python scripts/migrate_to_sqlite.py export --db "postgresql://..."

    # Import to SQLite
    python scripts/migrate_to_sqlite.py import --db "sqlite:///jobiai.db"

    # Full migration (export + import)
    python scripts/migrate_to_sqlite.py migrate \\
        --from "postgresql://postgres:postgres@localhost:5436/jobiai" \\
        --to "sqlite:///C:/Users/USERNAME/AppData/Local/JobiAI/jobiai.db"
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def serialize_value(value: Any) -> Any:
    """Convert value to JSON-serializable format."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, dict)):
        return value
    return value


def deserialize_value(value: Any, column_type: str) -> Any:
    """Convert JSON value back to Python type."""
    if value is None:
        return None
    if 'datetime' in column_type.lower() or 'timestamp' in column_type.lower():
        if isinstance(value, str):
            return datetime.fromisoformat(value)
    return value


def export_to_json(database_url: str, output_dir: Path):
    """Export all tables from database to JSON files."""
    from sqlalchemy import create_engine, MetaData, text

    print(f"Connecting to: {database_url[:50]}...")

    # Use sync engine for simplicity
    sync_url = database_url.replace('+asyncpg', '').replace('+aiosqlite', '')
    engine = create_engine(sync_url)

    # Get all tables
    metadata = MetaData()
    metadata.reflect(bind=engine)

    output_dir.mkdir(parents=True, exist_ok=True)

    with engine.connect() as conn:
        for table_name, table in metadata.tables.items():
            print(f"Exporting table: {table_name}")

            # Get all rows
            result = conn.execute(table.select())
            rows = []

            for row in result:
                row_dict = {}
                for column in table.columns:
                    value = getattr(row, column.name)
                    row_dict[column.name] = serialize_value(value)
                rows.append(row_dict)

            # Save to JSON
            output_file = output_dir / f"{table_name}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'table': table_name,
                    'columns': [c.name for c in table.columns],
                    'row_count': len(rows),
                    'rows': rows,
                }, f, indent=2, ensure_ascii=False)

            print(f"  Exported {len(rows)} rows to {output_file}")

    print(f"\nExport complete! Files saved to: {output_dir}")


def import_from_json(database_url: str, input_dir: Path):
    """Import data from JSON files into database."""
    from sqlalchemy import create_engine, MetaData, text

    print(f"Connecting to: {database_url[:50]}...")

    # Use sync engine
    sync_url = database_url.replace('+asyncpg', '').replace('+aiosqlite', '')
    engine = create_engine(sync_url)

    # Create tables first
    print("Creating tables...")
    from app.database import Base
    from app.models import job, contact, template, site_selector, hebrew_name, activity

    Base.metadata.create_all(engine)

    # Get table metadata
    metadata = MetaData()
    metadata.reflect(bind=engine)

    # Import order matters for foreign keys
    import_order = [
        'templates',
        'hebrew_names',
        'site_selectors',
        'jobs',
        'contacts',
        'activity_logs',
    ]

    with engine.connect() as conn:
        # Disable foreign key checks for SQLite during import
        if 'sqlite' in database_url:
            conn.execute(text("PRAGMA foreign_keys=OFF"))

        for table_name in import_order:
            json_file = input_dir / f"{table_name}.json"
            if not json_file.exists():
                print(f"Skipping {table_name} (no JSON file)")
                continue

            print(f"Importing table: {table_name}")

            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            table = metadata.tables.get(table_name)
            if table is None:
                print(f"  Warning: Table {table_name} not found in database")
                continue

            rows = data.get('rows', [])
            if not rows:
                print(f"  No rows to import")
                continue

            # Clear existing data
            conn.execute(table.delete())

            # Insert rows
            for row in rows:
                # Filter to only columns that exist in the table
                valid_columns = {c.name for c in table.columns}
                filtered_row = {k: v for k, v in row.items() if k in valid_columns}

                # Convert datetime strings to datetime objects for SQLite
                from datetime import datetime
                for col in table.columns:
                    col_name = col.name
                    if col_name in filtered_row and filtered_row[col_name] is not None:
                        if 'DATETIME' in str(col.type).upper() or 'TIMESTAMP' in str(col.type).upper():
                            val = filtered_row[col_name]
                            if isinstance(val, str):
                                # Try parsing ISO format datetime
                                try:
                                    filtered_row[col_name] = datetime.fromisoformat(val.replace('Z', '+00:00'))
                                except ValueError:
                                    # Try another format
                                    try:
                                        filtered_row[col_name] = datetime.strptime(val, '%Y-%m-%dT%H:%M:%S.%f')
                                    except ValueError:
                                        filtered_row[col_name] = datetime.strptime(val, '%Y-%m-%dT%H:%M:%S')

                conn.execute(table.insert().values(**filtered_row))

            conn.commit()
            print(f"  Imported {len(rows)} rows")

        # Re-enable foreign key checks
        if 'sqlite' in database_url:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()

    print(f"\nImport complete!")


def migrate(from_url: str, to_url: str, temp_dir: Path = None):
    """Full migration from one database to another."""
    if temp_dir is None:
        temp_dir = Path.home() / '.jobiai_migration'

    print("=== JobiAI Database Migration ===\n")

    # Step 1: Export from source
    print("Step 1: Exporting from source database...")
    export_to_json(from_url, temp_dir)

    # Step 2: Import to destination
    print("\nStep 2: Importing to destination database...")
    import_from_json(to_url, temp_dir)

    # Step 3: Verify
    print("\nStep 3: Verifying migration...")
    verify_migration(from_url, to_url)

    print("\n=== Migration Complete! ===")
    print(f"Temporary files at: {temp_dir}")
    print("You can delete this directory after verifying the migration.")


def verify_migration(from_url: str, to_url: str):
    """Verify row counts match between databases."""
    from sqlalchemy import create_engine, MetaData

    from_sync = from_url.replace('+asyncpg', '').replace('+aiosqlite', '')
    to_sync = to_url.replace('+asyncpg', '').replace('+aiosqlite', '')

    from_engine = create_engine(from_sync)
    to_engine = create_engine(to_sync)

    from_meta = MetaData()
    from_meta.reflect(bind=from_engine)

    to_meta = MetaData()
    to_meta.reflect(bind=to_engine)

    print("\nRow count comparison:")
    print("-" * 40)

    all_match = True
    with from_engine.connect() as from_conn, to_engine.connect() as to_conn:
        for table_name in from_meta.tables:
            from_table = from_meta.tables[table_name]
            to_table = to_meta.tables.get(table_name)

            from_count = from_conn.execute(from_table.select()).rowcount
            # Count differently for proper results
            from sqlalchemy import func, select
            from_count = from_conn.scalar(select(func.count()).select_from(from_table))

            if to_table is not None:
                to_count = to_conn.scalar(select(func.count()).select_from(to_table))
            else:
                to_count = 0

            match = "✓" if from_count == to_count else "✗"
            if from_count != to_count:
                all_match = False

            print(f"  {table_name}: {from_count} -> {to_count} {match}")

    if all_match:
        print("\nAll tables migrated successfully!")
    else:
        print("\nWarning: Some tables have mismatched row counts.")


def main():
    parser = argparse.ArgumentParser(description='JobiAI Database Migration Tool')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export database to JSON')
    export_parser.add_argument('--db', required=True, help='Database URL')
    export_parser.add_argument('--output', default='./migration_data', help='Output directory')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import JSON to database')
    import_parser.add_argument('--db', required=True, help='Database URL')
    import_parser.add_argument('--input', default='./migration_data', help='Input directory')

    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Full migration')
    migrate_parser.add_argument('--from', dest='from_db', required=True, help='Source database URL')
    migrate_parser.add_argument('--to', dest='to_db', required=True, help='Destination database URL')
    migrate_parser.add_argument('--temp', default=None, help='Temporary directory for JSON files')

    args = parser.parse_args()

    if args.command == 'export':
        export_to_json(args.db, Path(args.output))
    elif args.command == 'import':
        import_from_json(args.db, Path(args.input))
    elif args.command == 'migrate':
        temp_dir = Path(args.temp) if args.temp else None
        migrate(args.from_db, args.to_db, temp_dir)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
