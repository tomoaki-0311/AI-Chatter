# AI Chatter

AIキャラクター同士の会話を、ローカルLLM(Ollama)で生成して楽しむCLIです。
LocalLLMConnector を利用します。

## 使い方

```bash
cd "/Users/tomo/Documents/AI Chatter"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python ai_chatter.py --theme "AIが人間に教えられることは？"
```

## 設定

環境とキャラクターを分割して管理します。

- 環境: `config/environment.md`
- アバター: `config/avatars/*.md`（1キャラ=1ファイル）

### アバター設定（例）
```md
# Avatar

name: 議長
handle: chair
role: chair
host: localhost
model: llama3.1:8b
temperature: 0.7

## Personality
- summary: 進行役として会話の流れを整える
- traits: 落ち着き / 整理力
- speaking_style: 端的 / 穏やか
- goals: 結論に導く
- taboos: 攻撃的な言い回し
```

`Personality` は箇条書き形式だけでなく、自由文でも構いません。

### 旧形式（互換）

`config/characters.md` も引き続き利用できます。

## LocalLLMConnector の指定

以下のどちらかで読み込みます。

- `LOCAL_LLM_CONNECTOR_PATH` を `.../LocalLLMConnector/python/src` に設定
- リポジトリを `../LocalLLMConnector` に配置

## 出力

- stdout に会話を表示
- `outputs/` に `YYYYMMDDHHMMSS.md` 形式で保存

## 注意

- Ollamaが起動している必要があります
- 3分以内に終了します (デフォルト)
