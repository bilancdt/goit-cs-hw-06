import os
import socket
import threading
import pickle
import pymongo
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
import urllib.parse
import mimetypes

# Підключення до MongoDB
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["messages_db"]
collection = db["messages"]
try:
    client.server_info()  # Якщо з'єднання працює, цей виклик не дасть помилки
    print("MongoDB підключено!")
except Exception as e:
    print(f"Не вдалося підключитися до MongoDB: {e}")
class MyHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == '/':
                self.path = 'templates/index.html'
            elif self.path == '/message':
                self.path = 'templates/message.html'
            

            elif self.path == '/error':
                self.path = 'templates/error.html'
            elif self.path.endswith(('.css', '.png', '.js')):
                self.path = 'static' + self.path

            # Визначення типу вмісту
            content_type, _ = mimetypes.guess_type(self.path)
            if not content_type:
                content_type = "application/octet-stream"

            # Надсилання заголовків
            self.send_response(200)
            self.send_header("Content-type", content_type)
            self.end_headers()

            # Читання та відправка файлу
            with open(self.path, 'rb') as file:
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            error_path = 'templates/error.html'
            with open(error_path, 'rb') as file:
                self.wfile.write(file.read())

    def do_POST(self):
        if self.path == '/message':
            try:
                # Отримання даних із форми
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = urllib.parse.parse_qs(post_data.decode('utf-8'))

                # Обробка даних форми
                message_data = {
                    "username": data.get("username", [""])[0],
                    "message": data.get("message", [""])[0],
                }

                # Пересилання даних на Socket-сервер
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.connect(('localhost', 5000))
                    sock.send(pickle.dumps(message_data))  # Відправка даних
                    response = sock.recv(1024).decode('utf-8')
                    print(f"Response from socket server: {response}")

                # Відправка відповіді клієнту
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"Message successfully sent!")
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"Error: {e}".encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"Page not found")


# HTTP сервер
def run_http_server():
    os.chdir(os.path.dirname(__file__))  # Робота у директорії поточного скрипта
    httpd = TCPServer(("", 3000), MyHandler)
    print("HTTP server started on port 3000")
    httpd.serve_forever()

# Socket сервер
def start_socket_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 5000))
    server.listen(5)
    print("Socket server started on port 5000")

    while True:
        try:
            client_socket, addr = server.accept()
            data = client_socket.recv(1024)
            message_data = pickle.loads(data)

            # Додавання часу до повідомлення
            message_data["date"] = str(datetime.now())

            # Збереження у MongoDB
            collection.insert_one(message_data)
            print(f"Saved message: {message_data}")

            client_socket.send(b"Message received")
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()

if __name__ == "__main__":
    # Запуск HTTP-сервера
    http_server_thread = threading.Thread(target=run_http_server)
    http_server_thread.start()

    # Запуск Socket-сервера
    socket_server_thread = threading.Thread(target=start_socket_server)
    socket_server_thread.start()

    # Очікування завершення процесів
    http_server_thread.join()
    socket_server_thread.join()
