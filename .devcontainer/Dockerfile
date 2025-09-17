FROM ros:jazzy

ENTRYPOINT ["/bin/bash", "-l", "-c"]

# Create the user
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y \
  python3-venv \
  python3-pip \
  libbullet-dev \
  python3-pytest-cov \
  ros-dev-tools
ENV SHELL=/bin/bash

RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc
RUN echo "source /workspace/install/local_setup.bash" >> /root/.bashrc

CMD ["bash", "-l"]
