ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python dependencies
RUN pip3 install --no-cache-dir requests aiohttp

# Copy addon files
WORKDIR /app
COPY run.sh /
COPY controller.py /app/
COPY web_ui.py /app/

RUN chmod +x /run.sh

CMD ["/run.sh"]
