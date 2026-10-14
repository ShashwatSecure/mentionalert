"""Hard block on non-loopback network access for the running app.

Once enable() is called, any attempt to resolve or connect to a host other
than this machine raises PermissionError. This makes "nothing leaves the PC"
enforced in code, not just promised.
"""
import ipaddress
import socket

_LOCAL_NAMES = {"localhost", "127.0.0.1", "::1"}
_orig_connect = socket.socket.connect
_orig_connect_ex = socket.socket.connect_ex
_orig_getaddrinfo = socket.getaddrinfo
_enabled = False


def _host_is_local(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode()
    if host is None or host == "":
        return True
    if host in _LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _check(address):
    if isinstance(address, tuple) and not _host_is_local(address[0]):
        raise PermissionError(f"MentionAlert netguard blocked non-local connection to {address[0]}")


def _connect(self, address):
    if _enabled:
        _check(address)
    return _orig_connect(self, address)


def _connect_ex(self, address):
    if _enabled:
        _check(address)
    return _orig_connect_ex(self, address)


def _getaddrinfo(host, *args, **kwargs):
    if _enabled and not _host_is_local(host):
        raise PermissionError(f"MentionAlert netguard blocked DNS lookup for {host}")
    return _orig_getaddrinfo(host, *args, **kwargs)


def enable() -> None:
    global _enabled
    _enabled = True
    socket.socket.connect = _connect
    socket.socket.connect_ex = _connect_ex
    socket.getaddrinfo = _getaddrinfo


def disable() -> None:
    global _enabled
    _enabled = False
