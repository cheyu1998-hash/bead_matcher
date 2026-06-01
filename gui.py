#!/usr/bin/env python3
"""Bead Matcher - PyQt6 桌面客户端启动器（双击运行）"""

import sys
from pathlib import Path

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from gui.main_window import main

if __name__ == "__main__":
    main()
