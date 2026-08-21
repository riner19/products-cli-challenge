import json
import os
from pathlib import Path

def config_path() -> Path:
    """For credentials"""
    env = os.environ.get("PRODUCTS_CLI_CONFIG")
    if env:
        return Path(env)
    return Path.home() / ".products-cli" / "config.json"

def save_config(base_url: str, access_token: str, refresh_token: str) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "base_url": base_url.rstrip("/"),
        "access_token": access_token,
        "refresh_token": refresh_token
    }
    path.write_text(json.dumps(payload, indent=2))
    path.chmod(0o600) # owner only

def load_config() -> dict:
    path = config_path()
    if not path.exists():
        raise RuntimeError("Not logged in. Run products-cli login first")
    return json.loads(path.read_text())

def save_tokens(access_token: str, refresh_token: str) -> None:
    """Only token pair updated"""
    cfg = load_config()
    save_config(cfg["base_url"], access_token, refresh_token)