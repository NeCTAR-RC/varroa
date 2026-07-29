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

"""Make security_risk.ipaddress nullable

Resource-first risks (for example a Magnum cluster running an EOL
Kubernetes version) are created with resource_id/resource_type/project_id
and no IP address.

Revision ID: f8c4d2e6a1b7
Revises: d5b2e8c1a3f4
Create Date: 2026-07-29 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8c4d2e6a1b7'
down_revision = 'd5b2e8c1a3f4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('security_risk', schema=None) as batch_op:
        batch_op.alter_column(
            'ipaddress',
            existing_type=sa.String(length=64),
            nullable=True,
        )


def downgrade():
    with op.batch_alter_table('security_risk', schema=None) as batch_op:
        batch_op.alter_column(
            'ipaddress',
            existing_type=sa.String(length=64),
            nullable=False,
        )
