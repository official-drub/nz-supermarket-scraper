FROM python:3.13.14-slim
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    xvfb \
    xauth \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY foodstuffs/requirements.txt foodstuffs/requirements.txt 
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r foodstuffs/requirements.txt
RUN python -m playwright install --with-deps chromium

COPY log_util.py .
COPY foodstuffs/__init__.py foodstuffs/__init__.py
COPY foodstuffs/foodstuffs_scraper.py foodstuffs/mapped_pid_bc.py foodstuffs/
COPY foodstuffs/paknsave/util/stores.json foodstuffs/paknsave/util/catagories.json foodstuffs/paknsave/util/
COPY foodstuffs/newWorld/util/stores.json foodstuffs/newWorld/util/catagories.json foodstuffs/newWorld/util/


ENTRYPOINT ["xvfb-run", "-a", "python3", "-m", "foodstuffs.foodstuffs_scraper"]
