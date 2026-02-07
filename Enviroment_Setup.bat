@echo off
REM Enviroment_Setup.bat - Sets up a portable venv using WinPython and installs requirements

REM Add PortableGit to PATH for this session
set PATH=D:\PortableGit\bin;D:\PortableGit\cmd;%PATH%

REM Set WinPython root (update if you install to a different folder)
set WINPY_ROOT=D:\CitizensFinance\WPy64-31241\python-3.12.4.amd64
set PYTHON_EXE=%WINPY_ROOT%\python.exe

REM Create venv in project root
%PYTHON_EXE% -m venv D:\CitizensFinance\venv

REM Upgrade pip
D:\CitizensFinance\venv\Scripts\python.exe -m pip install --upgrade pip

REM Install requirements
D:\CitizensFinance\venv\Scripts\python.exe -m pip install -r D:\CitizensFinance\requirements.txt

REM Activate venv and start a shell
call D:\CitizensFinance\venv\Scripts\activate.bat
cmd 