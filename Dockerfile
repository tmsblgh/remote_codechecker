FROM debian:buster

RUN apt-get update && apt-get install -y software-properties-common wget \ 
      && apt-get install --no-install-recommends -y \
      libboost-dev \
      libboost-test-dev \
      libboost-program-options-dev \
      libboost-system-dev \
      libboost-filesystem-dev \
      libevent-dev \
      automake \
      libtool \
      flex \
      bison \
      pkg-config \
      g++ \
      libssl-dev \
      ant \
      thrift-compiler \
      python3 \
      python3-pip \
      python3-setuptools \
      less \
      vim

COPY remote_analyze_api.thrift remote_analyze_api.thrift
COPY requirements_py/requirements.txt requirements_py/requirements.txt
COPY server server/

RUN pip3 install -r requirements_py/requirements.txt

EXPOSE 9090

CMD ["python3", "server/remote_agent.py"]
