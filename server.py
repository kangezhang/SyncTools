import socket
import threading
import json
import time

class SyncServer:
    def __init__(self, host='0.0.0.0', port=5001):
        self.host = host
        self.port = port
        self.clients = []
        self.devices = {}

    def start_server(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        print(f"服务器启动，监听端口 {self.port}...")
        
        threading.Thread(target=self.broadcast_device_status).start()
        
        while True:
            client_socket, client_address = server_socket.accept()
            print(f"新连接：{client_address}")
            self.clients.append(client_socket)
            self.devices[client_address] = {'status': 'online', 'socket': client_socket}
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket, client_address))
            client_thread.start()

    def handle_client(self, client_socket, client_address):
        try:
            while True:
                data = client_socket.recv(1024)
                if not data:
                    break
                print(f"收到数据：{data.decode()}")
                self.broadcast(data, client_socket)
        except (ConnectionAbortedError, ConnectionResetError):
            print(f"连接中断：{client_address}")
        finally:
            self.clients.remove(client_socket)
            self.devices[client_address]['status'] = 'offline'
            client_socket.close()

    def broadcast(self, data, sender_socket):
        for client in self.clients:
            if client != sender_socket:
                try:
                    client.send(data)
                except (ConnectionAbortedError, ConnectionResetError):
                    self.clients.remove(client)

    def broadcast_device_status(self):
        while True:
            device_status = json.dumps({str(k): v['status'] for k, v in self.devices.items()}).encode()
            self.broadcast(device_status, None)
            time.sleep(5)

if __name__ == '__main__':
    server = SyncServer()
    server.start_server()
