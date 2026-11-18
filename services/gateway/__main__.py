"""Execução: python -m services.gateway [--host 127.0.0.1] [--port 8000] [--reload]"""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="SquadForce gateway")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run("services.gateway.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
