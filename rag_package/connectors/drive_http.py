"""Bounded GET-only HTTPS transport; no proxies, redirects or retries."""
import http.client
import ssl
import time
from urllib.parse import urlsplit
from ..storage import RagError,require


def bounded_get(url,headers,limit,deadline):
    """Generic internal transport; production wrapper fixes Google destinations."""
    p=urlsplit(url);conn=None
    def remaining():
        left=deadline-time.monotonic();require(left>0,'timeout','transport');return min(30,left)
    try:
        if p.scheme=='https':conn=http.client.HTTPSConnection(p.hostname,p.port or 443,timeout=remaining(),context=ssl.create_default_context())
        else:
            require(p.scheme=='http' and p.hostname in ('127.0.0.1','::1'),'endpoint_denied','transport')
            conn=http.client.HTTPConnection(p.hostname,p.port or 80,timeout=remaining())
        conn.connect();sock=conn.sock;sock.settimeout(remaining())
        conn.request('GET',p.path+('?' + p.query if p.query else ''),headers=headers)
        sock.settimeout(remaining());response=conn.getresponse();status=response.status
        if status!=200:
            code={401:'auth_error',403:'access_denied',404:'not_found_or_inaccessible',429:'rate_limited',206:'partial_response'}.get(status,
                  'redirect_denied' if 300<=status<400 else 'upstream_error' if status>=500 else 'invalid_status')
            raise RagError(code,'transport')
        require(response.getheader('Content-Range') is None,'partial_response','transport')
        length=response.getheader('Content-Length');expected=None
        if length is not None:
            require(length.isascii() and length.isdecimal(),'invalid_content_length','transport');expected=int(length)
            require(0<expected<=limit,'body_size_limit','transport')
        body=bytearray()
        while True:
            sock.settimeout(remaining());part=response.read1(min(65536,limit+1-len(body)))
            if not part:break
            body.extend(part);require(len(body)<=limit,'body_size_limit','transport')
            if expected is not None and len(body)==expected:break
        remaining();require(bool(body),'empty_body','transport')
        require(expected is None or len(body)==expected,'content_length_mismatch','transport')
        return bytes(body)
    except RagError:raise
    except (TimeoutError,):raise RagError('timeout','transport') from None
    except http.client.IncompleteRead:raise RagError('partial_response','transport') from None
    except (OSError,http.client.HTTPException,ValueError):raise RagError('connection_error','transport') from None
    finally:
        if conn is not None:conn.close()


def drive_get(url,headers,limit,deadline):
    p=urlsplit(url)
    require(p.scheme=='https' and p.netloc=='www.googleapis.com' and p.path.startswith('/drive/v3/files/'),'endpoint_denied','transport')
    return bounded_get(url,headers,limit,deadline)
