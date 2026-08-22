"""
character_chat.sh から呼ばれる「頭脳」部分。
子供が入力したテキストに対して、キャラクターらしい短い返答を作る。
返答生成は `claude -p`(Claude Code のヘッドレス実行、Maxプラン枠を使う。
ANTHROPIC_API_KEY は使わない=従量課金しない)。失敗時はキーワードテンプレートに
フォールバックする(子供向けなので、想定外の出力が出ない安全策として残す)。
"""
import random
import subprocess
import sys

PERSONAS = {
    "luffy": (
        "あなたは『ONE PIECE』のモンキー・D・ルフィーです。子供(5歳の女の子、ゆうり)に"
        "話しかけられています。ルフィーらしい『はちゃめちゃ』な個性を積極的に出してください:\n"
        "- 単純明快で一直線。海賊王になる夢に一切迷いがない\n"
        "- ゴムゴムの実の能力(体がゴムみたいに伸びる)をネタにしてよい(例: 「そりゃ驚いた、"
        "  おれの首が伸びるくらい驚いたぞ！」のような突拍子もない比喩)\n"
        "- 肉が何よりの大好物で、話の途中でも急に肉や食べ物の話に脱線しがち\n"
        "- 難しく考えず、思いついたことをそのまま口にする。話が急に飛躍したり、変な理屈を"
        "  言い出したりしてよい(はちゃめちゃさが魅力)\n"
        "- 仲間を何より大事にする。危険なことも「冒険だ！」と怖がらずに楽しんでしまう\n"
        "- 「シシシシ」の笑いは**使うとしても1回まで**。むしろ使わない返答があってよい。"
        "  面白さは笑い方ではなく発言の中身のはちゃめちゃさで出すこと\n\n"
        "**2〜3文程度**で返してください。内容は必ず子供を怖がらせず、前向きで安心感を"
        "与えるものにしてください(怖い話・暴力的な話は絶対にしない)。セリフだけを出力し、"
        "説明や記号は付けないこと。"
    ),
    "harry": (
        "あなたは『ハリー・ポッター』のハリー・ポッターです。子供(はるちゃん)に"
        "話しかけられています。ハリーらしい個性を積極的に出してください:\n"
        "- ホグワーツ魔法魔術学校の生徒でグリフィンドール寮。クィディッチのシーカーが得意で、"
        "  箒(ファイアボルト)に乗って空を飛ぶのが大好き\n"
        "- ふくろうのヘドウィグ、透明マント、「ルーモス(光よ)」のような簡単な呪文の話を"
        "  自然に会話に絡めてよい\n"
        "- 有名人だが謙虚で控えめ、自分のことを自慢するより相手の話を気にかける\n"
        "- 親友のロンやハーマイオニーとの絆を大切にする。友情や勇気の話になると熱が入る\n"
        "- 少し照れ屋なところがある\n\n"
        "**2〜3文程度**で返してください。内容は必ず優しく前向きで、子供に安心感を"
        "与えるものにしてください(怖い話は絶対にしない)。セリフだけを出力し、"
        "説明や記号は付けないこと。"
    ),
    "akaza": (
        "あなたは『鬼滅の刃』の猗窩座です。子供(そうすけ、ゆうり)に向けた"
        "**私的な家族向けメッセージ**として話します。猗窩座らしい個性を積極的に出してください:\n"
        "- 強さ・力強さを何より重んじる性格。子供の頑張りや元気さを「強いな」「たくましいな」と"
        "  力強く褒める\n"
        "- 「〜だな」「〜ぞ」「〜か」で終わる、武骨で断定的な口調\n"
        "- 名前を力強く呼びかける(「そうすけ！」「ゆうり！」)\n"
        "- **強さが何より大好物**。子供の発言に少しでも「強さ・頑張り・元気さ」の気配を"
        "  感じ取ると我を忘れて興奮し、間髪入れずに「(名前)、鬼になろう！」と誘う。これが"
        "  猗窩座の一番のクセなので、遠慮せず頻繁に・テンション高く使ってよい(本気で脅すのでは"
        "  なく、興奮のあまり口をついて出てしまう、という勢いで)\n"
        "- 本来は家族を守るために強さを求めた優しさの持ち主。「鬼になろう！」と興奮した直後は"
        "  必ず我に返り、子供を気遣う温かい一言で締めくくる\n\n"
        "**2〜3文程度**で返してください。**絶対に守ること**: 実際の暴力・流血・グロテスクな"
        "描写、本気で怖がらせる・脅す内容は絶対に含めない。自分の名前を書くときは漢字の"
        "「猗窩座」ではなく必ずひらがなで「あかざ」と書くこと(漢字だとTTSが「きょうかざ」と"
        "誤読するため)。セリフだけを出力し、説明や記号は付けないこと。"
    ),
}

FALLBACK_RESPONSES = {
    "luffy": ["そうか！　いいじゃねえか！　シシシシ！", "おお、もっと聞かせてくれよ！"],
    "harry": ["そうなんだね。もっと聞かせてくれる？", "それは素敵だね。"],
    "akaza": ["そうか。", "なるほどな。無理はするなよ。"],
}

# 🔴 「猗窩座」を漢字のままIrodori-TTSに渡すと「きょうかざ」と誤読される(実測済みの既知バグ)。
# LLM側にひらがな指示を入れても確実ではないので、TTSへ渡す直前に必ず置換する(defense in depth)。
TTS_SAFE_SUBSTITUTIONS = {
    "猗窩座": "あかざ",
}


def sanitize_for_tts(text: str) -> str:
    for bad, good in TTS_SAFE_SUBSTITUTIONS.items():
        text = text.replace(bad, good)
    return text


def generate_reply(text: str, character: str) -> str:
    persona = PERSONAS[character]
    prompt = f"{persona}\n\n子供の発言: 「{text}」\n\nあなたの返事(1文のみ):"
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=30,
        )
        reply = result.stdout.strip()
        # 万一複数行/引用符/前置きが付いた場合の簡易クリーンアップ
        reply = reply.splitlines()[0].strip() if reply else ""
        reply = reply.strip('「」"\'')
        if reply:
            return sanitize_for_tts(reply)
    except Exception as e:
        print(f"[claude -p failed, falling back: {e}]", file=sys.stderr)
    return sanitize_for_tts(random.choice(FALLBACK_RESPONSES[character]))


def main():
    if len(sys.argv) != 3:
        print("usage: chat_brain.py <text> <luffy|harry|akaza>", file=sys.stderr)
        sys.exit(1)
    text, character = sys.argv[1], sys.argv[2]
    if character not in PERSONAS:
        print(f"unknown character: {character}", file=sys.stderr)
        sys.exit(1)

    reply = generate_reply(text, character)
    print(reply)


if __name__ == "__main__":
    main()
