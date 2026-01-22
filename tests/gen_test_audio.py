"""
生成测试音频文件的工具脚本。
"""

import argparse
import wave
from pathlib import Path


def generate_test_wav(
    output_path: str,
    duration_seconds: int = 3,
    sample_rate: int = 16000,
) -> None:
    """
    生成测试用的 WAV 文件（16k mono）。
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    n_frames = sample_rate * duration_seconds

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)  # mono
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        # 写入静音数据（可修改为含有音频）
        wf.writeframes(b"\x00\x00" * n_frames)

    size_kb = output.stat().st_size / 1024
    print(f"生成测试音频: {output_path}")
    print(f"  时长: {duration_seconds}s")
    print(f"  采样率: {sample_rate} Hz")
    print(f"  大小: {size_kb:.2f} KB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成测试音频文件")
    parser.add_argument(
        "--output",
        type=str,
        default="test_audio.wav",
        help="输出文件路径",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=3,
        help="音频时长（秒）",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="采样率 (Hz)",
    )

    args = parser.parse_args()
    generate_test_wav(args.output, args.duration, args.sample_rate)
