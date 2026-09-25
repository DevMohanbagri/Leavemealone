"""Start LeaveMeAlone on this machine.

Listens on 127.0.0.1 by default, so other devices on your network cannot open
the dossier. Set LEAVEMEALONE_HOST=0.0.0.0 only if you mean to share it.
"""

import os

import uvicorn


def main() -> None:
    host = os.environ.get("LEAVEMEALONE_HOST", "127.0.0.1")
    port = int(os.environ.get("LEAVEMEALONE_PORT", "8787"))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
