from __future__ import annotations

import hashlib
import json
import os
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


# ============================================================
# ARCMATRIX
# Enterprise Engineering, Cloud & AI Intelligence Platform
#
# RAW INGESTION ENGINE
# ============================================================


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

# Change this only if your dataset folder is somewhere else.
#
# Based on your screenshot, your current folder is:
# C:\Users\Rashmita\Downloads\ArcMatrix dataset
#
DATA_ROOT = Path(
    os.getenv(
        "ARCMATRIX_DATA_ROOT",
        r"C:\Users\Rashmita\Downloads\ArcMatrix dataset"
    )
)


# PostgreSQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "arcmatrix")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")


# ============================================================
# DATABASE ENGINE
# ============================================================

def create_engine_connection():
    """
    Create SQLAlchemy connection to ArcMatrix PostgreSQL DB.
    """

    if not DB_PASSWORD:
        raise RuntimeError(
            "DB_PASSWORD is not set. "
            "Create a .env file with DB_PASSWORD=..."
        )

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )

    return create_engine(
        url,
        pool_pre_ping=True,
        future=True,
    )


engine = create_engine_connection()


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_database() -> None:
    """
    Make sure ArcMatrix schemas and control tables exist.
    """

    with engine.begin() as conn:

        conn.execute(
            text(
                """
                CREATE SCHEMA IF NOT EXISTS raw;
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE SCHEMA IF NOT EXISTS core;
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE SCHEMA IF NOT EXISTS analytics;
                """
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

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS core.pipeline_runs (
                    run_id BIGSERIAL PRIMARY KEY,
                    pipeline_name TEXT NOT NULL,
                    source_name TEXT,
                    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP,
                    status TEXT,
                    records_processed BIGINT DEFAULT 0,
                    records_failed BIGINT DEFAULT 0,
                    error_message TEXT
                );
                """
            )
        )


# ============================================================
# FILE DISCOVERY
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
    ".json",
    ".jsonl",
    ".gz",
}


def discover_files(root: Path) -> list[Path]:
    """
    Recursively discover supported files.
    """

    if not root.exists():
        raise FileNotFoundError(
            f"Dataset directory does not exist:\n{root}"
        )

    files: list[Path] = []

    for path in root.rglob("*"):

        if not path.is_file():
            continue

        suffix = path.suffix.lower()

        # Special handling for .json.gz / .csv.gz
        if suffix in SUPPORTED_EXTENSIONS:
            files.append(path)

    return sorted(files)


# ============================================================
# FILE HASH
# ============================================================

def file_hash(path: Path) -> str:
    """
    SHA256 hash for duplicate detection.
    """

    sha256 = hashlib.sha256()

    with path.open(
        "rb"
    ) as file:

        while True:

            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


# ============================================================
# COLUMN NORMALIZATION
# ============================================================

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert source column names to PostgreSQL-safe names.
    Duplicate columns receive suffixes.
    """

    new_columns = []

    for index, column in enumerate(
        df.columns
    ):

        name = str(column)

        name = name.strip().lower()

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
            name = f"column_{index + 1}"

        new_columns.append(name)

    # Resolve duplicates
    counts: dict[str, int] = {}

    final_columns = []

    for name in new_columns:

        if name not in counts:

            counts[name] = 0
            final_columns.append(name)

        else:

            counts[name] += 1

            final_columns.append(
                f"{name}_{counts[name]}"
            )

    df.columns = final_columns

    return df


# ============================================================
# GENERIC CLEANING
# ============================================================

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Minimal RAW-layer cleaning.

    We deliberately avoid changing business meaning.
    """

    df = df.copy()

    df = normalize_columns(df)

    df = df.replace(
        r"^\s*$",
        pd.NA,
        regex=True
    )

    return df


# ============================================================
# CSV / EXCEL READER
# ============================================================

def read_tabular_file(path: Path) -> pd.DataFrame:
    """
    Read CSV/XLS/XLSX with common encoding fallbacks.
    """

    suffix = path.suffix.lower()

    # --------------------------------------------------------
    # Excel
    # --------------------------------------------------------

    if suffix in {".xlsx", ".xls"}:

        return pd.read_excel(
            path
        )

    # --------------------------------------------------------
    # GZIP
    # --------------------------------------------------------

    if suffix == ".gz":

        name = path.name.lower()

        if name.endswith(".csv.gz"):

            return pd.read_csv(
                path,
                compression="gzip",
                low_memory=False
            )

        if name.endswith(".json.gz"):

            return read_json_gz(
                path
            )

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    encodings = [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin1",
    ]

    last_error = None

    for encoding in encodings:

        try:

            return pd.read_csv(
                path,
                encoding=encoding,
                low_memory=False
            )

        except Exception as error:

            last_error = error

    raise last_error


# ============================================================
# JSON READER
# ============================================================

def read_json_file(path: Path) -> pd.DataFrame:
    """
    Read either:
    1. Standard JSON
    2. JSON Lines / NDJSON
    """

    # --------------------------------------------------------
    # Try standard JSON first
    # --------------------------------------------------------

    try:
        with path.open(
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, list):
            return pd.json_normalize(data)

        if isinstance(data, dict):

            for key in (
                "data",
                "records",
                "results",
                "items",
            ):

                if isinstance(
                    data.get(key),
                    list
                ):

                    return pd.json_normalize(
                        data[key]
                    )

            return pd.json_normalize(data)

    except json.JSONDecodeError:

        # ----------------------------------------------------
        # Fallback: JSON Lines / NDJSON
        # ----------------------------------------------------

        records = []

        with path.open(
            "r",
            encoding="utf-8"
        ) as file:

            for line_number, line in enumerate(
                file,
                start=1
            ):

                line = line.strip()

                if not line:
                    continue

                try:

                    records.append(
                        json.loads(line)
                    )

                except json.JSONDecodeError as error:

                    print(
                        f"⚠ Invalid JSON line "
                        f"{line_number} "
                        f"in {path.name}: "
                        f"{error}"
                    )

        if records:

            return pd.json_normalize(
                records
            )

        raise ValueError(
            f"No valid JSON records found in {path.name}"
        )


# ============================================================
# JSON.GZ READER
# ============================================================

def read_json_gz(path: Path) -> pd.DataFrame:

    import gzip

    with gzip.open(
        path,
        "rt",
        encoding="utf-8"
    ) as file:

        first_character = file.read(1)

        file.seek(0)

        # JSON Lines
        if first_character != "[":

            records = []

            for line in file:

                line = line.strip()

                if not line:
                    continue

                records.append(
                    json.loads(line)
                )

            return pd.json_normalize(
                records
            )

        # Regular JSON
        data = json.load(file)

        if isinstance(data, list):

            return pd.json_normalize(
                data
            )

        return pd.json_normalize(
            data
        )


# ============================================================
# JSONL READER
# ============================================================

def read_jsonl_file(
    path: Path
) -> pd.DataFrame:

    records = []

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        for line in file:

            line = line.strip()

            if not line:
                continue

            try:

                records.append(
                    json.loads(line)
                )

            except json.JSONDecodeError:

                continue

    if not records:

        return pd.DataFrame()

    return pd.json_normalize(
        records
    )


# ============================================================
# GENERAL FILE READER
# ============================================================

def read_file(path: Path) -> pd.DataFrame:
    """
    Detect format and return DataFrame.
    """

    name = path.name.lower()

    if name.endswith(
        ".jsonl"
    ):

        return read_jsonl_file(
            path
        )

    if name.endswith(
        ".json"
    ):

        return read_json_file(
            path
        )

    return read_tabular_file(
        path
    )


# ============================================================
# SOURCE CLASSIFICATION
# ============================================================

def classify_source(
    path: Path,
    df: pd.DataFrame | None = None
) -> str | None:
    """
    Identify one of the ArcMatrix source domains.
    """

    name = path.name.lower()

    full_path = str(
        path
    ).lower()

    # --------------------------------------------------------
    # GHPR / GitHub
    # --------------------------------------------------------

    if (
        "ghpr" in name
        or "pull_request" in name
        or "pull_requests" in name
        or "github" in full_path
        and "repository" not in name
    ):

        return "github_engineering"

    # --------------------------------------------------------
    # FOCUS
    # --------------------------------------------------------

    if (
        "focus" in name
        or "focus-sample" in full_path
        or "focus_sample" in name
    ):

        return "cloud_cost_usage"

    # --------------------------------------------------------
    # AI / LLM
    # --------------------------------------------------------

    if (
        "llm" in full_path
        or "benchmark" in full_path
        or "bench-data" in full_path
        or "telemetry" in name
        or "inference" in name
    ):

        return "ai_telemetry"

    # --------------------------------------------------------
    # CI/CD
    # --------------------------------------------------------

    if (
        "cicd" in full_path
        or "ci-cd" in full_path
        or "github actions" in full_path
        or "github_action" in full_path
        or "pipeline" in name
        or "workflow" in name
    ):

        return "cicd_runs"

    # --------------------------------------------------------
    # Repository metadata
    # --------------------------------------------------------

    if (
        "repositories" in name
        or name == "repositories.json"
    ):

        return "github_repositories"

    # --------------------------------------------------------
    # CI/CD research dataset
    # --------------------------------------------------------

    if (
        "final_research_dataset_master.csv"
        in name
        or "github actions" in full_path
        or "cicd pipeline prediction" in full_path
    ):

        return "cicd_runs"

    # --------------------------------------------------------
    # Column-based detection
    # --------------------------------------------------------

    if df is not None:

        columns = {
            str(c).lower()
            for c in df.columns
        }

        # GitHub PR
        if {
            "pull_number",
            "pull_created_at",
            "pull_merged_at",
        }.intersection(columns):

            return "github_engineering"

        # FOCUS
        if {
            "billedcost",
            "effectivecost",
            "providername",
        }.intersection(columns):

            return "cloud_cost_usage"

        # CI/CD
        if {
            "run_id",
            "workflow_id",
            "conclusion",
        }.intersection(columns):

            return "cicd_runs"

        # AI telemetry
        if {
            "latency",
            "ttft",
            "tokens_per_second",
        }.intersection(columns):

            return "ai_telemetry"

    return None


# ============================================================
# TABLE NAME
# ============================================================

SOURCE_TABLES = {
    "github_engineering":
        "github_engineering",

    "cloud_cost_usage":
        "cloud_cost_usage",

    "cicd_runs":
        "cicd_runs",

    "ai_telemetry":
        "ai_telemetry",

    "github_repositories":
        "github_repositories",
}


def table_for_source(
    source: str
) -> str:

    return SOURCE_TABLES[
        source
    ]


# ============================================================
# DATE DETECTION
# ============================================================

def detect_date_range(
    df: pd.DataFrame
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:

    date_columns = []

    for column in df.columns:

        name = str(
            column
        ).lower()

        if any(
            token in name
            for token in [
                "timestamp",
                "created_at",
                "updated_at",
                "merged_at",
                "started_at",
                "finished_at",
                "run_started_at",
                "billingperiodstart",
                "billingperiodend",
                "date",
            ]
        ):

            date_columns.append(
                column
            )

    timestamps = []

    for column in date_columns:

        try:

            values = pd.to_datetime(
                df[column],
                errors="coerce",
                utc=True
            )

            values = values.dropna()

            if not values.empty:

                timestamps.append(
                    values.min()
                )

                timestamps.append(
                    values.max()
                )

        except Exception:

            continue

    if not timestamps:

        return None, None

    return (
        min(timestamps),
        max(timestamps)
    )


# ============================================================
# REGISTRY LOOKUP
# ============================================================

def registry_contains(
    source: str,
    file_name: str
) -> bool:

    query = text(
        """
        SELECT dataset_id
        FROM core.dataset_registry
        WHERE source_name = :source
          AND file_name = :file_name
          AND status = 'SUCCESS'
        LIMIT 1;
        """
    )

    with engine.connect() as conn:

        result = conn.execute(
            query,
            {
                "source": source,
                "file_name": file_name,
            }
        ).fetchone()

    return result is not None


# ============================================================
# PIPELINE RUN CREATION
# ============================================================

def start_pipeline_run(
    source: str
) -> int:

    query = text(
        """
        INSERT INTO core.pipeline_runs
        (
            pipeline_name,
            source_name,
            started_at,
            status
        )
        VALUES
        (
            'arcmatrix_raw_ingestion',
            :source,
            :started_at,
            'RUNNING'
        )
        RETURNING run_id;
        """
    )

    with engine.begin() as conn:

        result = conn.execute(
            query,
            {
                "source":
                    source,

                "started_at":
                    datetime.now(),
            }
        )

        return result.scalar_one()


# ============================================================
# PIPELINE RUN COMPLETION
# ============================================================

def finish_pipeline_run(
    run_id: int,
    status: str,
    records_processed: int = 0,
    records_failed: int = 0,
    error_message: str | None = None
) -> None:

    query = text(
        """
        UPDATE core.pipeline_runs

        SET
            finished_at = :finished_at,
            status = :status,
            records_processed = :records_processed,
            records_failed = :records_failed,
            error_message = :error_message

        WHERE run_id = :run_id;
        """
    )

    with engine.begin() as conn:

        conn.execute(
            query,
            {
                "run_id":
                    run_id,

                "finished_at":
                    datetime.now(),

                "status":
                    status,

                "records_processed":
                    records_processed,

                "records_failed":
                    records_failed,

                "error_message":
                    error_message,
            }
        )


# ============================================================
# REGISTRY INSERT
# ============================================================

def register_dataset(
    source: str,
    file_path: Path,
    table_name: str,
    rows: int,
    columns: int,
    data_start,
    data_end,
    status: str,
    notes: str = ""
) -> None:

    query = text(
        """
        INSERT INTO core.dataset_registry
        (
            source_name,
            file_name,
            source_type,
            table_name,
            row_count,
            column_count,
            data_start,
            data_end,
            status,
            notes
        )

        VALUES
        (
            :source_name,
            :file_name,
            :source_type,
            :table_name,
            :row_count,
            :column_count,
            :data_start,
            :data_end,
            :status,
            :notes
        );
        """
    )

    source_type = file_path.suffix.lower()

    with engine.begin() as conn:

        conn.execute(
            query,
            {
                "source_name":
                    source,

                "file_name":
                    file_path.name,

                "source_type":
                    source_type,

                "table_name":
                    table_name,

                "row_count":
                    rows,

                "column_count":
                    columns,

                "data_start":
                    data_start,

                "data_end":
                    data_end,

                "status":
                    status,

                "notes":
                    notes,
            }
        )


# ============================================================
# LOAD INTO POSTGRESQL
# ============================================================

def load_dataframe(
    df: pd.DataFrame,
    table_name: str,
    append: bool = False
) -> None:

    if df.empty:

        raise ValueError(
            "DataFrame is empty."
        )

    df.to_sql(
        name=table_name,
        con=engine,
        schema="raw",
        if_exists="append" if append else "replace",
        index=False,
        chunksize=5000,
        method="multi",
    )


# ============================================================
# PROCESS ONE SOURCE FILE
# ============================================================

def process_file(
    path: Path,
    source: str,
    append: bool = False
) -> None:

    table_name = table_for_source(
        source
    )

    print()
    print("=" * 70)

    print(
        f"SOURCE : {source}"
    )

    print(
        f"FILE   : {path.name}"
    )

    try:

        # ----------------------------------------------------
        # DUPLICATE CHECK
        # ----------------------------------------------------

        if registry_contains(
            source,
            path.name
        ):

            print(
                "⏭ Already successfully loaded."
            )

            return

        # ----------------------------------------------------
        # READ
        # ----------------------------------------------------

        df = read_file(
            path
        )

        print(
            f"Rows read    : {len(df):,}"
        )

        print(
            f"Columns read : {len(df.columns):,}"
        )

        # ----------------------------------------------------
        # CLEAN
        # ----------------------------------------------------

        df = clean_dataframe(
            df
        )

        # ----------------------------------------------------
        # CLASSIFY AGAIN
        # ----------------------------------------------------

        detected_source = classify_source(
            path,
            df
        )

        if detected_source != source:

            print(
                f"⚠ Detection changed: "
                f"{source} → {detected_source}"
            )

        # ----------------------------------------------------
        # DATE RANGE
        # ----------------------------------------------------

        data_start, data_end = (
            detect_date_range(
                df
            )
        )

        # ----------------------------------------------------
        # LOAD
        # ----------------------------------------------------

        load_dataframe(
            df,
            table_name,
            append=append
        )

        # ----------------------------------------------------
        # REGISTER
        # ----------------------------------------------------

        register_dataset(
            source=source,
            file_path=path,
            table_name=table_name,
            rows=len(df),
            columns=len(df.columns),
            data_start=data_start,
            data_end=data_end,
            status="SUCCESS",
            notes=(
                f"Loaded from {path.name}"
            ),
        )

        print(
            f"✅ Loaded → raw.{table_name}"
        )

    except Exception as error:

        error_message = (
            f"{type(error).__name__}: {error}"
        )

        print(
            f"❌ FAILED: {error_message}"
        )

        traceback.print_exc()

        register_dataset(
            source=source,
            file_path=path,
            table_name=table_name,
            rows=0,
            columns=0,
            data_start=None,
            data_end=None,
            status="FAILED",
            notes=error_message,
        )


# ============================================================
# GROUP SOURCE FILES
# ============================================================

def group_sources(
    files: Iterable[Path]
) -> dict[str, list[Path]]:

    groups = {
        "github_engineering": [],
        "cloud_cost_usage": [],
        "cicd_runs": [],
        "ai_telemetry": [],
        "github_repositories": [],
    }

    for path in files:

        source = classify_source(
            path
        )

        if source is None:

            print(
                f"⚠ Unclassified: "
                f"{path.name}"
            )

            continue

        groups[source].append(
            path
        )

    return groups


# ============================================================
# MAIN SOURCE PROCESSING
# ============================================================

def process_source_group(
    source: str,
    files: list[Path]
) -> None:

    if not files:

        print()
        print(
            f"⚠ No files found for {source}"
        )

        return

    run_id = start_pipeline_run(
        source
    )

    total_rows = 0
    failures = 0

    # --------------------------------------------------------
    # We use REPLACE for the first file and APPEND afterwards.
    # This lets multiple AI / CI/CD files form one raw table.
    # --------------------------------------------------------

    first_loaded = False

    try:

        for path in files:

            before_failed = failures

            try:

                df = read_file(
                    path
                )

                df = clean_dataframe(
                    df
                )

                if df.empty:

                    print(
                        f"⚠ Empty file skipped: "
                        f"{path.name}"
                    )

                    continue

                table_name = table_for_source(
                    source
                )

                data_start, data_end = (
                    detect_date_range(
                        df
                    )
                )

                load_dataframe(
                    df,
                    table_name,
                    append=first_loaded
                )

                register_dataset(
                    source=source,
                    file_path=path,
                    table_name=table_name,
                    rows=len(df),
                    columns=len(df.columns),
                    data_start=data_start,
                    data_end=data_end,
                    status="SUCCESS",
                    notes=(
                        "Appended to shared raw table"
                        if first_loaded
                        else
                        "Initial load"
                    ),
                )

                print(
                    f"✅ {source}: "
                    f"{path.name} → "
                    f"raw.{table_name} "
                    f"({len(df):,} rows)"
                )

                total_rows += len(df)

                first_loaded = True

            except Exception as error:

                failures += 1

                error_message = (
                    f"{type(error).__name__}: {error}"
                )

                print(
                    f"❌ {source}: "
                    f"{path.name} → "
                    f"{error_message}"
                )

                register_dataset(
                    source=source,
                    file_path=path,
                    table_name=table_for_source(
                        source
                    ),
                    rows=0,
                    columns=0,
                    data_start=None,
                    data_end=None,
                    status="FAILED",
                    notes=error_message,
                )

            if failures > before_failed:

                continue

        status = (
            "SUCCESS"
            if failures == 0
            else
            "PARTIAL"
            if total_rows > 0
            else
            "FAILED"
        )

        finish_pipeline_run(
            run_id=run_id,
            status=status,
            records_processed=total_rows,
            records_failed=failures,
        )

    except Exception as error:

        error_message = (
            f"{type(error).__name__}: {error}"
        )

        finish_pipeline_run(
            run_id=run_id,
            status="FAILED",
            records_processed=total_rows,
            records_failed=failures,
            error_message=error_message,
        )

        raise


# ============================================================
# MAIN INGESTION
# ============================================================

def run_ingestion() -> None:

    print()
    print("=" * 75)

    print(
        "                ARCMATRIX INGESTION ENGINE"
    )

    print("=" * 75)

    print()
    print(
        f"Dataset root:\n{DATA_ROOT}"
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    print()
    print(
        "Connecting to PostgreSQL..."
    )

    with engine.connect() as conn:

        conn.execute(
            text(
                "SELECT current_database();"
            )
        )

    initialize_database()

    print(
        "✅ PostgreSQL connection successful."
    )

    # --------------------------------------------------------
    # FILE DISCOVERY
    # --------------------------------------------------------

    files = discover_files(
        DATA_ROOT
    )

    print()
    print(
        f"Files discovered: {len(files)}"
    )

    if not files:

        print(
            "❌ No supported files found."
        )

        return

    # --------------------------------------------------------
    # SOURCE GROUPING
    # --------------------------------------------------------

    groups = group_sources(
        files
    )

    print()
    print("Source classification:")

    for source, source_files in groups.items():

        print(
            f"  {source:<25} "
            f"{len(source_files)} file(s)"
        )

    # --------------------------------------------------------
    # PROCESS SOURCES
    # --------------------------------------------------------

    for source in (
        "github_engineering",
        "cloud_cost_usage",
        "cicd_runs",
        "ai_telemetry",
        "github_repositories",
    ):

        process_source_group(
            source,
            groups[source]
        )

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    print()
    print()
    print("=" * 75)

    print(
        "                 INGESTION COMPLETE"
    )

    print("=" * 75)

    with engine.connect() as conn:

        dataset_summary = conn.execute(
            text(
                """
                SELECT
                    status,
                    COUNT(*) AS count
                FROM core.dataset_registry
                GROUP BY status
                ORDER BY status;
                """
            )
        ).fetchall()

        table_summary = conn.execute(
            text(
                """
                SELECT
                    schemaname,
                    relname,
                    n_live_tup
                FROM pg_stat_user_tables
                WHERE schemaname = 'raw'
                ORDER BY relname;
                """
            )
        ).fetchall()

    print()
    print("Dataset registry status:")

    for row in dataset_summary:

        print(
            f"  {row.status:<10} "
            f"{row.count}"
        )

    print()
    print("RAW tables:")

    for row in table_summary:

        print(
            f"  raw.{row.relname} "
            f"~ {row.n_live_tup:,} rows"
        )

    print()
    print(
        "Schemas:"
    )

    print(
        "  raw       → source data"
    )

    print(
        "  core      → standardized/reference data"
    )

    print(
        "  analytics → ArcMatrix intelligence"
    )

    print()
    print("=" * 75)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_ingestion()