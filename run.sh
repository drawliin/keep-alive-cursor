#!/usr/bin/env bash
cd "$(dirname "${BASH_SOURCE[0]}")"
python -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
python3 script.py