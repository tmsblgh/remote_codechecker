FROM ubuntu:18.04

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
      python3 \
      python3-pip \
      python3-setuptools \
      less \
      vim

RUN wget http://www.us.apache.org/dist/thrift/0.11.0/thrift-0.11.0.tar.gz
RUN tar -xvf thrift-0.11.0.tar.gz
RUN rm thrift-0.11.0.tar.gz

RUN cd thrift-0.11.0/ && ./configure

RUN cd thrift-0.11.0/ && make
RUN cd thrift-0.11.0/ && make install

COPY remote_analyze_api.thrift remote_analyze_api.thrift
COPY requirements_py.txt requirements_py.txt
COPY server server/
COPY gen-py gen-py/

RUN thrift --gen py -r remote_analyze_api.thrift

RUN pip3 install -r requirements_py/requirements.txt

EXPOSE 9090

CMD ["python3", "server/remote_agent.py"]
