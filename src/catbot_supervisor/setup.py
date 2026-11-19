from glob import glob

from setuptools import find_packages, setup

setup(
    name="catbot_supervisor",
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/catbot_supervisor"]),
        ("share/catbot_supervisor", ["package.xml"]),
        ("share/catbot_supervisor/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="catbot",
    maintainer_email="hiroto125takeuchi@gmail.com",
    license="MIT",
    description="RPi safety decisions and Orin managed services",
    entry_points={
        "console_scripts": [
            "rpi = catbot_supervisor.node:main",
            "orin = catbot_supervisor.orin:main",
        ]
    },
)
