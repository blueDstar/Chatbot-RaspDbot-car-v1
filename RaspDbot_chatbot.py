import os
import sys
from llama_cpp import Llama

MODEL_PATH = r"/home/dmachine/Documents/RaspDbot/raspdbot-car.Q4_K_M.gguf"

SYSTEM_PROMPT = (
    "Bạn là trợ lý kỹ thuật cho xe tự hành RaspDbot-Car. "
    "Trả lời ngắn gọn, đúng trọng tâm, có thể dùng gạch đầu dòng. "
    "Nếu thiếu dữ liệu thì nói rõ và gợi ý cần thông tin gì."
)

def build_prompt(history: list[dict]) -> str:
    # Prompt kiểu chat đơn giản, hợp với đa số model chat GGUF
    # Bạn có thể thay format nếu model của bạn dùng template khác.
    parts = [f"### System:\n{SYSTEM_PROMPT}\n"]
    for m in history:
        role = m["role"]
        content = m["content"]
        if role == "user":
            parts.append(f"### User:\n{content}\n")
        else:
            parts.append(f"### Assistant:\n{content}\n")
    parts.append("### Assistant:\n")
    return "\n".join(parts)

def main():
    if not os.path.exists(MODEL_PATH):
        print(f"Không tìm thấy model: {MODEL_PATH}")
        sys.exit(1)

    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=4096,      # tăng/giảm tùy RAM
        n_threads=os.cpu_count() or 4,
        n_gpu_layers=0,  # 0 = chạy CPU; nếu có GPU + build CUDA thì tăng lên
        verbose=False
    )

    history: list[dict] = []
    print("🤖 RaspDbot-Star Chat (gõ 'exit' để thoát)\n")

    while True:
        user_text = input("Bạn: ").strip()
        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit", "q"):
            break

        history.append({"role": "user", "content": user_text})
        prompt = build_prompt(history)

        # Sinh câu trả lời
        out = llm(
            prompt,
            max_tokens=256,
            temperature=0.7,
            top_p=0.9,
            stop=["### User:", "### System:", "### Assistant:"],
        )

        answer = out["choices"][0]["text"].strip()
        if not answer:
            answer = "(Không sinh được câu trả lời — thử tăng max_tokens hoặc đổi prompt template.)"

        print(f"\nBot: {answer}\n")
        history.append({"role": "assistant", "content": answer})

if __name__ == "__main__":
    main()
