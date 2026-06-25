from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import string
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable


INTERNAL_PACKAGE = "_x"
WRAPPER_MARKER = "# generated compatibility wrapper"
DEFAULT_SALT = "jy-audio-qc-v1.0.0"
DEFAULT_CONDA_ENV = "audio_qc"
DEFAULT_PYARMOR_MODE = "basic"


class ObfuscationBuildError(RuntimeError):
    pass


class PrepareResult:
    def __init__(self, build_root: Path, stage_root: Path, stage_app: Path, context_root: Path):
        self.build_root = build_root
        self.stage_root = stage_root
        self.stage_app = stage_app
        self.context_root = context_root


def app_relative(path: Path, app_root: Path) -> Path:
    return path.relative_to(app_root)


def is_stable_module(rel_path: Path) -> bool:
    parts = rel_path.parts
    if rel_path.name == "__init__.py":
        return True
    if rel_path == Path("main.py"):
        return True
    if parts and parts[0] == "api":
        return True
    return False


def generate_module_name(rel_path: Path, used: set[str], salt: str = DEFAULT_SALT) -> str:
    digest = hashlib.sha256(f"{salt}:{rel_path.as_posix()}".encode("utf-8")).digest()
    alphabet = string.ascii_lowercase
    length = 4 + digest[0] % 3
    offset = 1
    while True:
        name = "".join(alphabet[b % len(alphabet)] for b in digest[offset : offset + length])
        if name not in used:
            used.add(name)
            return name
        digest = hashlib.sha256(digest + rel_path.as_posix().encode("utf-8")).digest()
        offset = 0


