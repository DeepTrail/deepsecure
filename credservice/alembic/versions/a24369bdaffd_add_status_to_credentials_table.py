"""add_status_to_credentials_table"""

# revision identifiers, used by Alembic.
revision = 'a24369bdaffd'
down_revision = '13bdfc2959b8'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column('credentials', sa.Column('status', sa.String(), nullable=False, server_default='issued'))

def downgrade() -> None:
    op.drop_column('credentials', 'status')