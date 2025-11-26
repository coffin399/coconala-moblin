# moblin-smart-translation

PC 全体（既定のスピーカー出力）から拾った **日本語音声** をデフォルトでキャプチャし、

- 日本語特化 Whisper モデル **RoachLin/kotoba-whisper-v2.2-faster** で文字起こし（ASR）し、
- オフラインの **CTranslate2 + SentencePiece (entai2965/sugoi-v4-ja-en-ctranslate2)** で **ja→en 翻訳** し、
- Web ブラウザ経由で字幕表示・OBS に重ねる

ためのローカルアプリです。

- デフォルトは **CPU モード**（配信 PC の安定性優先）
- オプションで **GPU モード (CUDA)** も利用可能
- GPU 利用は `MST_ENABLE_CUDA=1` が設定されている場合だけ有効
- CUDA 初期化に失敗しても **自動で CPU にフォールバック** し、アプリは止まらない
- Windows（WASAPI ループバック対応）前提
- UI は Web ベース（`/settings` と `/display` の 2 画面）

字幕表示は **常に最大 3 行固定** で、
新しいテキストが下から出て古い行が上に流れていくレイアウトになっています。

---

## 主な機能

- **日本語 → 英語 翻訳字幕**（ASR: kotoba-whisper, 翻訳: Sugoi v4 ja→en）
- **3 行固定の字幕表示**（論理行バッファも 3 行にトリム）
- **Web UI からの制御**
  - 音声入力デバイス選択 + 更新
  - ワーカー（音声→翻訳処理）の Start / Stop
  - モード選択: `翻訳 (ja→en)` / `文字起こし (ja)`
  - 言語選択（将来拡張に備えた UI）
  - 品質プリセット: `ultra_low` / `low` / `normal` / `high` / `ultra_high`
  - デバイスモード: `CPU` / `GPU (CUDA)`
  - テキストクリアボタン（即座に字幕を消す）
  - イベントログ（モード変更・ワーカー開始/停止などを表示）
- **無音区間のノイズ抑制**
  - 非常に小さい音量のブロックは「無音」と見なしてスキップ
  - 「I'm sorry」などの不要な誤訳が出にくいように調整
- **VAD 無効化による連続性の改善**
  - 短い無音で認識が途切れないよう、常にチャンク単位で ASR を実行
- **CUDA 利用の安全ゲート**
  - `device=cuda` を指定しても、`MST_ENABLE_CUDA=1` が無ければ **CPU 強制**
  - CUDA 初期化エラー時は自動フォールバック＆警告ログのみ

---

## セットアップ

1. **Python 3.11** をインストール（`py -3.11 --version` が通る状態）
2. このプロジェクトを任意のフォルダに展開
3. Windows の「サウンド」設定で、通常利用しているスピーカー（既定の再生デバイス）が有効になっていることを確認

特別な仮想オーディオデバイスを用意しなくても、**PC 全体の再生音（既定のスピーカーに出ている音）** をそのままキャプチャして字幕化できます。

より高度なルーティング（特定アプリだけを別デバイスに流したい等）が必要な場合は、VB-Cable などの仮想デバイスを併用し、OS 側で出力先を切り替える運用も可能です（後述の「オーディオルーティングのヒント」を参照）。

必要に応じて `sounddevice` のデバイス一覧を確認できます:

```bash
python -m sounddevice
```

---

## かんたん起動（start.bat 推奨）

プロジェクトフォルダ直下で `start.bat` を実行すると、以下を自動で行います。

1. `.venv` を Python 3.11 で作成 or 再利用
2. `pip install -r requirements.txt` で依存インストール
3. サーバー起動（デフォルトは CPU モード + 適切な品質プリセット）

実行後、数秒するとブラウザが自動で開き、次の URL に遷移します。

```text
http://127.0.0.1:5000/settings
```

サーバー停止は、`start.bat` を開いているコンソールで `Ctrl + C` です。

---

## CUDA (GPU) を使いたい場合

1. 対応する **NVIDIA GPU + ドライバ + CUDA + cuDNN** をセットアップ
2. プロジェクト直下の `check_cuda.bat` を実行し、
   - `PASS` になれば CUDA 利用の準備は概ね OK
3. 環境変数 `MST_ENABLE_CUDA=1` を設定した状態で `start.bat` を実行
4. Web UI `/settings` の「デバイスモード」で **GPU (CUDA)** を選択

起動時のコンソールに、例えば次のように表示されれば GPU で動作しています。

```text
[model] creating kotoba-whisper-v2.2-faster model_id='RoachLin/kotoba-whisper-v2.2-faster' device='cuda' compute_type='int8_float16' ...
```

もし CUDA 初期化に失敗した場合は、アプリは次のような警告を出しつつ **自動で CPU にフォールバック** します。

```text
[model warning] CUDA initialisation failed (...); falling back to CPU (int8).
[model] retrying on device='cpu' compute_type='int8'
```

この場合でもアプリ自体は動き続けますが、処理は CPU モードと同等の速度になります。

GPU を使わない運用にする場合は、単に `MST_ENABLE_CUDA` を設定せず、
Web UI 側でも **CPU モード** を選んでください。

---

## Web UI の構成

サーバー起動後、ブラウザで次の URL にアクセスします。

```text
http://127.0.0.1:5000/settings
```

モダンなダークUIの **設定画面 + ライブプレビュー** が表示されます。

### /settings — 設定 & プレビュータブ

