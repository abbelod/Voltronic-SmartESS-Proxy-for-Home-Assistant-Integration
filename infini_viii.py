import socket
import threading
import time
import json
import paho.mqtt.client as mqtt

set_load_source_solar = "22f20001000a05040506139a00016d25"
set_load_source_sbu = "22f50001000a05040506139a00022d24"
set_load_source_utility = "22ef0001000a05040506139a0000ace5"

ESS_HOST = "8.218.198.113"  # IP of ess.eybond.com
ESS_PORT = 502

LOCAL_HOST = "0.0.0.0"
LOCAL_PORT = 502

MQTT_BROKER = "localhost"  # replace with your broker
MQTT_PORT = 1883
MQTT_TOPIC = "inverter/data"

def on_message(client, userdata, msg):
    message = msg.payload.decode().lower()

    print(f"Received message on topic {msg.topic}: {message}")
    

    inverter_sock = userdata.get("inverter_sock")
    if(inverter_sock):
        if(msg.topic.endswith("loadsource")):
            if("solar" in message):
                print("sending reqeust for solar")
                try:
                    request = bytes.fromhex(set_load_source_solar)
                    inverter_sock.sendall(request)
                    time.sleep(1)
                except Exception as e:
                    print(f"Error while sending command request: {e}")

            elif("sbu" in message):
                print("sending reqeust for sbu")
                try:
                    request = bytes.fromhex(set_load_source_sbu)
                    inverter_sock.sendall(request)
                    time.sleep(1)
                except Exception as e:
                    print(f"Error while sending command request: {e}")
                    
            elif("utility" in message):
                print("sending reqeust for utility")
                try:
                    request = bytes.fromhex(set_load_source_utility)
                    inverter_sock.sendall(request)
                    time.sleep(1)
                except Exception as e:
                    print(f"Error while sending command request: {e}")


# --- MQTT client setup ---
mqtt_client = mqtt.Client(userdata = {"inverter_sock": None})
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
mqtt_client.subscribe("inverter/command/#")
mqtt_client.loop_start()  # start background thread


def forward(src, dst, name, stop_event):
    while not stop_event.is_set():
        try:
            data = src.recv(4096)
            if not data:
                break
            values = process_inverter_data(data)
            print(f"{name}:", data.hex())
            if values:
                mqtt_client.publish(MQTT_TOPIC, json.dumps(values))
            dst.sendall(data)
        except Exception as e:
            print(f"{name} error: {e}")
            break
    stop_event.set()  # Signal all other threads to stop


def periodic_inverter_requests(inverter_sock, stop_event):
    while not stop_event.is_set():
        try:
            request = bytes.fromhex("4a0a0001000cff045e50303035475358140d")
            inverter_sock.sendall(request)
            print("Sent request to inverter:", request.hex())
            time.sleep(5)
        except Exception as e:
            print(f"Periodic request error: {e}")
            stop_event.set()
            break


def process_inverter_data(data: bytes):

    hex = data.hex()
    if ('4a0a00010071ff045e' not in hex):
        return None
    print(hex[0])
    print(hex[1])

    # 18 characters from beginning remove
    # 9 bytes from beginning remove
    # 6 characters / 3 bytes from end remove

    # Removing first 9 Bytes () and last 3 Bytes, keeping only the DATA
    new_hex = hex[18:-6]
    print("new hex: ", new_hex)


    ascii_str = bytes.fromhex(new_hex).decode("utf-8")
    print("ASCII:", ascii_str)

    ascii_str = ascii_str.split(',')

    GRID_VOLTAGE = int(ascii_str[0][4:]) / 10
    GRID_FREQUENCY = int(ascii_str[1]) / 10
    AC_OUT_VOLTAGE = ascii_str[2]
    AC_OUT_POWER = ascii_str[4]
    LOAD_OUT_PERCENTAGE = ascii_str[6]
    BT_VOLTAGE = int(ascii_str[7]) / 10
    BT_DISCHARGE_CURRENT = int(ascii_str[10]) / 10
    BT_CHARGE_CURRENT = int(ascii_str[11])/10
    BT_SOC = int(ascii_str[12])
    INVERTER_TEMP = int(ascii_str[13])
    PV1_INPUT_POWER = ascii_str[16]
    PV1_INPUT_VOLTAGE = int(ascii_str[18]) / 10

    result = {}
    result["batteryVoltage"] = BT_VOLTAGE
    result["batteryCharged"] = BT_SOC
    result["batteryChargingCurr"] = BT_CHARGE_CURRENT
    result["batteryDisChargingCurr"] = BT_DISCHARGE_CURRENT
    # result["outputVoltage"] = get_data(output_voltage_idx, 10)
    # result["outputFrequency"] = get_data(output_frequency_idx, 10)
    result["outputPower"] = AC_OUT_POWER
    # result["outputLoad"] = get_data_int(output_load_idx)
    result["acVoltage"] = GRID_VOLTAGE
    result["acFrequency"] = GRID_FREQUENCY 
    # result["pvVoltage"] = get_data(pv_voltage_idx, 10)
    result["pvPower"] = PV1_INPUT_POWER
    # result["mode"] = get_data_int(mode_idx)
    # result["chargeState"] = get_data_int(charge_state_idx)
    # result["loadState"] = get_data_int(load_state_idx)

    print(result)
    return result


def main():
    while True:
        ess_sock = None
        inverter_sock = None
        server = None
        try:
            ess_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"Connecting to ESS {ESS_HOST}:{ESS_PORT}...")
            ess_sock.connect((ESS_HOST, ESS_PORT))
            print("Connected to ESS")

            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((LOCAL_HOST, LOCAL_PORT))
            server.listen(1)
            print(f"Waiting for inverter on port {LOCAL_PORT}...")

            inverter_sock, addr = server.accept()
            inverter_sock.settimeout(10)
            mqtt_client._userdata["inverter_sock"] = inverter_sock
            print("Inverter connected:", addr)

            stop_event = threading.Event()

            threads = [
                threading.Thread(target=forward, args=(inverter_sock, ess_sock, "Inverter→ESS", stop_event)),
                threading.Thread(target=forward, args=(ess_sock, inverter_sock, "ESS→Inverter", stop_event)),
                threading.Thread(target=periodic_inverter_requests, args=(inverter_sock, stop_event)),
            ]
            for t in threads:
                t.daemon = True
                t.start()

            # Block until any thread signals failure
            stop_event.wait()
            print("Connection lost — reconnecting in 5 seconds...")

        except Exception as e:
            print(f"Setup error: {e}")

        finally:
            for sock in [ess_sock, inverter_sock, server]:
                try:
                    if sock:
                        sock.close()
                except:
                    pass
            time.sleep(5)

if __name__ == "__main__":
    main()
