"""
Kafka producer that replays the synthetic leave events generated during data
preparation. The script publishes JSON payloads so that downstream services
can ingest them with minimal transformation.

Usage:
    python -m simulation.kafka_producer --csv data/seed_leave_events.csv
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time
from typing import Iterable

import pandas as pd
from kafka import KafkaProducer

from src.config import load as load_config


def _serialize(record: dict) -> bytes:
    return json.dumps(record, separators=(",", ":")).encode("utf-8")


def iter_records(csv_path: pathlib.Path) -> Iterable[dict]:
    df = pd.read_csv(csv_path)
    for row in df.to_dict(orient="records"):
        # pandas converts NaN to float; replace with None for JSON serialization
        yield {key: (None if isinstance(value, float) and pd.isna(value) else value) for key, value in row.items()}


def main(csv_path: pathlib.Path, linger: float) -> None:
    cfg = load_config()
    producer = KafkaProducer(
        bootstrap_servers=cfg.kafka_bootstrap.split(","),
        value_serializer=_serialize,
        key_serializer=lambda value: value.encode("utf-8"),
        linger_ms=int(linger * 1000),
    )
    try:
        for record in iter_records(csv_path):
            key = record["employee_id"]
            producer.send(cfg.kafka_topic, key=key, value=record)
            print(f"sent {record['event_type']} for {key}")  # noqa: T201
            time.sleep(linger)
    finally:
        producer.flush()
        producer.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay leave events into Kafka.")
    parser.add_argument("--csv", type=pathlib.Path, default=pathlib.Path("data/seed_leave_events.csv"))
    parser.add_argument("--linger", type=float, default=1.0, help="Seconds to wait between messages.")
    args = parser.parse_args()
    main(args.csv, args.linger)


