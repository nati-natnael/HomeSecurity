FROM ubuntu:latest

ENV APP_NAME=homesecurity
ENV WORK_DIR=/usr/${APP_NAME}
ENV BUILD_DIR=${WORK_DIR}/build

WORKDIR ${WORK_DIR}

COPY . .

RUN apt-get update && apt-get upgrade -y

RUN DEBIAN_FRONTEND=noninteractive \
    apt-get install -y             \
    zlib1g-dev                     \
    wget                           \
    git                            \
    gcc                            \
    make                           \
    vim

RUN mkdir ${BUILD_DIR}                                                                &&\
    cd ${BUILD_DIR}                                                                   &&\
    wget https://www.python.org/ftp/python/3.7.0/Python-3.7.0.tgz                     &&\
    tar xzf Python-3.7.0.tgz                                                          &&\
    Python-3.7.0/configure --enable-optimizations --prefix=/usr/bin/python3           &&\
    make altinstall                                                                   &&\
    ln -s /usr/bin/python3/bin/python3.7 /usr/bin/python                              &&\
    rm Python-3.7.0.tgz                                                               &&\
    wget https://bootstrap.pypa.io/get-pip.py                                         &&\
    python get-pip.py                                                                 &&\
    ln -s /usr/bin/python3/bin/pip3.7 /usr/bin/pip                                    &&\
    pip install -r ${WORK_DIR}/requirements.txt

