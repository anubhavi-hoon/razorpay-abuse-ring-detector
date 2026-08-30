"""Initial persistence schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "detection_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("artifact_versions", sa.JSON(), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("timings_seconds", sa.JSON(), nullable=False),
        sa.Column("outputs", sa.JSON(), nullable=False),
        sa.Column(
            "loaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("status = 'complete'", name="ck_detection_runs_status"),
    )
    op.create_table(
        "accounts",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email_hash", sa.String(length=128), nullable=False),
        sa.Column("phone_hash", sa.String(length=128), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("payment_instrument_id", sa.String(length=128), nullable=False),
        sa.Column("label", sa.Integer(), nullable=False),
        sa.Column("ring_label", sa.String(length=64)),
        sa.CheckConstraint("label IN (0, 1)", name="ck_accounts_label"),
        sa.ForeignKeyConstraint(("run_id",), ("detection_runs.run_id",), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id", "account_id"),
    )
    op.create_table(
        "transactions",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("merchant_id", sa.String(length=128), nullable=False),
        sa.Column("promotion_id", sa.String(length=128)),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_transactions_amount"),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed', 'refunded')", name="ck_transactions_status"
        ),
        sa.ForeignKeyConstraint(
            ("run_id", "account_id"),
            ("accounts.run_id", "accounts.account_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", "transaction_id"),
    )
    op.create_table(
        "account_results",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("ml_score", sa.Float(), nullable=False),
        sa.Column("predicted_label", sa.Integer(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.CheckConstraint("ml_score BETWEEN 0 AND 1", name="ck_account_results_score"),
        sa.CheckConstraint("predicted_label IN (0, 1)", name="ck_account_results_label"),
        sa.ForeignKeyConstraint(
            ("run_id", "account_id"),
            ("accounts.run_id", "accounts.account_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", "account_id"),
    )
    op.create_table(
        "rings",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("ring_id", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="new", nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column("shared_entity_count", sa.Integer(), nullable=False),
        sa.Column("entity_types", sa.JSON(), nullable=False),
        sa.Column("density", sa.Float(), nullable=False),
        sa.Column("promotion_concentration", sa.Float(), nullable=False),
        sa.Column("mean_ml_score", sa.Float(), nullable=False),
        sa.Column("max_ml_score", sa.Float(), nullable=False),
        sa.Column("temporal_concentration", sa.Float(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('new', 'reviewing', 'confirmed', 'dismissed')", name="ck_rings_status"
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 1", name="ck_rings_score"),
        sa.CheckConstraint("member_count >= 2", name="ck_rings_member_count"),
        sa.CheckConstraint(
            "density BETWEEN 0 AND 1 AND promotion_concentration BETWEEN 0 AND 1 "
            "AND mean_ml_score BETWEEN 0 AND 1 AND max_ml_score BETWEEN 0 AND 1 "
            "AND temporal_concentration BETWEEN 0 AND 1",
            name="ck_rings_metrics",
        ),
        sa.ForeignKeyConstraint(("run_id",), ("detection_runs.run_id",), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id", "ring_id"),
    )
    op.create_table(
        "ring_members",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("ring_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("ml_score", sa.Float(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.CheckConstraint("ml_score BETWEEN 0 AND 1", name="ck_ring_members_score"),
        sa.ForeignKeyConstraint(
            ("run_id", "account_id"),
            ("accounts.run_id", "accounts.account_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ("run_id", "ring_id"), ("rings.run_id", "rings.ring_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("run_id", "ring_id", "account_id"),
    )
    op.create_table(
        "relationships",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("ring_id", sa.String(length=64), nullable=False),
        sa.Column("source_account_id", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=512), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "relationship_type IN "
            "('device', 'ip', 'payment_instrument', 'email', 'phone', 'merchant', 'promotion')",
            name="ck_relationships_type",
        ),
        sa.ForeignKeyConstraint(
            ("run_id", "ring_id"), ("rings.run_id", "rings.ring_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ("run_id", "source_account_id"),
            ("accounts.run_id", "accounts.account_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "run_id", "ring_id", "source_account_id", "target_id", "relationship_type"
        ),
    )


def downgrade() -> None:
    op.drop_table("relationships")
    op.drop_table("ring_members")
    op.drop_table("rings")
    op.drop_table("account_results")
    op.drop_table("transactions")
    op.drop_table("accounts")
    op.drop_table("detection_runs")
