import socket
import threading
from flask import Flask, jsonify

# TCP and Flask settings
TCP_HOST = '0.0.0.0'
TCP_PORT = 6050
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5001

app = Flask(__name__)

# Global data store
vehicles = {}  # {IMEI: {'lat': lat, 'lng': lng, 'status': status, 'battery': battery}}
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

                # Handle received commands (example: '*SCOR,OM,123456789123456,Q0,...#')
                if data.startswith("*SCOR"):
                    parts = data.split(',')
                    imei = parts[2]
                    command_type = parts[3]

                    if command_type == 'Q0':  # Registration command
                        battery = int(parts[4]) / 100.0
                        signal = int(parts[6])
                        vehicles[imei] = {'status': 'registered', 'battery': battery, 'signal': signal}
                        logs.append(f"Device registered: IMEI={imei}, Battery={battery}V, Signal={signal}")

                    elif command_type == 'H0':  # Heartbeat command
                        status = 'locked' if parts[4] == '1' else 'unlocked'
                        battery = int(parts[5]) / 100.0
                        signal = int(parts[6])
                        vehicles[imei].update({'status': status, 'battery': battery, 'signal': signal})
                        logs.append(f"Heartbeat: IMEI={imei}, Status={status}, Battery={battery}V, Signal={signal}")

                    elif command_type == 'D0':  # Positioning command
                        if parts[6] == 'A':  # Valid positioning
                            lat = convert_coordinates(parts[7], parts[8])
                            lng = convert_coordinates(parts[9], parts[10])
                            vehicles[imei].update({'lat': lat, 'lng': lng})
                            logs.append(f"Position updated: IMEI={imei}, lat={lat}, lng={lng}")
                        else:
                            logs.append(f"Invalid positioning data: IMEI={imei}")

                    else:
                        logs.append(f"Unknown command type: {command_type}")
            except Exception as e:
                print(f"Error: {e}")
                logs.append(f"Error: {e}")
                break

# Coordinate conversion function
def convert_coordinates(coord, hemisphere):
    try:
        if hemisphere in ['N', 'S']:
            degrees = int(coord[:2])
            minutes = float(coord[2:])
        elif hemisphere in ['E', 'W']:
            degrees = int(coord[:3])
            minutes = float(coord[3:])
        else:
            raise ValueError("Invalid hemisphere")

        decimal = degrees + (minutes / 60)
        if hemisphere in ['S', 'W']:
            decimal = -decimal

        return round(decimal, 6)
    except Exception as e:
        logs.append(f"Coordinate conversion error: {e}")
        return None

# Flask Routes
@app.route('/')
def index():
    return jsonify({"status": "Server is running", "connected_devices": len(vehicles)})

@app.route('/logs')
def get_logs():
    return jsonify(logs[-50:])  # Last 50 logs

@app.route('/vehicles')
def get_vehicles():
    return jsonify(vehicles)

if __name__ == '__main__':
    threading.Thread(target=tcp_server, daemon=True).start()
    app.run(host=FLASK_HOST, port=FLASK_PORT)
