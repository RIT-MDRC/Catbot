# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["torch==2.14.0", "rsl-rl-lib==5.4.2", "wandb==0.30.0"]
#
# [tool.uv.sources]
# torch = [{ index = "pytorch-cpu", marker = "sys_platform == 'linux'" }]
# torchvision = [{ index = "pytorch-cpu", marker = "sys_platform == 'linux'" }]
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Download and prepare a selected W&B checkpoint for the ROS policy node.

Run `uv run pull_policy.py RUN_ID [CHECKPOINT_NUMBER]` from this directory.
The default project is hiromon-rochester-institute-of-technology/catbot;
omitting the checkpoint selects the latest checkpoint in the specified run. This prepares a policy without
starting ROS or moving hardware; `ros2 launch catbot_policy catbot.launch.py`
then uses the successfully prepared bundle by default.
"""

from catbot_policy.deployment import main

if __name__ == "__main__":
    main()
