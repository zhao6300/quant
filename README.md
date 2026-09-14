# Multi-Market Quant Platform

This is the first local research slice of the platform. It keeps a FastAPI control plane and a separate React/Vite web client.

```bash
./scripts/install.sh
./scripts/start.sh --foreground
```

Use `--host` and `--port` to override the default backend listener `0.0.0.0:80`,
and `--background` to run detached with logs under `/tmp`.

The frontend is available at `http://localhost:5173`.
