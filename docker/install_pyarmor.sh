#!/usr/bin/env bash
set -euo pipefail

CONDA_ENV="${CONDA_ENV:-audio_qc}"
PYARMOR_PACKAGE="${PYARMOR_PACKAGE:-pyarmor}"

if ! command -v conda >/dev/null 2>&1; then
  echo "未找到 conda 命令。请安装 Miniconda/Anaconda，或先激活可使用 conda 的 shell。" >&2
  exit 2
fi

if ! conda env list | awk '{print $1}' | grep -qx "${CONDA_ENV}"; then
  echo "未找到 conda 环境 '${CONDA_ENV}'。" >&2
  exit 2
fi

conda run -n "${CONDA_ENV}" python -m pip install -U "${PYARMOR_PACKAGE}"

echo "已在 conda 环境 '${CONDA_ENV}' 中安装 PyArmor 包。"
echo "如果有 PyArmor Pro 注册文件，可执行以下命令注册："
echo "  conda run -n ${CONDA_ENV} pyarmor reg /path/to/pyarmor-regfile.zip"
echo "然后执行以下命令验证："
echo "  conda run -n ${CONDA_ENV} pyarmor --version"
