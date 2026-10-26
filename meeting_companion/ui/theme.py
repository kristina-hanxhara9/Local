import tkinter as tk
from tkinter import ttk

PALETTES = {
    "light": dict(bg="#F4F6F4", surface="#FFFFFF", text="#192E2B", muted="#667772",
                  line="#DDE6E0", accent="#117D70", soft="#E3F2EC", danger="#B3443A"),
    "dark": dict(bg="#142320", surface="#1D302C", text="#EEF6F1", muted="#A5BBB2",
                 line="#345047", accent="#46B9A3", soft="#24473C", danger="#FF9184"),
}


def apply_theme(root, name):
    p = PALETTES[name]
    style = ttk.Style(root)
    style.theme_use("clam")
    root.option_add("*Font", "{Segoe UI} 10")
    root.option_add("*Text.Font", "{Segoe UI} 11")
    style.configure(".", background=p["bg"], foreground=p["text"], font=("Segoe UI", 10))
    style.configure("TFrame", background=p["bg"])
    style.configure("Card.TFrame", background=p["surface"])
    style.configure("TLabel", background=p["bg"], foreground=p["text"])
    style.configure("Muted.TLabel", foreground=p["muted"])
    style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
    style.configure("Timer.TLabel", font=("Segoe UI", 30, "bold"))
    style.configure("TButton", padding=(12, 8), borderwidth=0, background=p["line"], foreground=p["text"])
    style.map("TButton", background=[("active", p["soft"])], foreground=[("disabled", p["muted"])])
    style.configure("Accent.TButton", background=p["accent"], foreground="#FFFFFF")
    style.map("Accent.TButton", background=[("active", "#166A5F"), ("disabled", p["line"])])
    style.configure("Danger.TButton", foreground=p["danger"])
    style.configure("TEntry", fieldbackground=p["surface"], foreground=p["text"], padding=7)
    style.configure("TCombobox", fieldbackground=p["surface"], foreground=p["text"], padding=5)
    style.map("TCombobox", fieldbackground=[("readonly", p["surface"])],
              foreground=[("readonly", p["text"])])
    style.configure("TCheckbutton", background=p["bg"], foreground=p["text"])
    style.map("TCheckbutton", background=[("active", p["bg"])])
    style.configure("Treeview", background=p["surface"], fieldbackground=p["surface"],
                    foreground=p["text"], rowheight=32)
    style.configure("Horizontal.TProgressbar", background=p["accent"], troughcolor=p["line"])
    root.configure(bg=p["bg"])
    return p


def text_area(parent, palette, **kwargs):
    return tk.Text(parent, bg=palette["surface"], fg=palette["text"], insertbackground=palette["text"],
                   selectbackground=palette["soft"], relief="flat", padx=16, pady=12,
                   wrap="word", undo=False, **kwargs)
