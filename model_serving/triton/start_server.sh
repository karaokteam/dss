#!/usr/bin/env bash
# Start Triton (HTTP on port 8000, gRPC on 8001).   bash start_server.sh
#
# TRITON_HOME    a tritonserver build with the Python backend (we used the one inside nvidia-pytriton 0.7.0)
# PYTHON_ENV     the Python environment model.py runs in (torch, torchvision, ultralytics); the backend finds it
#                through the first python3 on PATH
# LIBPYTHON_DIR  folder with libpython3.11.so (for a venv: the base Python's lib folder)
# SITE_PACKAGES  extra package folders, e.g. where tensorrt is installed
cd "$(dirname "$0")"
export PATH=$PYTHON_ENV/bin:$PATH
export LD_LIBRARY_PATH=$LIBPYTHON_DIR:$LD_LIBRARY_PATH
export SITE_PACKAGES   # model.py adds these to sys.path
exec "$TRITON_HOME/bin/tritonserver" --model-repository "$PWD/model_repository" --backend-directory "$TRITON_HOME/backends"
