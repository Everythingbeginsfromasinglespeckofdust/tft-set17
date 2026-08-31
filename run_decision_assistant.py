"""TFT Decision Assistant Web Application Launcher v1."""
import argparse
import os
import sys
import webbrowser
import uvicorn

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="TFT Decision Assistant Web Application")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print("=" * 80)
    print(f"[*] TFT Decision Assistant Web v1 running at: {url}")
    print("=" * 80)

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    from tft.webapp.server import app
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
