"""Reusable governed transport primitives for SuccessByCS T480 applications.

This package deliberately contains no application operations. Application
repositories own their fixed operation catalogs and pass only those reviewed
operations to this transport layer.
"""

from .core import (
    Operation,
    TransportSettings,
    append_execution_log,
    build_ssh_command,
    build_wsl_powershell_command,
    execute_operation,
    fingerprint_files,
    load_transport_settings,
    preflight,
    resolve_ssh_target,
    validate_catalog,
)

__all__ = [
    "Operation",
    "TransportSettings",
    "append_execution_log",
    "build_ssh_command",
    "build_wsl_powershell_command",
    "execute_operation",
    "fingerprint_files",
    "load_transport_settings",
    "preflight",
    "resolve_ssh_target",
    "validate_catalog",
]
