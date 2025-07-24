"""Add metadata column to secrets table"""

# revision identifiers, used by Alembic.
revision = '85a042468f08'
down_revision = '556ee3ed451b'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.add_column('secrets', sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Arbitrary metadata for the secret, e.g., target_base_url'))


def downgrade() -> None:
    op.drop_column('secrets', 'metadata')