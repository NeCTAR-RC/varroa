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

"""Add notify to security_risk

Clients can opt in to having the owning project notified (via taynac)
once a risk has been attributed to a resource. Existing risks were
created before the option existed, so they default to not notifying.

Revision ID: b3e9a1c5d7f2
Revises: f8c4d2e6a1b7
Create Date: 2026-08-26 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3e9a1c5d7f2'
down_revision = 'f8c4d2e6a1b7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('security_risk', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'notify',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade():
    with op.batch_alter_table('security_risk', schema=None) as batch_op:
        batch_op.drop_column('notify')
