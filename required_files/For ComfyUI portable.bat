@echo off
echo Flow2 SageAttention One-Click Installer

set TRITON_URL=https://github.com/woct0rdho/triton-windows/releases/download/v3.2.0-windows.post10/triton-3.2.0-cp312-cp312-win_amd64.whl
set INCLUDE_LIBS_URL=https://github.com/woct0rdho/triton-windows/releases/download/v3.0.0-windows.post1/python_3.12.7_include_libs.zip

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo Installing Visual Studio Build Tools...
winget install --id Microsoft.VisualStudio.2022.BuildTools -e --source winget --override "--quiet --wait --norestart --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows10SDK.20348"

echo Installing Triton...
python_embeded\python.exe -m pip install "%TRITON_URL%"

for %%F in ("%INCLUDE_LIBS_URL%") do (
    set FILE_NAME=%%~nxF
)

echo Downloading Python include/libs from URL...
curl -L -o "%FILE_NAME%" "%INCLUDE_LIBS_URL%"

echo Extracting Python include/libs using tar...
tar -xf "%FILE_NAME%" -C python_embeded

echo Cloning SageAttention repository...
git clone https://github.com/thu-ml/SageAttention.git

echo Installing SageAttention...
python_embeded\python.exe -s -m pip install -e SageAttention

echo Success!
pause