rem author: mwolf
rem date: 20251026
rem desc: install the python package to build and executable. then compile the exe and rename it.

@echo off
pip install pyinstaller
mkdir dist
cp relay_settings.xml dist/
cd .venv/Scripts
pyinstaller --onefile --noconsole --distpath ../../dist/ ../../main.py
cd ../../
cd dist
move main.exe "RS232 Relay Test.exe"
echo .exe file created.
pause
@echo on
