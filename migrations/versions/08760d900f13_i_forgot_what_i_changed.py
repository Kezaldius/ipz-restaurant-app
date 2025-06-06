"""I forgot what i changed

Revision ID: 08760d900f13
Revises: 163fe43f658d
Create Date: 2025-04-29 15:39:31.787989

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '08760d900f13'
down_revision = '163fe43f658d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('order_item_modifiers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_item_id', sa.Integer(), nullable=False),
    sa.Column('modifier_option_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['modifier_option_id'], ['modifier_options.id'], ),
    sa.ForeignKeyConstraint(['order_item_id'], ['order_items.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('variant_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key(None, 'dish_variants', ['variant_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('variant_id')

    op.drop_table('order_item_modifiers')
    # ### end Alembic commands ###
