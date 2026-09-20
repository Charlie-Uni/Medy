"""Run candidate B's fixed synthetic smoke in a networkless, volume-free container.

Output is a new evidence directory. This does not read the frozen probe dataset.
The image tag is resolved once and all runtime operations use the actual image ID.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import tarfile
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAG = "medy-dec001-b:zhparser2.3-scws1.2.3"
SOURCES = {
    "zhparser": {
        "commit": "dd292fd591edbcb7ebee79d3c3cdc969e9cddced",
        "url": "https://codeload.github.com/amutu/zhparser/tar.gz/dd292fd591edbcb7ebee79d3c3cdc969e9cddced",
        "sha256": "ae670786b1372337d0527917692e7b40910fff0e3e9a727b3cccc09b73bd5584",
    },
    "scws": {
        "commit": "a04ef5e655213eb6b07fb57761d0eac72c281ad4",
        "url": "https://codeload.github.com/hightman/scws/tar.gz/a04ef5e655213eb6b07fb57761d0eac72c281ad4",
        "sha256": "c4f83883bf453aa9829a36abea76a11d546016fe639838b72b66bfca9f7f4d0d",
    },
}


def run(*args: str, stdin: str | None = None, timeout: int = 60) -> str:
    return subprocess.run(args, input=stdin, text=True, capture_output=True, check=True, timeout=timeout).stdout


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def archive_metadata(path: Path, image_id: str) -> dict:
    """Bind the saved OCI index, platform manifest and config to Docker's actual ID."""
    with tarfile.open(path) as archive:

        def blob(digest: str) -> dict:
            algorithm, value = digest.split(":", 1)
            if algorithm != "sha256" or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("invalid image digest")
            stream = archive.extractfile(f"blobs/sha256/{value}")
            if stream is None:
                raise ValueError("missing image archive blob")
            raw = stream.read()
            if hashlib.sha256(raw).hexdigest() != value:
                raise ValueError("image archive blob checksum mismatch")
            return json.loads(raw)

        index = blob(image_id)
        manifests = [
            entry
            for entry in index["manifests"]
            if entry.get("platform", {}).get("architecture") == "arm64"
            and entry.get("platform", {}).get("os") == "linux"
        ]
        if len(manifests) != 1:
            raise ValueError("expected exactly one linux/arm64 image manifest")
        manifest_digest = manifests[0]["digest"]
        manifest = blob(manifest_digest)
        config_digest = manifest["config"]["digest"]
        config = blob(config_digest)
        if config["architecture"] != "arm64" or config["os"] != "linux":
            raise ValueError("unexpected archive platform")
        for name, source in SOURCES.items():
            if config["config"]["Labels"].get(f"medy.{name}.commit") != source["commit"]:
                raise ValueError("image archive source mismatch")
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
        "oci_index_digest": image_id,
        "platform_manifest_digest": manifest_digest,
        "image_config_digest": config_digest,
    }


