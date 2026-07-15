"""Initial Backend 2 schema.

Revision ID: 0001
"""
from alembic import op
from app.database.base import Base
import app.models  # noqa: F401
revision="0001";down_revision=None;branch_labels=None;depends_on=None
def upgrade(): Base.metadata.create_all(bind=op.get_bind(),checkfirst=True)
def downgrade(): Base.metadata.drop_all(bind=op.get_bind(),checkfirst=True)
