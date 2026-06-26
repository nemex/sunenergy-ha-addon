FROM python:3.11-alpine

# bash is needed for run.sh script handling
RUN apk add --no-cache bash \
    && pip3 install --no-cache-dir requests

WORKDIR /app
COPY controller.py /app/
COPY web_ui.py /app/
COPY index.html /app/

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
