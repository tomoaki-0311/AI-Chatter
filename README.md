# AI Chatter

AIキャラクター同士の会話を、ローカルLLM(Ollama)で生成して楽しむCLIです。

## 使い方

```bash
cd "/Users/tomo/Documents/AI Chatter"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python ai_chatter.py --theme "AIが人間に教えられることは？"
```

## 設定

`config/characters.md` に環境とキャラクターを定義します。

- `# Environment` 配下: 会話の環境設定
- `# Characters` 配下: キャラクターごとに `host` / `model` / `personality` を指定

Ollamaのホストやモデルはキャラクターごとに変えられます。

## 出力

- stdout に会話を表示
- `outputs/` に `YYYYMMDDHHMMSS.md` 形式で保存

## 注意

- Ollamaが起動している必要があります
- 3分以内に終了します (デフォルト)
