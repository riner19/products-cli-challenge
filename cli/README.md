# Products CLI

A command-line client for the Products API. Authenticates once, persists the
token pair to disk, and transparently refreshes it when the access token's
budget runs out.

## Install & run

The server must be running first (from the repository root):

```bash
docker compose up
```

> The server listens on `http://localhost:8000`. If that port is taken on your
> machine, change the host-side port mapping in `docker-compose.yml` and pass
> the matching `--base-url` at login.

Then, from this folder:

```bash
cd cli
uv sync
uv run products-cli --help
```

## Usage

Authenticate first — this is the only command that takes `--base-url`, and it is
required. The URL is stored alongside the tokens so later commands reuse it:

```bash
uv run products-cli login --base-url http://localhost:8000 --username demo --password password123
# {"status": "ok"}
```

### Listing and filtering

```bash
uv run products-cli products list
uv run products-cli products list --section electronics --limit 5
uv run products-cli products list --min-price 20 --max-price 100
uv run products-cli products list --name mouse
uv run products-cli products list --has-discount
uv run products-cli products list --no-discount
```

`GET /products` returns a paginated envelope; the CLI extracts `items` and
prints a bare JSON array, as specified.

### Single-product operations

```bash
uv run products-cli products get --id 1
uv run products-cli products create --name "Desk Lamp" --section home --price 39.99
uv run products-cli products update --id 1 --discount 15
uv run products-cli products delete --id 1
```

`update` sends only the fields you pass, so unspecified fields are left
untouched by the `PATCH`.

### Batch update

```bash
uv run products-cli products batch-update --section electronics --discount 25
# {"updated": 5}
```

## Output contract

- Successful data commands print valid JSON to **stdout** and exit `0`.
- Errors print a message to **stderr** and exit non-zero; stdout stays empty so
  the output is always safe to pipe into `jq`.

## Code structure

| File | Responsibility |
|------|----------------|
| `src/products_cli/config.py` | Reads and writes the credentials file |
| `src/products_cli/client.py` | HTTP layer: login, refresh, authenticated requests |
| `src/products_cli/__init__.py` | Typer commands — argument parsing and JSON output |

Every command goes through a single `client.request()` helper, so the
refresh-on-401 logic is written once and applies everywhere automatically.

## Where tokens are stored

`~/.products-cli/config.json`, created with mode `0600` (owner read/write only).
Keeping it outside the repository means tokens can't be committed by accident.
The path can be overridden with the `PRODUCTS_CLI_CONFIG` environment variable,
which is useful for testing against several servers.

## Token refresh

An access token expires after 20 authenticated requests or 60 seconds,
whichever comes first. `client.request()` handles this without the user noticing:

1. Send the request with the stored access token.
2. If the response is `401`, POST the stored refresh token to `/auth/refresh`.
3. Persist **both** new tokens — refresh tokens are rotated, so keeping the old
   refresh token would break the next refresh.
4. Retry the original request once with the new access token.

The retry happens only once. If a request still fails after a successful
refresh, something is genuinely wrong (revoked credentials, a server restart
that cleared its in-memory token state) and retrying in a loop would only hide
the problem. In that case the CLI exits non-zero and tells the user to log in
again.

## Batch update: approach and trade-offs

The server has no bulk endpoint, so `batch-update` runs client-side: it lists
the products in the section, then issues one `PATCH` per product and reports how
many were updated.

**Why not add a server endpoint?** Adding `POST /products/batch` would be faster
— a single round trip, and the writes could share one transaction. I chose the
client-side approach because in practice the API is often owned by another team
and can't be changed to suit one consumer, so a client that works against the
API as published is the more realistic deliverable. If this were a real
recurring workload, a server-side bulk endpoint would be the right fix, and I'd
raise it with whoever owns the service.

**Pagination.** The listing step pages through the results using the `total`
value in the envelope rather than assuming everything fits in one page, so
sections larger than the default page size are handled correctly.

**Known limitation — the writes are sequential.** Each mutation is published to
a downstream event bus before the response returns, which costs roughly 430 ms
per write. On a four-product section `time` reports 1.8s wall clock against
0.14s of CPU, so over 90% of the run is spent waiting on the network; a full
15-product section takes about 6.5 seconds.

Issuing the `PATCH` requests concurrently would cut this to roughly the latency
of a single write. The complication is the interaction with token refresh: with
several requests in flight, more than one can receive a `401` at the same time,
and because refresh tokens are rotated, the first refresh invalidates the token
the others are holding. Doing this correctly needs a lock around the refresh so
that one caller performs it while the rest wait and then pick up the new token.

I kept the sequential version because it is correct and easy to follow, and the
assignment asks for a small, clean solution. The concurrent version is the
obvious next step if throughput mattered.

**Refreshing pre-emptively.** Every authenticated response carries
`X-Token-Requests-Used` and `X-Token-Expires-At`. A client could watch those and
refresh just before the budget runs out, avoiding the wasted 401 round trip
entirely. Reacting to the 401 is simpler and still correct, so that's what this
implementation does — but the headers make the smarter approach available.

## Server changes

None. The server is used exactly as provided.