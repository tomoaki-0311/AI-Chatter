#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests

MENTION_RE = re.compile(r"@([A-Za-z0-9_\-]+)")


@dataclass
class Character:
    name: str
    handle: str
    host: str
    model: str
    temperature: float
    personality: str
    role: str = ""


@dataclass
class Message:
    speaker: str
    handle: str
    text: str


class ConfigError(Exception):
    pass


def slugify_handle(name: str) -> str:
    slug = re.sub(r"\W+", "_", name.strip())
    slug = slug.strip("_").lower()
    return slug or "speaker"


def parse_markdown_config(path: str) -> Tuple[str, List[Character]]:
    if not os.path.exists(path):
        raise ConfigError(f"config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    mode = None
    env_lines: List[str] = []
    characters: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip("\n")

        if line.startswith("# "):
            title = line[2:].strip().lower()
            if title == "environment":
                mode = "env"
            elif title == "characters":
                mode = "chars"
            else:
                mode = None
            i += 1
            continue

        if line.startswith("## ") and mode == "chars":
            if current:
                characters.append(current)
            current = {"name": line[3:].strip()}
            i += 1
            continue

        if mode == "env":
            if line.strip() != "":
                env_lines.append(line)
            i += 1
            continue

        if mode == "chars" and current is not None and line.strip().startswith("-"):
            entry = line.strip()[2:]
            if ":" not in entry:
                i += 1
                continue
            key, value = entry.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "|":
                i += 1
                collected: List[str] = []
                while i < len(lines):
                    next_line = lines[i].rstrip("\n")
                    if next_line.startswith("    "):
                        collected.append(next_line[4:])
                        i += 1
                        continue
                    if next_line.strip() == "":
                        collected.append("")
                        i += 1
                        continue
                    break
                current[key] = "\n".join(collected).strip()
                continue
            current[key] = value
            i += 1
            continue

        i += 1

    if current:
        characters.append(current)

    environment = "\n".join(env_lines).strip()
    if not environment:
        raise ConfigError("Environment section is empty")

    parsed: List[Character] = []
    for raw_char in characters:
        name = raw_char.get("name")
        if not name:
            continue
        handle = raw_char.get("handle") or slugify_handle(name)
        host = raw_char.get("host")
        model = raw_char.get("model")
        personality = raw_char.get("personality")
        if not host or not model or not personality:
            raise ConfigError(f"Character {name} missing host/model/personality")
        temperature = float(raw_char.get("temperature", "0.7"))
        role = raw_char.get("role", "")
        parsed.append(
            Character(
                name=name,
                handle=handle,
                host=host,
                model=model,
                temperature=temperature,
                personality=personality,
                role=role,
            )
        )

    if not parsed:
        raise ConfigError("No characters defined")

    return environment, parsed


def choose_chair(characters: List[Character]) -> Character:
    for c in characters:
        if c.role.lower() == "chair":
            return c
    for c in characters:
        if c.handle.lower() == "chair" or "議長" in c.name:
            return c
    return characters[0]


def format_transcript(history: List[Message]) -> str:
    lines = []
    for msg in history:
        lines.append(f"{msg.speaker}(@{msg.handle}): {msg.text}")
    return "\n".join(lines)


def build_system_prompt(
    character: Character,
    environment: str,
    theme: str,
    handles: List[str],
) -> str:
    handles_str = ", ".join([f"@{h}" for h in handles])
    return (
        "あなたは会話に参加するAIキャラクターです。\n"
        f"名前: {character.name}\n"
        f"ハンドル: @{character.handle}\n"
        f"性格: {character.personality}\n"
        f"環境: {environment}\n"
        "会話ルール:\n"
        "- 感情の温度を保ち、必要以上に冷静にならない。\n"
        "- 会話の流れに沿い、自然な口調で話す。\n"
        "- 他のキャラクターに呼びかける時は @handle を使う。\n"
        f"- テーマ: {theme}\n"
        f"- 使えるメンション: {handles_str}\n"
        "出力はセリフのみ。話者名や記号は付けない。"
    )


def call_ollama(character: Character, system_prompt: str, transcript: str) -> str:
    payload = {
        "model": character.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "以下がこれまでの会話ログです。流れに沿って発言してください。\n"
                    + transcript
                ),
            },
        ],
        "options": {"temperature": character.temperature},
        "stream": False,
    }
    url = character.host.rstrip("/") + "/api/chat"
    resp = requests.post(url, json=payload, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    return data.get("message", {}).get("content", "").strip()


def detect_mentions(text: str, handles: List[str]) -> List[str]:
    found = []
    for handle in MENTION_RE.findall(text):
        if handle in handles:
            found.append(handle)
    return found


def choose_next_speaker(
    characters: List[Character],
    last_handle: Optional[str],
    forced: Optional[str],
) -> Character:
    if forced:
        for c in characters:
            if c.handle == forced:
                return c
    candidates = [c for c in characters if c.handle != last_handle]
    if not candidates:
        candidates = characters
    return random.choice(candidates)


def chair_prompt(chair: Character, target: Character) -> str:
    return f"@{target.handle} どう思う？"


def should_end_conversation(history: List[Message]) -> bool:
    if len(history) < 4:
        return False
    tail = "\n".join(m.text for m in history[-3:])
    end_signals = ["結論", "まとめ", "以上", "終わり", "もう言うことはない", "締める"]
    if any(sig in tail for sig in end_signals) and "@" not in tail:
        return True
    return False


def run_conversation(
    environment: str,
    characters: List[Character],
    theme: str,
    max_seconds: int,
) -> List[Message]:
    history: List[Message] = []
    chair = choose_chair(characters)

    opening = f"本日のテーマは「{theme}」です。"
    history.append(Message(chair.name, chair.handle, opening))

    start = time.time()
    last_handle: Optional[str] = chair.handle
    forced_next: Optional[str] = None

    while time.time() - start < max_seconds:
        handles = [c.handle for c in characters]
        speaker = choose_next_speaker(characters, last_handle, forced_next)
        forced_next = None

        transcript = format_transcript(history)
        system_prompt = build_system_prompt(speaker, environment, theme, handles)

        try:
            response = call_ollama(speaker, system_prompt, transcript)
        except Exception as exc:
            response = ""
            history.append(
                Message(
                    chair.name,
                    chair.handle,
                    f"今の発言取得で問題があったよ。{speaker.name}はあとで話してね。",
                )
            )
            last_handle = chair.handle
            continue

        if not response or len(response.strip()) < 2:
            target = random.choice([c for c in characters if c.handle != chair.handle])
            prompt = chair_prompt(chair, target)
            history.append(Message(chair.name, chair.handle, prompt))
            last_handle = chair.handle
            forced_next = target.handle
            continue

        history.append(Message(speaker.name, speaker.handle, response))
        last_handle = speaker.handle

        mentions = detect_mentions(response, handles)
        if mentions:
            forced_next = mentions[0]

        if should_end_conversation(history):
            break

    return history


def write_output(history: List[Message], environment: str, theme: str) -> str:
    os.makedirs("outputs", exist_ok=True)
    now = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    path = os.path.join("outputs", f"{now}.md")

    lines = [
        f"# テーマ\n\n{theme}\n",
        f"# 環境\n\n{environment}\n",
        "# 会話\n",
    ]
    for msg in history:
        lines.append(f"- **{msg.speaker}** (@{msg.handle}): {msg.text}")

    content = "\n".join(lines).strip() + "\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


def print_history(history: List[Message]) -> None:
    for msg in history:
        print(f"{msg.speaker} (@{msg.handle}): {msg.text}")


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Chatter (Ollama local LLM)")
    parser.add_argument("--config", default="config/characters.md", help="config markdown path")
    parser.add_argument("--theme", required=True, help="conversation theme")
    parser.add_argument("--max-seconds", type=int, default=180, help="max duration in seconds")
    args = parser.parse_args()

    try:
        environment, characters = parse_markdown_config(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 1

    history = run_conversation(environment, characters, args.theme, args.max_seconds)

    print_history(history)
    output_path = write_output(history, environment, args.theme)
    print(f"\n[output] {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
