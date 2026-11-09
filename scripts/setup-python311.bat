@echo off
echo Setting up Apply ^& Pray with Python 3.11...
py -3.11 -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
echo Setup complete.
pause
