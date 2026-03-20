# 追加予定 #
## core ##
    - 各Tabにヘルプ
    - フォルダを開く

        - タブを外にドラッグして別Windowにする。
        - 終了時に開いてたタブを再起動時に選択
        - color調整

## markdown ##
        - import時にTabのリネーム（重複時index）
        - ドラッグでimport
        - export時にTab名をファイル名にする。
        - 外のファイルと同期（？）するモード
        - option
            1.color
            2.shortcut

## clamp ##
        - preview
        - option
            1.少数点以下の桁
            2.文字サイズ（ctrlスクロール対応）
            3.color

# 新規Tool案 #
    - linear-gradient
    - クリップボード

        - カラーピック
        - ギター指盤コード逆引き

# 就活用 #
    - README
    - Test
    - エラー処理
        1. except Exception:を減らす
        2. ユーザーにエラー表示する
        3. ログ出す（printでもいい）
    - 開発者向けドキュメント書け


# 2026-03 Large Refactor Notes

## Goal
- Make `clamp` / `clip-path` history shared per tool instead of per tab.
- Persist current input values and toggle states per tab.
- Restore each tab's working state on restart.

## Confirmed Decisions
- Keep `tab name = folder name`.
- Keep user data under the app folder for portability and clean reinstall by folder deletion.
- Do not use `%LOCALAPPDATA%`.
- Exclude `Users/` from update overwrite/delete targets.

## Proposed Structure
```text
ToolBox/
├─ ToolBox.exe
├─ updater.exe
└─ Users/
   ├─ Tabs/
   │  ├─ ex.markdown/
   │  │  ├─ meta.json
   │  │  ├─ state.json
   │  │  └─ file.md
   │  ├─ ex.clamp/
   │  │  ├─ meta.json
   │  │  └─ state.json
   │  └─ ex.clip-path/
   │     ├─ meta.json
   │     └─ state.json
   └─ ToolData/
      ├─ markdown/
      │  └─ settings.json
      ├─ clamp/
      │  ├─ history.json
      │  └─ settings.json
      └─ clip-path/
         ├─ history.json
         └─ settings.json
```

## Naming
- Rename `tool.json` to `meta.json`.
- `meta.json` stores tab metadata.
- `state.json` stores tab-local working state.
- `ToolData/<tool>/history.json` stores shared history.
- `ToolData/<tool>/settings.json` stores shared tool settings.

## Responsibility Split
### `Users/Tabs/<tab-name>/meta.json`
- `tool`
- `order`
- `label`
- `schema_version`

Note:
- For now, `label` and folder name stay the same.

### `Users/Tabs/<tab-name>/state.json`
- Current form values
- Toggle states
- Per-tab temporary UI state
- Restart restore target data

Examples:
- `clamp`
  - `free_input`
  - `min_px`
  - `min_view`
  - `max_view`
  - `max_px`
  - `reverse_input`
  - `last_edited`
- `clip-path`
  - `points`
  - `circles`
  - `mode`
  - `size`
  - `unit`
  - `grid_value`
  - `grid_enabled`

### `Users/ToolData/<tool>/history.json`
- Shared by all tabs of the same tool.

### `Users/ToolData/<tool>/settings.json`
- Shared options such as color, shortcut, default values.

## Implementation Rules
- Pass both `tab_dir` and `tool_data_dir` to each tool.
- Separate shared data access from tab state access.
- Closing a tab removes only `Users/Tabs/<tab-name>`.
- Shared tool data must remain.
- Renaming a tab still renames the folder.
- Tools must not keep hard-coded tab path strings.
- Tab state always saves to that tab's `state.json`.
- Tool history always saves to that tool's `history.json`.

## Current Code Issues
- `ToolBase` only has one `folder`, so shared/tab separation is impossible.
- `core/tab_storage.py` assumes tool-owned files live under each tab.
- `clamp` stores history in tab-local `history.json`.
- `clip-path` ignores the tab folder and hard-codes `tabs/Clip-Path/history.json`.
- Tool loading is static, so `Users/Tools/` would be a misleading name.

## Updater Requirements
- Do not overwrite or delete `Users/` during update.
- Update only shipped application files.
- Even if a zip contains `Users/`, skip it during copy.
- Clean install remains "delete the ToolBox folder".
- Portability remains "move the ToolBox folder".

## Migration Requirements
- Migrate old `tabs/<tab>/tool.json` to `Users/Tabs/<tab>/meta.json`.
- Merge old clamp tab histories into `Users/ToolData/clamp/history.json`.
- Move old clip-path history from `tabs/Clip-Path/history.json` to `Users/ToolData/clip-path/history.json`.
- Run migration automatically on first launch after the refactor.
- Migration must be idempotent.
- On migration failure, do not delete old data.

## Suggested Order
1. Update `core.paths` to define `Users/`, `Tabs/`, and `ToolData/`.
2. Update `ToolBase` to accept `tab_dir` / `tool_data_dir`.
3. Refactor tab creation, restore, rename, and close storage handling.
4. Update updater logic to skip `Users/`.
5. Refactor `clamp` to shared history + tab state.
6. Refactor `clip-path` to shared history + tab state.
7. Add migration logic.
