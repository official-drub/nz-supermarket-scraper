FROM python:3.13.14-slim
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY log_util.py parser_to_db.py ./
COPY parsers/ parsers/

ENTRYPOINT [ "python3", "parser_to_db.py"  ]