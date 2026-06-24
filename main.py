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
            request = bytes.fromhex("3D0C00010003001100")
            inverter_sock.sendall(request)
            print("Sent request to inverter:", request.hex())
            time.sleep(1)
        except Exception as e:
            print(f"Periodic request error: {e}")
            stop_event.set()
            break


def process_inverter_data(data: bytes):
    charge_solar_only = "40630001000A05040506139900031CE4"
    charge_solar_utility = "48E30001000A0504050613990002DD24"
    load_utility = "490A0001000A05040506139A0000ACE5"
    load_sbu = "490D0001000A05040506139A00022D24"

    # Indexes
    mode_idx = 14
    ac_voltage_idx = 16
    ac_frequency_idx = 18
    pv_voltage_idx = 20
    pv_power_idx = 22
    battery_voltage_idx = 24
    battery_charged_idx = 26
    battery_charging_curr_idx = 28
    battery_discharging_curr_idx = 30
    output_voltage_idx = 32
    output_frequency_idx = 34
    output_power_idx = 38
    output_load_idx = 40
    charge_state_idx = 84
    load_state_idx = 86

    def get_data(idx, denominator=1):
        b = 0
        for i in range(1, -1, -1):
            b = (b << 8) + (data[idx + i] & 0xFF)
        return b / denominator

    def get_data_int(idx, denominator=1):
        b = 0
        for i in range(1, -1, -1):
            b = (b << 8) + (data[idx + i] & 0xFF)
        return b // denominator

    result = {}
    if len(data) < 90:
        return result

    hex_data = data.hex().upper()

    # TELEMETRY PACKET
    if data[2] == 0x09 and data[3] == 0x25:
        result["batteryVoltage"] = get_data(battery_voltage_idx, 10)
        result["batteryCharged"] = get_data_int(battery_charged_idx)
        result["batteryChargingCurr"] = get_data(battery_charging_curr_idx, 10)
        result["batteryDisChargingCurr"] = get_data(battery_discharging_curr_idx, 10)
        result["outputVoltage"] = get_data(output_voltage_idx, 10)
        result["outputFrequency"] = get_data(output_frequency_idx, 10)
        result["outputPower"] = get_data_int(output_power_idx)
        result["outputLoad"] = get_data_int(output_load_idx)
        result["acVoltage"] = get_data(ac_voltage_idx, 10)
        result["acFrequency"] = get_data(ac_frequency_idx, 10)
        result["pvVoltage"] = get_data(pv_voltage_idx, 10)
        result["pvPower"] = get_data_int(pv_power_idx)
        result["mode"] = get_data_int(mode_idx)
        result["chargeState"] = get_data_int(charge_state_idx)
        result["loadState"] = get_data_int(load_state_idx)

    # COMMAND ACK PACKET
    if data[2] == 0x00 and data[3] == 0x01:
        charge_state = None
        load_state = None

        if charge_solar_only and hex_data == charge_solar_only:
            charge_state = 3
        elif charge_solar_utility and hex_data == charge_solar_utility:
            charge_state = 2
        elif load_sbu and hex_data == load_sbu:
            load_state = 2
        elif load_utility and hex_data == load_utility:
            load_state = 0

        if charge_state is not None:
            result["chargeState"] = charge_state
        if load_state is not None:
            result["loadState"] = load_state
	
    # print(result)
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
