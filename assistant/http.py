import json
import time
import urllib.error
import urllib.parse
import urllib.request


class ApiError(RuntimeError):
    pass


def request(method, url, *, params=None, json_body=None, form=None, headers=None, retries=3):
    """Gọi HTTP, trả về JSON. Tự retry với lỗi mạng / 429 / 5xx."""
    if params:
        url = f"{url}?{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
    data = None
    hdrs = dict(headers or {})
    if json_body is not None:
        data = json.dumps(json_body).encode()
        hdrs["Content-Type"] = "application/json; charset=utf-8"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode()
                try:
                    return json.loads(body or "{}")
                except json.JSONDecodeError:
                    raise ApiError(f"{method} {url.split('?')[0]} -> không phải JSON: {body[:200]!r}") from None
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:500]
            if (e.code == 429 or e.code >= 500) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise ApiError(f"{method} {url.split('?')[0]} -> HTTP {e.code}: {body}") from None
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise ApiError(f"{method} {url.split('?')[0]} -> {e.reason}") from None
