"""Keep ROS collection explicit; selecting ROS requires working bindings."""


def pytest_ignore_collect(collection_path, config):
    return collection_path.name.startswith(
        "test_ros_"
    ) and "ros" not in config.option.markexpr.replace("not ros", "")
