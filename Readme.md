# Inverter MQTT Proxy for Eybond ESS

This project provides a **real-time TCP proxy and MQTT publisher** for Eybond inverters (ESS). It allows users to:

* Monitor inverter parameters such as battery voltage, solar PV voltage, output power, AC voltage, frequency, and load in real time.
* Forward inverter data to a local MQTT broker for integration with **Home Assistant** or other IoT platforms.
* Act as a transparent proxy between the inverter and the Eybond cloud server, preserving normal cloud functionality.

This solution is particularly useful for home automation enthusiasts who want to **collect real-time inverter telemetry** without modifying the official Eybond infrastructure.

---

## Features

* **TCP Proxy:** Listens locally for inverter connections and forwards requests/responses between the inverter and the Eybond server.
* **Telemetry Parsing:** Extracts inverter data fields such as battery voltage, battery state, PV voltage, output power, AC voltage, and more.
* **MQTT Publishing:** Publishes parsed inverter values in JSON format to a local MQTT broker.
* **Periodic Requests:** Sends regular polling requests to the inverter to maintain up-to-date telemetry.
* **Seamless Integration:** Compatible with Home Assistant via MQTT for dashboards, automation, and alerts.

---

## Requirements

* Python 3.9 or higher
* [paho-mqtt](https://pypi.org/project/paho-mqtt/) library
* Local or remote MQTT broker (e.g., Mosquitto)
* Network access to the inverter and ESS cloud server

Install dependencies using pip:

```bash
pip install paho-mqtt
```

---

## Setup and Usage

### 1. Configure MQTT Broker

Modify the following variables in the script according to your MQTT broker configuration:

```python
MQTT_BROKER = "localhost"   # or the IP of your MQTT broker
MQTT_PORT = 1883
MQTT_TOPIC = "inverter/data"
```

### 2. Configure ESS Server

Set the IP and port of the Eybond ESS server:

```python
ESS_HOST = "8.218.198.113"  # Eybond ESS cloud server
ESS_PORT = 502
```

### 3. Configure Local Proxy

Set the local listening address for your inverter:

```python
LOCAL_HOST = "0.0.0.0"  # listen on all interfaces
LOCAL_PORT = 502         # match inverter TCP port
```

### 4. Run the Proxy

Run the Python script:

```bash
python <appropriate_script>.py
```

* The proxy will first connect to the ESS cloud server.
* It will then start a local TCP server waiting for the inverter to connect.
* Once the inverter connects, the proxy will:

  * Forward packets between the inverter and the ESS server.
  * Parse inverter telemetry.
  * Publish JSON-formatted telemetry to the configured MQTT topic.
  * Send periodic requests to the inverter to maintain updates.

### 5. Verify MQTT Messages

Subscribe to the MQTT topic to verify telemetry is being published:

```bash
mosquitto_sub -h <broker_ip> -t inverter/data
```

Expected JSON output example:

```json
{
  "batteryVoltage": 51.2,
  "batteryCharged": 82,
  "batteryChargingCurr": 12.4,
  "batteryDisChargingCurr": 0.0,
  "outputVoltage": 230.1,
  "outputFrequency": 50.0,
  "outputPower": 1200,
  "outputLoad": 35,
  "acVoltage": 228.7,
  "acFrequency": 50.0,
  "pvVoltage": 345.2,
  "pvPower": 1800,
  "mode": 2,
  "chargeState": 3,
  "loadState": 1
}
```

---

## Integration with Home Assistant

To integrate the MQTT telemetry into Home Assistant:

1. Enable the **MQTT integration** in Home Assistant.
2. Add sensors in your configuration.yaml or via UI:

```yaml
sensor:
  - platform: mqtt
    name: "Battery Voltage"
    state_topic: "inverter/data"
    value_template: "{{ value_json.batteryVoltage }}"
    unit_of_measurement: "V"

  - platform: mqtt
    name: "PV Power"
    state_topic: "inverter/data"
    value_template: "{{ value_json.pvPower }}"
    unit_of_measurement: "W"
```

3. Repeat for all fields you want to monitor (e.g., AC voltage, output power, load, battery state, etc.).

4. Home Assistant will now receive real-time updates from the inverter via MQTT.

---

## Notes

* The proxy maintains normal cloud communication; the inverter continues reporting to the Eybond cloud.
* Ensure your network firewall allows connections on port 502.
* The proxy parses packets based on **observed Eybond inverter protocol**. Firmware changes may affect parsing accuracy.

---

## License

This project is provided under the MIT License. Use at your own risk.

---

