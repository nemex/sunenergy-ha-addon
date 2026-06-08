ARG BUILD_FROM
FROM $BUILD_FROM

# bash wird für 'wait -n' in run.sh benötigt (im HA-Base-Image meist vorhanden,
# zur Sicherheit hier explizit installiert).
RUN apk add --no-cache bash \
    && pip3 install --no-cache-dir requests

WORKDIR /app
COPY controller.py /app/
COPY web_ui.py /app/

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
