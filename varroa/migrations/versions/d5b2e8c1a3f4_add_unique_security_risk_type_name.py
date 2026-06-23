#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Add unique constraint on security_risk_type.name

Revision ID: d5b2e8c1a3f4
Revises: c4e1f7a9b2d3
Create Date: 2026-06-23 09:30:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'd5b2e8c1a3f4'
down_revision = 'c4e1f7a9b2d3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('security_risk_type', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_security_risk_type_name', ['name']
        )


def downgrade():
    with op.batch_alter_table('security_risk_type', schema=None) as batch_op:
        batch_op.drop_constraint('uq_security_risk_type_name', type_='unique')
