"""${message}"""

# revision identifiers, used by Alembic.
revision = '${up_revision}'
down_revision = ${down_revision}
branch_labels = ${branch_labels}
depends_on = ${depends_on}

from alembic import op
import sqlalchemy as sa
${imports}

def upgrade() -> None:
    ${upgrades if upgrades else "pass"}

def downgrade() -> None:
    ${downgrades if downgrades else "pass"}