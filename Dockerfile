FROM python:3.12.6-slim-buster

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /program

RUN apt-get update && apt-get install procps -y
RUN apt-get install python3-pip python3-dev libpq-dev -y

COPY . .

RUN pip3 install -r requirements-prod.txt
EXPOSE 8080

RUN chmod +x /program/entrypoint.sh
CMD ["sh", "/program/entrypoint.sh"]
