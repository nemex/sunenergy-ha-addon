FROM python:3.11-alpine

RUN pip3 install --no-cache-dir requests

WORKDIR /app
COPY controller.py /app/
COPY web_ui.py /app/

# Startscript das beide parallel startet
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
