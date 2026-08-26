"""Add functional_area and in_critical_suite.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("test_case_versions", sa.Column("functional_area", sa.String(100), nullable=False, server_default="Unclassified"))
    op.add_column("test_case_versions", sa.Column("in_critical_suite", sa.Boolean(), nullable=False, server_default="false"))

def downgrade():
    op.drop_column("test_case_versions", "in_critical_suite")
    op.drop_column("test_case_versions", "functional_area")
