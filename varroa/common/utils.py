#
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

import ipaddress


# Documentation/test ranges (RFC 5737 / RFC 3849). These are reserved but we
# treat them as public so they can be used as sample addresses in tests and
# examples; Python's ipaddress module otherwise classifies them as private.
_DOC_NETWORKS = [
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("2001:db8::/32"),
]

# Non-routable ranges that older Python versions do not classify as private,
# checked explicitly so behaviour is consistent across interpreter versions.
_EXTRA_PRIVATE_NETWORKS = [
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT (RFC 6598)
]


def is_private_ip(address):
    """Return True if the address is not publicly routable.

    Covers RFC1918, loopback, link-local, carrier-grade NAT and unspecified
    addresses for IPv4, and unique-local, link-local, loopback and unspecified
    addresses for IPv6. Documentation ranges are treated as public (see
    _DOC_NETWORKS). Unparsable input is treated as non-private; validating the
    address is the caller's responsibility.
    """
    try:
        ip = ipaddress.ip_address(address)
    except (ValueError, TypeError):
        return False
    if any(ip in net for net in _DOC_NETWORKS):
        return False
    if any(ip in net for net in _EXTRA_PRIVATE_NETWORKS):
        return True
    return ip.is_private