def cleanup(container: str, owner: str, out: Path) -> None:
    """Clean after a launch attempt, including a CLI timeout after Docker started it."""
    inspected = subprocess.run(["docker", "inspect", container], capture_output=True, text=True, timeout=30)
    if inspected.returncode != 0:
        if "No such object" in inspected.stderr or "No such container" in inspected.stderr:
            return
        raise RuntimeError(f"could not inspect temporary container for cleanup: {inspected.stderr}")
    details = json.loads(inspected.stdout)[0]
    if details["Config"]["Labels"].get("medy.dec001.owner") != owner:
        raise RuntimeError("refusing to clean a container with a different owner label")
    try:
        logs = subprocess.run(["docker", "logs", container], capture_output=True, text=True, check=True, timeout=30)
        (out / "container.log").write_text(logs.stdout + logs.stderr)
    finally:
        run("docker", "rm", "--force", "--volumes", container)
    if run("docker", "ps", "-aq", "--filter", f"name=^/{container}$").strip():
        raise RuntimeError("temporary container survived cleanup")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--image-archive", required=True, type=Path, help="docker image save archive, kept outside Git")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    for name, source in SOURCES.items():
        if sha256(args.source_dir / f"{name}.tar.gz") != source["sha256"]:
            raise ValueError(f"{name}: source archive checksum mismatch")
    image = json.loads(run("docker", "image", "inspect", TAG))[0]
    if image["Architecture"] != "arm64" or image["Os"] != "linux":
        raise ValueError("unexpected image platform")
    for name, source in SOURCES.items():
        if image["Config"]["Labels"].get(f"medy.{name}.commit") != source["commit"]:
            raise ValueError(f"{name}: image source label mismatch")
    saved_image = archive_metadata(args.image_archive, image["Id"])
    args.out.mkdir(parents=True, exist_ok=False)
    owner = uuid.uuid4().hex
    container = "medy-dec001-b-smoke-" + owner[:12]
    started = time.monotonic()
    try:
        run(
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            container,
            "--label",
            f"medy.dec001.owner={owner}",
            "--network",
            "none",
            "--cpus",
            "1",
            "--memory",
            "512m",
            "--read-only",
            "--tmpfs",
            "/var/lib/postgresql/data:rw,size=268435456",
            "--tmpfs",
            "/var/run/postgresql:rw,size=16777216",
            "--tmpfs",
            "/tmp:rw,size=16777216",
            "--env",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "--env",
            "POSTGRES_DB=dec001_b",
            image["Id"],
        )
        ready = False
        for _ in range(100):
            probe = subprocess.run(
                # The entrypoint's initialization server accepts Unix sockets before
                # POSTGRES_DB exists; only the final server listens on loopback TCP.
                ["docker", "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "dec001_b"],
                capture_output=True,
                timeout=5,
            )
            if probe.returncode == 0:
                ready = True
                break
            time.sleep(0.2)
        if not ready:
            raise RuntimeError("isolated PostgreSQL startup timed out")
        psql = ("docker", "exec", "-i", container, "psql", "-X", "-qAt", "-U", "postgres", "-d", "dec001_b")
        run(*psql, stdin=(HERE / "smoke.sql").read_text())
        first = json.loads(run(*psql, stdin=(HERE / "metadata.sql").read_text()))
        second = json.loads(run(*psql, stdin=(HERE / "metadata.sql").read_text()))
        if first != second:
            raise ValueError("synthetic metadata/tokenization changed across fresh connections")
        expected_gucs = {
            "zhparser.dict_in_memory": "off",
            "zhparser.extra_dicts": "",
            "zhparser.multi_duality": "off",
            "zhparser.multi_short": "off",
            "zhparser.multi_zall": "off",
            "zhparser.multi_zmain": "off",
            "zhparser.punctuation_ignore": "off",
            "zhparser.seg_with_duality": "off",
        }
        if {entry["name"]: entry["setting"] for entry in first["guc"]} != expected_gucs:
            raise ValueError("unexpected zhparser GUC snapshot")
        if first["pos_mapping"] != [
            {"maptokentype": value, "mapseqno": 1, "dictionary": "simple"}
            for value in range(97, 123)
            if value != ord("w")
        ]:
            raise ValueError("unexpected POS mapping")
        files = {
            "runtime_packages.tsv": ("dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"),
            "build_packages.tsv": ("cat", "/opt/dec001-b/build-packages.tsv"),
            "scws_config.log": ("cat", "/opt/dec001-b/scws-config.log"),
            "pg_config.txt": ("cat", "/opt/dec001-b/pg-config.txt"),
            "gcc_version.txt": ("cat", "/opt/dec001-b/gcc-version.txt"),
            "os_release.txt": ("cat", "/etc/os-release"),
            "scws_version.txt": ("scws", "-v"),
            "installed_sha256sums.txt": (
                "sh",
                "-c",
                "sha256sum /usr/local/etc/rules* "
                "/usr/share/postgresql/16/tsearch_data/dict.utf8.xdb "
                "/usr/share/postgresql/16/tsearch_data/rules.utf8.ini "
                "/usr/local/lib/libscws.so* /usr/lib/postgresql/16/lib/zhparser.so "
                "/opt/dec001-b/SCWS-COPYING /opt/dec001-b/zhparser-COPYRIGHT",
            ),
            "dynamic_linking.txt": ("ldd", "/usr/lib/postgresql/16/lib/zhparser.so"),
            "custom_dictionary_files.txt": ("find", "/var/lib/postgresql/data/base", "-name", "zhprs_dict_*"),
        }
        for filename, command in files.items():
            (args.out / filename).write_text(run("docker", "exec", container, *command))
        if (args.out / "custom_dictionary_files.txt").read_text().strip():
            raise ValueError("unexpected database-specific custom dictionary file")
        if "1.2.3" not in (args.out / "scws_version.txt").read_text():
            raise ValueError("unexpected SCWS runtime version")
        container_info = json.loads(run("docker", "inspect", container))[0]
        host = container_info["HostConfig"]
        if container_info["Mounts"] or set(host["Tmpfs"]) != {
            "/var/lib/postgresql/data",
            "/var/run/postgresql",
            "/tmp",
        }:
            raise ValueError("unexpected persistent or bind-mounted container data")
        evidence = {
            "candidate": "B",
            "status": "synthetic_smoke_passed_not_selection_evidence",
            "created_at": dt.datetime.now(dt.UTC).isoformat(),
            "sources": SOURCES,
            "base_image": "pgvector/pgvector:pg16@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b",
            "image": {
                key: image.get(key) for key in ("Id", "RepoTags", "RepoDigests", "Architecture", "Os", "Created")
            },
            "image_id_semantics": "Docker inspect Id; RepoDigests separately recorded, no registry push",
            "saved_image_archive": saved_image,
            "container": {
                "name": container,
                "network": container_info["HostConfig"]["NetworkMode"],
                "port_bindings": container_info["HostConfig"]["PortBindings"],
                "mounts": container_info["Mounts"],
                "read_only_rootfs": container_info["HostConfig"]["ReadonlyRootfs"],
                "tmpfs": host["Tmpfs"],
                "memory_bytes": host["Memory"],
                "nano_cpus": host["NanoCpus"],
            },
            "runtime": first,
            "fresh_connection_outputs_equal": True,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "source_and_config_files_sha256": {
                name: sha256(HERE / name)
                for name in ("Dockerfile", "build.sh", "smoke.sql", "metadata.sql", "collect.py")
            },
            "evidence_files_sha256": {path.name: sha256(path) for path in sorted(args.out.iterdir())},
            "probe_queries_read_or_executed": 0,
            "production_license_approval": None,
            "unverified": [
                "ordinary-role/RLS/count/version adapter contract",
                "75-query retrieval and latency gates",
                "production dictionary license clearance",
                "bit-for-bit rebuild from moving apt repositories",
            ],
        }
    except Exception as exc:
        failure = {"exception": type(exc).__name__, "message": str(exc)}
        if isinstance(exc, subprocess.CalledProcessError):
            failure.update(stdout=exc.stdout or "", stderr=exc.stderr or "")
        (args.out / "failure.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n")
        raise
    finally:
        cleanup(container, owner, args.out)
    evidence["container"]["removed"] = True
    evidence["evidence_files_sha256"]["container.log"] = sha256(args.out / "container.log")
    (args.out / "metadata.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(f"PASS: synthetic candidate B evidence written to {args.out}; temporary container removed")


if __name__ == "__main__":
    main()
