"""Tkinter control window + alert pop-ups."""
import datetime
import queue
import tkinter as tk
import winsound
from tkinter import messagebox, ttk

from .config import save_config
from .engine import Engine
from .store import EventStore

CONSENT = ("I have my employer's approval, and I have informed (or have consent from) the "
           "meeting participants, to run local transcription of this meeting.")


class App:
    def __init__(self, cfg):
        self.cfg = cfg
        self.events: queue.Queue = queue.Queue()
        self.store = EventStore(retention_hours=cfg["retention_hours"])
        self.engine = None
        self.popups: dict[str, dict] = {}

        self.root = tk.Tk()
        self.root.title("MentionAlert (local only)")
        self.root.geometry("640x620")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build()
        self.purge()
        self.refresh_history()
        self.root.after(200, self.poll)
        self.root.after(3600_000, self.hourly_purge)

    def _build(self):
        r = self.root
        pad = {"padx": 10, "pady": 4}
        ttk.Label(r, text="MentionAlert", font=("Segoe UI", 15, "bold")).pack(anchor="w", **pad)
        ttk.Label(r, text="Everything runs on this PC. No audio or text leaves it. Nothing is "
                          "saved except short alert summaries (auto-deleted).",
                  wraplength=600).pack(anchor="w", **pad)

        self.consent = tk.BooleanVar(value=False)
        tk.Checkbutton(r, text=CONSENT, variable=self.consent, command=self.update_buttons,
                       wraplength=600, justify="left").pack(anchor="w", **pad)

        row = ttk.Frame(r)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="My name(s), comma separated:").pack(side="left")
        self.names = tk.StringVar(value=", ".join(self.cfg["names"]))
        ttk.Entry(row, textvariable=self.names, width=36).pack(side="left", padx=6)
        ttk.Button(row, text="Save", command=self.save_names).pack(side="left")

        self.status = tk.StringVar(value="\u25CB STOPPED")
        self.status_lbl = tk.Label(r, textvariable=self.status, font=("Segoe UI", 14, "bold"),
                                   fg="gray30")
        self.status_lbl.pack(anchor="w", **pad)

        btns = ttk.Frame(r)
        btns.pack(fill="x", **pad)
        self.b_start = ttk.Button(btns, text="Start", command=self.start)
        self.b_pause = ttk.Button(btns, text="Pause", command=self.pause)
        self.b_stop = ttk.Button(btns, text="Stop", command=self.stop)
        for b in (self.b_start, self.b_pause, self.b_stop):
            b.pack(side="left", padx=4)

        self.stats = tk.StringVar(value="")
        ttk.Label(r, textvariable=self.stats).pack(anchor="w", **pad)

        self.show_tx = tk.BooleanVar(value=self.cfg["show_live_transcript_default"])
        ttk.Checkbutton(r, text="Show live transcript below (display only, never saved)",
                        variable=self.show_tx).pack(anchor="w", **pad)
        self.tx = tk.Text(r, height=7, wrap="word", state="disabled")
        self.tx.pack(fill="x", **pad)

        ttk.Label(r, text="Recent alerts (encrypted on disk, auto-deleted):").pack(anchor="w", **pad)
        self.history = tk.Text(r, height=9, wrap="word", state="disabled")
        self.history.pack(fill="both", expand=True, **pad)

        row2 = ttk.Frame(r)
        row2.pack(fill="x", **pad)
        ttk.Button(row2, text="Purge expired now", command=self.purge_click).pack(side="left", padx=4)
        ttk.Button(row2, text="Delete ALL data", command=self.delete_all).pack(side="left", padx=4)
        self.update_buttons()

    def update_buttons(self):
        state = (self.engine.state if self.engine else "stopped")
        ok = self.consent.get()
        self.b_start.configure(state="normal" if ok and state in ("stopped", "paused") else "disabled")
        self.b_pause.configure(state="normal" if state == "listening" else "disabled")
        self.b_stop.configure(state="normal" if state != "stopped" else "disabled")

    def save_names(self):
        if self.engine and self.engine.state != "stopped":
            messagebox.showinfo("MentionAlert", "Stop capture before changing names.")
            return
        names = [n.strip() for n in self.names.get().split(",") if n.strip()]
        if not names:
            messagebox.showwarning("MentionAlert", "Enter at least one name.")
            return
        self.cfg["names"] = names
        save_config(self.cfg)
        messagebox.showinfo("MentionAlert", f"Saved: {', '.join(names)}")

    def start(self):
        if not self.cfg["names"]:
            messagebox.showwarning("MentionAlert", "Set and save your name first.")
            return
        if self.engine is None or self.engine.state == "stopped":
            self.engine = Engine(self.cfg, self.events.put, self.store)
        self.engine.start()
        self.update_buttons()

    def pause(self):
        if self.engine:
            self.engine.pause()
        self.update_buttons()

    def stop(self):
        if self.engine:
            self.engine.stop()
        self.update_buttons()

    def poll(self):
        try:
            while True:
                self.handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(200, self.poll)

    def handle(self, ev):
        t = ev["type"]
        if t == "status":
            labels = {"stopped": ("\u25CB STOPPED", "gray30"),
                      "loading": ("\u25D4 LOADING MODEL...", "darkorange"),
                      "listening": ("\u25CF LISTENING (capturing system audio)", "red"),
                      "paused": ("\u275A\u275A PAUSED", "darkorange")}
            text, color = labels[ev["state"]]
            self.status.set(text)
            self.status_lbl.configure(fg=color)
            self.update_buttons()
        elif t == "stats":
            self.stats.set(f"Chunks processed: {ev['chunks']}   Dropped (overload): {ev['dropped']}")
        elif t == "transcript" and self.show_tx.get():
            self.tx.configure(state="normal")
            self.tx.insert("end", ev["text"] + "\n")
            lines = int(self.tx.index("end-1c").split(".")[0])
            if lines > 40:
                self.tx.delete("1.0", f"{lines - 40}.0")
            self.tx.see("end")
            self.tx.configure(state="disabled")
        elif t == "mention":
            self.show_popup(ev)
        elif t == "summary":
            self.update_popup(ev)
            self.refresh_history()
        elif t in ("error", "notice"):
            messagebox.showwarning("MentionAlert", ev["msg"])

    def show_popup(self, ev):
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass
        w = tk.Toplevel(self.root)
        w.title("You were mentioned")
        w.attributes("-topmost", True)
        w.geometry("460x230+60+60")
        ttk.Label(w, text="\U0001F514 Your name was mentioned", font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=10, pady=6)
        ttk.Label(w, text="Heard:", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10)
        snippet = tk.StringVar(value=ev["snippet"])
        ttk.Label(w, textvariable=snippet, wraplength=430).pack(anchor="w", padx=10)
        ttk.Label(w, text="Why (summary):", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        summ = tk.StringVar(value="Summarising...")
        ttk.Label(w, textvariable=summ, wraplength=430).pack(anchor="w", padx=10)
        ttk.Button(w, text="Dismiss", command=w.destroy).pack(pady=8)
        self.popups[ev["id"]] = {"win": w, "snippet": snippet, "var": summ}

    def update_popup(self, ev):
        p = self.popups.pop(ev["id"], None)
        if p and p["win"].winfo_exists():
            p["snippet"].set(ev["snippet"])
            p["var"].set(ev["summary"])

    def refresh_history(self):
        events = sorted(self.store.list(), key=lambda e: e["ts"], reverse=True)[:20]
        self.history.configure(state="normal")
        self.history.delete("1.0", "end")
        for e in events:
            when = datetime.datetime.fromtimestamp(e["ts"]).strftime("%Y-%m-%d %H:%M:%S")
            self.history.insert("end", f"[{when}] {e['summary']}\n   heard: {e['snippet']}\n\n")
        self.history.configure(state="disabled")

    def purge(self):
        return self.store.purge_expired()

    def purge_click(self):
        n = self.purge()
        self.refresh_history()
        messagebox.showinfo("MentionAlert", f"Removed {n} expired alert(s).")

    def hourly_purge(self):
        self.purge()
        self.refresh_history()
        self.root.after(3600_000, self.hourly_purge)

    def delete_all(self):
        if messagebox.askyesno("MentionAlert", "Delete all saved alerts and the encryption key?"):
            self.store.delete_all()
            self.refresh_history()

    def on_close(self):
        if self.engine:
            self.engine.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
