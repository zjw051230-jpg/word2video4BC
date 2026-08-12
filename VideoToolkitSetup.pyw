import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ROOT = Path(__file__).resolve().parent


def powershell(script, args):
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(script)] + args
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startup)


class Setup(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("word2video4BC 首次安装")
        self.geometry("760x560")
        self.minsize(680, 500)
        self.configure(bg="#f5f7fa")
        self.workspace = tk.StringVar(value=r"D:\视频生成")
        self.status = tk.StringVar(value="正在扫描本机环境...")
        self._build()
        self.after(100, self.scan)

    def _build(self):
        outer = ttk.Frame(self, padding=24)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="word2video4BC", font=("Segoe UI", 23, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Codex 主入口 · 仅安装扫描使用此程序", font=("Segoe UI", 11)).pack(anchor="w", pady=(2, 18))
        form = ttk.LabelFrame(outer, text="安装位置", padding=12)
        form.pack(fill="x")
        ttk.Label(form, text="工作区").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(form, textvariable=self.workspace).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Button(form, text="选择...", command=self.choose_workspace).grid(row=0, column=2, padx=(8, 0))
        ttk.Label(form, text="项目创建").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Label(form, text="安装后请直接告诉 Codex 创建项目").grid(row=1, column=1, columnspan=2, sticky="w", pady=5)
        form.columnconfigure(1, weight=1)
        scan = ttk.LabelFrame(outer, text="安装前扫描", padding=10)
        scan.pack(fill="both", expand=True, pady=14)
        self.tree = ttk.Treeview(scan, columns=("state", "detail"), show="headings", height=10)
        self.tree.heading("state", text="状态")
        self.tree.heading("detail", text="项目")
        self.tree.column("state", width=120, anchor="center")
        self.tree.column("detail", width=500)
        self.tree.pack(side="left", fill="both", expand=True)
        ttk.Scrollbar(scan, orient="vertical", command=self.tree.yview).pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=lambda a, b: None)
        ttk.Label(outer, textvariable=self.status).pack(anchor="w")
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="重新扫描", command=self.scan).pack(side="left")
        ttk.Button(actions, text="安装 / 更新", command=self.install).pack(side="right")

    def choose_workspace(self):
        value = filedialog.askdirectory(title="选择视频生成工作区")
        if value:
            self.workspace.set(value)
            self.scan()

    def scan(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        root = Path(os.path.expandvars(self.workspace.get())).expanduser()
        codex = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        checks = [
            ("Python", bool(self._which("py")), "Python 启动器"),
            ("ffmpeg", bool(self._which("ffmpeg")), "视频抽帧、转码和拼接"),
            ("视频技能", (codex / "skills" / "seedance-20" / "SKILL.md").exists(), "Codex Seedance 2.0 技能"),
            ("配音技能", (codex / "skills" / "seedance-voice-video-batch" / "SKILL.md").exists(), "检测到已有配音工具，跳过音频程序"),
            ("工作区", (root / "1.projects").exists(), str(root)),
        ]
        for name, exists, detail in checks:
            self.tree.insert("", "end", values=("已存在，跳过" if exists else "缺失，需要补充", f"{name}：{detail}"))
        self.status.set("扫描完成。日常生产请回到 Codex；配音工具只检测，不会重复安装或覆盖。")

    @staticmethod
    def _which(command):
        import shutil
        return shutil.which(command)

    def install(self):
        if not self.workspace.get().strip():
            messagebox.showerror("无法安装", "请选择工作区目录。")
            return
        self.status.set("正在安装，请稍候...")
        threading.Thread(target=self._install, daemon=True).start()

    def _install(self):
        args = ["-WorkspaceRoot", self.workspace.get().strip()]
        result = powershell(ROOT / "install.ps1", args)
        if result.returncode == 0:
            self.after(0, lambda: (self.status.set("安装完成。可以关闭窗口并重启 Codex。"), messagebox.showinfo("安装完成", "视频生成工具已安装。已有配音工具未重复安装。")))
        else:
            detail = (result.stderr or result.stdout or "未知错误").strip()
            self.after(0, lambda: (self.status.set("安装失败"), messagebox.showerror("安装失败", detail[-3000:])))


if __name__ == "__main__":
    Setup().mainloop()
