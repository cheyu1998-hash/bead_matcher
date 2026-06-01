"""本地启动器：启动 Flask Web 服务并自动打开浏览器。"""

import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

PORT = 5000


def _kill_port_occupier(port: int = PORT) -> None:
    """检查端口是否被占用，如果被占用则终止占用进程（仅限本机）。"""
    for attempt in range(3):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return  # 端口空闲

        # Windows: 用 netstat 找 PID，然后 taskkill
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                encoding="gbk",
                errors="ignore",
            )
            killed = False
            for line in result.stdout.splitlines():
                if f"127.0.0.1:{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        subprocess.run(
                            ["taskkill", "/PID", pid, "/F"],
                            capture_output=True,
                        )
                        print(f"  已终止占用端口 {port} 的进程 (PID: {pid})")
                        killed = True
                        break
            if not killed and attempt == 2:
                # 没找到监听进程但端口仍被占，尝试终止所有 python.exe
                print("  正在清理残留 Python 进程...")
                subprocess.run(
                    ["taskkill", "/IM", "python.exe", "/F"],
                    capture_output=True,
                )
            time.sleep(1)
        except Exception:
            time.sleep(1)


def _wait_and_open():
    time.sleep(1.2)
    webbrowser.open(f"http://127.0.0.1:{PORT}/")


if __name__ == "__main__":
    _kill_port_occupier()

    from web.app import app

    threading.Thread(target=_wait_and_open, daemon=True).start()

    print("=" * 42)
    print("  Bead Matcher 本地服务已启动")
    print("  正在打开浏览器...")
    print("  按 Ctrl+C 关闭服务")
    print("=" * 42)

    try:
        app.run(debug=False, port=PORT)
    except KeyboardInterrupt:
        print("\n服务已停止")
