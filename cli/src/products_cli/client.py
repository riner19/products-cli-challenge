import httpx
from products_cli import config

class ApiError(RuntimeError):
    """Raised if API has error response"""

def login(base_url: str, username: str, password: str) -> None:
    """Authentication"""
    base_url = base_url.rstrip("/")
    resp = httpx.post(
        f"{base_url}/auth/login",
        json={"username":username, "password": password},
        timeout=10.0,
    )
    if resp.status_code !=200:
        raise ApiError(f"Login failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    config.save_config(base_url, data["access_token"], data["refresh_token"])

def _refresh(base_url: str, refresh_token: str) -> str:
    """Changing refresh token for new one, returns new access token"""
    resp = httpx.post(
        f"{base_url}/auth/refresh",
        json={"refresh_token": refresh_token},
        timeout=10.0,
    )
    if resp.status_code !=200:
        raise ApiError(
            "Token refresh failed"
            f"({resp.status_code})"
        )

    data = resp.json()

    config.save_tokens(data["access_token"], data["refresh_token"])
    return data["access_token"]

def request(method: str, path: str, **kwargs) ->dict | list | None:
    cfg = config.load_config()
    base_url = cfg["base_url"]
    access_token = cfg["access_token"]
    url = f"{base_url}{path}"

    def _send(token: str) -> httpx.Response:
        return httpx.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
            **kwargs
        )
    resp = _send(access_token)

    if resp.status_code == 401:
        new_token = _refresh(base_url, cfg["refresh_token"])
        resp = _send(new_token)

    if resp.status_code >= 400:
        raise ApiError(f"API error ({resp.status_code}): {resp.text}")

    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()

