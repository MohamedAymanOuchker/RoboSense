# RoboSense ROS 2 bridge

A small `rclpy` node (`telemetry_bridge`) that subscribes to ROS 2 topics and
forwards their values to a RoboSense backend's ingest API. It decouples ROS topic
rates from ingestion: callbacks store the latest value per sensor and a timer
POSTs the accumulated snapshot at a fixed period (so high-rate topics don't blow
through the per-device rate limit).

Out of the box it bridges:

- `sensor_msgs/msg/BatteryState` → `battery` (%) and `voltage` (V)
- `std_msgs/msg/Float64` → a single, configurable sensor

Tested against ROS 2 Jazzy / Kilted (Python `rclpy`). Uses only the Python
standard library for HTTP — no extra pip packages.

## Prerequisites

- A running RoboSense backend (`make up` in the repo root).
- A device API key — run `make seed` (prints one) or create a device in the dashboard.
- A ROS 2 installation, sourced: `source /opt/ros/jazzy/setup.bash`.

## Build

```bash
# from a colcon workspace, with this package on the path:
cd examples/ros2
colcon build --packages-select telemetry_bridge
source install/setup.bash
```

## Run

```bash
ros2 run telemetry_bridge bridge \
  --ros-args \
  -p api_url:=http://localhost:8000 \
  -p api_key:=rsk_your_device_api_key \
  -p device_id:=ros2-robot \
  -p publish_period:=2.0 \
  -p battery_topic:=/battery \
  -p value_topic:=/sensor/value \
  -p value_sensor_name:=temperature
```

You should see `sent [...]` log lines, and the device's data appear live in the
dashboard.

## Try it without a robot

In another sourced terminal, publish some messages and watch them land:

```bash
# Battery at 42% / 11.5 V on /battery
ros2 topic pub -r 1 /battery sensor_msgs/msg/BatteryState \
  "{percentage: 0.42, voltage: 11.5}"

# A generic numeric sensor on /sensor/value (mapped to 'temperature' above)
ros2 topic pub -r 1 /sensor/value std_msgs/msg/Float64 "{data: 24.5}"
```

## Parameters

| Parameter            | Default                  | Description                                   |
| -------------------- | ------------------------ | --------------------------------------------- |
| `api_url`            | `http://localhost:8000`  | RoboSense backend base URL                    |
| `api_key`            | _(empty)_                | Device API key (required; sent as X-API-Key)  |
| `device_id`          | `ros2-robot`             | Label included in the payload                 |
| `publish_period`     | `2.0`                    | Seconds between ingest POSTs                   |
| `battery_topic`      | `/battery`               | `sensor_msgs/msg/BatteryState` topic          |
| `value_topic`        | `/sensor/value`          | `std_msgs/msg/Float64` topic                  |
| `value_sensor_name`  | `value`                  | Sensor name for the Float64 topic             |

## Extending

To bridge another message type, add a subscription in
[`bridge_node.py`](telemetry_bridge/telemetry_bridge/bridge_node.py) whose
callback writes into `self._latest[sensor_name] = float(value)` — the timer
handles batching and POSTing. Any numeric key in the payload becomes a sensor on
the backend.