def iter_app_files(app_root: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(app_root):
        dirs[:] = [d for d in sorted(dirs) if d not in {"__pycache__", ".pytest_cache", INTERNAL_PACKAGE}]
        for name in sorted(files):
            if name.endswith((".pyc", ".pyo")):
                continue
            yield Path(root) / name


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def wrapper_text(random_name: str) -> str:
    return (
        f"{WRAPPER_MARKER}; protected implementation lives in {INTERNAL_PACKAGE}.{random_name}\n"
        f"from {INTERNAL_PACKAGE}.{random_name} import *  # noqa: F401,F403\n"
    )


def prepare_staging(repo_root: Path, build_dir: Path, salt: str = DEFAULT_SALT) -> PrepareResult:
    repo_root = repo_root.resolve()
    source_app = repo_root / "app"
    if not source_app.is_dir():
        raise ObfuscationBuildError(f"app directory not found: {source_app}")

    build_root = build_dir.resolve()
    stage_root = build_root / "stage"
    stage_app = stage_root / "app"
    internal_root = stage_app / INTERNAL_PACKAGE

    clean_dir(stage_root)
    internal_root.mkdir(parents=True, exist_ok=True)
    (internal_root / "__init__.py").write_text("", encoding="utf-8")

    used: set[str] = set()
    module_map: dict[str, str] = {}
    protected_modules: list[str] = []
    stable_modules: list[str] = []

    for src in iter_app_files(source_app):
        rel = app_relative(src, source_app)
        dst = stage_app / rel
        if src.suffix != ".py":
            copy_file(src, dst)
            continue

        if is_stable_module(rel):
            copy_file(src, dst)
            stable_modules.append(rel.as_posix())
            continue

        random_name = generate_module_name(rel, used, salt=salt)
        protected_modules.append(rel.as_posix())
        module_map[rel.as_posix()] = random_name
        copy_file(src, internal_root / f"{random_name}.py")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(wrapper_text(random_name), encoding="utf-8")

    manifest = {
        "internal_package": INTERNAL_PACKAGE,
        "module_map": module_map,
        "protected_modules": protected_modules,
        "stable_modules": stable_modules,
    }
    (stage_root / "obfuscation-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return PrepareResult(
        build_root=build_root,
        stage_root=stage_root,
        stage_app=stage_app,
        context_root=build_root / "context",
    )


def assert_no_original_protected_sources(app_root: Path, manifest: dict) -> None:
    for rel in manifest.get("protected_modules", []):
        candidate = app_root / rel
        if not candidate.exists():
            continue
        text = candidate.read_text(encoding="utf-8")
        if not text.startswith(WRAPPER_MARKER):
            raise ObfuscationBuildError(f"protected source is not a generated wrapper: {rel}")


def run_command(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def resolve_pyarmor_bin(
    pyarmor_bin: str,
    conda_env: str = DEFAULT_CONDA_ENV,
    conda_bin: str = "conda",
) -> str | None:
    resolved = shutil.which(pyarmor_bin)
    if resolved is not None:
        return resolved

    if os.sep in pyarmor_bin:
        candidate = Path(pyarmor_bin)
        return str(candidate) if candidate.exists() and os.access(candidate, os.X_OK) else None

    conda = shutil.which(conda_bin)
    if conda is None or not conda_env:
        return None

    result = run_command(
        [
            conda,
            "run",
            "-n",
            conda_env,
            "python",
            "-c",
            "import sys; print(sys.executable)",
        ]
    )
    if result.returncode != 0:
        return None

    python_path = Path(result.stdout.strip().splitlines()[-1])
    candidate = python_path.with_name("pyarmor")
    return str(candidate) if candidate.exists() and os.access(candidate, os.X_OK) else None


def validate_pyarmor(
    pyarmor_bin: str,
    build_root: Path,
    conda_env: str = DEFAULT_CONDA_ENV,
    mode: str = DEFAULT_PYARMOR_MODE,
) -> str:
    if mode not in {"basic", "pro"}:
        raise ObfuscationBuildError("PYARMOR_MODE must be 'basic' or 'pro'")

    resolved = resolve_pyarmor_bin(pyarmor_bin, conda_env=conda_env)
    if resolved is None:
        raise ObfuscationBuildError(
            "PyArmor is required for obfuscated Docker builds. Install PyArmor "
            f"for conda env '{conda_env}', then rerun docker/build.sh."
        )

    version = run_command([resolved, "--version"])
    if version.returncode != 0:
        raise ObfuscationBuildError(f"failed to run PyArmor: {version.stdout.strip()}")

    if mode == "basic":
        return resolved

    probe_root = build_root / "pyarmor-probe"
    clean_dir(probe_root)
    probe_src = probe_root / "probe.py"
    probe_src.write_text("def probe(value):\n    return value + 1\n", encoding="utf-8")
    probe_out = probe_root / "out"
    probe = run_command([resolved, "gen", "--enable-rft", "-O", str(probe_out), str(probe_src)])
    if probe.returncode != 0:
        raise ObfuscationBuildError(
            "PyArmor Pro RFT probe failed. Confirm PyArmor Pro is installed and registered.\n"
            + probe.stdout.strip()
        )
    return resolved


def validate_pyarmor_pro(pyarmor_bin: str, build_root: Path, conda_env: str = DEFAULT_CONDA_ENV) -> str:
    return validate_pyarmor(
        pyarmor_bin=pyarmor_bin,
        build_root=build_root,
        conda_env=conda_env,
        mode="pro",
    )


def run_pyarmor(
    stage_app: Path,
    obfuscated_root: Path,
    pyarmor_bin: str,
    enable_rft: bool,
) -> None:
    clean_dir(obfuscated_root)
    cmd = [pyarmor_bin, "gen", "-r", "-O", str(obfuscated_root)]
    if enable_rft:
        cmd.append("--enable-rft")
    cmd.append(str(stage_app / INTERNAL_PACKAGE))
    result = run_command(cmd)
    if result.returncode != 0:
        raise ObfuscationBuildError("PyArmor obfuscation failed.\n" + result.stdout.strip())


def copy_pyarmor_output(obfuscated_root: Path, context_app: Path) -> None:
    internal_dst = context_app / INTERNAL_PACKAGE
    if internal_dst.exists():
        shutil.rmtree(internal_dst)

    internal_src = obfuscated_root / INTERNAL_PACKAGE
    if not internal_src.is_dir():
        raise ObfuscationBuildError(f"obfuscated internal package not found: {internal_src}")
    shutil.copytree(internal_src, internal_dst)

    for item in obfuscated_root.iterdir():
        if item.name == INTERNAL_PACKAGE:
            continue
        dst = context_app / item.name
        if item.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(item, dst)
        else:
            copy_file(item, dst)


def write_context_dockerignore(context_root: Path) -> None:
    (context_root / ".dockerignore").write_text(
        "\n".join(
            [
                ".build/",
                "__pycache__/",
                "*.pyc",
                "*.pyo",
                "*.pyd",
                "*.so",
                "*.egg-info/",
                ".git/",
                "tests/",
                "docs/",
                "scripts/",
                "",
            ]
        ),
        encoding="utf-8",
    )


def assemble_context(repo_root: Path, result: PrepareResult, obfuscated_root: Path) -> None:
    context_root = result.context_root
    clean_dir(context_root)
    shutil.copytree(result.stage_app, context_root / "app")
    copy_pyarmor_output(obfuscated_root, context_root / "app")

    for rel in ["config.toml", "vad_model"]:
        src = repo_root / rel
        dst = context_root / rel
        if not src.exists():
            raise ObfuscationBuildError(f"required deployment asset not found: {src}")
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            copy_file(src, dst)

    requirements = repo_root / "docker" / "requirements-runtime.txt"
    copy_file(requirements, context_root / "requirements-runtime.txt")
    copy_file(result.stage_root / "obfuscation-manifest.json", context_root / "obfuscation-manifest.json")
    copy_file(result.stage_root / "obfuscation-manifest.json", context_root / "app" / "obfuscation-manifest.json")
    write_context_dockerignore(context_root)

    manifest = json.loads((context_root / "obfuscation-manifest.json").read_text(encoding="utf-8"))
    assert_no_original_protected_sources(context_root / "app", manifest)


def prepare_obfuscated_context(
    repo_root: Path,
    build_dir: Path,
    salt: str,
    pyarmor_bin: str,
    conda_env: str,
    mode: str,
    enable_rft: bool,
) -> PrepareResult:
    if enable_rft and mode != "pro":
        raise ObfuscationBuildError("PYARMOR_ENABLE_RFT=1 requires PYARMOR_MODE=pro")

    build_root = build_dir.resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    resolved_pyarmor = validate_pyarmor(
        pyarmor_bin=pyarmor_bin,
        build_root=build_root,
        conda_env=conda_env,
        mode=mode,
    )
    result = prepare_staging(repo_root=repo_root, build_dir=build_dir, salt=salt)
    obfuscated_root = result.build_root / "pyarmor"
    run_pyarmor(
        stage_app=result.stage_app,
        obfuscated_root=obfuscated_root,
        pyarmor_bin=resolved_pyarmor,
        enable_rft=enable_rft,
    )
    assemble_context(repo_root=repo_root.resolve(), result=result, obfuscated_root=obfuscated_root)
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare an obfuscated Docker build context.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--build-dir", type=Path, default=Path("docker/.build"))
    parser.add_argument("--salt", default=os.environ.get("OBFUSCATION_SALT", DEFAULT_SALT))
    parser.add_argument("--pyarmor", default=os.environ.get("PYARMOR_BIN", "pyarmor"))
    parser.add_argument(
        "--conda-env",
        default=os.environ.get("PYARMOR_CONDA_ENV", DEFAULT_CONDA_ENV),
        help="Conda environment used as a fallback when pyarmor is not on PATH.",
    )
    parser.add_argument(
        "--enable-rft",
        action="store_true",
        default=os.environ.get("PYARMOR_ENABLE_RFT", "0") == "1",
        help="Enable PyArmor RFT for protected modules after the Pro probe passes.",
    )
    parser.add_argument(
        "--mode",
        choices=("basic", "pro"),
        default=os.environ.get("PYARMOR_MODE", DEFAULT_PYARMOR_MODE),
        help="basic works with PyArmor free/trial; pro requires an RFT-capable PyArmor Pro license.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        result = prepare_obfuscated_context(
            repo_root=args.repo_root,
            build_dir=args.build_dir,
            salt=args.salt,
            pyarmor_bin=args.pyarmor,
            conda_env=args.conda_env,
            mode=args.mode,
            enable_rft=args.enable_rft,
        )
    except ObfuscationBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({"context": str(result.context_root), "stage": str(result.stage_root)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
