"""Verify candidate C in a network-isolated, disposable, synthetic-only container."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path


def command(
    args: list[str], *, data: str | None = None, timeout: int = 60, diagnostics: list[str] | None = None
) -> str:
    result = subprocess.run(args, input=data, text=True, capture_output=True, check=False, timeout=timeout)
    if result.returncode:
        # All commands use this isolated synthetic fixture; no application DSN or source text.
        raise RuntimeError(f"synthetic command failed ({result.returncode}): {result.stderr.strip()}")
    if diagnostics is not None and result.stderr:
        diagnostics.append(result.stderr)
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="medy-dec001-c:pg16-pgsearch-0.25.9-r28")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists() or args.out.is_symlink():
        raise ValueError("output already exists")
    here = Path(__file__).resolve().parent
    sql = (here / "smoke.sql").read_text(encoding="utf-8")
    image = json.loads(command(["docker", "image", "inspect", args.image]))[0]
    if image["Architecture"] != "arm64":
        raise ValueError("candidate C must use linux/arm64")
    # Run the inspected immutable ID rather than allowing the local tag to change.
    container = command(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--network",
            "none",
            "--name",
            f"medy-dec001-c-smoke-{uuid.uuid4().hex[:12]}",
            "--cpus",
            "1",
            "--memory",
            "1g",
            "--shm-size",
            "128m",
            "--tmpfs",
            "/var/lib/postgresql/data:rw,size=512m",
            "--env",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "--env",
            "OPENBLAS_NUM_THREADS=1",
            "--env",
            "OMP_NUM_THREADS=1",
            image["Id"],
            "postgres",
            "-c",
            "shared_preload_libraries=pg_search",
            "-c",
            "max_parallel_workers=0",
            "-c",
            "shared_buffers=64MB",
        ]
    ).strip()
    started = time.monotonic()
    try:
        while True:
            ready = subprocess.run(
                ["docker", "exec", container, "pg_isready", "-U", "postgres"],
                text=True,
                capture_output=True,
                timeout=10,
            )
            pid1 = command(["docker", "exec", container, "cat", "/proc/1/comm"]).strip()
            if ready.returncode == 0 and pid1 == "postgres":
                break
            if time.monotonic() - started > 45:
                raise TimeoutError("isolated PostgreSQL did not become ready in 45 seconds")
            time.sleep(0.5)
        sql_diagnostics: list[str] = []
        sql_output = command(
            ["docker", "exec", "--interactive", container, "psql", "-X", "-A", "-t", "-q", "-U", "postgres"],
            data=sql,
            diagnostics=sql_diagnostics,
        )
        package_inventory = command(
            ["docker", "exec", container, "dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"]
        )
        extension_hashes = command(
            [
                "docker",
                "exec",
                container,
                "sha256sum",
                "/usr/lib/postgresql/16/lib/pg_search.so",
                "/usr/share/postgresql/16/extension/pg_search.control",
            ]
        )
        runtime_inspect = json.loads(command(["docker", "inspect", container]))[0]
        if runtime_inspect["HostConfig"]["NetworkMode"] != "none" or runtime_inspect["HostConfig"]["PortBindings"]:
            raise ValueError("smoke container must have no network or published port")
        evidence = {
            "candidate": "C",
            "verified_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "status": "synthetic_build_smoke_passed",
            "release_status": "release_blocked",
            "image_tag": args.image,
            "image_id": image["Id"],
            "image_repo_digests": image["RepoDigests"],
            "architecture": image["Architecture"],
            "os": image["Os"],
            "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
            "sql_stdout": sql_output,
            "sql_stderr": "".join(sql_diagnostics),
            "installed_packages_tsv": package_inventory,
            "extension_file_sha256s": extension_hashes,
            "isolation": {
                "network": "none",
                "published_ports": False,
                "data": "512MiB tmpfs",
                "cpus": 1,
                "memory_bytes": 1073741824,
            },
            "scope": "Only synthetic build/tokenizer/BM25 smoke as bootstrap superuser; no probe, RLS, latency, or production approval",
        }
    finally:
        command(["docker", "rm", "--force", container])
    evidence["temporary_container_removed"] = True
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"candidate C synthetic smoke passed; evidence: {args.out}")


if __name__ == "__main__":
    main()
