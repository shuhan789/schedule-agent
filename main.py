"""入口：python main.py <命令>。把 src/ 加入路径，免去安装步骤（Windows / macOS / Linux 通用）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from schedule_agent.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
