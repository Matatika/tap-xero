"""Shared pytest fixtures."""

import pytest

from tap_xero.auth import proxy_authenticator, standard_authenticator


@pytest.fixture(autouse=True)
def reset_authenticator_caches():
    """Give every test its own authenticators.

    Both caches are module-global and hand back mutable authenticators whose access and
    refresh tokens rotate in place. Without this reset a cached instance leaks token
    state across tests -- and because tests/test_core.py and tests/test_auth.py use
    byte-identical standard credentials, both resolve to the same cached object -- which
    makes assertions depend on execution order.
    """
    standard_authenticator.cache_clear()
    proxy_authenticator.cache_clear()
    yield
    standard_authenticator.cache_clear()
    proxy_authenticator.cache_clear()
