import socket
import threading
from flask import Flask, render_template, request, jsonify

# TCP and Flask settings
TCP_HOST = '0.0.0.0'
TCP_PORT = 6050
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5001

app = Flask(__name__)

# Global data store
vehicles = {}  # {IMEI: {'lat': lat, 'lng': lng, 'last_command': cmd}}
logs = []      # Keeps logs for web display
connections = {}  # {IMEI: socket}

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
    global vehicles, logs, connections
    print(f"Connection from {addr}")
    logs.append(f"Connected: {addr}")
    imei = None

    with client_socket:
        while True:
            try:
                # Receive and decode data
                try:
                    data = client_socket.recv(1024).decode('utf-8').strip()
                except UnicodeDecodeError as e:
                    logs.append(f"Decoding error from {addr}: {e}")
                    break

                if not data:
                    break

                print(f"Received: {data}")
                logs.append(f"Received: {data}")

                # Parse SCOR commands
                if data.startswith("*SCOR"):
                    parts = data.split(',')
                    if len(parts) < 9:
                        logs.append(f"Malformed command from {addr}: {data}")
                        continue

                    imei = parts[2] if len(parts) > 2 and parts[2].isdigit() else None
                    if not imei:
                        logs.append(f"Invalid IMEI in command: {data}")
                        continue

                    # Add to connections
                    connections[imei] = client_socket
                    command_type = parts[3]

                    if command_type == 'Q0':  # Registration command
                        vehicles[imei] = {'registered': True, 'last_command': command_type}
                        logs.append(f"Device registered with IMEI {imei}")
                    elif command_type == 'H0':  # Summary information
                        vehicles[imei] = {'registered': True, 'last_command': command_type}
                        logs.append(f"Summary info received for IMEI {imei}")

                    elif command_type == 'D0':  # Positioning command
                        try:
                            if not parts[5].replace('.', '').isdigit() or not parts[7].replace('.', '').isdigit():
                                logs.append(f"Invalid GPS format: {data}")
                                continue

                            lat = convert_coordinates(parts[5], parts[6])
                            lng = convert_coordinates(parts[7], parts[8])
                        except ValueError as e:
                            logs.append(f"Invalid GPS coordinates from {imei}: {e}")
                            continue

                        vehicles[imei] = {'lat': lat, 'lng': lng, 'last_command': command_type}
                        logs.append(f"Updated IMEI {imei}: lat={lat}, lng={lng}")
                    else:
                        logs.append(f"Unknown command type: {command_type}")
            except Exception as e:
                print(f"Error: {e}")
                logs.append(f"Error: {e}")
                break

        # Clean up connection
        if imei and imei in connections:
            del connections[imei]

def convert_coordinates(coord, hemisphere):
    """
    Convert GPS coordinates from ddmm.mmmm or dddmm.mmmm to WGS84 decimal format.

    :param coord: str, coordinate in ddmm.mmmm or dddmm.mmmm format
    :param hemisphere: str, 'N', 'S', 'E', 'W' indicating hemisphere
    :return: float, decimal format of the coordinate
    """
    try:
        if not coord or not hemisphere:
            raise ValueError(f"Invalid input: coord='{coord}', hemisphere='{hemisphere}'")

        if hemisphere in ['N', 'S']:
            degrees = int(coord[:2])
            minutes = float(coord[2:])
        elif hemisphere in ['E', 'W']:
            degrees = int(coord[:3])
            minutes = float(coord[3:])
        else:
            raise ValueError(f"Invalid hemisphere: {hemisphere}")

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

    client_socket = connections.get(imei)
    if not client_socket:
        return jsonify({"status": "error", "message": f"No connection for IMEI {imei}"}), 404

    try:
        client_socket.sendall(f"{command}\n".encode('utf-8'))
        logs.append(f"Command sent to IMEI {imei}: {command}")
        return jsonify({"status": "success", "message": f"Command '{command}' sent to {imei}"}), 200
    except Exception as e:
        logs.append(f"Error sending command to {imei}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Run Flask and TCP Server concurrently
if __name__ == '__main__':
    threading.Thread(target=tcp_server, daemon=True).start()
    app.run(host=FLASK_HOST, port=FLASK_PORT)
