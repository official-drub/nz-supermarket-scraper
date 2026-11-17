#!/usr/bin/env bash

set -e
export MSYS_NO_PATHCONV=1

cd "$(dirname "$0")"

INDEX=${INDEX:-0}
TOTAL_MACHINES=${TOTAL_MACHINES:-1}

build() {
    docker build -f woolworths/Dockerfile -t wwscraper .
    docker build -f foodstuffs/Dockerfile -t foodstuffs-scraper .
    docker build -t parser .
}

scrape() {
    mkdir -p data/ww data/ps data/nw

    docker run --rm --init -v "$PWD/data/ww:/app/woolworths/output" wwscraper -i "$INDEX" -t "$TOTAL_MACHINES" &
    docker run --rm --init --env-file .env -v "$PWD/data/ps:/app/foodstuffs/paknsave/output" foodstuffs-scraper -s paknsave -i "$INDEX" -t "$TOTAL_MACHINES" &
    docker run --rm --init --env-file .env -v "$PWD/data/nw:/app/foodstuffs/newWorld/output" foodstuffs-scraper -s newworld -i "$INDEX" -t "$TOTAL_MACHINES" &
    
    wait
}

parse() {
    docker run --rm -it --init --env-file .env \
    -v "$PWD/data/ww:/app/woolworths/output:ro" \
    -v "$PWD/data/ps:/app/foodstuffs/paknsave/output:ro" \
    -v "$PWD/data/nw:/app/foodstuffs/newWorld/output:ro" \
    parser
}

usage() {
    echo "usage: INDEX=0 TOTAL_MACHINES=4 ./run.sh <build|scrape|parse> "
    echo "e.g INDEX=0 TOTAL_MACHINES=4 ./run.sh build scrape or ./run.sh scrape parse or ./run.sh build parse scrape"
}

if [[ $# -eq 0 ]]; then
    usage
    exit 1
fi

if ! [[ "$INDEX" =~ ^[0-9]+$ && "$TOTAL_MACHINES" =~ ^[1-9][0-9]*$ ]]; then
    usage
    echo "ERROR: INDEX must be >= 0 and TOTAL_MACHINES must be >=1"
    exit 1
fi


# checking the args first so something like build hello doesnt complain
for arg in "$@"; do
    if [[ ! "$arg" =~ ^(build|scrape|parse)$ ]]; then
        echo "unknown command: $arg"
        usage
        exit 1
    fi
done

for arg in "$@"; do
    echo "Running $arg"
    "$arg"
done