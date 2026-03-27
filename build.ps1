taskkill /IM ToolBox.exe /F 2>$null
Remove-Item dist -Recurse -Force 2>$null
Remove-Item build -Recurse -Force 2>$null
 

# ToolBox本体
pyinstaller ToolBox.spec --clean

# updater（onefile推奨）
pyinstaller updater.spec --clean

# ToolBoxに移動
Move-Item dist\updater.exe dist\ToolBox\updater.exe -Force
