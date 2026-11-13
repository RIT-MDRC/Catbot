from glob import glob

from setuptools import find_packages, setup

setup(
    name="catbot_policy",
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/catbot_policy"]),
        ("share/catbot_policy", ["package.xml"]),
        ("share/catbot_policy/launch", glob("launch/*.launch.py")),
    ],
    package_data={
        "catbot_policy": [
            "default_mapping.json",
            "inference/*.toml",
            "inference/*.lock",
            "inference/*.py",
        ]
    },
    install_requires=["setuptools"],
    zip_safe=False,
    maintainer="Catbot",
    maintainer_email="hiroto125takeuchi@gmail.com",
    description="Trained Catbot actor inference and actuator commands",
    license="MIT",
    entry_points={"console_scripts": ["policy = catbot_policy.node:main"]},
)
