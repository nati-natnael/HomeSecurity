FROM python:latest

ENV APP_NAME=homesecurity
ENV WORK_DIR=/usr/${APP_NAME}

WORKDIR ${WORK_DIR}

COPY . .

RUN python -m pip install -r ${WORK_DIR}/requirements.txt

CMD ["python", "src/main.py", "-f src/application.yml"]

