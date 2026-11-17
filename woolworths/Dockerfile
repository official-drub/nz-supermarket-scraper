FROM python:3.13.14-slim
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY woolworths/requirements.txt woolworths/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r woolworths/requirements.txt

COPY log_util.py .
COPY woolworths/__init__.py woolworths/__init__.py
COPY woolworths/wwscraper.py woolworths/wwscraper.py
COPY woolworths/util/ woolworths/util/

ENTRYPOINT [ "python3", "-m", "woolworths.wwscraper"  ]