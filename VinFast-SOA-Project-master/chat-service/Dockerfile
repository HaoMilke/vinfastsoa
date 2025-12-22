FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Sử dụng eventlet để hỗ trợ WebSocket tốt nhất
CMD ["python", "app.py"]