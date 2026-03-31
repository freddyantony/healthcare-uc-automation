import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import pandas as pd
import re
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
from paramiko.ssh_exception import SSHException

class CiscoToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Cisco IOS Info Dump Tool v2.0")
        self.input_df = None
        self.output_df = pd.DataFrame()

        # Existing credential checkboxes
        self.use_username = tk.BooleanVar(value=True)
        self.use_password = tk.BooleanVar(value=True)
        self.use_secret = tk.BooleanVar(value=True)
        
        # Master credentials toggle
        self.use_master_creds = tk.BooleanVar(value=False)
        
        # Master credentials storage
        self.master_username = tk.StringVar()
        self.master_password = tk.StringVar()
        self.master_secret = tk.StringVar()

        self._build_gui()

    def _build_gui(self):
        # Top button frame
        frm_top = tk.Frame(self.root)
        frm_top.pack(padx=10, pady=5, fill=tk.X)

        tk.Button(frm_top, text="1. Load Input CSV", command=self.load_input_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(frm_top, text="2. Run Discovery", command=self.run_discovery).pack(side=tk.LEFT, padx=5)
        tk.Button(frm_top, text="3. Export Output CSV", command=self.export_output_csv).pack(side=tk.LEFT, padx=5)

        # Master Credentials Frame
        frm_master = tk.LabelFrame(self.root, text="Master Credentials", padx=10, pady=10)
        frm_master.pack(padx=10, pady=5, fill=tk.X)
        
        # Checkbox to use master credentials
        tk.Checkbutton(
            frm_master, 
            text="Use Master Credentials (instead of CSV credentials)", 
            variable=self.use_master_creds,
            font=("Arial", 10, "bold")
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
        
        # Master Username
        tk.Label(frm_master, text="Username:").grid(row=1, column=0, sticky="e", padx=5)
        tk.Entry(frm_master, textvariable=self.master_username, width=20).grid(row=1, column=1, sticky="w", padx=5)
        
        # Master Password (masked)
        tk.Label(frm_master, text="Password:").grid(row=1, column=2, sticky="e", padx=5)
        tk.Entry(frm_master, textvariable=self.master_password, width=20, show="*").grid(row=1, column=3, sticky="w", padx=5)
        
        # Master Enable Secret (masked)
        tk.Label(frm_master, text="Enable Secret:").grid(row=2, column=0, sticky="e", padx=5)
        tk.Entry(frm_master, textvariable=self.master_secret, width=20, show="*").grid(row=2, column=1, sticky="w", padx=5)

        # Credential usage checkboxes frame
        frm_check = tk.Frame(self.root)
        frm_check.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(frm_check, text="Use Credentials:").pack(side=tk.LEFT)
        tk.Checkbutton(frm_check, text="Username", variable=self.use_username).pack(side=tk.LEFT, padx=5)
        tk.Checkbutton(frm_check, text="Password", variable=self.use_password).pack(side=tk.LEFT, padx=5)
        tk.Checkbutton(frm_check, text="Enable Secret", variable=self.use_secret).pack(side=tk.LEFT, padx=5)

        # Input CSV preview
        tk.Label(self.root, text="Loaded CSV Preview").pack(anchor="w", padx=10)
        self.tree_input = ttk.Treeview(self.root)
        self.tree_input.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)

        # Logs
        tk.Label(self.root, text="Log Output").pack(anchor="w", padx=10)
        self.log_text = tk.Text(self.root, height=10, wrap="word")
        self.log_text.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)

        # Output preview
        tk.Label(self.root, text="Output Data Preview").pack(anchor="w", padx=10)
        self.tree_output = ttk.Treeview(self.root)
        self.tree_output.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        print(message)

    def mask_password(self, value):
        if pd.isna(value) or value == "":
            return ""
        return "****"

    def load_input_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not file_path:
            return
        try:
            self.input_df = pd.read_csv(file_path)
            self.log(f"Loaded input CSV with {len(self.input_df)} entries.")
            self.display_input_table()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV: {e}")

    def display_input_table(self):
        self.tree_input.delete(*self.tree_input.get_children())
        if self.input_df is None or self.input_df.empty:
            return

        self.tree_input["columns"] = list(self.input_df.columns)
        self.tree_input["show"] = "headings"
        
        for col in self.input_df.columns:
            self.tree_input.heading(col, text=col)
            self.tree_input.column(col, width=100)
        
        for _, row in self.input_df.iterrows():
            display_values = []
            for col in self.input_df.columns:
                value = row[col]
                if col.lower() in ['password', 'secret']:
                    display_values.append(self.mask_password(value))
                else:
                    display_values.append(value)
            self.tree_input.insert("", "end", values=display_values)

    def run_discovery(self):
        if self.input_df is None:
            messagebox.showwarning("No Input", "Please load an input CSV first.")
            return

        if self.use_master_creds.get():
            if not self.master_username.get():
                messagebox.showerror("Missing Credentials", "Master Username is required when using Master Credentials mode.")
                return
            if self.use_password.get() and not self.master_password.get():
                messagebox.showwarning("Missing Password", "Master Password is empty. Continue anyway?")
            if self.use_secret.get() and not self.master_secret.get():
                messagebox.showwarning("Missing Secret", "Master Enable Secret is empty. Continue anyway?")
            
            self.log("Using MASTER CREDENTIALS for all devices.")
        else:
            self.log("Using credentials from CSV file.")

        results = []
        for _, row in self.input_df.iterrows():
            ip = row['ip']
            self.log(f"Connecting to {ip}...")

            device = {
                'device_type': 'cisco_ios',
                'ip': ip,
                'ssh_strict': False,
                'fast_cli': False,
            }
            
            if self.use_master_creds.get():
                if self.use_username.get():
                    device['username'] = self.master_username.get()
                if self.use_password.get():
                    device['password'] = self.master_password.get()
                if self.use_secret.get():
                    device['secret'] = self.master_secret.get()
            else:
                if self.use_username.get():
                    device['username'] = row.get('username', '')
                if self.use_password.get():
                    device['password'] = row.get('password', '')
                if self.use_secret.get():
                    device['secret'] = row.get('secret', '')

            try:
                conn = ConnectHandler(**device)
                if self.use_secret.get():
                    conn.enable()
                output = conn.send_command('show version')

                try:
                    hostname = re.search(r'(\S+)\s+uptime', output).group(1)
                except: hostname = "N/A"

                try:
                    uptime = re.search(r'\S+\s+uptime is\s+(.+)', output).group(1).replace(',', '')
                except: uptime = "N/A"

                try:
                    version = re.search(r'Cisco\s(?:IOS|NX-OS)\s(?:Software,)?\s?.*Version\s([\w.()]+)', output).group(1)
                except: version = "N/A"

                try:
                    serial = re.search(r'Processor\sboard\sID\s(\S+)', output)
                    if not serial:
                        serial = re.search(r'System\sserial\snumber\s*:\s*(\S+)', output, re.IGNORECASE)
                    serial = serial.group(1) if serial else "N/A"
                except: serial = "N/A"

                try:
                    ios = re.search(r'System\simage\sfile\sis\s"([^"]+)"', output).group(1)
                except: ios = "N/A"

                try:
                    model_match = re.search(r'[Cc]isco\s(\S+)\s+\(.+\)\s+processor', output)
                    if not model_match:
                        model_match = re.search(r'[Cc]isco\s+(\S+).*memory', output)
                    if not model_match:
                        model_match = re.search(r'Model number\s*:\s*(\S+)', output)
                    model = model_match.group(1) if model_match else "N/A"
                except: model = "N/A"

                try:
                    memory_match = re.search(r'with\s+([\d,]+)\s+bytes of memory', output)
                    if not memory_match:
                        memory_match = re.search(r'Memory size\s*:\s*(\d+)', output)
                    memory = memory_match.group(1) if memory_match else "N/A"
                except: memory = "N/A"

                results.append({
                    "IP Address": ip,
                    "Hostname": hostname,
                    "Uptime": uptime,
                    "Current_Version": version,
                    "Current_Image": ios,
                    "Serial_Number": serial,
                    "Device_Model": model,
                    "Device_Memory": memory,
                })
                self.log(f"OK {ip} processed successfully.")

            except (NetmikoTimeoutException, SSHException, NetmikoAuthenticationException, ValueError) as e:
                self.log(f"BAD {ip} failed: {str(e)}")
                results.append({"IP Address": ip, "Error": str(e)})

        self.output_df = pd.DataFrame(results)
        self.display_output_table()

    def display_output_table(self):
        self.tree_output.delete(*self.tree_output.get_children())
        self.tree_output["columns"] = list(self.output_df.columns)
        self.tree_output["show"] = "headings"

        for col in self.output_df.columns:
            self.tree_output.heading(col, text=col)
            self.tree_output.column(col, width=150)

        for _, row in self.output_df.iterrows():
            self.tree_output.insert("", "end", values=list(row))

    def export_output_csv(self):
        if self.output_df.empty:
            messagebox.showinfo("No Data", "Nothing to export.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv")
        if file_path:
            self.output_df.to_csv(file_path, index=False)
            self.log(f"Output saved to {file_path}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CiscoToolGUI(root)
    root.geometry("1200x900")
    root.mainloop()