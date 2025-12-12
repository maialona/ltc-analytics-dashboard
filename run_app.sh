#!/bin/bash
echo "Checking requirements..."
pip install -r requirements.txt --default-timeout=100 -i https://pypi.org/simple

echo "Running Verification Tests..."
python3 test_logic.py

echo "Starting App..."
streamlit run app.py
