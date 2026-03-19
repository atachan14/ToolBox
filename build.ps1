taskkill /IM ToolBox.exe /F 2>$null
Remove-Item dist -Recurse -Force 2>$null
Remove-Item build -Recurse -Force 2>$null
Remove-Item *.spec -Force 2>$null

# ToolBox本体
pyinstaller main.py `
  --onedir `
  --windowed `
  --name ToolBox `
  --clean `
  --icon=toolbox.ico `
  --collect-submodules tools `
  --exclude-module PySide6.QtWebEngine `
  --add-data "toolbox.qss;." `
  --add-data "toolbox.ico;."

# updater（onefile推奨）
pyinstaller updater.py `
  --onefile `
  --name updater `
  --clean `
  --icon=toolbox.ico

# ToolBoxに移動
Move-Item dist\updater.exe dist\ToolBox\updater.exe -Force