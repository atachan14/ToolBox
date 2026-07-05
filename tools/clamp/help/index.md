# Clamp Help

数値から CSS の `clamp(...)` を作るツールです。

## Calculatorタブ

`+`タブからCalculatorを複数追加できます。各タブは名前、入力内容、単位、計算結果を個別に保持します。

- タブをダブルクリック、右クリックメニュー、または`F2`でリネーム
- タブをドラッグして並べ替え
- タブの右クリックメニューから削除
- Calculatorをすべて削除した場合も、`+`タブから再度追加可能

## Input Form

`min value`、`min view`、`max view`、`max value`を入力し、Enterキーまたは`calculate`で計算します。

valueとviewには単位を直接入力できます。入力した単位はセレクターより優先されます。

```text
min value: 16px
min view: 600dvh
max view: 994
max value: 32px
```

minとmaxの片方だけに単位を入力した場合も、その単位を使用します。両方に異なる単位が入力されている場合はエラーになります。

## Unit Selector

結果欄の右側に2つの単位セレクターがあります。

- 空白 / `px / % / rem`: valueの単位（初期値は`px`）
- 空白 / `vw / vh`: viewの単位（初期値は`vw`）

セレクターは単位なしで入力した場合の既定値です。入力欄には、セレクターにない任意の単位も指定できます。

## calculation / reset

計算完了時に結果を表示し、クリップボードへコピーします。結果をクリックすると再コピーできます。

- 計算: `Enter`
- 全入力のリセット: `Ctrl+Delete`

## Reverse

下部の`reverse...`に既存の`clamp(...)`を入力すると、各値とview rangeを逆算してフォームへ戻します。

`vw`、`vh`に加えて、任意のview単位を読み取れます。
