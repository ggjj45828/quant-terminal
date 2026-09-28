FROM python:3.11-slim

# 零第三方依赖, 只用标准库 (GBK 解码由 Python 内置编解码器提供)
WORKDIR /app
COPY bridge.py /app/bridge.py

ENV PORT=8899 \
    TENCENT_TIMEOUT=15

EXPOSE 8899

CMD ["python", "-u", "/app/bridge.py"]
