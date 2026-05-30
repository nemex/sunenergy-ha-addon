FROM python:3.11-alpine

# Install dependencies
RUN pip3 install --no-cache-dir requests

# Copy addon files
WORKDIR /app
COPY controller.py /app/
COPY web_ui.py /app/

CMD ["python3", "/app/controller.py"]
