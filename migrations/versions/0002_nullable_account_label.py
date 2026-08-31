"""Allow accounts.label to be NULL for uploaded data without ground truth."""

from alembic import op
import sqlalchemy as sa

revision = "0002_nullable_account_label"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _accounts(label_nullable: bool, check: str) -> sa.Table:
    """The accounts table as it exists on the side of the migration being left."""
    return sa.Table(
        "accounts",
        sa.MetaData(),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email_hash", sa.String(length=128), nullable=False),
        sa.Column("phone_hash", sa.String(length=128), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("payment_instrument_id", sa.String(length=128), nullable=False),
        sa.Column("label", sa.Integer(), nullable=label_nullable),
        sa.Column("ring_label", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("run_id", "account_id"),
        sa.ForeignKeyConstraint(["run_id"], ["detection_runs.run_id"], ondelete="CASCADE"),
        sa.CheckConstraint(check, name="ck_accounts_label"),
    )


def upgrade() -> None:
    with op.batch_alter_table(
        "accounts", copy_from=_accounts(False, "label IN (0, 1)")
    ) as batch:
        batch.alter_column("label", existing_type=sa.Integer(), nullable=True)
        batch.drop_constraint("ck_accounts_label", type_="check")
        batch.create_check_constraint("ck_accounts_label", "label IS NULL OR label IN (0, 1)")


def downgrade() -> None:
    # A run with unlabelled accounts cannot survive the NOT NULL constraint, and
    # dropping only those accounts would leave its rings and recorded counts
    # describing rows that no longer exist. Drop each affected run whole.
    bind = op.get_bind()
    run_ids = [
        row[0]
        for row in bind.exec_driver_sql(
            "SELECT DISTINCT run_id FROM accounts WHERE label IS NULL"
        )
    ]
    if run_ids:
        # Ordered child-first so this holds on SQLite too, where Alembic connects
        # with foreign keys disabled and the ON DELETE CASCADE keys never fire.
        # Enabling them here is not an option: the batch rebuild below drops the
        # old accounts table, which would cascade into the surviving runs.
        placeholders = ", ".join(f":id{index}" for index in range(len(run_ids)))
        parameters = {f"id{index}": run_id for index, run_id in enumerate(run_ids)}
        for table in (
            "relationships",
            "ring_members",
            "rings",
            "account_results",
            "transactions",
            "accounts",
            "detection_runs",
        ):
            op.execute(
                sa.text(f"DELETE FROM {table} WHERE run_id IN ({placeholders})").bindparams(
                    **parameters
                )
            )

    with op.batch_alter_table(
        "accounts", copy_from=_accounts(True, "label IS NULL OR label IN (0, 1)")
    ) as batch:
        batch.alter_column("label", existing_type=sa.Integer(), nullable=False)
        batch.drop_constraint("ck_accounts_label", type_="check")
        batch.create_check_constraint("ck_accounts_label", "label IN (0, 1)")
