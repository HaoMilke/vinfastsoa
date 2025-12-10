# Sử dụng Python nhẹ
FROM python:3.9-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy file thư viện và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào container
COPY . .

# Lệnh chạy (Sẽ được ghi đè trong docker-compose, nhưng để mặc định ở đây)
CMD ["python", "app.py"]