"""Legacy gateway module marked for deletion.

The dual-socket implementation now lives in
``app.gateways.vista_dual_socket_gateway`` and this stub remains only as a
placeholder to avoid import errors while downstream code migrates. No runtime
logic should depend on this file; it can be safely removed when tooling allows.
"""

from __future__ import annotations

from .vista_dual_socket_gateway import VistaDualSocketGateway as VistaSocketGateway  # noqa: F401
