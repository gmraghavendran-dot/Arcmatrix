from __future__ import annotations

from sqlalchemy import create_engine, text
from backend.config import settings


def main() -> int:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        print("Database:", conn.execute(text("SELECT current_database()")).scalar_one())
        print("PostgreSQL:", conn.execute(text("SELECT version()")).scalar_one().splitlines()[0])

        tables = conn.execute(text('''
            SELECT schemaname, tablename
            FROM pg_tables
            WHERE schemaname IN ('raw', 'core', 'analytics')
            ORDER BY schemaname, tablename
        ''')).fetchall()

        print("\nArcMatrix tables:")
        for schema, table in tables:
            print(f"  {schema}.{table}")

    print("\nDatabase check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
