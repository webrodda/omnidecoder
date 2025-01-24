import socket
import threading
from flask import Flask, render_template, request, jsonify
import folium

# TCP and Flask settings
TCP_HOST = '0.0.0.0'
TCP_PORT = 6050
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5001

app = Flask(__name__)

# Global data store
vehicles = {}  # {IMEI: {'lat': lat, 'lng': lng, 'last_command': cmd}}
logs = []      # Keeps logs for web display

# TCP Server Logic
def tcp_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((TCP_HOST, TCP_PORT))
    server_socket.listen(5)
    print(f"TCP Server listening on port {TCP_PORT}")

    while True:
        client_socket, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(client_socket, addr)).start()

def handle_client(client_socket, addr):
    global vehicles, logs
    print(f"Connection from {addr}")
    logs.append(f"Connected: {addr}")

    with client_socket:
        while True:
            try:
                data = client_socket.recv(1024).decode('utf-8').strip()
                if not data:
                    break

                print(f"Received: {data}")
                logs.append(f"Received: {data}")

                # Handle received commands (example: '*SCOR,OM,123456789123456,D0,...#')
                if data.startswith("*SCOR"):
                    parts = data.split(',')
                    imei = parts[2]
                    command_type = parts[3]

                    if command_type == 'D0':  # Positioning command
                        lat = convert_coordinates(parts[5], parts[6])
                        lng = convert_coordinates(parts[7], parts[8])
                        vehicles[imei] = {'lat': lat, 'lng': lng, 'last_command': command_type}
                        logs.append(f"Updated IMEI {imei}: lat={lat}, lng={lng}")
                    else:
                        logs.append(f"Unknown command type: {command_type}")
            except Exception as e:
                print(f"Error: {e}")
                logs.append(f"Error: {e}")
                break

def convert_coordinates(coord, hemisphere):
    degrees = int(coord[:2])
    minutes = float(coord[2:])
    decimal = degrees + minutes / 60
    if hemisphere in ['S', 'W']:
        decimal = -decimal
    return decimal

# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/map-data')
def map_data():
    return jsonify(vehicles)

@app.route('/logs')
def get_logs():
    return jsonify(logs[-50:])  # Last 50 logs

@app.route('/send-command', methods=['POST'])
def send_command():
    imei = request.json.get('imei')
    command = request.json.get('command')

    if not imei or not command:
        return jsonify({"status": "error", "message": "IMEI and Command are required"}), 400

    if imei not in vehicles:
        return jsonify({"status": "error", "message": "IMEI not found"}), 404

    logs.append(f"Command sent to {imei}: {command}")
    return jsonify({"status": "success", "message": f"Command '{command}' sent to {imei}"}), 200

# Run Flask and TCP Server concurrently
if __name__ == '__main__':
    threading.Thread(target=tcp_server, daemon=True).start()
    app.run(host=FLASK_HOST, port=FLASK_PORT)
