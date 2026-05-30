ARG BUILD_FROM
FROM $BUILD_FROM AS base

# Install Python dependencies
RUN pip3 install --no-cache-dir requests

# Copy addon files
WORKDIR /app
COPY controller.py /app/
COPY web_ui.py /app/

CMD ["python3", "/app/controller.py"]
