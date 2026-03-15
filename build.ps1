taskkill /IM ToolBox.exe /F 2>$null
Remove-Item dist -Recurse -Force 2>$null
pyinstaller main.py --onedir --windowed --name ToolBox --clean --icon=toolbox.ico --collect-submodules tools --exclude-module PySide6.QtWebEngine