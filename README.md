# ToolBox

Windows 向けの PySide6 製ユーティリティ集です。  
複数の小さなツールをタブで切り替えながら使えます。

## Screenshot

![plus](images/readme/plus.png)
![plus](images/readme/clamp.png)
![plus](images/readme/gradient.png)


## 使用方法

1. Releasesから最新版をダウンロードし、zipを解凍してください。
2. 中に入っているToolBox.exeを起動してください。
（未確認のアプリケーションとして警告が出る場合があります。
スマートアプリコントロールが有効になっている場合は起動できない場合があります。）
3. 起動後は自動で[+]タブが開かれます。
[+]タブ内の各Toolをクリックすることで対象Toolを開き、タブに追加します。
[+]タブ内の各Tool（もしくは開いたToolのタブ）を右クリックすることでMenuを開き、MenuからHelpを起動することができます。

各Toolの使用法については各Helpを参照してください。

## 使用方法（その他）
- タブを右クリックした menu からタブの削除やリネームが行えます。
対象タブにカーソルを合わせて F2キー でもリネームが行えます。
- Windowの場合、alt+W でウィンドウを最前面に固定できます。
- [+]タブを右クリックした menu から、閉じたタブの復元が行えます。
- Release 更新時はダイアログが表示され、自動更新が可能になっています。

## Included Tools

詳細についてはアプリケーション内の各Helpを参照してください。

### MarkDown

シンプルな Markdown エディタです。
主に簡易メモとしての使用を想定して制作しています。

### Clamp

CSS の `clamp(...)` を作るための計算ツールです。

### Clip-Path

CSS の `clip-path: polygon(...)` を組み立てるツールです。

### ClipBoard

定型文やテキスト断片を保存して再利用するためのツールです。

### Gradient

CSS グラデーションを視覚的に作るツールです。

## Environment

- Python 3.14
- PySide6
- Windows

## Run

```powershell
python main.py
```

## Build

`build.ps1` で PyInstaller ビルドを実行します。

```powershell
./build.ps1
```

ビルド後の想定:
- `dist/ToolBox/_internal/`
- `dist/ToolBox/ToolBox.exe`
- `dist/ToolBox/updater.exe`

## Project Structure

```text
.
├─ core/        # アプリ共通機能
├─ tools/       # 各ツール本体
├─ Users/       # ユーザーデータ
├─ main.py      # アプリ起動
├─ updater.py   # 更新用処理
├─ build.ps1    # ビルドスクリプト
└─ README.md
```

## Data Persistence

このアプリはツールごとのデータやタブ状態を保存します。

Users/
├─ Tabs/　タブ毎のデータ
└─ ToolData/ ツール共有のデータ

## Version

現在のバージョン: `1.2.8`

## Roadmap / Notes

- Help の最適化
- 各Tool の UI/UX の最適化
- ツールの追加
- ツールのパッケージ化/プラグイン化

## License

MIT License

## 制作経緯
事業所でのclamp計算を楽にしたいという思いから始まり、ついでの機能を構想し、自分用のアプリケーションとして開発しました。
またポートフォリオとしても活用できるよう、自分以外の使用を想定したHelpの追加やUIの調整、自分のためだけなら過剰だが誰かにとっては必要そうな機能を追加しました。

## AI
v1.0.0まで(MarkDown と Clamp)はChatGPTと共同で制作しており、それ以降は殆どをCodeXに制作させています。
