# moblin-smart-translation

VB-Cable から拾った音声を、軽量 Whisper（`faster-whisper`）で英語に翻訳し、
Web ブラウザ経由で字幕表示・OBS に重ねるためのローカルアプリです。

- デフォルトは **CPU モード**（GPU VRAM を節約）
- オプションで **GPU モード (cuda)** も指定可能
- Windows + VB-Cable 前提
- UI は Web ベース（`/settings` と `/display` の 2 画面）

---

## セットアップ

1. Python 3.11 をインストール（`py -3.11 --version` が通る状態）
2. このプロジェクトを展開
3. Windows の「サウンド」設定で、**VB-Cable を既定の録音デバイス**に設定

必要に応じて `sounddevice` のデバイス一覧を確認:

```bash
python -m sounddevice
```

---

## かんたん起動（start.bat 推奨）

プロジェクトフォルダ直下で `start.bat` を実行すると、以下を自動で行います。

1. `.venv` を Python 3.11 で作成 or 再利用
2. `pip install -r requirements.txt` で依存インストール
3. CPU モード + `quality=ultra_low` でサーバー起動

実行後、ブラウザで次を開きます。

```text
http://127.0.0.1:5000/settings
```

サーバー停止は、`start.bat` を開いているコンソールで `Ctrl + C` です。

---

## 直接起動（CLI オプション）

自前の仮想環境などで動かしたい場合:

```bash
pip install -r requirements.txt

python app.py --device cpu --quality ultra_low
```

主なオプション:

- `--device`: `cpu` または `cuda`。省略時は `cpu`
- `--audio-device`: `sounddevice` の入力デバイス番号。省略時は OS の既定デバイス（VB-Cable を推奨）
- `--segment-seconds`: 録音チャンク長。短くすると遅延は減るが CPU 負荷は増える
- `--quality`: `ultra_low` / `low` / `normal` / `high` / `ultra_high`
  - `ultra_low`: 最速・最軽量（tiny, beam_size 1）
  - `low`: 速い・やや精度アップ
  - `normal`: バランス（標準）
  - `high`: 精度寄り
  - `ultra_high`: 最高精度寄り（CPU/GPU 負荷が最も高い）
- `--port`: Web UI のポート番号（デフォルト 5000）

---

## Web UI の構成

サーバー起動後、ブラウザで:

```text
http://127.0.0.1:5000/settings
```

を開くと、モダンなダークUIの **設定画面 + プレビュー** が表示されます。

### /settings — テキスト設定タブ

- Font family: System / Sans / Serif / Monospace
- Font size: フォントサイズ（px）
- Line height: 行間
- Alignment: Left / Center / Right
- Max lines: 表示行数の上限（0 は無制限、>0 で末尾 N 行のみ）
- Text color: 文字色
- Shadow: ドロップシャドウの有無
- Background: 背景モード（Transparent / Dark blur / Solid dark）
- Padding: テキスト周りの余白（px）

右側の「Live preview」が、現在の `/transcript` の内容を取得しつつ、
上記設定を反映した見た目でプレビューします。

ヘッダー右上のタブ:

- `Text settings` … 設定画面（現在のページ）
- `Open output tab` … `/display` を新しいタブで開くためのリンク

設定はブラウザの LocalStorage (`mst_text_settings_v1`) に保存され、
`/display` 側でも同じ設定が使われます。

### /display — テキスト出力タブ

`/settings` で保存された設定を読み込み、
実際に OBS などに重ねる **字幕出力専用ページ** です。

URL 例:

```text
http://127.0.0.1:5000/display
```

特徴:

- 背景は透明 or 半透明ダーク（`/settings` の Background 次第）
- フルスクリーン相当のテキスト表示のみ
- `/transcript` をポーリングして、最新テキストを表示

---

## OBS との連携

OBS では「ブラウザ」ソースとして `/display` を読み込むことで、
字幕レイヤーとして重ねられます。

1. OBS で **ソースを追加 → 「ブラウザ」** を選択
2. URL に `http://127.0.0.1:5000/display` を指定
3. 幅・高さを配信解像度に合わせる（例: 1920x1080）
4. `/settings` でフォントや背景、行数などを調整

これで、VB-Cable に流れている音声 → 翻訳テキスト → `/display` → OBS のブラウザソース
という流れで字幕を重ねられます。

---

## オーディオルーティングのヒント

基本構成（おすすめ）:

- Windows の録音デバイス既定値を **VB-Cable** にする
- moblin などボイチェン・エフェクタの出力を VB-Cable に向ける
- このアプリは OS 既定デバイス（= VB-Cable）から音を取得
- OBS は VB-Cable をオーディオソースとして取り込む

これにより、

```text
マイク → moblin（エフェクト） → VB-Cable → [OBS / moblin-smart-translation 両方]
```

というルーティングになり、配信に乗る音と字幕化される音を揃えられます。

特定の入力デバイスだけを使いたい場合（例: 素のマイクのみ）は、
`--audio-device` で `python -m sounddevice` の ID を直接指定してください。

---

## メモ

- モデルは `faster-whisper` を使用
- 品質プリセットにより `tiny` / `base` / `small` / `medium` を切り替え
- 精度よりも軽さ・リアルタイム性を優先した構成（特に `ultra_low` / `low`）
