#!/usr/bin/env python3
"""
Screendex Quick Start Script
Runs the server with sensible defaults.

Usage:
  python run.py               # development mode (auto-reload)
  python run.py --prod        # production mode
  python run.py --port 9000   # custom port
"""

import argparse
import subprocess
import sys
import os

def main():
    parser = argparse.ArgumentParser(description="Run Screendex Server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--prod", action="store_true", help="Production mode (no reload)")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    cmd = [
        sys.executable, "-m", "uvicorn",
        "main:app",
        "--host", args.host,
        "--port", str(args.port),
    ]

    if not args.prod:
        cmd.append("--reload")
        cmd += ["--log-level", "info"]
    else:
        cmd += ["--workers", str(args.workers)]
        cmd += ["--log-level", "warning"]

    print(f"""
+--------------------------------------------------+
|        SCREENDEX - AI Image Search System        |
|          MCA Project | Version 1.0.0             |
+--------------------------------------------------+
|  URL:     http://localhost:{args.port:<22}|
|  API:     http://localhost:{args.port}/api/docs{'':13}|
|  Mode:    {'Production' if args.prod else 'Development (auto-reload)':33}|
+--------------------------------------------------+
""")

    subprocess.run(cmd)

if __name__ == "__main__":
    main()
