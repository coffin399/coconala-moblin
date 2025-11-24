# moblin-smart-translation

VB-Cable から拾った音声を、超軽量 Whisper モデル（tiny）で英語に翻訳して、HTML で表示するローカルアプリです。

- デフォルトは **CPU モード**（GPU VRAM を節約）
- オプションで **GPU モード (cuda)** も指定可能
- Windows + VB-Cable 前提

## セットアップ

1. Python 仮想環境を作成（任意）
2. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

3. Windows の「サウンド」設定で、**VB-Cable を既定の録音デバイス**に設定

必要に応じて `sounddevice` のデバイス一覧を確認:

```bash
python -m sounddevice
```

## 起動方法（Web UI）

CPU モード（おすすめ）:

```bash
python app.py --device cpu
```

GPU モード（VRAM に余裕がある場合のみ）:

```bash
python app.py --device cuda
```

カスタム設定の例:

```bash
python app.py --device cpu --audio-device 3 --segment-seconds 6 --quality low --port 8000
```

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

## 使い方

1. 上記のコマンドでサーバーを起動
2. ブラウザで `http://127.0.0.1:5000/` （または指定ポート）を開く
3. VB-Cable に流れている音声が自動的に英語に翻訳されて表示されます

## 起動方法（GUI 版）

Tkinter ベースの GUI 版ランチャーもあります。

```bash
python gui_app.py
```

GUI から以下を設定できます。

- Device: `cpu` / `cuda`
- Mode: `translate`（英語に翻訳） / `transcribe`（元の言語で書き起こし）
- Audio device index: `python -m sounddevice` で確認した入力デバイス番号（空欄なら OS 既定）
- Segment seconds: 1 チャンクの長さ（短いほど遅延は減るが CPU 負荷は増える）
- Quality: `ultra_low` / `low` / `normal` / `high` / `ultra_high`（速度と精度のプリセット）

「Start」を押すとモデルをロードして、VB-Cable からの音声をリアルタイムに処理します。

## Nuitka で exe にビルド

Windows で Python アプリを単一 exe にする例です（簡易例）。

1. Nuitka をインストール

```bash
pip install nuitka
```

2. GUI 版を exe 化（コンソール非表示）

```bash
python -m nuitka \
  --onefile \
  --windows-disable-console \
  --enable-plugin=tk-inter \
  gui_app.py
```

生成された `gui_app.exe` を実行すると、Python なしで GUI が起動します。

## メモ

- モデルは `faster-whisper` の **tiny** を使用
- 翻訳タスク (`task="translate"`) を使って常に英語に翻訳（GUI の `Mode=translate` の場合）
- 精度よりも軽さ・リアルタイム性を優先した設定です
