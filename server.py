from flask import Flask, render_template, request, jsonify, Response
import socket
import threading
import time

app = Flask(__name__)

TCP_IP = "0.0.0.0"
TCP_PORT = 6050
FLASK_PORT = 5001

logs = []  # Список логов для отображения
positions = {}  # Словарь для хранения координат по хостам

def add_log(message):
    """Добавить сообщение в логи."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    logs.append(log_message)
    if len(logs) > 100:  # Ограничиваем количество логов
        logs.pop(0)

# TCP сервер
def start_tcp_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((TCP_IP, TCP_PORT))
    server_socket.listen(5)
    add_log(f"TCP Server started on {TCP_IP}:{TCP_PORT}")
    while True:
        conn, addr = server_socket.accept()
        data = conn.recv(1024).decode().strip()
        add_log(f"Received from {addr}: {data}")

        # Проверяем, являются ли данные координатами
        try:
            lat, lon = map(float, data.split(","))
            positions[addr[0]] = {"lat": lat, "lon": lon}  # Обновляем позицию хоста
            add_log(f"Updated position for {addr[0]}: {lat}, {lon}")
        except ValueError:
            add_log(f"Invalid data format: {data}")

        conn.sendall(f"Command received: {data}\n".encode())
        conn.close()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/logs")
def stream_logs():
    def generate_logs():
        """Генератор для передачи логов в режиме реального времени."""
        previous_length = 0
        while True:
            if len(logs) > previous_length:
                for log in logs[previous_length:]:
                    yield f"data: {log}\n\n"
                previous_length = len(logs)
            time.sleep(1)

    return Response(generate_logs(), content_type="text/event-stream")

@app.route("/positions")
def get_positions():
    """Возвращает текущие позиции всех устройств."""
    return jsonify(positions)

@app.route("/send_command", methods=["POST"])
def send_command():
    data = request.json
    command = data.get("command")
    if not command:
        return jsonify({"message": "Нет команды для отправки"}), 400

    try:
        # Отправляем TCP команду
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_client:
            tcp_client.connect((TCP_IP, TCP_PORT))
            tcp_client.sendall(command.encode())
            response = tcp_client.recv(1024).decode()
        add_log(f"Sent command: {command}")
        return jsonify({"message": f"Ответ от устройства: {response}"})
    except Exception as e:
        add_log(f"Ошибка отправки команды: {str(e)}")
        return jsonify({"message": f"Ошибка: {str(e)}"}), 500

if __name__ == "__main__":
    threading.Thread(target=start_tcp_server, daemon=True).start()
    app.run(host="0.0.0.0", port=FLASK_PORT)
