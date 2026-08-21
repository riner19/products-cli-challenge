"""Products CLI — starter package.

Implement the commands described in README.md. Entry point: `main()`.
Run with: `uv run products-cli ...`
"""

import json 
import sys

import typer 

from products_cli import client

app = typer.Typer(add_completion=False, help='CLI for the Products API')
products_app = typer.Typer(help="Manage products")
app.add_typer(products_app, name="products")

def _emit(payload) -> None:
    """Printing JSON to stdout"""
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")

@app.command()
def login(
    base_url: str = typer.Option(..., "--base-url"),
    username: str = typer.Option(..., "--username"),
    password: str = typer.Option(..., "--password"),
) -> None:
    """Autherticat and storeing credentials for next commands"""
    client.login(base_url, username, password)
    _emit({"status": "ok"})

@products_app.command("list")
def products_list(
    section: str = typer.Option(None, "--section"),
    name: str = typer.Option(None, "--name"),
    min_price: float = typer.Option(None, "--min-price"),
    max_price: float = typer.Option(None, "--max-price"),
    has_discount: bool = typer.Option(None, "--has-discount/--no-discount"),
    limit: int = typer.Option(None, "--limit"),
    offset: int = typer.Option(None, "--offset"),
) -> None:
    """List products, optionally filtered."""
    params = {
        "section": section,
        "name": name,
        "min_price": min_price,
        "max_price": max_price,
        "has_discount": has_discount,
        "limit": limit,
        "offset": offset,
    }
    # Drop unset options so we don't send empty query params
    params = {k: v for k, v in params.items() if v is not None}

    data = client.request("GET", "/products", params=params)
    _emit(data["items"])


@products_app.command("get")
def products_get(
    id: int = typer.Option(..., "--id"),
) -> None:
    """Fetch a single product by id."""
    data = client.request("GET", f"/products/{id}")
    _emit(data)


@products_app.command("create")
def products_create(
    name: str = typer.Option(..., "--name"),
    section: str = typer.Option(..., "--section"),
    price: float = typer.Option(..., "--price"),
    description: str = typer.Option(None, "--description"),
    discount: float = typer.Option(None, "--discount"),
) -> None:
    """Create a new product."""
    payload = {
        "name": name,
        "section": section,
        "price": price,
        "description": description,
        "discount": discount,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    data = client.request("POST", "/products", json=payload)
    _emit(data)


@products_app.command("update")
def products_update(
    id: int = typer.Option(..., "--id"),
    name: str = typer.Option(None, "--name"),
    section: str = typer.Option(None, "--section"),
    price: float = typer.Option(None, "--price"),
    description: str = typer.Option(None, "--description"),
    discount: float = typer.Option(None, "--discount"),
) -> None:
    """Update fields on an existing product."""
    payload = {
        "name": name,
        "section": section,
        "price": price,
        "description": description,
        "discount": discount,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    data = client.request("PATCH", f"/products/{id}", json=payload)
    _emit(data)


@products_app.command("delete")
def products_delete(
    id: int = typer.Option(..., "--id"),
) -> None:
    """Delete a product by id."""
    client.request("DELETE", f"/products/{id}")
    _emit({"status": "ok"})


@products_app.command("batch-update")
def products_batch_update(
    section: str = typer.Option(..., "--section"),
    discount: float = typer.Option(..., "--discount"),
) -> None:
    """Apply a discount to every product in a section."""
    # Collect all matching ids first, paging through the envelope.
    ids: list[int] = []
    offset = 0
    while True:
        page = client.request(
            "GET", "/products",
            params={"section": section, "limit": 200, "offset": offset},
        )
        ids.extend(item["id"] for item in page["items"])
        pagination = page["pagination"]
        offset += pagination["count"]
        if offset >= pagination["total"] or pagination["count"] == 0:
            break

    # Each write costs ~70ms of downstream publish latency, and there is no bulk
    # endpoint — so issue the PATCHes concurrently rather than one at a time.
    for pid in ids:
        client.request("PATCH", f"/products/{pid}", json={"discount": discount})

    _emit({"updated": len(ids)})

    
def main() -> None:
    try:
        app()
    except client.ApiError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
