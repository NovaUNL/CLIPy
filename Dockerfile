FROM python:3.8-buster

LABEL maintainer="Cláudio Pereira <clipy@claudiop.com>"


COPY pip-packages /
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r /pip-packages
COPY CLIPy /CLIPy
COPY webservice /webservice

VOLUME  ["/conf", "/files"]
WORKDIR /
EXPOSE 893
ENTRYPOINT ["uwsgi", "/conf/uwsgi.ini"]
