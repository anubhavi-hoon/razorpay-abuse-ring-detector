"""Persist detection-resilience analysis for rings."""

from alembic import op
import sqlalchemy as sa

revision = "0003_detection_resilience"
down_revision = "0002_nullable_account_label"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rings") as batch:
        batch.add_column(sa.Column("detection_resilience", sa.String(length=16)))
        batch.add_column(sa.Column("min_entity_removals", sa.Integer()))
        batch.add_column(sa.Column("critical_entity_types", sa.JSON()))
        batch.create_check_constraint(
            "ck_rings_detection_resilience",
            "detection_resilience IS NULL OR detection_resilience IN ('low', 'moderate', 'high')",
        )
        batch.create_check_constraint(
            "ck_rings_min_entity_removals",
            "min_entity_removals IS NULL OR min_entity_removals >= 1",
        )


def downgrade() -> None:
    with op.batch_alter_table("rings") as batch:
        batch.drop_constraint("ck_rings_min_entity_removals", type_="check")
        batch.drop_constraint("ck_rings_detection_resilience", type_="check")
        batch.drop_column("critical_entity_types")
        batch.drop_column("min_entity_removals")
        batch.drop_column("detection_resilience")
