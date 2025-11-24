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

## 起動方法

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
python app.py --device cpu --audio-device 3 --segment-seconds 6 --port 8000
```

- `--device`: `cpu` または `cuda`。省略時は `cpu`
- `--audio-device`: `sounddevice` の入力デバイス番号。省略時は OS の既定デバイス（VB-Cable を推奨）
- `--segment-seconds`: 録音チャンク長。短くすると遅延は減るが CPU 負荷は増える
- `--port`: Web UI のポート番号（デフォルト 5000）

## 使い方

1. 上記のコマンドでサーバーを起動
2. ブラウザで `http://127.0.0.1:5000/` （または指定ポート）を開く
3. VB-Cable に流れている音声が自動的に英語に翻訳されて表示されます

## メモ

- モデルは `faster-whisper` の **tiny** を使用
- 翻訳タスク (`task="translate"`) を使って常に英語に翻訳
- 精度よりも軽さ・リアルタイム性を優先した設定です
