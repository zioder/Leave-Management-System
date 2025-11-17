"""
Utilities for converting the provided Excel workbook into normalized CSV
artifacts that can be ingested by the streaming pipeline.

The workbook is expected to contain rows with at least the following columns:

- Employee Name
- Department
- Position
- Leave Type
- Start Date
- End Date
- Days Taken
- Total Leave Entitlement
- Leave Taken So Far
- Remaining Leaves

Run as a script to generate two CSV files under `data/`:

1. `seed_engineers.csv` – one row per employee with allowance metadata.
2. `seed_leave_events.csv` – synthetic event log for the streaming simulator.
"""
from __future__ import annotations

import argparse
import pathlib
from datetime import datetime
from typing import Iterable

import pandas as pd


DEFAULT_INPUT = pathlib.Path("employee leave tracking data.xlsx")
DEFAULT_OUTPUT_DIR = pathlib.Path("data")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names so downstream code can rely on them."""
    rename_map = {
        "Employee Name": "employee_name",
        "Department": "department",
        "Position": "position",
        "Leave Type": "leave_type",
        "Start Date": "start_date",
        "End Date": "end_date",
        "Days Taken": "days_taken",
        "Total Leave Entitlement": "total_entitlement",
        "Leave Taken So Far": "taken_to_date",
        "Remaining Leaves": "remaining_leaves",
    }
    missing = [col for col in rename_map if col not in df.columns]
    if missing:
        raise ValueError(f"Input workbook is missing columns: {missing}")
    df = df.rename(columns=rename_map)
    df["employee_id"] = (
        df["employee_name"]
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "-", regex=True)
        .str.strip("-")
    )
    return df


def build_employee_dimension(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate static employee attributes plus allowance totals."""
    aggregations = {
        "department": "first",
        "position": "first",
        "total_entitlement": "max",
        "taken_to_date": "max",
        "remaining_leaves": "max",
    }
    employees = df.groupby("employee_id", as_index=False).agg(aggregations)
    employees["annual_allowance"] = employees["total_entitlement"]
    employees["carried_over"] = (
        employees["annual_allowance"] - employees["taken_to_date"] - employees["remaining_leaves"]
    ).clip(lower=0)
    employees["updated_at"] = datetime.utcnow().isoformat()
    employees["status"] = employees["remaining_leaves"].apply(
        lambda remaining: "ACTIVE" if remaining > 0 else "NO_BALANCE"
    )
    return employees[
        [
            "employee_id",
            "department",
            "position",
            "annual_allowance",
            "carried_over",
            "taken_to_date",
            "remaining_leaves",
            "status",
            "updated_at",
        ]
    ]


def build_leave_events(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expand the raw rows into a synthetic event log that the Kafka producer can
    replay. Each original row spawns two events: request_created and the final
    state (approved by default).
    """
    request_events = []
    for idx, row in df.iterrows():
        request_id = f"{row.employee_id}-{idx:05d}"
        base_event = {
            "request_id": request_id,
            "employee_id": row.employee_id,
            "leave_type": row.leave_type,
            "start_date": pd.to_datetime(row.start_date).date().isoformat(),
            "end_date": pd.to_datetime(row.end_date).date().isoformat(),
            "days": int(row.days_taken),
            "created_at": datetime.utcnow().isoformat(),
        }
        request_events.append({**base_event, "event_type": "request_created", "status": "PENDING"})
        request_events.append(
            {
                **base_event,
                "event_type": "request_approved",
                "status": "APPROVED",
                "approved_at": datetime.utcnow().isoformat(),
            }
        )
    return pd.DataFrame(request_events)


def write_csv(df: pd.DataFrame, path: pathlib.Path, order: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, columns=list(order))
    print(f"Wrote {len(df)} rows to {path}")  # noqa: T201 - intentional CLI output


def main(input_path: pathlib.Path, output_dir: pathlib.Path) -> None:
    sheet = pd.read_excel(input_path)
    normalized = _normalize_columns(sheet)
    employees = build_employee_dimension(normalized)
    events = build_leave_events(normalized)
    write_csv(
        employees,
        output_dir / "seed_engineers.csv",
        order=[
            "employee_id",
            "department",
            "position",
            "annual_allowance",
            "carried_over",
            "taken_to_date",
            "remaining_leaves",
            "status",
            "updated_at",
        ],
    )
    write_csv(
        events,
        output_dir / "seed_leave_events.csv",
        order=[
            "request_id",
            "employee_id",
            "leave_type",
            "start_date",
            "end_date",
            "days",
            "event_type",
            "status",
            "created_at",
            "approved_at",
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normalize the Excel workbook into ingestion CSV files.")
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=pathlib.Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    main(args.input, args.output_dir)



