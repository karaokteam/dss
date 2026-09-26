#!/usr/bin/env bash
# Start Triton with the model repository.   bash start_server.sh ENGINE INSTANCES BATCHING(on|off)
#
# TRITON_HOME    a tritonserver build with the Python backend (we used the one inside nvidia-pytriton 0.7.0)
# PYTHON_ENV     the Python environment model.py runs in (torch, torchvision, ultralytics); the backend finds it
#                through the first python3 on PATH
# LIBPYTHON_DIR  folder with libpython3.11.so (for a venv: the base Python's lib folder)
# SITE_PACKAGES  extra package folders, e.g. where tensorrt is installed
cd "$(dirname "$0")"
ENGINE=$1
INSTANCES=$2
BATCHING=$3

batching=''
if [ "$BATCHING" = on ]; then
  batching='dynamic_batching { max_queue_delay_microseconds: 2000 }'
fi
cat > model_repository/yolo26l/config.pbtxt <<EOF
backend: "python"
max_batch_size: 16
input [{ name: "image", data_type: TYPE_UINT8, dims: [-1], allow_ragged_batch: true }]
output [
  { name: "boxes", data_type: TYPE_FP32, dims: [300, 6] },
  { name: "count", data_type: TYPE_INT32, dims: [1] }
]
instance_group [{ count: $INSTANCES, kind: KIND_GPU }]
parameters { key: "engine", value: { string_value: "$ENGINE" } }
$batching
EOF

export PATH=$PYTHON_ENV/bin:$PATH
export LD_LIBRARY_PATH=$LIBPYTHON_DIR:$LD_LIBRARY_PATH
export SITE_PACKAGES   # model.py adds these to sys.path
exec "$TRITON_HOME/bin/tritonserver" --model-repository "$PWD/model_repository" --backend-directory "$TRITON_HOME/backends"
