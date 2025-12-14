import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from datetime import datetime
import math
import csv
import statistics

# Matplotlib for plotting in Tkinter
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Try importing pandas for convenient CSV export; fallback to csv module
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except Exception:
    PANDAS_AVAILABLE = False


DB_FILE = "bmi_app.db"


# ---------- Database helpers ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            weight_kg REAL NOT NULL,
            height_m REAL NOT NULL,
            bmi REAL NOT NULL,
            category TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


def get_or_create_user(name: str):
    name = name.strip()
    if not name:
        return None
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE name = ?", (name,))
    row = c.fetchone()
    if row:
        user_id = row[0]
    else:
        c.execute("INSERT INTO users (name) VALUES (?)", (name,))
        user_id = c.lastrowid
        conn.commit()
    conn.close()
    return user_id


def save_record(user_id: int, weight: float, height: float, bmi: float, category: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().isoformat(timespec='seconds')
    c.execute("""
        INSERT INTO records (user_id, date, weight_kg, height_m, bmi, category)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, now, weight, height, bmi, category))
    conn.commit()
    conn.close()


def fetch_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, name FROM users ORDER BY name COLLATE NOCASE")
    rows = c.fetchall()
    conn.close()
    return rows


def fetch_records_for_user(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT id, date, weight_kg, height_m, bmi, category
        FROM records
        WHERE user_id = ?
        ORDER BY date
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def fetch_all_records_for_user_as_dicts(user_id: int):
    rows = fetch_records_for_user(user_id)
    return [
        {
            "id": r[0],
            "date": r[1],
            "weight_kg": r[2],
            "height_m": r[3],
            "bmi": r[4],
            "category": r[5],
        }
        for r in rows
    ]

# BMI LOGIC
def calculate_bmi(weight_kg: float, height_m: float) -> float:
    # guard against zero height
    if height_m <= 0:
        raise ValueError("Height must be positive and non-zero.")
    bmi = weight_kg / (height_m ** 2)
    return bmi

def bmi_category(bmi: float) -> str:
    # WHO-ish categories (common)
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25.0:
        return "Normal"
    elif bmi < 30.0:
        return "Overweight"
    else:
        return "Obese"


# Graphical User Interface
class BMIApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BMI Calculator & Tracker")
        self.geometry("980x650")
        self.minsize(900, 600)

        # Initialize DB
        init_db()

        # UI Layout: left (input) / right (history + plot)
        self.left_frame = ttk.Frame(self, padding=(10, 10))
        self.right_frame = ttk.Frame(self, padding=(10, 10))

        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._build_left()
        self._build_right()
        self.refresh_users_dropdown()

    def _build_left(self):
        # Title
        ttk.Label(self.left_frame, text="BMI Calculator", font=("Times new Roman", 16, "bold")).pack(pady=(0, 10))

        # Name
        name_frame = ttk.Frame(self.left_frame)
        name_frame.pack(fill=tk.X, pady=4)
        ttk.Label(name_frame, text="User name:").pack(side=tk.LEFT)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=25)
        self.name_entry.pack(side=tk.LEFT, padx=(6, 0))

        # Weight
        w_frame = ttk.Frame(self.left_frame)
        w_frame.pack(fill=tk.X, pady=4)
        ttk.Label(w_frame, text="Weight (kg):").pack(side=tk.LEFT)
        self.weight_var = tk.StringVar()
        self.weight_entry = ttk.Entry(w_frame, textvariable=self.weight_var, width=12)
        self.weight_entry.pack(side=tk.LEFT, padx=(6, 0))

        # Height
        h_frame = ttk.Frame(self.left_frame)
        h_frame.pack(fill=tk.X, pady=4)
        ttk.Label(h_frame, text="Height (m):").pack(side=tk.LEFT)
        self.height_var = tk.StringVar()
        self.height_entry = ttk.Entry(h_frame, textvariable=self.height_var, width=12)
        self.height_entry.pack(side=tk.LEFT, padx=(6, 0))

        # Buttons
        btn_frame = ttk.Frame(self.left_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        calc_btn = ttk.Button(btn_frame, text="Calculate & Save", command=self.on_calculate_and_save)
        calc_btn.pack(side=tk.LEFT, padx=2)
        calc_only_btn = ttk.Button(btn_frame, text="Calculate Only", command=self.on_calculate_only)
        calc_only_btn.pack(side=tk.LEFT, padx=2)

        # Results
        self.result_str = tk.StringVar(value="BMI: N/A")
        ttk.Label(self.left_frame, textvariable=self.result_str, font=("Helvetica", 12, "bold")).pack(pady=(10, 2))
        self.cat_str = tk.StringVar(value="Category: N/A")
        ttk.Label(self.left_frame, textvariable=self.cat_str).pack()

        # Separator
        ttk.Separator(self.left_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=12)

        # Controls for history & export
        history_controls = ttk.Frame(self.left_frame)
        history_controls.pack(fill=tk.X, pady=4)

        ttk.Label(history_controls, text="Select user:").pack(side=tk.LEFT)
        self.user_combo_var = tk.StringVar()
        self.user_combo = ttk.Combobox(history_controls, textvariable=self.user_combo_var, state="readonly", width=20)
        self.user_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.user_combo.bind("<<ComboboxSelected>>", lambda e: self.on_user_selected())

        refresh_btn = ttk.Button(history_controls, text="Refresh Users", command=self.refresh_users_dropdown)
        refresh_btn.pack(side=tk.LEFT, padx=6)

        export_btn = ttk.Button(self.left_frame, text="Export History (CSV)", command=self.export_history_csv)
        export_btn.pack(fill=tk.X, pady=(10, 0))

        clear_btn = ttk.Button(self.left_frame, text="Clear All Records (Danger!)", command=self.clear_all_records)
        clear_btn.pack(fill=tk.X, pady=(10, 0))

    def _build_right(self):
        # Top: Treeview for history
        ttk.Label(self.right_frame, text="History", font=("Helvetica", 14, "bold")).pack(anchor=tk.W)
        self.tree = ttk.Treeview(self.right_frame, columns=("date", "weight", "height", "bmi", "category"), show="headings", height=10)
        for col, text in [("date", "Date"), ("weight", "Weight (kg)"), ("height", "Height (m)"), ("bmi", "BMI"), ("category", "Category")]:
            self.tree.heading(col, text=text)
            self.tree.column(col, anchor=tk.CENTER, width=110)
        self.tree.pack(fill=tk.X, pady=6)

        # Statistics row
        stats_frame = ttk.Frame(self.right_frame)
        stats_frame.pack(fill=tk.X, pady=(4, 12))
        self.stat_mean = tk.StringVar(value="Mean BMI: N/A")
        self.stat_min = tk.StringVar(value="Min BMI: N/A")
        self.stat_max = tk.StringVar(value="Max BMI: N/A")
        ttk.Label(stats_frame, textvariable=self.stat_mean).pack(side=tk.LEFT, padx=6)
        ttk.Label(stats_frame, textvariable=self.stat_min).pack(side=tk.LEFT, padx=6)
        ttk.Label(stats_frame, textvariable=self.stat_max).pack(side=tk.LEFT, padx=6)

        # Plot area
        ttk.Label(self.right_frame, text="BMI Trend", font=("Helvetica", 14, "bold")).pack(anchor=tk.W)
        self.fig = Figure(figsize=(6, 3.5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("No user selected")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("BMI")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.right_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ---------- Event handlers ----------
    def on_calculate_only(self):
        try:
            weight = float(self.weight_var.get())
            height = float(self.height_var.get())
            bmi = calculate_bmi(weight, height)
            cat = bmi_category(bmi)
            self.result_str.set(f"BMI: {bmi:.2f}")
            self.cat_str.set(f"Category: {cat}")
        except Exception as e:
            messagebox.showerror("Input error", f"Invalid input: {e}")

    def on_calculate_and_save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Please enter a user name.")
            return
        try:
            weight = float(self.weight_var.get())
            height = float(self.height_var.get())
            bmi = calculate_bmi(weight, height)
            cat = bmi_category(bmi)
        except Exception as e:
            messagebox.showerror("Input error", f"Invalid input: {e}")
            return

        user_id = get_or_create_user(name)
        if user_id is None:
            messagebox.showerror("User error", "Could not create or find user.")
            return

        save_record(user_id, weight, height, bmi, cat)
        self.result_str.set(f"BMI: {bmi:.2f}")
        self.cat_str.set(f"Category: {cat}")
        messagebox.showinfo("Saved", f"Saved record for {name} (BMI {bmi:.2f}, {cat}).")
        self.refresh_users_dropdown()
        # If saved user is selected, refresh history & plot
        cur = self.user_combo_var.get()
        if cur == name:
            self.on_user_selected()

    def refresh_users_dropdown(self):
        users = fetch_users()
        names = [r[1] for r in users]
        self.user_combo['values'] = names
        # If currently selected user not present, clear table
        selected = self.user_combo_var.get()
        if selected not in names:
            self.user_combo_var.set('')
            self.clear_history_table()
            self.clear_plot()

    def on_user_selected(self):
        name = self.user_combo_var.get()
        if not name:
            return
        # find user id
        users = fetch_users()
        user_id = None
        for u in users:
            if u[1] == name:
                user_id = u[0]
                break
        if user_id is None:
            return
        self.populate_history_for_user(user_id)
        self.plot_for_user(user_id)

    def clear_history_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.stat_mean.set("Mean BMI: N/A")
        self.stat_min.set("Min BMI: N/A")
        self.stat_max.set("Max BMI: N/A")

    def populate_history_for_user(self, user_id: int):
        self.clear_history_table()
        records = fetch_records_for_user(user_id)
        for rec in records:
            _id, date, weight, height, bmi, cat = rec
            self.tree.insert('', tk.END, values=(date, f"{weight:.2f}", f"{height:.2f}", f"{bmi:.2f}", cat))
        # update stats
        bmis = [r[4] for r in records]
        if bmis:
            mean_b = statistics.mean(bmis)
            min_b = min(bmis)
            max_b = max(bmis)
            self.stat_mean.set(f"Mean BMI: {mean_b:.2f}")
            self.stat_min.set(f"Min BMI: {min_b:.2f}")
            self.stat_max.set(f"Max BMI: {max_b:.2f}")
        else:
            self.stat_mean.set("Mean BMI: N/A")
            self.stat_min.set("Min BMI: N/A")
            self.stat_max.set("Max BMI: N/A")

    def clear_plot(self):
        self.ax.clear()
        self.ax.set_title("No user selected")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("BMI")
        self.canvas.draw()

    def plot_for_user(self, user_id: int):
        rows = fetch_records_for_user(user_id)
        if not rows:
            self.clear_plot()
            return
        dates = [datetime.fromisoformat(r[1]) for r in rows]
        bmis = [r[4] for r in rows]
        self.ax.clear()
        self.ax.plot(dates, bmis, marker='o', linestyle='-', linewidth=2)
        self.ax.set_title("BMI Trend")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("BMI")
        self.ax.grid(True, linestyle='--', alpha=0.4)
        # annotate points with BMI values
        for x, y in zip(dates, bmis):
            self.ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points", xytext=(0,6), ha='center', fontsize=8)
        self.fig.autofmt_xdate()
        self.canvas.draw()

    def export_history_csv(self):
        name = self.user_combo_var.get().strip()
        if not name:
            messagebox.showwarning("No user selected", "Select a user to export their history.")
            return
        # get user id
        users = fetch_users()
        user_id = None
        for u in users:
            if u[1] == name:
                user_id = u[0]
                break
        if user_id is None:
            messagebox.showerror("Error", "User not found.")
            return
        recs = fetch_all_records_for_user_as_dicts(user_id)
        if not recs:
            messagebox.showinfo("No records", "This user has no records to export.")
            return

        # ask for file path
        filetypes = [("CSV files", "*.csv"), ("All files", "*.*")]
        default_name = f"{name}_bmi_history.csv"
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=filetypes, initialfile=default_name)
        if not path:
            return

        try:
            if PANDAS_AVAILABLE:
                df = pd.DataFrame(recs)
                df.to_csv(path, index=False)
            else:
                # Use csv module
                keys = ["date", "weight_kg", "height_m", "bmi", "category"]
                with open(path, "w", newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["date", "weight_kg", "height_m", "bmi", "category"])
                    for r in recs:
                        writer.writerow([r["date"], r["weight_kg"], r["height_m"], r["bmi"], r["category"]])
            messagebox.showinfo("Exported", f"History exported to: {path}")
        except Exception as e:
            messagebox.showerror("Export error", f"Could not export CSV: {e}")

    def clear_all_records(self):
        if not messagebox.askyesno("Confirm delete", "This will permanently delete ALL users and records. Continue?"):
            return
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM records")
            c.execute("DELETE FROM users")
            conn.commit()
            conn.close()
            messagebox.showinfo("Cleared", "All users and records have been deleted.")
            self.refresh_users_dropdown()
            self.clear_history_table()
            self.clear_plot()
        except Exception as e:
            messagebox.showerror("Error", f"Could not clear data: {e}")


if __name__ == "__main__":
    app = BMIApp()
    app.mainloop()
5
