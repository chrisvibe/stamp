import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from datetime import datetime, timedelta
from pytz import timezone, utc
import sqlite3
import yaml
import csv
from pathlib import Path

class StampApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Stamp In/Out Application")

        # Load defaults from YAML file
        self.defaults = self.load_defaults('defaults.yaml')

        # Load codes from defaults
        self.codes = [code.strip() for code in self.defaults.get('codes', 'work,play').split(',')]
        self.default_code_stamp_in = self.defaults.get('default_code_stamp_in', 'work')
        self.default_code_stamp_out = self.defaults.get('default_code_stamp_out', 'play')

        self.lunch_start = datetime.strptime(self.defaults.get('typical_lunch_start', '10:30'), '%H:%M').time()
        self.lunch_stop = datetime.strptime(self.defaults.get('typical_lunch_stop', '13:00'), '%H:%M').time()

        self.stamped_in = None
        self.time_zone = timezone(str(datetime.now().astimezone().tzinfo))

        self.text_size = self.defaults.get('text_size', 12)
        self.font = self.defaults.get('font', 'Courier')

        self.setup_ui()

        # Set the database file path and backup if necesarry
        db_file = Path(self.defaults.get('default_code_stamp_out', 'data/time_log.db'))
        if not (db_file.is_file() and db_file.suffix == '.db'):
            db_file = Path('data/time_log.db')
        print('using database:', db_file)
        self.DB_FILE = db_file 
        self.DB_FILE.parent.mkdir(exist_ok=True)
        self.backup_days = int(self.defaults.get('backup_days', '7'))
        self.backup_dir = Path(self.defaults.get('backup_dir', 'out/backups/'))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.check_creation_date_and_backup()

        # Set window size after UI is created
        self.set_window_size()

        path = Path(self.DB_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.DB_FILE)
        self.setup_database()

        self.update_status_from_database()
    
    def check_creation_date_and_backup(self):
        def copy_file(src, dst):
            dst.write_bytes(src.read_bytes())

        current_time = datetime.now()
        if self.DB_FILE.exists():
            creation_time = datetime.fromtimestamp(self.DB_FILE.stat().st_ctime)
            age_in_days = (current_time - creation_time).days

            if age_in_days > self.backup_days:
                backup_filename = f"{current_time.strftime('%Y-%m-%d')}_{self.DB_FILE.name}"
                backup_path = self.backup_dir / backup_filename
                copy_file(self.DB_FILE, backup_path)
                print(f"Database backed up to: {backup_path}")

    def load_defaults(self, file_path):
        try:
            with open(file_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            return {}
        except yaml.YAMLError as e:
            return {}

    def setup_database(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''CREATE TABLE IF NOT EXISTS log (
                                id INTEGER PRIMARY KEY,
                                timestamp TEXT NOT NULL,
                                status TEXT NOT NULL,
                                code TEXT NOT NULL,
                                comment TEXT
                            )''')
            self.conn.commit()
        finally:
            cursor.close()
            
    def update_status_from_database(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT timestamp, status FROM log ORDER BY timestamp DESC LIMIT 1")
            last_db_entry = cursor.fetchone()
        finally:
            cursor.close()

        status = 'in'
        if last_db_entry:
            last_entry_time_utc = datetime.fromisoformat(last_db_entry[0]).replace(tzinfo=utc)
            last_entry_time_local = last_entry_time_utc.astimezone(self.time_zone)
            status = last_db_entry[1]
            status_msg = f"Status: {status} @{last_entry_time_local.strftime('%Y-%m-%d %H:%M:%S')}"
            self.status_label.config(text=status_msg)
            self.stamped_in = last_entry_time_utc if status == 'in' else None
        else:
            self.status_label.config(text="Status: ")
        self.set_window_size()
        button_clr_dict = {'in': 'green', 'out': 'red'}
        self.stamp_button.config(bg=button_clr_dict[status] if status in button_clr_dict else 'green')

    def set_window_size(self):
        # Let the window calculate its required size
        self.root.update_idletasks()
        
        # Get the required window size
        width = self.root.winfo_reqwidth() + 40
        height = self.root.winfo_reqheight()
        
        # Get the screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate the x and y coordinates for the window
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # Set the window size and position
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # Prevent window resizing
        self.root.resizable(False, False)

    def setup_ui(self):
        self.status_label = tk.Label(self.root, text="Status: ", font=(self.font, self.text_size, 'italic'))
        self.status_label.pack(anchor='nw', pady=10)

        # Frame for code and comment
        input_frame = tk.Frame(self.root)
        input_frame.pack(fill='x', padx=5)

        # Code dropdown
        code_label = tk.Label(input_frame, text="Code:", font=(self.font, self.text_size, "bold"))
        code_label.pack(anchor='w', padx=(0, 5))

        self.code_var = tk.StringVar(value=self.default_code_stamp_in)
        self.code_dropdown = ttk.Combobox(input_frame, textvariable=self.code_var, values=self.codes, 
                                        font=(self.font, self.text_size), width=15, state='readonly')
        self.code_dropdown.pack(fill='x', padx=(0, 10))

        # Comment entry
        self.comment_label = tk.Label(input_frame, text=self.defaults.get('stamp_in_comment_msg', 'Stamp in comment:'), 
                                    font=(self.font, self.text_size, "bold"))
        self.comment_label.pack(anchor='w', padx=(0, 5), pady=(10, 0))  # Added pady for better spacing

        self.comment_var = tk.StringVar(value=self.defaults.get('default_stamp_in_comment', ''))
        self.comment_entry = tk.Entry(input_frame, textvariable=self.comment_var, font=(self.font, self.text_size))
        self.comment_entry.pack(fill='x', expand=True, pady=(0, 10))  # Added pady for better spacing

        self.stamp_button = tk.Button(self.root, text=" Stamp In/Out ", bg='green', font=(self.font, self.text_size), 
                                    command=self.stamp_in_out)
        self.stamp_button.pack(pady=5)

        self.modify_button = tk.Button(self.root, text="Modify Entries", bg='orange', font=(self.font, self.text_size), 
                                     command=self.modify_last_entry)
        self.modify_button.pack(pady=5)

        self.browse_button = tk.Button(self.root, text="Browse Entries", bg='black', fg='white', 
                                     font=(self.font, self.text_size), command=self.browse_entries)
        self.browse_button.pack(pady=5)

    def stamp_in_out(self):
        now_utc = datetime.now(utc)
        now_local = now_utc.astimezone(self.time_zone)

        if self.stamped_in is None:
            self.stamped_in = now_utc
            code = self.code_var.get()
            comment = self.comment_var.get()
            cursor = self.conn.cursor()
            try:
                cursor.execute("INSERT INTO log (timestamp, status, code, comment) VALUES (?, ?, ?, ?)", 
                             (now_utc.isoformat(), 'in', code, comment))
                self.conn.commit()
            finally:
                cursor.close()

            self.comment_label.config(text=self.defaults.get('stamp_out_comment_msg', 'Stamp out comment:'))
            self.comment_var.set(self.defaults.get('default_stamp_out_comment', ''))
            self.code_var.set(self.default_code_stamp_out)
            status_msg = f"Status: in @{now_local.strftime('%Y-%m-%d %H:%M:%S')}"
            self.stamp_button.config(bg='green')
        else:
            if self.lunch_start <= now_local.time() <= self.lunch_stop:
                default_comment = self.defaults.get('default_stamp_out_lunch_comment', 'lunch')
            else:
                default_comment = self.defaults.get('default_stamp_out_comment', '')
            
            code = self.code_var.get()
            comment = self.comment_var.get()
            comment = comment if comment != "" else default_comment

            cursor = self.conn.cursor()
            try:
                cursor.execute("INSERT INTO log (timestamp, status, code, comment) VALUES (?, ?, ?, ?)", 
                             (now_utc.isoformat(), 'out', code, comment))
                self.conn.commit()
            finally:
                cursor.close()

            self.stamped_in = None
            self.comment_label.config(text=self.defaults.get('stamp_in_comment_msg', 'Stamp in comment:'))
            self.comment_var.set(self.defaults.get('default_stamp_in_comment', ''))
            self.code_var.set(self.default_code_stamp_in)
            status_msg = f"Status: out @{now_local.strftime('%Y-%m-%d %H:%M:%S')}"
            self.stamp_button.config(bg='red')

        self.status_label.config(text=status_msg)
        self.root.update_idletasks()

    def modify_last_entry(self):
        try:
            cursor = self.conn.cursor()
            try:
                cursor.execute("SELECT id, timestamp, status, comment FROM log ORDER BY id DESC LIMIT 1")
                last_entry = cursor.fetchone()
            finally:
                cursor.close()

            if last_entry is None:
                raise Exception("No entries found")

            entry_id_var = tk.StringVar(value=last_entry[0])

            modify_window = tk.Toplevel(self.root)
            modify_window.title("Modify Entry")

            def update_entry_display(*args):
                entry_id = entry_id_var.get()
                if not entry_id.isdigit():
                    entry_display.config(state=tk.NORMAL)
                    entry_display.delete("1.0", tk.END)
                    entry_display.insert(tk.END, "Invalid ID.")
                    entry_display.config(state=tk.DISABLED)
                    return

                cursor = self.conn.cursor()
                try:
                    cursor.execute("SELECT id, timestamp, status, comment FROM log WHERE id = ?", (entry_id,))
                    entry = cursor.fetchone()
                finally:
                    cursor.close()

                if entry:
                    entry_str = f"ID: {entry[0]}\nTimestamp: {entry[1]}\nStatus: {entry[2]}\nComment: {entry[3]}"
                    entry_display.config(state=tk.NORMAL)
                    entry_display.delete("1.0", tk.END)
                    entry_display.insert(tk.END, entry_str)
                    entry_display.config(state=tk.DISABLED)
                else:
                    entry_display.config(state=tk.NORMAL)
                    entry_display.delete("1.0", tk.END)
                    entry_display.insert(tk.END, "Entry not found.")
                    entry_display.config(state=tk.DISABLED)

            def delete_entry():
                entry_id = entry_id_var.get()
                if not entry_id.isdigit():
                    return

                cursor = self.conn.cursor()
                try:
                    cursor.execute("DELETE FROM log WHERE id = ?", (entry_id,))
                    self.conn.commit()
                finally:
                    cursor.close()

                update_entry_display()

            def edit_entry():
                entry_id = entry_id_var.get()
                if not entry_id.isdigit():
                    return
                self.edit_entry(int(entry_id))

            def prev_entry():
                entry_id = entry_id_var.get()
                if not entry_id.isdigit():
                    return
                entry_id = int(entry_id)

                cursor = self.conn.cursor()
                try:
                    cursor.execute("SELECT id FROM log WHERE id < ? ORDER BY id DESC LIMIT 1", (entry_id,))
                    prev_entry = cursor.fetchone()
                finally:
                    cursor.close()

                if prev_entry:
                    entry_id_var.set(prev_entry[0])
                    update_entry_display()

            def next_entry():
                entry_id = entry_id_var.get()
                if not entry_id.isdigit():
                    return
                entry_id = int(entry_id)

                cursor = self.conn.cursor()
                try:
                    cursor.execute("SELECT id FROM log WHERE id > ? ORDER BY id ASC LIMIT 1", (entry_id,))
                    next_entry = cursor.fetchone()
                finally:
                    cursor.close()

                if next_entry:
                    entry_id_var.set(next_entry[0])
                    update_entry_display()

            # Bind the update_entry_display method to the entry_id_var
            entry_id_var.trace_add("write", update_entry_display)

            tk.Label(modify_window, text="Entry ID:", font=(self.font, self.text_size)).pack()
            entry_id_entry = tk.Entry(modify_window, textvariable=entry_id_var, font=(self.font, self.text_size))
            entry_id_entry.pack()

            # Create a frame for the text display with scrollbar
            text_frame = tk.Frame(modify_window)
            text_frame.pack()
            scrollbar = tk.Scrollbar(text_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            entry_display = tk.Text(text_frame, height=10, width=50, font=(self.font, self.text_size), wrap=tk.WORD, yscrollcommand=scrollbar.set)
            entry_display.pack(side=tk.LEFT, fill=tk.BOTH)
            entry_display.config(state=tk.DISABLED)
            scrollbar.config(command=entry_display.yview)

            btn_frame = tk.Frame(modify_window)
            btn_frame.pack()

            tk.Button(btn_frame, text="<", bg='#39FF14', command=prev_entry, font=(self.font, self.text_size)).pack(side=tk.LEFT)
            tk.Button(btn_frame, text="Delete", bg="red", command=delete_entry, font=(self.font, self.text_size)).pack(side=tk.LEFT)
            tk.Button(btn_frame, text=" Edit ", bg="orange", command=edit_entry, font=(self.font, self.text_size)).pack(side=tk.LEFT)
            tk.Button(btn_frame, text="Cancel", bg="green", command=modify_window.destroy, font=(self.font, self.text_size)).pack(side=tk.LEFT)
            tk.Button(btn_frame, text=">", bg='#39FF14', command=next_entry, font=(self.font, self.text_size)).pack(side=tk.LEFT)

            update_entry_display()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def browse_entries(self):
        browse_window = tk.Toplevel(self.root)
        browse_window.title("Browse Entries")
        
        # Configure grid weights
        browse_window.grid_columnconfigure(1, weight=1)
        browse_window.grid_columnconfigure(3, weight=1)
        
        # Date filters row
        from_date_label = tk.Label(browse_window, text="From:", font=(self.font, self.text_size))
        from_date_label.grid(row=0, column=0, padx=5, pady=5, sticky='e')
        
        from_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M"))
        from_date_entry = tk.Entry(browse_window, textvariable=from_date_var, font=(self.font, self.text_size))
        from_date_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        to_date_label = tk.Label(browse_window, text="To:", font=(self.font, self.text_size))
        to_date_label.grid(row=0, column=2, padx=5, pady=5, sticky='e')
        
        to_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M"))
        to_date_entry = tk.Entry(browse_window, textvariable=to_date_var, font=(self.font, self.text_size))
        to_date_entry.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        
        view_by_date_button = tk.Button(
            browse_window,
            text="Filter by Date Range",
            command=lambda: self.display_entries(browse_window, from_date_var.get(), to_date_var.get(), None),
            font=(self.font, self.text_size)
        )
        view_by_date_button.grid(row=0, column=4, padx=5, pady=5)
        
        # SQL filter row
        sql_label = tk.Label(browse_window, text="SQL Query:", font=(self.font, self.text_size))
        sql_label.grid(row=1, column=0, padx=5, pady=5, sticky='e')
        
        current_year_month = datetime.now().strftime("%Y-%m")
        default_query = f"SELECT * FROM log WHERE timestamp LIKE '{current_year_month}%'"
        sql_var = tk.StringVar(value=default_query)
        sql_entry = tk.Entry(browse_window, textvariable=sql_var, font=(self.font, self.text_size))
        sql_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky='ew')
        
        view_by_sql_button = tk.Button(
            browse_window,
            text="Filter by SQL",
            command=lambda: self.display_entries(browse_window, None, None, sql_var.get()),
            font=(self.font, self.text_size)
        )
        view_by_sql_button.grid(row=1, column=4, padx=5, pady=5)
        
        # Dump to CSV button
        dump_button = tk.Button(
            browse_window,
            text="Dump to CSV",
            command=lambda: self.dump_to_csv(from_date_var.get(), to_date_var.get(), sql_var.get()),
            font=(self.font, self.text_size)
        )
        dump_button.grid(row=2, column=0, columnspan=5, pady=10)

    def edit_entry(self, entry_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT id, timestamp, status, code, comment FROM log WHERE id = ?", (entry_id,))
            entry = cursor.fetchone()
        finally:
            cursor.close()

        if not entry:
            messagebox.showerror("Error", f"No entry found with ID {entry_id}")
            return

        edit_window = tk.Toplevel(self.root)
        edit_window.title("Edit Entry")
        edit_window.minsize(width=1000, height=100)

        tk.Label(edit_window, text="Edit entry (ID, Timestamp, Status, Code, Comment):", 
                font=(self.font, self.text_size)).pack()

        entry_var = tk.StringVar(value=f"{entry[0]}, {entry[1]}, {entry[2]}, {entry[3]}, {entry[4]}")
        entry_editor = tk.Entry(edit_window, textvariable=entry_var, font=(self.font, self.text_size))
        entry_editor.pack(pady=10, fill='x', expand=True)

        def save_changes():
            entry_data = entry_var.get().split(", ")
            if len(entry_data) != 5:
                messagebox.showerror("Error", "Invalid entry format. Use: ID, Timestamp, Status, Code, Comment")
                return

            new_id, new_timestamp, new_status, new_code, new_comment = entry_data

            try:
                new_id = int(new_id)
                new_timestamp = datetime.fromisoformat(new_timestamp)
            except ValueError:
                messagebox.showerror("Error", "Invalid ID or Timestamp format.")
                return

            cursor = self.conn.cursor()
            try:
                cursor.execute("UPDATE log SET timestamp = ?, status = ?, code = ?, comment = ? WHERE id = ?", 
                             (new_timestamp.isoformat(), new_status, new_code, new_comment, entry_id))
                self.conn.commit()
            finally:
                cursor.close()

            edit_window.destroy()
            self.update_status_from_database()

        def cancel_edit():
            edit_window.destroy()

        tk.Button(edit_window, text="Save", bg="orange", command=save_changes, 
                 font=(self.font, self.text_size)).pack(side=tk.LEFT, padx=5)
        tk.Button(edit_window, text="Cancel", bg="green", command=cancel_edit, 
                 font=(self.font, self.text_size)).pack(side=tk.LEFT, padx=5)

        edit_window.protocol("WM_DELETE_WINDOW", edit_window.destroy)

    def display_entries(self, window, from_date_str, to_date_str, query_str):
        try:
            cursor = self.conn.cursor()
            try:
                if query_str:  # SQL filter mode
                    cursor.execute(query_str)
                    rows = cursor.fetchall()
                    header_text = f"Entries for query: {query_str}\n\n"
                else:  # Date filter mode
                    from_date = self.parse_date(from_date_str, datetime.now() - timedelta(days=7), seconds_included=True)
                    if from_date.tzinfo is None:
                        from_date = self.time_zone.localize(from_date).astimezone(utc)

                    to_date = self.parse_date(to_date_str, datetime.now(), seconds_included=False)
                    if to_date.tzinfo is None:
                        to_date = self.time_zone.localize(to_date).astimezone(utc)

                    to_date = to_date.replace(second=59, microsecond=999999)
                    
                    cursor.execute(
                        "SELECT * FROM log WHERE timestamp BETWEEN ? AND ?",
                        (from_date.isoformat(), to_date.isoformat())
                    )
                    rows = cursor.fetchall()
                    header_text = f"Entries from {from_date_str} to {to_date_str}:\n\n"
            finally:
                cursor.close()

            # Clear any existing display
            for widget in window.winfo_children():
                if isinstance(widget, scrolledtext.ScrolledText):
                    widget.destroy()

            entry_display = scrolledtext.ScrolledText(window, wrap=tk.WORD, width=100, height=20, 
                                                    font=(self.font, self.text_size))
            entry_display.grid(row=3, column=0, columnspan=5, padx=5, pady=5, sticky='nsew')

            if not rows:
                entry_display.insert(tk.END, "No entries found for the specified filter.")
            else:
                entry_display.insert(tk.END, header_text)
                for row in rows:
                    row_utc_time = datetime.fromisoformat(row[1]).replace(tzinfo=utc)
                    entry_text = f"ID: {row[0]}, Timestamp: {row_utc_time.strftime('%Y-%m-%d %H:%M:%S')}, " \
                               f"Status: {row[2]}, Code: {row[3]}, Comment: {row[4]}\n"
                    entry_display.insert(tk.END, entry_text)

        except Exception as e:
            messagebox.showerror("Error", str(e))


    def dump_to_csv(self, from_date_str, to_date_str, query_str):
        try:
            from_date = self.parse_date(from_date_str, datetime.now() - timedelta(days=7), seconds_included=True)
            if from_date.tzinfo is None:
                from_date = self.time_zone.localize(from_date).astimezone(utc)

            to_date = self.parse_date(to_date_str, datetime.now(), seconds_included=False)
            if to_date.tzinfo is None:
                to_date = self.time_zone.localize(to_date).astimezone(utc)

            to_date = to_date.replace(second=59, microsecond=999999)

            cursor = self.conn.cursor()
            try:
                if query_str:
                    cursor.execute(query_str)
                else:
                    cursor.execute("SELECT * FROM log WHERE timestamp BETWEEN ? AND ?", (from_date.isoformat(), to_date.isoformat()))
                rows = cursor.fetchall()
            finally:
                cursor.close()

            if not rows:
                messagebox.showinfo("Info", "No entries found for the specified date range.")
                return

            path = Path('out')
            path.mkdir(exist_ok=True) 
            csv_filename = f"{from_date_str[:10]}_{to_date_str[:10]}.csv"
            with open(path / csv_filename, 'w', newline='') as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerow(['ID', 'Timestamp', 'Status', 'Code', 'Comment'])
                for row in rows:
                    row_utc_time = datetime.fromisoformat(row[1]).replace(tzinfo=utc)
                    row_local_time = row_utc_time.astimezone(self.time_zone)
                    csvwriter.writerow([row[0], row_local_time.strftime('%Y-%m-%d %H:%M:%S'), row[2], row[3], row[4]])
                
            messagebox.showinfo("Info", f"Data successfully dumped to {csv_filename}")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def parse_date(self, date_str, default_time, seconds_included=True):
        formats = [
            "%Y-%m-%d %H:%M:%S" if seconds_included else "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return default_time

    def on_closing(self):
        self.conn.close()
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = StampApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
