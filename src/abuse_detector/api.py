"""FastAPI service for reviewing the latest loaded detection run."""

from __future__ import annotations

import os
import tempfile
import threading
import uuid
from collections.abc import Iterator
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import and_, exists, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from . import __version__
from .data import DataValidationError, load_dataset
from .db import (
    Account,
    AccountResult,
    DetectionRun,
    Relationship,
    Ring,
    RingMember,
    TransactionRecord,
    create_database_engine,
    load_pipeline_run,
)
from .pipeline import run_pipeline

ReviewStatus = Literal["new", "reviewing", "confirmed", "dismissed"]
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ACCOUNT_ROWS = 5_000
MAX_TRANSACTION_ROWS = 25_000
DEFAULT_MODEL_ARTIFACT = Path("runs/demo/artifacts/model.pkl")

# ponytail: one process-wide lock, because the Buildathon deployment is a single
# uvicorn process sharing one workspace, so in-process mutual exclusion is the
# whole story. Move to a DB advisory lock if this ever runs more than one worker.
_analysis_lock = threading.Lock()
VALID_TRANSITIONS: dict[str, set[str]] = {
    "new": {"new", "reviewing"},
    "reviewing": {"new", "reviewing", "confirmed", "dismissed"},
    "confirmed": {"confirmed", "reviewing"},
    "dismissed": {"dismissed", "reviewing"},
}


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]
    run_id: str | None


class SummaryResponse(BaseModel):
    run_id: str
    account_count: int
    transaction_count: int
    scored_account_count: int
    flagged_account_count: int
    ring_count: int
    score_distribution: dict[str, int]
    review_status_totals: dict[str, int]


class RingItem(BaseModel):
    ring_id: str
    score: float
    status: ReviewStatus
    created_at: datetime
    member_count: int
    shared_entity_count: int
    entity_types: list[str]
    promotion_ids: list[str]
    reason_codes: list[str]


class RingPage(BaseModel):
    items: list[RingItem]
    page: int
    page_size: int
    total: int


class RingMemberOut(BaseModel):
    account_id: str
    ml_score: float
    reason_codes: list[str]


class GraphNode(BaseModel):
    id: str
    type: str
    label: str


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class SharedEntity(BaseModel):
    id: str
    type: str
    label: str


class RingDetail(RingItem):
    density: float
    promotion_concentration: float
    mean_ml_score: float
    max_ml_score: float
    temporal_concentration: float
    detection_resilience: Literal["low", "moderate", "high"] | None
    min_entity_removals: int | None
    critical_entity_types: list[str]
    members: list[RingMemberOut]
    shared_entities: list[SharedEntity]
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class TransactionOut(BaseModel):
    transaction_id: str
    merchant_id: str
    promotion_id: str | None
    amount: float
    created_at: datetime
    status: Literal["succeeded", "failed", "refunded"]


class AccountDetail(BaseModel):
    account_id: str
    created_at: datetime
    email_hash: str
    phone_hash: str
    device_id: str
    ip_address: str
    payment_instrument_id: str
    ml_score: float
    predicted_label: int
    reason_codes: list[str]
    features: dict[str, float]
    ring_ids: list[str]
    transactions: list[TransactionOut]


class ReviewStatusUpdate(BaseModel):
    status: ReviewStatus


class ReviewStatusResponse(BaseModel):
    ring_id: str
    status: ReviewStatus


class AnalyzeResponse(BaseModel):
    run_id: str
    account_count: int
    transaction_count: int
    ring_count: int
    labels_available: bool


