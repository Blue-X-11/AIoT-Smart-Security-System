FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

# [修改这里] 补充安装 libgl1, libglib2.0-0, libxcb1 等 OpenCV 所需的底层 C++ 依赖
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libgl1 \
    libglib2.0-0 \
    libxcb1 \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple \
    --extra-index-url https://mirrors.aliyun.com/pytorch-wheels/cpu

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]