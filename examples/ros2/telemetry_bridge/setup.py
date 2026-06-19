from setuptools import find_packages, setup

package_name = "telemetry_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="RoboSense contributors",
    maintainer_email="noreply@example.com",
    description="Bridges ROS 2 topics to a RoboSense backend's telemetry ingest API.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "bridge = telemetry_bridge.bridge_node:main",
        ],
    },
)
