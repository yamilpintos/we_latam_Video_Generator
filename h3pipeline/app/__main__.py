"""python -X utf8 -u -m h3pipeline.app [puerto]"""
import sys

import uvicorn


def main() -> int:
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    print(f"La Fábrica · http://127.0.0.1:{puerto}   (Ctrl+C para cerrar)")
    uvicorn.run("h3pipeline.app.server:app", host="127.0.0.1", port=puerto,
                log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
