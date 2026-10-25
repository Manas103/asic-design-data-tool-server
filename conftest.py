"""Points this project's DSNs at WSL2's Postgres before any test imports asictools.db.

Postgres (with pgvector built for it) runs inside WSL2 Ubuntu-22.04, started by BUILDER's own
setup, not by this repo. WSL2's `localhost` port-forwarding was not reachable from this Windows
checkout during this build (connection refused), so this resolves the WSL2 instance's actual IP
address via `wsl.exe hostname -I` and points the DSNs there instead, unless the DSN env vars are
already set (CI or a differently-networked machine would set them explicitly instead).
"""

import os
import subprocess


def _wsl_ip() -> str | None:
    try:
        out = subprocess.run(
            ["wsl.exe", "-d", "Ubuntu-22.04", "--", "hostname", "-I"],
            capture_output=True, text=True, timeout=15,
        )
        return out.stdout.split()[0].strip() if out.stdout.strip() else None
    except Exception:
        return None


if "ASICTOOLS_READER_DSN" not in os.environ or "ASICTOOLS_APP_DSN" not in os.environ:
    ip = _wsl_ip()
    if ip:
        os.environ.setdefault(
            "ASICTOOLS_APP_DSN",
            f"dbname=asic_tools user=asic_tools_app password=asic_tools_app_pw host={ip}",
        )
        os.environ.setdefault(
            "ASICTOOLS_READER_DSN",
            f"dbname=asic_tools user=asic_tools_reader password=asic_tools_reader_pw host={ip}",
        )
