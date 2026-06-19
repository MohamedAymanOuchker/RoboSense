"""RoboSense ROS 2 telemetry bridge.

Subscribes to ROS 2 topics and forwards their values to a RoboSense backend's
ingest API (``POST /api/telemetry`` with an ``X-API-Key`` header).

High-rate ROS topics are decoupled from the ingest API: each callback just stores
the latest value per sensor, and a timer POSTs the accumulated snapshot at a
fixed period. This keeps ingestion well under the per-device rate limit while
still reflecting current readings.

Out of the box it bridges:
  * ``sensor_msgs/msg/BatteryState`` -> ``battery`` (%) and ``voltage`` (V)
  * ``std_msgs/msg/Float64``         -> a single, configurable sensor name

Everything is configurable via ROS 2 parameters (see README.md).
"""

import json
import math
import urllib.error
import urllib.request

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Float64


class TelemetryBridge(Node):
    def __init__(self) -> None:
        super().__init__("telemetry_bridge")

        # --- Parameters ---
        self.api_url = self._param("api_url", "http://localhost:8000").rstrip("/")
        self.api_key = self._param("api_key", "")
        self.device_id = self._param("device_id", "ros2-robot")
        self.publish_period = float(self._param("publish_period", 2.0))
        battery_topic = self._param("battery_topic", "/battery")
        value_topic = self._param("value_topic", "/sensor/value")
        self.value_sensor_name = self._param("value_sensor_name", "value")

        if not self.api_key:
            self.get_logger().warn(
                "No 'api_key' parameter set — ingestion will be rejected (401). "
                "Pass -p api_key:=rsk_..."
            )

        # Latest value per sensor, flushed on a timer.
        self._latest: dict[str, float] = {}

        self.create_subscription(BatteryState, battery_topic, self._on_battery, 10)
        self.create_subscription(Float64, value_topic, self._on_value, 10)
        self.create_timer(self.publish_period, self._flush)

        self.get_logger().info(
            f"telemetry_bridge -> {self.api_url} as device '{self.device_id}'; "
            f"battery_topic={battery_topic}, value_topic={value_topic}, "
            f"period={self.publish_period}s"
        )

    def _param(self, name: str, default):
        return self.declare_parameter(name, default).value

    # --- Subscriptions ---

    def _on_battery(self, msg: BatteryState) -> None:
        # BatteryState.percentage is 0..1; expose it as a 0..100 percent.
        if not math.isnan(msg.percentage):
            self._latest["battery"] = round(msg.percentage * 100.0, 2)
        if not math.isnan(msg.voltage):
            self._latest["voltage"] = round(msg.voltage, 3)

    def _on_value(self, msg: Float64) -> None:
        self._latest[self.value_sensor_name] = float(msg.data)

    # --- Ingest ---

    def _flush(self) -> None:
        if not self._latest:
            return
        payload = {"device_id": self.device_id, **self._latest}
        sensors = list(self._latest)
        try:
            self._post(payload)
            self.get_logger().info(f"sent {sensors}")
        except urllib.error.HTTPError as exc:
            self.get_logger().warn(f"ingest rejected (HTTP {exc.code}): {exc.read().decode()}")
        except Exception as exc:  # noqa: BLE001 — log and keep running on any network error
            self.get_logger().warn(f"ingest error: {exc}")

    def _post(self, payload: dict) -> None:
        data = json.dumps(payload).encode()
        request = urllib.request.Request(
            f"{self.api_url}/api/telemetry",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "X-API-Key": self.api_key},
        )
        with urllib.request.urlopen(request, timeout=5):
            pass


def main() -> None:
    rclpy.init()
    node = TelemetryBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
