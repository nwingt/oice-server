"""add mailChimp_status to user table

Revision ID: 4d5807cb5f7
Revises: 157262ce371
Create Date: 2016-10-25 11:47:42.193759

"""

# revision identifiers, used by Alembic.
revision = '4d5807cb5f7'
down_revision = '157262ce371'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('mailchimp_stage', sa.Integer(),
        server_default='1', nullable=False))
    conn = op.get_bind()
    conn.execute("""UPDATE user SET mailchimp_stage = 1;""");
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'mailchimp_stage')
    ### end Alembic commands ###
