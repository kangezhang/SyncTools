import tkinter as tk
from tkinter import filedialog, messagebox, ttk, Menu
import json
import threading
from client import SyncClient
from server import SyncServer
import os
import traceback
import shutil
import time

def main():
    try:
        print("Starting SyncApp...")  # 调试信息
        root = tk.Tk()
        app = SyncApp(root)
        root.mainloop()
    except Exception as e:
        print("An error occurred:", str(e))
        traceback.print_exc()
        input("Press Enter to continue...")

class SyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("文件同步工具")

        # 设置应用图标
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, 'assets', 'icon.icns')
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)
            print(f"Icon loaded from {icon_path}")

        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.sync_folder = tk.StringVar()
        self.local_folder = tk.StringVar()
        self.server_host = tk.StringVar(value='127.0.0.1')
        self.server_port = tk.IntVar(value=5001)
        
        self.config = self.load_config()
        if self.config:
            self.sync_folder.set(self.config['sync_folder'])
            self.local_folder.set(self.config.get('local_folder', ''))
            self.server_host.set(self.config['server_host'])
            self.server_port.set(self.config['server_port'])
        
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        print("Main frame created")

        ttk.Label(main_frame, text="同步文件夹:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        ttk.Entry(main_frame, textvariable=self.sync_folder, width=50).grid(row=0, column=1, padx=10, pady=10)
        ttk.Button(main_frame, text="选择文件夹", command=self.select_sync_folder).grid(row=0, column=2, padx=10, pady=10)
        print("Sync folder selection controls created")
        
        ttk.Label(main_frame, text="本地文件夹:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        ttk.Entry(main_frame, textvariable=self.local_folder, width=50).grid(row=1, column=1, padx=10, pady=10)
        ttk.Button(main_frame, text="选择文件夹", command=self.select_local_folder).grid(row=1, column=2, padx=10, pady=10)
        print("Local folder selection controls created")

        ttk.Label(main_frame, text="服务器地址:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        ttk.Entry(main_frame, textvariable=self.server_host, width=50).grid(row=2, column=1, padx=10, pady=10)
        
        ttk.Label(main_frame, text="服务器端口:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
        ttk.Entry(main_frame, textvariable=self.server_port, width=50).grid(row=3, column=1, padx=10, pady=10)
        print("Server address and port controls created")

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, padx=10, pady=10)
        ttk.Button(button_frame, text="保存配置", command=self.save_config).grid(row=0, column=0, padx=10)
        ttk.Button(button_frame, text="启动同步", command=self.start_sync).grid(row=0, column=1, padx=10)
        ttk.Button(button_frame, text="同步本地文件夹", command=self.sync_local_folders).grid(row=0, column=2, padx=10)
        print("Buttons created")
        
        self.tree = ttk.Treeview(main_frame, columns=("status"), show='headings')
        self.tree.heading("status", text="同步状态")
        self.tree.column("status", width=100, anchor="center")
        self.tree.grid(row=5, column=0, columnspan=3, padx=10, pady=10, sticky='nsew')
        self.tree.bind("<Button-3>", self.show_context_menu)  # 绑定右键点击事件
        print("Treeview created")
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=6, column=0, columnspan=3, padx=20, pady=20)
        
        self.progress_label = ttk.Label(main_frame, text="Progress: 0%")
        self.progress_label.grid(row=7, column=0, columnspan=3)
        print("Progress bar and label created")

        device_frame = ttk.Frame(root, padding="10")
        device_frame.grid(row=8, column=0, columnspan=3, sticky="nsew")
        self.device_tree = ttk.Treeview(device_frame, columns=("device", "status"), show='headings')
        self.device_tree.heading("device", text="设备")
        self.device_tree.heading("status", text="状态")
        self.device_tree.column("device", width=200, anchor="center")
        self.device_tree.column("status", width=100, anchor="center")
        self.device_tree.grid(row=0, column=0, columnspan=3, padx=10, pady=10, sticky='nsew')
        print("Device treeview created")

        root.grid_rowconfigure(5, weight=1)
        root.grid_columnconfigure(1, weight=1)
        print("Grid configured")

        self.start_server()
        self.start_client()
        self.schedule_refresh()

    def select_sync_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.sync_folder.set(folder)
            self.populate_file_list()

    def select_local_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.local_folder.set(folder)

    def save_config(self):
        self.config = {
            'sync_folder': self.sync_folder.get(),
            'local_folder': self.local_folder.get(),
            'server_host': self.server_host.get(),
            'server_port': self.server_port.get()
        }
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, 'assets', 'config.json')
        with open(config_path, 'w') as f:
            json.dump(self.config, f)
        messagebox.showinfo("信息", "配置已保存！")

    def load_config(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, 'assets', 'config.json')
        if not os.path.exists(config_path):
            default_config = {
                'sync_folder': '',
                'local_folder': '',
                'server_host': '127.0.0.1',
                'server_port': 5001
            }
            with open(config_path, 'w') as f:
                json.dump(default_config, f)
            print(f"Created default config at {config_path}")
            return default_config
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading config file at {config_path}")
            return None

    def populate_file_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for root_dir, dirs, files in os.walk(self.sync_folder.get()):
            for file in files:
                file_path = os.path.join(root_dir, file)
                self.tree.insert('', 'end', values=(file_path, "未同步"), tags=("unsynced",))

        self.tree.tag_configure('synced', background='lightgreen')
        self.tree.tag_configure('unsynced', background='lightcoral')

    def start_sync(self):
        if not self.sync_folder.get() or not self.server_host.get() or not self.server_port.get():
            messagebox.showwarning("警告", "请填写完整的同步配置！")
            return

        if not hasattr(self, 'client_thread') or not self.client_thread.is_alive():
            self.client_thread = threading.Thread(target=self.client.start_client)
            self.client_thread.daemon = True
            self.client_thread.start()
            messagebox.showinfo("信息", "同步已启动！")

    def sync_local_folders(self):
        if not self.sync_folder.get() or not self.local_folder.get():
            messagebox.showwarning("警告", "请填写同步文件夹和本地文件夹！")
            return

        sync_folder = self.sync_folder.get()
        local_folder = self.local_folder.get()

        for root_dir, dirs, files in os.walk(sync_folder):
            for file in files:
                src_file = os.path.join(root_dir, file)
                relative_path = os.path.relpath(src_file, sync_folder)
                dst_file = os.path.join(local_folder, relative_path)

                dst_dir = os.path.dirname(dst_file)
                if not os.path.exists(dst_dir):
                    os.makedirs(dst_dir)

                shutil.copy2(src_file, dst_file)
                print(f"Copied {src_file} to {dst_file}")

        messagebox.showinfo("信息", "本地文件夹同步完成！")

    def start_server(self):
        self.server = SyncServer(self.server_host.get(), self.server_port.get())
        self.server_thread = threading.Thread(target=self.server.start_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        print("Server thread started")

    def start_client(self):
        self.client = SyncClient(self.sync_folder.get(), self.server_host.get(), self.server_port.get())
        self.client_thread = threading.Thread(target=self.client.start_client)
        self.client_thread.daemon = True
        self.client_thread.start()
        print("Client thread started")
        self.update_device_status()

    def update_device_status(self):
        def update():
            while True:
                time.sleep(5)
                devices = self.client.devices
                for item in self.device_tree.get_children():
                    self.device_tree.delete(item)
                for device, status in devices.items():
                    self.device_tree.insert('', 'end', values=(device, status), tags=(status,))
                self.device_tree.tag_configure('online', background='lightgreen')
                self.device_tree.tag_configure('offline', background='lightcoral')
        threading.Thread(target=update, daemon=True).start()

    def update_progress(self, progress):
        self.progress_var.set(progress)
        self.progress_label.config(text=f"Progress: {progress:.2f}%")
        self.root.update_idletasks()

    def update_file_status(self, file_path, status):
        for item in self.tree.get_children():
            if self.tree.item(item, "values")[0] == file_path:
                self.tree.item(item, values=(file_path, status), tags=("synced",) if status == "已同步" else ("unsynced",))
                break

    def schedule_refresh(self):
        self.populate_file_list()
        self.root.after(5000, self.schedule_refresh)  # 每5秒刷新一次文件列表

    def show_context_menu(self, event):
        selected_item = self.tree.identify_row(event.y)
        if selected_item:
            self.tree.selection_set(selected_item)
            file_path = self.tree.item(selected_item, "values")[0]

            menu = Menu(self.root, tearoff=0)
            menu.add_command(label="选择版本另存为", command=lambda: self.choose_version(file_path))
            menu.post(event.x_root, event.y_root)

    def choose_version(self, file_path):
        versions = self.client.get_versions(file_path)
        if not versions:
            messagebox.showinfo("信息", "没有可用的版本。")
            return

        version = tk.simpledialog.askinteger("选择版本", "输入版本号 (1-{}):".format(len(versions)))
        if version is None or version < 1 or version > len(versions):
            messagebox.showwarning("警告", "无效的版本号。")
            return

        version_id = versions[version - 1]
        version_data = self.client.restore_version(file_path, version_id)
        if version_data is None:
            messagebox.showwarning("警告", "无法恢复该版本。")
            return

        save_path = filedialog.asksaveasfilename(initialfile=os.path.basename(file_path))
        if save_path:
            with open(save_path, 'wb') as f:
                f.write(version_data)
            messagebox.showinfo("信息", "版本已成功保存。")

if __name__ == '__main__':
    print("Running SyncApp...")  # 调试信息
    main()
