"""Guard: every impersonate target settfex defaults to must exist in the installed curl_cffi.

The unit suite mocks all HTTP, so a curl_cffi upgrade that drops an impersonation target
(e.g. retires ``chrome120``) would pass tests and then fail — or worse, silently change the
TLS fingerprint — against the real Incapsula-protected origins. This test reads the defaults
from the code (never a second hardcoded copy) and asserts membership in the installed
package's own enumeration, ``curl_cffi.requests.impersonate.BrowserTypeLiteral``.
"""

import inspect
import typing

from curl_cffi.requests.impersonate import BrowserTypeLiteral

from settfex.utils.data_fetcher import FetcherConfig
from settfex.utils.http import HTTPClient
from settfex.utils.session_manager import SessionManager, get_session_for_url, get_shared_session

ACCEPTED_TARGETS = frozenset(typing.get_args(BrowserTypeLiteral))


def _signature_default(func, param: str):
    return inspect.signature(func).parameters[param].default


def collect_impersonate_defaults() -> dict[str, str]:
    """Every impersonate/browser default the package ships, keyed by its owner."""
    return {
        "FetcherConfig.browser_impersonate": FetcherConfig().browser_impersonate,
        "HTTPClient.__init__ impersonate": _signature_default(HTTPClient.__init__, "impersonate"),
        "SessionManager.__init__ browser": _signature_default(SessionManager.__init__, "browser"),
        "SessionManager.get_instance browser": _signature_default(
            SessionManager.get_instance, "browser"
        ),
        "get_shared_session browser": _signature_default(get_shared_session, "browser"),
        "get_session_for_url browser": _signature_default(get_session_for_url, "browser"),
    }


class TestImpersonateTargets:
    def test_enumeration_source_is_nonempty(self):
        assert len(ACCEPTED_TARGETS) > 10, "BrowserTypeLiteral shrank suspiciously"

    def test_every_shipped_default_is_an_accepted_target(self):
        defaults = collect_impersonate_defaults()
        missing = {
            owner: target for owner, target in defaults.items() if target not in ACCEPTED_TARGETS
        }
        assert not missing, (
            f"impersonate defaults not accepted by installed curl_cffi: {missing}; "
            f"accepted targets: {sorted(ACCEPTED_TARGETS)}"
        )
