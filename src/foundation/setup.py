from setuptools import find_packages, setup

package_name = "foundation"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    package_data={
        "foundation": ["pinconfig.json"],
        "foundation.component.motor": ["odrive-cansimple.dbc"],
    },
    install_requires=[
        "adafruit-circuitpython-mcp230xx",
        "cantools",
        "gpiozero",
        "python-can",
        "python-dotenv",
        "smbus2",
    ],
    zip_safe=True,
    maintainer="catbot",
    description="Main low-level control node",
    license="My license",
    # tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "main = foundation.main:main",
            "simulation = foundation.simulation:main",
        ],
    },
)
