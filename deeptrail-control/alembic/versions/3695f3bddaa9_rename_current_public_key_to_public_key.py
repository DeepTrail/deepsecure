"""rename_current_public_key_to_public_key"""

# revision identifiers, used by Alembic.
revision = '3695f3bddaa9'
down_revision = 'ad30f11f4f01'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Rename the column from current_public_key to public_key
    op.alter_column('agents', 'current_public_key', new_column_name='public_key')
    
    # Update the unique constraint name to match the new column name
    op.drop_constraint('uq_agents_current_public_key', 'agents', type_='unique')
    op.create_unique_constraint('uq_agents_public_key', 'agents', ['public_key'])


def downgrade() -> None:
    # Reverse the operations: rename back to current_public_key
    op.drop_constraint('uq_agents_public_key', 'agents', type_='unique')
    op.create_unique_constraint('uq_agents_current_public_key', 'agents', ['current_public_key'])
    
    # Rename the column back from public_key to current_public_key
    op.alter_column('agents', 'public_key', new_column_name='current_public_key')