#!/bin/bash
echo "creating the virtual environment in ollivenv"
python -m venv ollivenv
echo "installing the requirements"
source ollivenv/bin/activate && pip install -r requirements.py
echo done.

