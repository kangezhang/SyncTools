import socket
import os
import threading
import time
import json

class SyncClient:
    def __init__(self, sync_folder, server_host='127.0.0.1', server_port=5001):
        self.sync_folder = sync_folder
        self.server_host = server_host
        self.server_port = server_port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.devices = {}
        self.file_snapshots = self.scan_files()
        self.versions = {}  # 存储文件的版本信息

    def start_client(self):
        while True:
            try:
                self.client_socket.connect((self.server_host, self.server_port))
                print(f"已连接到服务器 {self.server_host}:{self.server_port}")

                recv_thread = threading.Thread(target=self.receive_data)
                recv_thread.start()

                watch_thread = threading.Thread(target=self.watch_files)
                watch_thread.start()
                break  # 成功连接后退出重试循环
            except (ConnectionAbortedError, ConnectionResetError, ConnectionRefusedError) as e:
                print(f"连接中止：{e}")
                time.sleep(5)  # 等待5秒后重试

    def send_data(self, action, file_path):
        relative_path = os.path.relpath(file_path, self.sync_folder)
        if action == "delete":
            data = json.dumps({"action": action, "path": relative_path}).encode()
        else:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            version_id = time.time()
            self.save_version(file_path, version_id, file_data)
            data = json.dumps({"action": action, "path": relative_path, "size": len(file_data), "version": version_id}).encode() + file_data
        self.client_socket.send(data)
        print(f"发送 {action} 文件：{relative_path}")

    def receive_data(self):
        try:
            while True:
                data = self.client_socket.recv(1024)
                if not data:
                    break
                try:
                    action_info = json.loads(data.decode())
                    if 'status' in action_info.values():
                        self.devices = action_info
                        continue
                except json.JSONDecodeError:
                    print(f"接收到无效的JSON数据：{data}")
                    continue
                
                if 'action' not in action_info:
                    print(f"接收到的数据中缺少'action'键：{action_info}")
                    continue
                
                action = action_info["action"]
                relative_path = action_info["path"]
                file_path = os.path.join(self.sync_folder, relative_path)
                
                if action == "delete":
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    print(f"删除文件：{relative_path}")
                else:
                    file_size = action_info["size"]
                    version_id = action_info.get("version", None)
                    file_data = self.client_socket.recv(file_size)
                    self.save_version(file_path, version_id, file_data)
                    with open(file_path, 'wb') as f:
                        f.write(file_data)
                    print(f"接收 {action} 文件：{relative_path}")
        except (ConnectionAbortedError, ConnectionResetError):
            print(f"连接中断")
        finally:
            self.client_socket.close()

    def scan_files(self):
        file_snapshots = {}
        for root, dirs, files in os.walk(self.sync_folder):
            for file in files:
                file_path = os.path.join(root, file)
                file_snapshots[file_path] = os.path.getmtime(file_path)
        return file_snapshots

    def watch_files(self):
        while True:
            time.sleep(1)
            new_snapshots = self.scan_files()
            deleted_files = set(self.file_snapshots.keys()) - set(new_snapshots.keys())
            added_files = set(new_snapshots.keys()) - set(self.file_snapshots.keys())
            modified_files = {file for file in new_snapshots if file in self.file_snapshots and new_snapshots[file] != self.file_snapshots[file]}

            for file in added_files:
                self.send_data("add", file)
            for file in modified_files:
                self.send_data("modify", file)
            for file in deleted_files:
                self.send_data("delete", file)

            self.file_snapshots = new_snapshots

    def save_version(self, file_path, version_id, file_data):
        if version_id is not None:
            version_dir = os.path.join(self.sync_folder, ".versions", os.path.relpath(file_path, self.sync_folder))
            if not os.path.exists(version_dir):
                os.makedirs(version_dir)
            version_file = os.path.join(version_dir, f"{version_id}.version")
            with open(version_file, 'wb') as f:
                f.write(file_data)
            if file_path not in self.versions:
                self.versions[file_path] = []
            self.versions[file_path].append(version_id)

    def get_versions(self, file_path):
        return self.versions.get(file_path, [])

    def restore_version(self, file_path, version_id):
        version_dir = os.path.join(self.sync_folder, ".versions", os.path.relpath(file_path, self.sync_folder))
        version_file = os.path.join(version_dir, f"{version_id}.version")
        if os.path.exists(version_file):
            with open(version_file, 'rb') as f:
                return f.read()
        return None

if __name__ == '__main__':
    sync_folder = '/path/to/sync/folder'
    client = SyncClient(sync_folder)
    client.start_client()
