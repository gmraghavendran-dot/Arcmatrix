from pathlib import Path
import os
import re
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.types import Text


# ============================================================
# ARCMATRIX
# DIRECT CI/CD RAW LOADER
# ============================================================

load_dotenv()


# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "arcmatrix")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")


CICD_FILE = Path(
    r"C:\Users\Rashmita\Downloads\ArcMatrix dataset"
    r"\A comprehensive GitHub Actions dataset for CICD pi"
    r"\final_research_dataset_MASTER.csv"
)


# ------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------

if not DB_PASSWORD:
    raise RuntimeError(
        "DB_PASSWORD is missing from .env"
    )


url = URL.create(
    drivername="postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)

engine = create_engine(
    url,
    pool_pre_ping=True,
)


# ------------------------------------------------------------
# SAFE COLUMN NAMES
# ------------------------------------------------------------

def clean_columns(df: pd.DataFrame) -> pd.DataFrame:

    names = []

    for i, column in enumerate(df.columns):

        name = str(column).strip().lower()

        name = re.sub(
            r"[^a-z0-9]+",
            "_",
            name
        )

        name = re.sub(
            r"_+",
            "_",
            name
        )

        name = name.strip("_")

        if not name:
            name = f"column_{i + 1}"

        names.append(name)

    # Handle duplicate column names
    counts = {}
    final = []

    for name in names:

        if name not in counts:

            counts[name] = 0
            final.append(name)

        else:

            counts[name] += 1

            final.append(
                f"{name}_{counts[name]}"
            )

    df.columns = final

    return df


# ------------------------------------------------------------
# INITIALIZE SCHEMAS
# ------------------------------------------------------------

def initialize():

    with engine.begin() as conn:

        conn.execute(
            text(
                "CREATE SCHEMA IF NOT EXISTS raw;"
            )
        )

        conn.execute(
            text(
                "CREATE SCHEMA IF NOT EXISTS core;"
            )
        )

        conn.execute(
            text(
                "CREATE SCHEMA IF NOT EXISTS analytics;"
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS core.dataset_registry (
                    dataset_id BIGSERIAL PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    file_name TEXT,
                    source_type TEXT,
                    table_name TEXT,
                    row_count BIGINT DEFAULT 0,
                    column_count INTEGER DEFAULT 0,
                    data_start TIMESTAMP,
                    data_end TIMESTAMP,
                    status TEXT DEFAULT 'PENDING',
                    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                );
                """
            )
        )


# ------------------------------------------------------------
# LOAD CI/CD
# ------------------------------------------------------------

def main():

    print()
    print("=" * 70)
    print("             ARCMATRIX CI/CD RAW LOADER")
    print("=" * 70)

    print()
    print("File:")
    print(CICD_FILE)

    if not CICD_FILE.exists():

        raise FileNotFoundError(
            f"CI/CD file not found:\n{CICD_FILE}"
        )

    initialize()

    print()
    print("Reading CI/CD dataset...")

    # Everything starts as text in RAW.
    # This avoids PostgreSQL inference problems.
    df = pd.read_csv(
        CICD_FILE,
        dtype=str,
        low_memory=False,
    )

    print(
        f"Rows    : {len(df):,}"
    )

    print(
        f"Columns : {len(df.columns):,}"
    )

    df = clean_columns(df)

    # Convert empty strings to NULL
    df = df.replace(
        r"^\s*$",
        pd.NA,
        regex=True
    )

    print()
    print("Loading → raw.cicd_runs")

    # All columns are stored as TEXT in RAW.
    # Core layer will later cast the important columns.
    dtype_map = {
        column: Text()
        for column in df.columns
    }

    df.to_sql(
        name="cicd_runs",
        con=engine,
        schema="raw",
        if_exists="replace",
        index=False,
        chunksize=5000,
        method="multi",
        dtype=dtype_map,
    )

    print(
        "✅ raw.cicd_runs created successfully."
    )

    # --------------------------------------------------------
    # REGISTER
    # --------------------------------------------------------

    with engine.begin() as conn:

        conn.execute(
            text(
                """
                INSERT INTO core.dataset_registry
                (
                    source_name,
                    file_name,
                    source_type,
                    table_name,
                    row_count,
                    column_count,
                    status,
                    loaded_at,
                    notes
                )
                VALUES
                (
                    'cicd_runs',
                    :file_name,
                    'csv',
                    'cicd_runs',
                    :row_count,
                    :column_count,
                    'SUCCESS',
                    :loaded_at,
                    'Direct CI/CD RAW load'
                );
                """
            ),
            {
                "file_name":
                    CICD_FILE.name,

                "row_count":
                    len(df),

                "column_count":
                    len(df.columns),

                "loaded_at":
                    datetime.now(),
            }
        )

    # --------------------------------------------------------
    # VERIFY
    # --------------------------------------------------------

    with engine.connect() as conn:

        result = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM raw.cicd_runs;
                """
            )
        )

        count = result.scalar_one()

    print()
    print(
        f"✅ Verified rows in raw.cicd_runs: {count:,}"
    )

    print()
    print("=" * 70)
    print("                 CI/CD LOAD COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()