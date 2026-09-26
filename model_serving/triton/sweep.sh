#!/usr/bin/env bash
# Load-test every combination of instance count and dynamic batching.   bash sweep.sh ENGINE IMAGE_FOLDER
cd "$(dirname "$0")"
ENGINE=$1
IMAGES=$2
mkdir -p results

for instances in 1 2 4; do
  for batching in off on; do
    bash start_server.sh "$ENGINE" $instances $batching > server.log 2>&1 &
    server=$!
    until curl -sf localhost:8000/v2/models/yolo26l/ready > /dev/null; do sleep 2; done

    nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 1 > gpu_memory.tmp &
    monitor=$!
    python load_test.py "$IMAGES" --label "$instances instance(s), batching $batching"
    kill $monitor
    echo "$instances instance(s), batching $batching: peak GPU memory $(sort -n gpu_memory.tmp | tail -1) MiB" \
      >> results/gpu_memory.txt

    kill $server
    wait $server
    sleep 5
  done
done