def create_app(
    *,
    engine: Engine | None = None,
    database_url: str | None = None,
    allowed_origins: list[str] | None = None,
    model_artifact: Path | None = None,
) -> FastAPI:
    engine = engine or create_database_engine(database_url)
    model_artifact = model_artifact or Path(
        os.getenv("MODEL_ARTIFACT", str(DEFAULT_MODEL_ARTIFACT))
    )
    if allowed_origins is None:
        allowed_origins = [
            origin.strip()
            for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        ]
    app = FastAPI(title="Razorpay Abuse Ring Detector", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "PATCH", "POST"],
        allow_headers=["Content-Type"],
    )

    def get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
    def health(session: Session = Depends(get_session)) -> dict[str, object]:
        try:
            run_id = session.scalar(
                select(DetectionRun.run_id)
                .order_by(DetectionRun.loaded_at.desc(), DetectionRun.run_id.desc())
                .limit(1)
            )
        except SQLAlchemyError as error:
            raise HTTPException(status_code=503, detail="Database unavailable") from error
        return {"status": "ok", "database": "ok", "run_id": run_id}

    @app.get("/api/v1/summary", response_model=SummaryResponse, tags=["review"])
    def summary(session: Session = Depends(get_session)) -> dict[str, object]:
        run_id = _current_run_id(session)
        scores = list(session.scalars(select(Ring.score).where(Ring.run_id == run_id)))
        status_totals = {status: 0 for status in VALID_TRANSITIONS}
        for status, count in session.execute(
            select(Ring.status, func.count()).where(Ring.run_id == run_id).group_by(Ring.status)
        ):
            status_totals[status] = count
        return {
            "run_id": run_id,
            "account_count": _count(session, Account, run_id),
            "transaction_count": _count(session, TransactionRecord, run_id),
            "scored_account_count": _count(session, AccountResult, run_id),
            "flagged_account_count": session.scalar(
                select(func.count())
                .select_from(AccountResult)
                .where(AccountResult.run_id == run_id, AccountResult.predicted_label == 1)
            ),
            "ring_count": len(scores),
            "score_distribution": {
                "low": sum(score < 0.5 for score in scores),
                "medium": sum(0.5 <= score < 0.8 for score in scores),
                "high": sum(score >= 0.8 for score in scores),
            },
            "review_status_totals": status_totals,
        }

    @app.get("/api/v1/rings", response_model=RingPage, tags=["review"])
    def list_rings(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        min_score: float = Query(0, ge=0, le=1, description="Minimum ring score, inclusive."),
        status: ReviewStatus | None = Query(None, description="Exact review status."),
        promotion: str | None = Query(
            None, min_length=1, max_length=128, description="Exact promotion ID."
        ),
        date_from: date | None = Query(
            None, description="Earliest member signup date, inclusive."
        ),
        date_to: date | None = Query(
            None, description="Latest member signup date, inclusive."
        ),
        session: Session = Depends(get_session),
    ) -> dict[str, object]:
        if date_from and date_to and date_from > date_to:
            raise HTTPException(status_code=422, detail="date_from must not be after date_to")
        run_id = _current_run_id(session)
        ring_dates = _ring_dates()
        conditions = [Ring.run_id == run_id, Ring.score >= min_score]
        if status:
            conditions.append(Ring.status == status)
        if promotion:
            conditions.append(
                exists(
                    select(TransactionRecord.transaction_id)
                    .join(
                        RingMember,
                        and_(
                            RingMember.run_id == TransactionRecord.run_id,
                            RingMember.account_id == TransactionRecord.account_id,
                        ),
                    )
                    .where(
                        RingMember.run_id == Ring.run_id,
                        RingMember.ring_id == Ring.ring_id,
                        TransactionRecord.promotion_id == promotion,
                    )
                )
            )
        if date_from:
            conditions.append(
                ring_dates.c.created_at >= datetime.combine(date_from, time.min, timezone.utc)
            )
        if date_to:
            conditions.append(
                ring_dates.c.created_at <= datetime.combine(date_to, time.max, timezone.utc)
            )
        join_condition = and_(
            ring_dates.c.run_id == Ring.run_id, ring_dates.c.ring_id == Ring.ring_id
        )
        total = session.scalar(
            select(func.count()).select_from(Ring).join(ring_dates, join_condition).where(*conditions)
        )
        rows = session.execute(
            select(Ring, ring_dates.c.created_at)
            .join(ring_dates, join_condition)
            .where(*conditions)
            .order_by(Ring.score.desc(), Ring.ring_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        promotions = _promotions_by_ring(session, run_id, [ring.ring_id for ring, _ in rows])
        return {
            "items": [
                _ring_item(ring, created_at, promotions.get(ring.ring_id, []))
                for ring, created_at in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    @app.get("/api/v1/rings/{ring_id}", response_model=RingDetail, tags=["review"])
    def ring_detail(ring_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        run_id = _current_run_id(session)
        ring = session.get(Ring, (run_id, ring_id))
        if ring is None:
            raise HTTPException(status_code=404, detail="Ring not found")
        members = list(
            session.scalars(
                select(RingMember)
                .where(RingMember.run_id == run_id, RingMember.ring_id == ring_id)
                .order_by(RingMember.account_id)
            )
        )
        relationships = list(
            session.scalars(
                select(Relationship)
                .where(Relationship.run_id == run_id, Relationship.ring_id == ring_id)
                .order_by(
                    Relationship.relationship_type,
                    Relationship.source_account_id,
                    Relationship.target_id,
                )
            )
        )
        created_at = session.scalar(
            select(func.min(Account.created_at))
            .join(
                RingMember,
                and_(
                    RingMember.run_id == Account.run_id,
                    RingMember.account_id == Account.account_id,
                ),
            )
            .where(RingMember.run_id == run_id, RingMember.ring_id == ring_id)
        )
        entities = sorted(
            {(item.target_id, item.relationship_type) for item in relationships},
            key=lambda item: (item[1], item[0]),
        )
        promotions = _promotions_by_ring(session, run_id, [ring_id])[ring_id]
        return {
            **_ring_item(ring, created_at, promotions),
            "density": ring.density,
            "promotion_concentration": ring.promotion_concentration,
            "mean_ml_score": ring.mean_ml_score,
            "max_ml_score": ring.max_ml_score,
            "temporal_concentration": ring.temporal_concentration,
            "detection_resilience": ring.detection_resilience,
            "min_entity_removals": ring.min_entity_removals,
            "critical_entity_types": ring.critical_entity_types or [],
            "members": [
                {
                    "account_id": member.account_id,
                    "ml_score": member.ml_score,
                    "reason_codes": member.reason_codes,
                }
                for member in members
            ],
            "shared_entities": [
                {"id": entity_id, "type": entity_type, "label": _entity_label(entity_id)}
                for entity_id, entity_type in entities
            ],
            "nodes": [
                *[
                    {"id": member.account_id, "type": "account", "label": member.account_id}
                    for member in members
                ],
                *[
                    {"id": entity_id, "type": entity_type, "label": _entity_label(entity_id)}
                    for entity_id, entity_type in entities
                ],
            ],
            "edges": [
                {
                    "source": relationship.source_account_id,
                    "target": relationship.target_id,
                    "type": relationship.relationship_type,
                }
                for relationship in relationships
            ],
        }

    @app.patch(
        "/api/v1/rings/{ring_id}/status",
        response_model=ReviewStatusResponse,
        tags=["review"],
    )
    def update_ring_status(
        ring_id: str,
        update: ReviewStatusUpdate,
        session: Session = Depends(get_session),
    ) -> dict[str, str]:
        run_id = _current_run_id(session)
        ring = session.get(Ring, (run_id, ring_id))
        if ring is None:
            raise HTTPException(status_code=404, detail="Ring not found")
        if update.status not in VALID_TRANSITIONS[ring.status]:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot move ring from {ring.status!r} to {update.status!r}",
            )
        ring.status = update.status
        session.commit()
        return {"ring_id": ring_id, "status": ring.status}

    @app.get("/api/v1/accounts/{account_id}", response_model=AccountDetail, tags=["review"])
    def account_detail(
        account_id: str, session: Session = Depends(get_session)
    ) -> dict[str, object]:
        run_id = _current_run_id(session)
        account = session.get(Account, (run_id, account_id))
        result = session.get(AccountResult, (run_id, account_id))
        if account is None or result is None:
            raise HTTPException(status_code=404, detail="Account not found")
        transactions = list(
            session.scalars(
                select(TransactionRecord)
                .where(
                    TransactionRecord.run_id == run_id,
                    TransactionRecord.account_id == account_id,
                )
                .order_by(TransactionRecord.created_at, TransactionRecord.transaction_id)
            )
        )
        ring_ids = list(
            session.scalars(
                select(RingMember.ring_id)
                .where(RingMember.run_id == run_id, RingMember.account_id == account_id)
                .order_by(RingMember.ring_id)
            )
        )
        return {
            "account_id": account.account_id,
            "created_at": _as_utc(account.created_at),
            "email_hash": account.email_hash,
            "phone_hash": account.phone_hash,
            "device_id": account.device_id,
            "ip_address": account.ip_address,
            "payment_instrument_id": account.payment_instrument_id,
            "ml_score": result.ml_score,
            "predicted_label": result.predicted_label,
            "reason_codes": result.reason_codes,
            "features": result.features,
            "ring_ids": ring_ids,
            "transactions": [
                {
                    "transaction_id": transaction.transaction_id,
                    "merchant_id": transaction.merchant_id,
                    "promotion_id": transaction.promotion_id,
                    "amount": float(transaction.amount),
                    "created_at": _as_utc(transaction.created_at),
                    "status": transaction.status,
                }
                for transaction in transactions
            ],
        }

    @app.post("/api/v1/analyze", response_model=AnalyzeResponse, tags=["review"])
    async def analyze(
        accounts: UploadFile = File(..., description="accounts.csv, UTF-8"),
        transactions: UploadFile = File(..., description="transactions.csv, UTF-8"),
    ) -> dict[str, object]:
        payloads = {
            "accounts.csv": await _read_upload(accounts, "accounts.csv"),
            "transactions.csv": await _read_upload(transactions, "transactions.csv"),
        }
        if not _analysis_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Another analysis is already running")
        try:
            return await run_in_threadpool(_analyze, payloads, engine, model_artifact)
        finally:
            _analysis_lock.release()

    return app


async def _read_upload(upload: UploadFile, name: str) -> str:
    """Buffer one upload under the size cap and decode it as UTF-8 text."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(64 * 1024):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"{name} exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
            )
        chunks.append(chunk)
    if not total:
        raise HTTPException(status_code=400, detail=f"{name} is empty")
    try:
        return b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=400, detail=f"{name} must be UTF-8 encoded") from error


def _analyze(
    payloads: dict[str, str], engine: Engine, model_artifact: Path
) -> dict[str, object]:
    """Score uploaded CSVs with the existing model and make the result active."""
    if not model_artifact.is_file():
        raise HTTPException(status_code=503, detail="No trained model artifact available")
    run_id = f"upload_{uuid.uuid4().hex}"
    # Raw uploads live only inside this directory, so they are gone once the request ends.
    with tempfile.TemporaryDirectory(prefix="analyze-") as temporary:
        workspace = Path(temporary)
        source = workspace / "source"
        source.mkdir()
        for name, text in payloads.items():
            (source / name).write_text(text, encoding="utf-8")

        try:
            accounts, transaction_rows = load_dataset(
                source / "accounts.csv", source / "transactions.csv"
            )
        except DataValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        _require_row_limit(len(accounts), MAX_ACCOUNT_ROWS, "accounts.csv")
        _require_row_limit(len(transaction_rows), MAX_TRANSACTION_ROWS, "transactions.csv")

        try:
            report = run_pipeline(
                workspace / "runs",
                run_id,
                model_artifact=model_artifact,
                source_dir=source,
            )
        except DataValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        load_pipeline_run(workspace / "runs" / run_id, engine)

    counts = report["counts"]
    return {
        "run_id": run_id,
        "account_count": counts["accounts"],
        "transaction_count": counts["transactions"],
        "ring_count": counts["rings"],
        # Partially labelled data is not usable ground truth, so it counts as unavailable.
        "labels_available": bool(accounts)
        and all(account.label is not None for account in accounts),
    }


def _require_row_limit(count: int, limit: int, name: str) -> None:
    if count > limit:
        raise HTTPException(
            status_code=413, detail=f"{name} has {count} rows, more than the {limit} row limit"
        )


def _current_run_id(session: Session) -> str:
    run_id = session.scalar(
        select(DetectionRun.run_id)
        .order_by(DetectionRun.loaded_at.desc(), DetectionRun.run_id.desc())
        .limit(1)
    )
    if run_id is None:
        raise HTTPException(status_code=503, detail="No detection run loaded")
    return run_id


def _count(session: Session, model: object, run_id: str) -> int:
    return session.scalar(select(func.count()).select_from(model).where(model.run_id == run_id))


def _ring_dates() -> object:
    return (
        select(
            RingMember.run_id.label("run_id"),
            RingMember.ring_id.label("ring_id"),
            func.min(Account.created_at).label("created_at"),
        )
        .join(
            Account,
            and_(
                Account.run_id == RingMember.run_id,
                Account.account_id == RingMember.account_id,
            ),
        )
        .group_by(RingMember.run_id, RingMember.ring_id)
        .subquery()
    )


def _promotions_by_ring(
    session: Session, run_id: str, ring_ids: list[str]
) -> dict[str, list[str]]:
    promotions = {ring_id: [] for ring_id in ring_ids}
    if not ring_ids:
        return promotions
    for ring_id, promotion_id in session.execute(
        select(RingMember.ring_id, TransactionRecord.promotion_id)
        .join(
            TransactionRecord,
            and_(
                TransactionRecord.run_id == RingMember.run_id,
                TransactionRecord.account_id == RingMember.account_id,
            ),
        )
        .where(
            RingMember.run_id == run_id,
            RingMember.ring_id.in_(ring_ids),
            TransactionRecord.promotion_id.is_not(None),
        )
        .distinct()
        .order_by(RingMember.ring_id, TransactionRecord.promotion_id)
    ):
        promotions[ring_id].append(promotion_id)
    return promotions


def _ring_item(ring: Ring, created_at: datetime, promotion_ids: list[str]) -> dict[str, object]:
    return {
        "ring_id": ring.ring_id,
        "score": ring.score,
        "status": ring.status,
        "created_at": _as_utc(created_at),
        "member_count": ring.member_count,
        "shared_entity_count": ring.shared_entity_count,
        "entity_types": ring.entity_types,
        "promotion_ids": promotion_ids,
        "reason_codes": ring.reason_codes,
    }


def _entity_label(entity_id: str) -> str:
    return entity_id.partition(":")[2] or entity_id


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


app = create_app()
