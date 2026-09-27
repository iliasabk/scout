# Deploy Scout to Nebius Serverless (demo URL)

The app is one FastAPI container, so it deploys as-is. SQLite rides on the
endpoint's disk for the demo; for anything longer-lived, point `DB_PATH` at a
volume or swap in a hosted DB.

## 1. Build and push the image

```bash
docker build -t <your-registry>/scout:latest .
docker push <your-registry>/scout:latest
```

## 2. Create the endpoint

```bash
nebius ai endpoint create \
  --name scout \
  --image <your-registry>/scout:latest \
  --platform cpu-e2 \
  --preset 2vcpu-8gb \
  --container-port 8787 \
  --env "NEBIUS_API_KEY=$NEBIUS_API_KEY" \
  --env "NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1" \
  --env "TAVILY_API_KEY=$TAVILY_API_KEY" \
  --public \
  --format json
```

The response contains the public URL — that is the working demo URL for the
submission. Verify with:

```bash
curl -s https://<endpoint-url>/api/state | jq .configured
```

## Notes

- Region-specific Token Factory base URL (e.g.
  `https://api.tokenfactory.us-central1.nebius.com/v1`): check your Nebius
  dashboard and set `NEBIUS_BASE_URL` accordingly.
- `nebius profile create` once to authenticate the CLI.
- Costs: the app is a plain HTTP service calling Token Factory per request —
  a `cpu-e2` preset is plenty; model spend happens per token on Token Factory.
