from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path so we can import tools
script_dir = Path(__file__).parent
parent_dir = script_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import tkinter as tk
from tkinter import ttk, messagebox
from tools.scheduler import list_task, create_user_task, delete_task, run_now, disable_task, enable_task


class SchedulerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Task Scheduler")
        self.geometry("560x360")

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        # Inputs
        self.name_var = tk.StringVar(value="KyloSyncPeriodic")
        self.mins_var = tk.IntVar(value=5)
        script_dir_str = str(script_dir.parent).replace("\\", "\\\\")
        self.cmd_var = tk.StringVar(value=f'cmd /c cd /d "{script_dir_str}" && python scripts\\run_both_syncs.py')

        row = 0
        ttk.Label(frm, text="Task Name").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.name_var, width=40).grid(row=row, column=1, columnspan=2, sticky="we")
        row += 1
        ttk.Label(frm, text="Every (minutes)").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.mins_var, width=10).grid(row=row, column=1, sticky="w")
        row += 1
        ttk.Label(frm, text="Command").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.cmd_var, width=40).grid(row=row, column=1, columnspan=2, sticky="we")

        # Buttons
        row += 1
        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=3, sticky="we", pady=8)
        ttk.Button(btns, text="Create/Update", command=self.create_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Run Now", command=self.run_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Enable", command=self.enable_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Disable", command=self.disable_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Delete", command=self.delete_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Refresh", command=self.refresh).pack(side=tk.RIGHT, padx=4)

        # Status
        row += 1
        self.tree = ttk.Treeview(frm, columns=("status", "next", "last", "result"), show="headings")
        self.tree.heading("status", text="Status")
        self.tree.heading("next", text="Next Run")
        self.tree.heading("last", text="Last Run")
        self.tree.heading("result", text="Last Result")
        self.tree.grid(row=row, column=0, columnspan=3, sticky="nsew")

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(row, weight=1)

        self.refresh()

    def refresh(self):
        name = self.name_var.get().strip()
        info = list_task(name)
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.tree.insert("", tk.END, values=(info.status or "N/A", info.next_run_time or "N/A", info.last_run_time or "N/A", info.last_result or "N/A"))

    def create_task(self):
        name = self.name_var.get().strip()
        mins = int(self.mins_var.get())
        cmd = self.cmd_var.get().strip()
        ok = create_user_task(name, mins, cmd)
        if not ok:
            messagebox.showerror("Error", "Failed to create/update task")
        self.refresh()

    def run_task(self):
        name = self.name_var.get().strip()
        ok = run_now(name)
        if not ok:
            messagebox.showerror("Error", "Failed to start task")
        self.refresh()

    def delete_task(self):
        name = self.name_var.get().strip()
        ok = delete_task(name)
        if not ok:
            messagebox.showerror("Error", "Failed to delete task")
        self.refresh()

    def disable_task(self):
        name = self.name_var.get().strip()
        ok = disable_task(name)
        if not ok:
            messagebox.showerror("Error", "Failed to disable task")
        self.refresh()

    def enable_task(self):
        name = self.name_var.get().strip()
        ok = enable_task(name)
        if not ok:
            messagebox.showerror("Error", "Failed to enable task")
        self.refresh()


if __name__ == "__main__":
    SchedulerGUI().mainloop()


