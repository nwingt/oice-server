"""Add featured library list and localization table

Revision ID: 7689849c5ede
Revises: d8737fd397e8
Create Date: 2017-10-06 07:45:45.252356

"""

# revision identifiers, used by Alembic.
revision = '7689849c5ede'
down_revision = 'd8737fd397e8'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('featured_library_list',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alias', sa.Unicode(length=256), nullable=False, index=True, unique=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('order', sa.Integer(), server_default='0', nullable=False, index=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('featured_library_list_localization',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('list_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Unicode(length=256), nullable=False),
        sa.Column('language', sa.Unicode(length=5), server_default='zh-HK', nullable=False),
        sa.ForeignKeyConstraint(['list_id'], ['featured_library_list.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.add_column('featured_library', sa.Column('list_id', sa.Integer(), nullable=False))

    conn = op.get_bind()
    conn.execute('''
        INSERT INTO `featured_library_list` VALUES \
        (1, "cc", 1, 0),
        (2, "characters", 1, 1),
        (3, "bg", 1, 2),
        (4, "sfx", 1, 3);

        INSERT INTO `featured_library_list_localization` (list_id, name, language) VALUES \
        (1, "創用CC", "zh-HK"),
        (1, "創用CC", "zh-TW"),
        (1, "Creative Commons", "en"),
        (1, "CCライセンス", "ja"),
        (2, "角色", "zh-HK"),
        (2, "角色", "zh-TW"),
        (2, "Characters", "en"),
        (2, "キャラ", "ja"),
        (3, "場景", "zh-HK"),
        (3, "場景", "zh-TW"),
        (3, "Background", "en"),
        (3, "背景画像", "ja"),
        (4, "音樂音效", "zh-HK"),
        (4, "音樂音效", "zh-TW"),
        (4, "Music and Sound", "en"),
        (4, "BGM/効果音", "ja");

        TRUNCATE TABLE `featured_library`;

        INSERT INTO `featured_library` (list_id, library_id, `order`) VALUES \
        (1, 2258, 0),
        (1, 2538, 1),
        (1, 2530, 2),
        (1, 2137, 3),
        (1, 2533, 4),
        (1, 2360, 5),
        (1, 2365, 6),
        (1, 2366, 7),
        (1, 2354, 8),
        (2, 1182, 0),
        (2, 1377, 1),
        (2, 2304, 2),
        (2, 460, 3),
        (2, 2163, 4),
        (2, 1230, 5),
        (2, 383, 6),
        (2, 2137, 7),
        (2, 234, 8),
        (3, 838, 0),
        (3, 2133, 1),
        (3, 3213, 2),
        (3, 2323, 3),
        (3, 3217, 4),
        (3, 3226, 5),
        (3, 3228, 6),
        (4, 410, 0),
        (4, 345, 1),
        (4, 1079, 2),
        (4, 426, 3),
        (4, 1230, 4),
        (4, 1, 5),
        (4, 559, 6);
    ''')

    op.create_foreign_key('featured_library_ibfk1', 'featured_library', 'featured_library_list', ['list_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('featured_library_ibfk1', 'featured_library', type_='foreignkey')
    op.drop_column('featured_library', 'list_id')
    op.drop_table('featured_library_list_localization')
    op.drop_table('featured_library_list')
    # ### end Alembic commands ###
