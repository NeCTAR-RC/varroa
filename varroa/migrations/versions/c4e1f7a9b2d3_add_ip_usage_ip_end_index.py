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

"""Add index on ip_usage (ip, end)

Revision ID: c4e1f7a9b2d3
Revises: 2d7ae226fd06
Create Date: 2026-06-22 16:50:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'c4e1f7a9b2d3'
down_revision = '2d7ae226fd06'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'ix_ip_usage_ip_end', 'ip_usage', ['ip', 'end'], unique=False
    )


def downgrade():
    op.drop_index('ix_ip_usage_ip_end', table_name='ip_usage')
