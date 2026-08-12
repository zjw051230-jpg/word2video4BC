import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


class ApiConfig(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Seedance API 配置")
        self.geometry("620x300")
        self.workspace = tk.StringVar(value=r"D:\视频生成")
        self.base_url = tk.StringVar(value="https://chat.q1.com/v1")
        self.model = tk.StringVar(value="doubao-seedance-2.0")
        self.key = tk.StringVar()
        self._build()

    def _build(self):
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Seedance API 密钥配置", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        ttk.Label(frame, text="仅用于输入涉密信息；普通任务请在 Codex 中操作。", font=("Segoe UI", 9)).grid(row=0, column=1, columnspan=2, sticky="e", pady=(0, 6))
        rows = [("工作区", self.workspace), ("API Key", self.key), ("Base URL", self.base_url), ("模型", self.model)]
        for i, (label, value) in enumerate(rows, 1):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=6)
            ttk.Entry(frame, textvariable=value, show="*" if label == "API Key" else "").grid(row=i, column=1, columnspan=2, sticky="ew", pady=6)
        ttk.Button(frame, text="选择...", command=self.choose).grid(row=1, column=3, padx=(8, 0))
        ttk.Button(frame, text="保存配置", command=self.save).grid(row=5, column=2, sticky="e", pady=(16, 0))
        frame.columnconfigure(1, weight=1)

    def choose(self):
        value = filedialog.askdirectory(title="选择视频生成工作区")
        if value:
            self.workspace.set(value)

    def save(self):
        if not self.key.get().strip():
            messagebox.showerror("无法保存", "API Key 不能为空。")
            return
        target = Path(os.path.expandvars(self.workspace.get())).expanduser() / "4.apis" / "seedance"
        target.mkdir(parents=True, exist_ok=True)
        (target / "credentials.json").write_text(json.dumps({"api_key": self.key.get().strip(), "authorization_header": "Authorization", "authorization_scheme": "Bearer"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (target / "doubao_api_config.json").write_text(json.dumps({"api_key": self.key.get().strip(), "base_url": self.base_url.get().strip(), "model": self.model.get().strip()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        messagebox.showinfo("已保存", f"配置已写入本机：\n{target}")


if __name__ == "__main__":
    ApiConfig().mainloop()
