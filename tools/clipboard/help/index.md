# ClipBoard Help

ClipBoard は List ごとに item と text を保持して、クリックで個別コピーできるツールです。

## Basic

1. `新規List` で List を追加します。
2. 上部の検索窓で List を絞り込みます。
3. `item検索` で現在の List 内の item を絞り込みます。
4. `name` をクリックすると名前をコピーします。
5. `text` をクリックするとその文字列をコピーします。

## Edit

- `edit` で item を編集状態にします。
- 編集中は name / text を直接変更できます。
- `save` で編集状態を終了します。
- 右クリックメニューから item の追加と削除ができます。
- `name` のドラッグで item 順序を入れ替えられます。
- `text` のドラッグで item 内の text 順序を入れ替えられます。

## Save

- データは `tool_data_dir` に保存されます。
- 編集中の内容や検索条件も自動保存されます。
