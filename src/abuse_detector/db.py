"""Persist one completed detection run in SQLite or PostgreSQL."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    create_engine,
    delete,
    event,
    insert,
    select,
    text,
)
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .data import load_dataset, parse_utc_timestamp
from .features import FEATURE_DEFINITIONS, FEATURE_FIELDS
from .graph import RING_FIELDS, load_account_scores

DEFAULT_DATABASE_URL = "sqlite:///./abuse_detector.db"


class Base(DeclarativeBase):
    pass


class DetectionRun(Base):
    __tablename__ = "detection_runs"
    __table_args__ = (CheckConstraint("status = 'complete'", name="ck_detection_runs_status"),)

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    artifact_versions: Mapped[dict[str, Any]] = mapped_column(JSON)
    counts: Mapped[dict[str, Any]] = mapped_column(JSON)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    timings_seconds: Mapped[dict[str, Any]] = mapped_column(JSON)
    outputs: Mapped[list[str]] = mapped_column(JSON)
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("label IS NULL OR label IN (0, 1)", name="ck_accounts_label"),
    )

    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("detection_runs.run_id", ondelete="CASCADE"), primary_key=True
    )
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    email_hash: Mapped[str] = mapped_column(String(128))
    phone_hash: Mapped[str] = mapped_column(String(128))
    device_id: Mapped[str] = mapped_column(String(128))
    ip_address: Mapped[str] = mapped_column(String(45))
    payment_instrument_id: Mapped[str] = mapped_column(String(128))
    label: Mapped[int | None] = mapped_column(Integer)
    ring_label: Mapped[str | None] = mapped_column(String(64))


class TransactionRecord(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        ForeignKeyConstraint(
            ("run_id", "account_id"),
            ("accounts.run_id", "accounts.account_id"),
            ondelete="CASCADE",
        ),
        CheckConstraint("amount >= 0", name="ck_transactions_amount"),
        CheckConstraint(
            "status IN ('succeeded', 'failed', 'refunded')", name="ck_transactions_status"
        ),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64))
    merchant_id: Mapped[str] = mapped_column(String(128))
    promotion_id: Mapped[str | None] = mapped_column(String(128))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))


class AccountResult(Base):
    __tablename__ = "account_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ("run_id", "account_id"),
            ("accounts.run_id", "accounts.account_id"),
            ondelete="CASCADE",
        ),
        CheckConstraint("ml_score BETWEEN 0 AND 1", name="ck_account_results_score"),
        CheckConstraint("predicted_label IN (0, 1)", name="ck_account_results_label"),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    features: Mapped[dict[str, float]] = mapped_column(JSON)
    ml_score: Mapped[float] = mapped_column(Float)
    predicted_label: Mapped[int] = mapped_column(Integer)
    reason_codes: Mapped[list[str]] = mapped_column(JSON)


class Ring(Base):
    __tablename__ = "rings"
    __table_args__ = (
        ForeignKeyConstraint(("run_id",), ("detection_runs.run_id",), ondelete="CASCADE"),
        CheckConstraint(
            "status IN ('new', 'reviewing', 'confirmed', 'dismissed')",
            name="ck_rings_status",
        ),
        CheckConstraint("score BETWEEN 0 AND 1", name="ck_rings_score"),
        CheckConstraint("member_count >= 2", name="ck_rings_member_count"),
        CheckConstraint(
            "density BETWEEN 0 AND 1 AND promotion_concentration BETWEEN 0 AND 1 "
            "AND mean_ml_score BETWEEN 0 AND 1 AND max_ml_score BETWEEN 0 AND 1 "
            "AND temporal_concentration BETWEEN 0 AND 1",
            name="ck_rings_metrics",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ring_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="new", server_default="new")
    member_count: Mapped[int] = mapped_column(Integer)
    shared_entity_count: Mapped[int] = mapped_column(Integer)
    entity_types: Mapped[list[str]] = mapped_column(JSON)
    density: Mapped[float] = mapped_column(Float)
    promotion_concentration: Mapped[float] = mapped_column(Float)
    mean_ml_score: Mapped[float] = mapped_column(Float)
    max_ml_score: Mapped[float] = mapped_column(Float)
    temporal_concentration: Mapped[float] = mapped_column(Float)
    reason_codes: Mapped[list[str]] = mapped_column(JSON)


class RingMember(Base):
    __tablename__ = "ring_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ("run_id", "ring_id"), ("rings.run_id", "rings.ring_id"), ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ("run_id", "account_id"),
            ("accounts.run_id", "accounts.account_id"),
            ondelete="CASCADE",
        ),
        CheckConstraint("ml_score BETWEEN 0 AND 1", name="ck_ring_members_score"),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ring_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ml_score: Mapped[float] = mapped_column(Float)
    reason_codes: Mapped[list[str]] = mapped_column(JSON)


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        ForeignKeyConstraint(
            ("run_id", "ring_id"), ("rings.run_id", "rings.ring_id"), ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ("run_id", "source_account_id"),
            ("accounts.run_id", "accounts.account_id"),
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "relationship_type IN "
            "('device', 'ip', 'payment_instrument', 'email', 'phone', 'merchant', 'promotion')",
            name="ck_relationships_type",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ring_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    relationship_type: Mapped[str] = mapped_column(String(32), primary_key=True)


def create_database_engine(database_url: str | None = None) -> Engine:
    url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False}
        if make_url(url).get_backend_name() == "sqlite"
        else {},
    )
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def load_pipeline_run(
    run_dir: Path,
    engine: Engine | None = None,
    *,
    if_empty: bool = False,
    if_missing: bool = False,
) -> dict[str, object]:
    if if_empty and if_missing:
        raise ValueError("if_empty and if_missing are mutually exclusive")
    engine = engine or create_database_engine()
    if if_empty or if_missing:
        with Session(engine) as session:
            query = select(DetectionRun.run_id)
            if if_missing:
                query = query.where(DetectionRun.run_id == run_dir.name)
            existing_run_id = session.scalar(query.limit(1))
        if existing_run_id is not None:
            return {"run_id": existing_run_id, "skipped": True}

    bundle = _read_run(run_dir)
    report = bundle["report"]
    run_id = report["run_id"]

    with Session(engine) as session, session.begin():
        existing = session.scalar(select(DetectionRun.run_id).where(DetectionRun.run_id == run_id))
        statuses = dict(
            session.execute(select(Ring.ring_id, Ring.status).where(Ring.run_id == run_id)).all()
        )
        session.execute(delete(DetectionRun).where(DetectionRun.run_id == run_id))
        session.execute(
            insert(DetectionRun),
            [
                {
                    "run_id": run_id,
                    "schema_version": report["schema_version"],
                    "status": report["status"],
                    "configuration": report["configuration"],
                    "artifact_versions": report["artifact_versions"],
                    "counts": report["counts"],
                    "metrics": report["metrics"],
                    "timings_seconds": report["timings_seconds"],
                    "outputs": report["outputs"],
                }
            ],
        )
        session.execute(insert(Account), bundle["accounts"])
        session.execute(insert(TransactionRecord), bundle["transactions"])
        session.execute(insert(AccountResult), bundle["account_results"])
        session.execute(
            insert(Ring),
            [
                {**ring, "status": statuses.get(ring["ring_id"], "new")}
                for ring in bundle["rings"]
            ],
        )
        session.execute(insert(RingMember), bundle["members"])
        session.execute(insert(Relationship), bundle["relationships"])

    return {
        "run_id": run_id,
        "replaced": existing is not None,
        "skipped": False,
        "counts": report["counts"],
    }


def _read_run(run_dir: Path) -> dict[str, Any]:
    try:
        report = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{run_dir}: missing or invalid run.json") from error
    if report.get("status") != "complete" or report.get("run_id") != run_dir.name:
        raise ValueError(f"{run_dir}: run must be complete and match its directory name")
    outputs = report.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError(f"{run_dir}: invalid output manifest")
    for relative in outputs:
        path = Path(relative) if isinstance(relative, str) else Path("..")
        if path.is_absolute() or ".." in path.parts or not (run_dir / path).is_file():
            raise ValueError(f"{run_dir}: invalid or missing output {relative!r}")

    accounts, transactions = load_dataset(
        run_dir / "raw/accounts.csv", run_dir / "raw/transactions.csv"
    )
    run_id = report["run_id"]
    account_ids = {account.account_id for account in accounts}
    feature_rows = _index_rows(
        _read_rows(run_dir / "processed/account_features.csv", FEATURE_FIELDS),
        "account_id",
        run_dir / "processed/account_features.csv",
    )
    if set(feature_rows) != account_ids:
        raise ValueError("feature IDs do not match source account IDs")
    scores = load_account_scores(run_dir / "artifacts/account_scores.csv", account_ids)
    ring_rows = _read_rows(run_dir / "rings/rings.csv", RING_FIELDS)
    member_rows = _read_rows(
        run_dir / "rings/ring_members.csv",
        ("ring_id", "account_id", "ml_score", "reason_codes"),
    )
    edge_rows = _read_rows(
        run_dir / "rings/graph_edges.csv",
        ("ring_id", "source", "target", "relationship_type"),
    )
    actual_counts = {
        "accounts": len(accounts),
        "transactions": len(transactions),
        "features": len(feature_rows),
        "account_scores": len(scores),
        "rings": len(ring_rows),
    }
    if report.get("counts") != actual_counts:
        raise ValueError(f"{run_dir}: recorded counts do not match its outputs")

    return {
        "report": report,
        "accounts": [
            {
                "run_id": run_id,
                "account_id": account.account_id,
                "created_at": parse_utc_timestamp(account.created_at),
                "email_hash": account.email_hash,
                "phone_hash": account.phone_hash,
                "device_id": account.device_id,
                "ip_address": account.ip_address,
                "payment_instrument_id": account.payment_instrument_id,
                "label": account.label,
                "ring_label": account.ring_label or None,
            }
            for account in accounts
        ],
        "transactions": [
            {
                "run_id": run_id,
                "transaction_id": transaction.transaction_id,
                "account_id": transaction.account_id,
                "merchant_id": transaction.merchant_id,
                "promotion_id": transaction.promotion_id or None,
                "amount": Decimal(transaction.amount),
                "created_at": parse_utc_timestamp(transaction.created_at),
                "status": transaction.status,
            }
            for transaction in transactions
        ],
        "account_results": [
            {
                "run_id": run_id,
                "account_id": account_id,
                "features": {
                    name: _finite_float(feature_rows[account_id][name], f"{account_id} {name}")
                    for name in FEATURE_DEFINITIONS
                },
                "ml_score": scores[account_id]["ml_score"],
                "predicted_label": scores[account_id]["predicted_label"],
                "reason_codes": _split_codes(str(scores[account_id]["reason_codes"])),
            }
            for account_id in sorted(account_ids)
        ],
        "rings": [
            {
                "run_id": run_id,
                "ring_id": row["ring_id"],
                "score": _finite_float(row["score"], f"{row['ring_id']} score"),
                "member_count": int(row["member_count"]),
                "shared_entity_count": int(row["shared_entity_count"]),
                "entity_types": _split_codes(row["entity_types"]),
                "density": _finite_float(row["density"], f"{row['ring_id']} density"),
                "promotion_concentration": _finite_float(
                    row["promotion_concentration"], f"{row['ring_id']} promotion_concentration"
                ),
                "mean_ml_score": _finite_float(
                    row["mean_ml_score"], f"{row['ring_id']} mean_ml_score"
                ),
                "max_ml_score": _finite_float(
                    row["max_ml_score"], f"{row['ring_id']} max_ml_score"
                ),
                "temporal_concentration": _finite_float(
                    row["temporal_concentration"], f"{row['ring_id']} temporal_concentration"
                ),
                "reason_codes": _split_codes(row["reason_codes"]),
            }
            for row in ring_rows
        ],
        "members": [
            {
                "run_id": run_id,
                "ring_id": row["ring_id"],
                "account_id": row["account_id"],
                "ml_score": _finite_float(row["ml_score"], "ring member ml_score"),
                "reason_codes": _split_codes(row["reason_codes"]),
            }
            for row in member_rows
        ],
        "relationships": [
            {
                "run_id": run_id,
                "ring_id": row["ring_id"],
                "source_account_id": row["source"],
                "target_id": row["target"],
                "relationship_type": row["relationship_type"],
            }
            for row in edge_rows
        ],
    }


def _read_rows(path: Path, expected_fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != expected_fields:
            raise ValueError(f"{path}: unexpected columns")
        rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError(f"{path}: row contains extra columns")
    return rows


def _index_rows(
    rows: list[dict[str, str]], key: str, path: Path
) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(rows, start=2):
        value = row[key]
        if not value or value in indexed:
            raise ValueError(f"{path}:{row_number}: missing or duplicate {key}")
        indexed[value] = row
    return indexed


def _finite_float(value: str, location: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{location}: expected a number") from error
    if not math.isfinite(parsed):
        raise ValueError(f"{location}: expected a finite number")
    return parsed


def _split_codes(value: str) -> list[str]:
    return value.split(";") if value else []


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--database-url")
    skip = parser.add_mutually_exclusive_group()
    skip.add_argument(
        "--if-empty",
        action="store_true",
        help="skip loading when the database already contains a detection run",
    )
    skip.add_argument(
        "--if-missing",
        action="store_true",
        help="skip loading when this run ID already exists",
    )
    args = parser.parse_args(argv)
    result = load_pipeline_run(
        args.run_dir,
        create_database_engine(args.database_url),
        if_empty=args.if_empty,
        if_missing=args.if_missing,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
