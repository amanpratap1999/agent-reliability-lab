import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def main() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    backend_dir = Path(__file__).resolve().parents[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=backend_dir,
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(40):
            if process.poll() is not None:
                raise RuntimeError(f"Uvicorn exited early with code {process.returncode}")
            try:
                live = httpx.get(f"{base_url}/health/live", timeout=1.0)
                ready = httpx.get(f"{base_url}/health/ready", timeout=1.0)
                if live.status_code == 200 and ready.status_code == 200:
                    print("Uvicorn startup smoke test passed: liveness and database readiness returned HTTP 200.")
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        raise RuntimeError("Uvicorn did not become ready within 10 seconds")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
