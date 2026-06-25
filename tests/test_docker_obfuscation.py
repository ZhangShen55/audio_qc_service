from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path


def load_prepare_module():
    module_path = Path(__file__).resolve().parents[1] / "docker" / "prepare_obfuscated_app.py"
    spec = importlib.util.spec_from_file_location("prepare_obfuscated_app", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_cpu_docker_defaults_use_available_torchaudio_version():
    build_script = (Path(__file__).resolve().parents[1] / "docker" / "build.sh").read_text(
        encoding="utf-8"
    )

    assert 'TORCH_VERSION="${TORCH_VERSION:-2.7.0+cpu}"' in build_script
    assert 'TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-2.7.0}"' in build_script


def test_dockerfile_obfuscates_inside_linux_builder_stage():
    dockerfile = (
        Path(__file__).resolve().parents[1] / "docker" / "Dockerfile.obfuscated"
    ).read_text(encoding="utf-8")

    assert "AS obfuscator" in dockerfile
    assert "pip install --no-cache-dir -U pip pyarmor" in dockerfile
    assert "COPY --from=obfuscator /work/build/context/app /srv/app/app" in dockerfile


def test_generated_module_names_are_short_lowercase_and_stable():
    helper = load_prepare_module()
    used: set[str] = set()

    first = helper.generate_module_name(Path("services/qc_service.py"), used, salt="test")
    second = helper.generate_module_name(Path("services/qc_service.py"), set(), salt="test")

    assert first == second
    assert re.fullmatch(r"[a-z]{4,6}", first)


def test_prepare_staging_randomizes_protected_modules_and_writes_wrappers(tmp_path):
    helper = load_prepare_module()
    repo = tmp_path / "repo"
    source_app = repo / "app"
    (source_app / "services").mkdir(parents=True)
    (source_app / "api").mkdir(parents=True)
    (source_app / "main.py").write_text("from api.routes import router\n", encoding="utf-8")
    (source_app / "api" / "routes.py").write_text("router = object()\n", encoding="utf-8")
    (source_app / "services" / "__init__.py").write_text("", encoding="utf-8")
    (source_app / "services" / "qc_service.py").write_text(
        "class AudioQCService:\n    pass\n", encoding="utf-8"
    )

    result = helper.prepare_staging(repo_root=repo, build_dir=tmp_path / "build", salt="test")

    manifest = json.loads((result.stage_root / "obfuscation-manifest.json").read_text())
    mapping = manifest["module_map"]
    random_name = mapping["services/qc_service.py"]

    assert re.fullmatch(r"[a-z]{4,6}", random_name)
    assert (result.stage_app / "_x" / f"{random_name}.py").read_text(encoding="utf-8").startswith(
        "class AudioQCService:"
    )
    assert (result.stage_app / "services" / "qc_service.py").read_text(
        encoding="utf-8"
    ).startswith("# 生成的兼容包装模块")


def test_original_protected_source_detector_rejects_unwrapped_files(tmp_path):
    helper = load_prepare_module()
    app_root = tmp_path / "app"
    protected = app_root / "services" / "qc_service.py"
    protected.parent.mkdir(parents=True)
    protected.write_text("class AudioQCService:\n    pass\n", encoding="utf-8")
    manifest = {"protected_modules": ["services/qc_service.py"]}

    try:
        helper.assert_no_original_protected_sources(app_root, manifest)
    except helper.ObfuscationBuildError as exc:
        assert "不是生成的 wrapper" in str(exc)
    else:
        raise AssertionError("expected original protected source detection to fail")


def test_resolve_pyarmor_bin_falls_back_to_conda_env(tmp_path, monkeypatch):
    helper = load_prepare_module()
    env_bin = tmp_path / "envs" / "audio_qc" / "bin"
    env_bin.mkdir(parents=True)
    pyarmor = env_bin / "pyarmor"
    pyarmor.write_text("#!/bin/sh\n", encoding="utf-8")
    pyarmor.chmod(0o755)
    conda = tmp_path / "bin" / "conda"
    conda.parent.mkdir()
    conda.write_text("#!/bin/sh\n", encoding="utf-8")
    conda.chmod(0o755)

    monkeypatch.setattr(helper.shutil, "which", lambda name: None if name == "pyarmor" else str(conda))
    monkeypatch.setattr(
        helper,
        "run_command",
        lambda cmd, cwd=None: helper.subprocess.CompletedProcess(
            cmd, 0, stdout=str(env_bin / "python") + "\n"
        ),
    )

    assert helper.resolve_pyarmor_bin("pyarmor", conda_env="audio_qc") == str(pyarmor)


def test_basic_mode_validation_does_not_require_rft_probe(tmp_path, monkeypatch):
    helper = load_prepare_module()
    calls: list[list[str]] = []

    monkeypatch.setattr(helper, "resolve_pyarmor_bin", lambda pyarmor_bin, conda_env: "/bin/pyarmor")

    def fake_run(cmd, cwd=None):
        calls.append(cmd)
        return helper.subprocess.CompletedProcess(cmd, 0, stdout="Pyarmor 9.2.5 (trial)\n")

    monkeypatch.setattr(helper, "run_command", fake_run)

    resolved = helper.validate_pyarmor(
        pyarmor_bin="pyarmor",
        build_root=tmp_path,
        conda_env="audio_qc",
        mode="basic",
    )

    assert resolved == "/bin/pyarmor"
    assert all("--enable-rft" not in cmd for cmd in calls)


def test_pro_mode_validation_requires_rft_probe(tmp_path, monkeypatch):
    helper = load_prepare_module()
    calls: list[list[str]] = []

    monkeypatch.setattr(helper, "resolve_pyarmor_bin", lambda pyarmor_bin, conda_env: "/bin/pyarmor")

    def fake_run(cmd, cwd=None):
        calls.append(cmd)
        return helper.subprocess.CompletedProcess(cmd, 0, stdout="Pyarmor 9.2.5 Pro\n")

    monkeypatch.setattr(helper, "run_command", fake_run)

    helper.validate_pyarmor(
        pyarmor_bin="pyarmor",
        build_root=tmp_path,
        conda_env="audio_qc",
        mode="pro",
    )

    assert any("--enable-rft" in cmd for cmd in calls)


def test_enable_rft_requires_pro_mode(tmp_path, monkeypatch):
    helper = load_prepare_module()
    monkeypatch.setattr(helper, "validate_pyarmor", lambda **kwargs: "/bin/pyarmor")

    try:
        helper.prepare_obfuscated_context(
            repo_root=tmp_path,
            build_dir=tmp_path / "build",
            salt="test",
            pyarmor_bin="pyarmor",
            conda_env="audio_qc",
            mode="basic",
            enable_rft=True,
        )
    except helper.ObfuscationBuildError as exc:
        assert "要求 PYARMOR_MODE=pro" in str(exc)
    else:
        raise AssertionError("expected RFT in basic mode to fail")
