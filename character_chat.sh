#!/bin/zsh
# ルフィー/ハリー/猗窩座とのターン制会話(テキスト入力→キャラクターの声で返答)。
# 使い方: ./character_chat.sh luffy | harry | akaza
set -e
cd "$(dirname "$0")"

CHARACTER="$1"
case "$CHARACTER" in
  luffy)
    REF="character_refs/luffy.wav"
    CAPTION="元気いっぱいで明るく少し粗野だが人懐っこい少年のような男性の声。よく笑う。大声で無邪気に話す。"
    ;;
  harry)
    REF="character_refs/harry.wav"
    CAPTION="優しく親しみやすい、少年のような温かい男性の声。落ち着いていて、子供に語りかけるように話す。"
    ;;
  akaza)
    REF="character_refs/akaza.wav"
    CAPTION="少し武骨でぶっきらぼうだが、根は優しい保護者のような男性の声。落ち着いた低めの声。"
    ;;
  *)
    echo "使い方: ./character_chat.sh luffy | harry | akaza"
    exit 1
    ;;
esac

WORKDIR="/tmp/character_chat_$$"
mkdir -p "$WORKDIR"
trap 'rm -rf "$WORKDIR"' EXIT

echo "=== $CHARACTER と話そう！ テキストを入力してEnter(終わるときは何も入力せずEnter) ==="

turn=0
while true; do
  turn=$((turn + 1))
  echo ""
  printf "あなた: "
  read -r INPUT

  if [[ -z "$INPUT" ]]; then
    echo "またね！"
    break
  fi

  echo "（考え中...）"
  # 🔴 ループ内のサブプロセスがstdinを横取りすると次のreadがEOF扱いで死ぬ(set -eで即終了)。
  # 全サブプロセスは明示的に < /dev/null で標準入力を切り離す。
  REPLY=$(uv run --no-sync python chat_brain.py "$INPUT" "$CHARACTER" < /dev/null)
  echo "$CHARACTER: $REPLY"

  REPLY_WAV="$WORKDIR/reply_${turn}.wav"
  uv run --no-sync python infer.py \
    --checkpoint local_ckpt/model.safetensors \
    --text "$REPLY" \
    --ref-wav "$REF" \
    --caption "$CAPTION" \
    --cfg-scale-speaker 1.0 --cfg-scale-text 3.0 --cfg-guidance-mode independent \
    --model-device mps --codec-device mps --num-steps 40 --seed 333 \
    --output-wav "$REPLY_WAV" < /dev/null > /dev/null 2>&1

  afplay "$REPLY_WAV" < /dev/null
done
