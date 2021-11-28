FROM ubuntu:latest

ENV APP_NAME=homesecurity
ENV WORK_DIR=/usr/${APP_NAME}

WORKDIR ${WORK_DIR}

COPY . .

RUN apt-get update && apt-get upgrade -y

RUN DEBIAN_FRONTEND=noninteractive \
    apt-get install -y             \
    python3.7                      \
    zlib1g-dev                     \
    libffi-dev                     \
    libssl-dev                     \
    wget                           \
    gcc                            \
    make                           \
    vim

RUN wget https://www.python.org/ftp/python/3.7.0/Python-3.7.0.tgz           &&\
    tar xzf Python-3.7.0.tgz                                                &&\
    Python-3.7.0/configure --enable-optimizations --prefix=/usr/bin/python  &&\
    make altinstall                                                         &&\
    rm Python-3.7.0.tgz

RUN wget https://bootstrap.pypa.io/get-pip.py &&\
    python get-pip.py


RUN python -m venv ${WORK_DIR}/venv               &&\
    pip install -r ${WORK_DIR}/requirements.txt