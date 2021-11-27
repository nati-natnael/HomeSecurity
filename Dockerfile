FROM python:3.7

ENV APP_NAME=homesecurity
ENV WORK_DIR=/usr/${APP_NAME}

WORKDIR ${WORK_DIR}

COPY . .

RUN python3 -m venv ${WORK_DIR}/venv

RUN pip install -r ${WORK_DIR}/requirements.txt