主な設定項目:

- **テキストスタイル**
  - フォントファミリー（System / Sans / Serif / Monospace）
  - フォントサイズ（px）
  - 行間（line-height）
  - 文字揃え（左 / 中央 / 右）
  - 文字色
  - ドロップシャドウ有無
  - 背景モード（Transparent / Dark blur / Solid dark）
  - 余白（padding）
- **動作モード**
  - 入力デバイス選択（将来的な拡張や上級者向けルーティング用。現時点では「既定のデバイスを使用」で PC 全体の音声を拾う運用を推奨）
  - デバイスモード: `CPU` / `GPU (CUDA)`
  - 品質プリセット: `ultra_low` / `low` / `normal` / `high` / `ultra_high`
  - モード: `翻訳 (ja→en)` / `文字起こし (ja)`
  - （将来拡張用）言語選択
- **制御**
  - ワーカー Start / Stop ボタン
  - テキストをクリア（バックエンドのバッファもクリア）
  - イベントログ（右下）に状態変更やエラーを表示

右側の「ライブプレビュー」は、現在の `/transcript` の内容をポーリングしつつ、
上記スタイルを反映した表示をリアルタイムに確認できます。

ヘッダー右上のリンク:

- `出力タブを開く` … `/display` を新しいタブで開き、OBS 用の本番表示を確認

設定はブラウザの LocalStorage に保存され、`/display` 側でも同じ設定が使われます。

### /display — テキスト出力タブ（OBS 向け）

`/settings` で保存された設定を読み込み、
実際に OBS などに重ねる **字幕出力専用ページ** です。

URL 例:

```text
http://127.0.0.1:5000/display
```

特徴:

- 背景は透明 or 半透明ダーク（`/settings` で指定）
- 画面下部に **常に最大 3 行だけ** を表示
  - バックエンドも常に直近 3 行のみ保存
  - 長い 1 行は自動でスロットに分割され、物理 3 行以内に収まるよう調整
- `/transcript` を数百 ms 間隔でポーリングし、最新テキストを表示
- テキストは下から積み上がり、古い行は上に流れて消えるような見た目

---

## OBS との連携

OBS では「ブラウザ」ソースとして `/display` を読み込むことで、
字幕レイヤーとして画面に重ねられます。

1. OBS で **ソースを追加 → 「ブラウザ」** を選択
2. URL に `http://127.0.0.1:5000/display` を指定
3. 幅・高さを配信解像度に合わせる（例: 1920x1080）
4. `/settings` でフォントや背景、位置を調整
5. 必要に応じて OBS 側でクロップや位置合わせを行う

これで、PC で再生されている音声（既定のスピーカー出力） → kotoba-whisper で日本語文字起こし →
ja→en 翻訳 → `/display` → OBS のブラウザソース、という流れで
英語字幕を配信に重ねられます。

---

## オーディオルーティングのヒント

### 基本構成（シンプル / 初心者向け）

- Windows の **既定の再生デバイス（スピーカー）** に、配信やゲーム、ブラウザなどの音をそのまま出す
- 本アプリは WASAPI ループバックで、その既定スピーカーの音声を PC 全体としてキャプチャ
- OBS ではブラウザソースで `/display` を重ねる

これにより、

```text
PC 上の音声（ゲーム / ブラウザ / 音楽 等） → 既定のスピーカー → moblin-smart-translation（PC 全体キャプチャ） → OBS の字幕レイヤー
```

というルーティングになり、特別な仮想デバイスなしに「聞こえている音」をそのまま字幕化できます。

### VB-Cable などを使った高度な構成（任意）

特定のアプリだけを分離したい場合や、ボイチェンチェーンをきれいに分けたい場合は、VB-Cable 等の仮想デバイスを併用します。

例:

- moblin などボイチェン・エフェクタの出力先を VB-Cable にする
- OBS で VB-Cable をマイク入力として取り込む
- 必要に応じて、Windows 側の「アプリごとの音量とデバイス設定」から、特定アプリの出力先を VB-Cable に切り替える

このアプリ側では、将来的に入力デバイス選択を使ってこうした仮想デバイスを指定することで、PC 全体ではなく特定デバイス経由の音だけを拾う構成も想定しています。

---

## 直接起動（CLI オプション・上級者向け）

通常は `start.bat` + Web UI だけで運用できますが、
自前の仮想環境などで直接 Flask アプリを起動することもできます。

```bash
pip install -r requirements.txt

python app.py --device cpu --quality normal
```

主なオプション:

- `--device`: `cpu` または `cuda`。省略時は `cpu`
- `--audio-device`: `sounddevice` の入力デバイス番号
- `--segment-seconds`: 録音チャンク長（秒）。短くすると遅延は減るが CPU/GPU 負荷は増える
- `--quality`: `ultra_low` / `low` / `normal` / `high` / `ultra_high`
- `--host` / `--port`: Web UI のバインド先

CLI で指定した値は初期値として使われますが、
実際のワーカー起動やモード・品質・デバイスモードの切り替えは、
基本的に **Web UI の `/settings` から行う** 想定です。

---

## 備考

- ASR: `RoachLin/kotoba-whisper-v2.2-faster`（CTranslate2 版 Whisper）
- 翻訳: `entai2965/sugoi-v4-ja-en-ctranslate2` + SentencePiece
- 翻訳は完全オフラインで動作（API キー不要）
- できるだけ **低レイテンシ・安定動作** を優先した構成です。
