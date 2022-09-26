FROM debian:sid-slim

RUN apt -y update && apt -y install python3-aiohttp

COPY litegpodder/ /code/litegpodder
ENV PYTHONPATH=/code

VOLUME /data

EXPOSE 8080

ENTRYPOINT python3 -m litegpodder -l 0.0.0.0 -d /data
