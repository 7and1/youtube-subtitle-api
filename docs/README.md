# Documentation Index

## Primary Documents

| Document                           | Description                        |
| ---------------------------------- | ---------------------------------- |
| [QUICK_START.md](./QUICK_START.md) | Local dev / test quick start       |
| [API-README.md](./API-README.md)   | API behavior and examples          |
| [DEPLOYMENT.md](./DEPLOYMENT.md)   | Production deployment instructions |

## Reference Documents

| Document                                                 | Description                    |
| -------------------------------------------------------- | ------------------------------ |
| [ARCHITECTURE-REFERENCE.md](./ARCHITECTURE-REFERENCE.md) | Detailed architecture (Gemini) |
| [DEPLOYMENT_SUMMARY.md](./DEPLOYMENT_SUMMARY.md)         | Full deployment summary        |
| [GENESIS.md](./GENESIS.md)                               | Original planning doc (legacy) |
| [MEETING-SUMMARY.md](./MEETING-SUMMARY.md)               | Multi-LLM meeting synthesis    |

## Quick Links

- **Local dev**: `make local-up` then `make local-test`
- **Backend deploy**: See `DEPLOYMENT.md`
- **Frontend deploy**: See `../frontend/README.md`

## File Structure

```
YouTube-Subtitle-API/
├── docs/                    # All documentation
│   ├── README.md            # This file
│   ├── GENESIS.md           # Master plan
│   ├── MEETING-SUMMARY.md   # Meeting synthesis
│   └── ...                  # Reference docs
├── frontend/                # Cloudflare Pages frontend (separate deploy)
├── src/                     # Backend implementation
├── main.py                  # FastAPI app entrypoint
├── worker.py                # RQ worker entrypoint
└── simple/                  # Legacy minimal variant (reference)
```
