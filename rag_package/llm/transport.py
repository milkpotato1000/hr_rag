"""Bounded HTTP, with no proxies, redirects, retries or raw error reporting."""
import json
import socket
import urllib.error
import urllib.request
from .config import strict_json, ValidationError

RESPONSE_LIMIT = 4 * 1024 * 1024

class TransportError(Exception):
    def __init__(self, code, outcome_unknown=False):
        self.code, self.outcome_unknown = code, outcome_unknown
        super().__init__(code)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_transport(method, url, headers, body, timeout):
    data = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(RESPONSE_LIMIT + 1)
        if len(raw) > RESPONSE_LIMIT:
            raise TransportError('response_too_large')
        try:
            return strict_json(raw.decode('utf-8'), 'response')
        except (ValidationError, UnicodeError):
            raise TransportError('invalid_response_json') from None
    except urllib.error.HTTPError as e:
        code = e.code
        e.close()
        if 300 <= code < 400: category = 'redirect_denied'
        elif code in (401,403,429): category = 'http_'+str(code)
        elif code >= 500: category = 'http_5xx'
        else: category = 'http_error'
        raise TransportError(category) from None
    except (TimeoutError, socket.timeout):
        raise TransportError('timeout', True) from None
    except urllib.error.URLError as e:
        timed_out = isinstance(e.reason, (TimeoutError, socket.timeout))
        raise TransportError('timeout' if timed_out else 'connection_error', True) from None
    except (OSError, ValueError):
        raise TransportError('connection_error', True) from None
