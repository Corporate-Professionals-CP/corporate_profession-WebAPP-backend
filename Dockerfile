FROM python:3.12.10

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /program

RUN apt-get update && apt-get install procps -y
RUN apt-get install python3-pip python3-dev libpq-dev -y

# Install Doppler CLI
RUN apt-get update && apt-get install -y apt-transport-https ca-certificates curl gnupg && \
    curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | apt-key add - && \
    echo "deb https://packages.doppler.com/public/cli/deb/debian any-version main" | tee /etc/apt/sources.list.d/doppler-cli.list && \
    apt-get update && \
    apt-get -y install doppler


COPY . .

RUN pip3 install -r requirements-prod.txt
EXPOSE 8080

RUN chmod +x /program/entrypoint.sh
CMD ["doppler", "run", "--", "sh", "/program/entrypoint.sh"]
