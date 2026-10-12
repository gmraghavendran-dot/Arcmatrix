from pathlib import Path
import os
import re

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.types import Text


load_dotenv()


# ============================================================
# CONFIG
# ============================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "arcmatrix")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")


DATA_ROOT = Path(
    r"C:\Users\Rashmita\Downloads\ArcMatrix dataset"
)


# ============================================================
# DATABASE
# ============================================================

if not DB_PASSWORD:
    raise RuntimeError(
        "DB_PASSWORD missing in .env"
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


# ============================================================
# FIND GHPR FILE
# ============================================================

files = list(
    DATA_ROOT.glob("ghpr*")
)

if not files:
    raise FileNotFoundError(
        "No GHPR file found in ArcMatrix dataset folder."
    )

ghpr_file = files[0]

print()
print("=" * 70)
print("             ARCMATRIX GITHUB RAW LOADER")
print("=" * 70)

print()
print("File:")
print(ghpr_file)


# ============================================================
# READ
# ============================================================

suffix = ghpr_file.suffix.lower()

if suffix in {".xlsx", ".xls"}:

    df = pd.read_excel(
        ghpr_file
    )

else:

    df = pd.read_csv(
        ghpr_file,
        low_memory=False
    )


print()
print(
    f"Rows    : {len(df):,}"
)

print(
    f"Columns : {len(df.columns):,}"
)


# ============================================================
# NORMALIZE COLUMN NAMES
# ============================================================

columns = []

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

    columns.append(name)


# Duplicate handling

counts = {}
final_columns = []

for name in columns:

    if name not in counts:

        counts[name] = 0
        final_columns.append(name)

    else:

        counts[name] += 1

        final_columns.append(
            f"{name}_{counts[name]}"
        )


df.columns = final_columns


# ============================================================
# CLEAN
# ============================================================

df = df.replace(
    r"^\s*$",
    pd.NA,
    regex=True
)


# ============================================================
# LOAD
# ============================================================

print()
print(
    "Loading → raw.github_engineering"
)

dtype_map = {
    column: Text()
    for column in df.columns
}


df.to_sql(
    name="github_engineering",
    con=engine,
    schema="raw",
    if_exists="replace",
    index=False,
    chunksize=5000,
    method="multi",
    dtype=dtype_map,
)


print(
    "✅ raw.github_engineering created."
)


# ============================================================
# VERIFY
# ============================================================

with engine.connect() as conn:

    from sqlalchemy import text

    count = conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM raw.github_engineering;
            """
        )
    ).scalar_one()


print()
print(
    f"✅ Verified rows: {count:,}"
)

print()
print("=" * 70)
print("              GITHUB LOAD COMPLETE")
print("=" * 70)