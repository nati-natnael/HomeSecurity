FROM ubuntu:latest

ENV APP_NAME=homesecurity
ENV WORK_DIR=/usr/${APP_NAME}

WORKDIR ${WORK_DIR}

COPY . .

RUN apt-get upgrade -y

RUN DEBIAN_FRONTEND=noninteractive \
    apt-get install -y             \
    python3.7                      \
    vim

RUN python3 -m venv ${WORK_DIR}/venv

RUN pip install -r ${WORK_DIR}/requirements.txt