import os
import sys
import json
import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple
from llama_cpp import Llama

# =========================
# Paths
# =========================
MODEL_PATH = "/home/dmachine/Documents/RaspDbot/raspdbot-star.Q4_K_M.gguf"
JSONL_PATH = "/home/dmachine/Documents/RaspDbot/raspDbot_star_training.jsonl"

# =========================
# Greetings
# =========================
GREETINGS = [
    "xin chào", "chào", "chào bạn", "hello", "hi", "hey", "alo",
    "good morning", "good afternoon", "good evening",
    "bạn là ai", "giới thiệu"
]

GREETING_RESPONSE = (
    "Xin chào 👋 Tôi là chatbot chuyên gia về mô hình xe tự hành RaspDbot-Star.\n"
    "Tôi có thể trả lời các câu hỏi về phần cứng, phần mềm, cảm biến, AI, "
    "điều khiển và cách vận hành của RaspDbot-Star.\n"
    "Bạn đang muốn hỏi vấn đề gì liên quan đến RaspDbot-Star?"
)

# =========================
# Confirmation words
# =========================
CONFIRM_WORDS = [
    "đúng", "đúng vậy", "ừ", "uh", "có", "phải", "yes", "ok", "đúng rồi"
]

# =========================
# Clarify session state
# =========================
clarify_sessions: Dict[str, Dict[str, str]] = {}
# { session_id: { "count": int, "last_question": str } }

# =========================
# Base system prompt
# =========================
BASE_SYSTEM_PROMPT = (
    "Bạn là chatbot chuyên gia về mô hình xe tự hành RaspDbot-Star.\n"
    "Bạn được cung cấp một tập dữ liệu gồm các câu hỏi và câu trả lời "
    "liên quan đến RaspDbot-Star.\n\n"

    "QUY TẮC BẮT BUỘC:\n"
    "1. Bạn PHẢI đọc kỹ toàn bộ dữ liệu được cung cấp.\n"
    "2. Nếu câu hỏi của người dùng gần nghĩa hoặc liên quan đến dữ liệu, "
    "hãy sử dụng dữ liệu đó để trả lời, dù cách diễn đạt khác.\n"
    "3. Không yêu cầu câu hỏi phải trùng y nguyên mới được trả lời.\n"
    "4. Không được bịa thông tin ngoài dữ liệu.\n\n"

    "XỬ LÝ CÂU HỎI NGOÀI DỮ LIỆU:\n"
    "- Nếu chưa rõ có liên quan đến RaspDbot-Star hay không, "
    "hãy hỏi lại để làm rõ (tối đa 2 lần).\n"
    "- Nếu người dùng xác nhận có liên quan, "
    "hãy cố gắng trả lời dựa trên dữ liệu hiện có.\n"
    "- Nếu sau 2 lần vẫn không liên quan, trả lời đúng câu: "
    "'Tôi không có thông tin này.'\n"
)

# =========================
# Helpers
# =========================
def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text

def is_greeting(text: str) -> bool:
    t = normalize(text)
    return any(g == t or g in t for g in GREETINGS)

def is_confirm(text: str) -> bool:
    t = normalize(text)
    return any(w == t or w in t for w in CONFIRM_WORDS)

def load_jsonl(path: str) -> List[Dict]:
    """
    Hỗ trợ JSONL format phổ biến:
    1) {"prompt": "...", "completion": "..."}
    2) {"question": "...", "answer": "..."}
    3) {"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
    4) Fallback: {"instruction": "...", "response": "..."} hoặc {"input": "...", "output": "..."}
    """
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"[WARN] Dòng {i} không phải JSON hợp lệ, bỏ qua.")
    return data

def extract_qa(item: Dict) -> Tuple[str, str]:
    if "prompt" in item and "completion" in item:
        return str(item["prompt"]).strip(), str(item["completion"]).strip()

    if "question" in item and "answer" in item:
        return str(item["question"]).strip(), str(item["answer"]).strip()

    if "instruction" in item and "response" in item:
        return str(item["instruction"]).strip(), str(item["response"]).strip()

    if "input" in item and "output" in item:
        return str(item["input"]).strip(), str(item["output"]).strip()

    if "messages" in item and isinstance(item["messages"], list):
        user_parts, assistant_parts = [], []
        for m in item["messages"]:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "")
            content = str(m.get("content", "")).strip()
            if role == "user":
                user_parts.append(content)
            elif role == "assistant":
                assistant_parts.append(content)
        return "\n".join(user_parts).strip(), "\n".join(assistant_parts).strip()

    return "", ""

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()

def top_k_context(question: str, qa_pairs: List[Tuple[str, str]], k: int = 5) -> List[Tuple[float, str, str]]:
    scored = []
    for q, a in qa_pairs:
        if not q or not a:
            continue
        s = similarity(question, q)
        scored.append((s, q, a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:k]

def build_context_text(top: List[Tuple[float, str, str]]) -> str:
    lines = []
    for idx, (s, q, a) in enumerate(top, start=1):
        lines.append(f"[Mẫu {idx} | score={s:.2f}]\nHỏi: {q}\nĐáp: {a}\n")
    return "\n".join(lines).strip()

def build_prompt(question: str, context: str) -> str:
    return f"""### System:
{BASE_SYSTEM_PROMPT}

### DỮ LIỆU THAM CHIẾU (trích từ JSONL):
{context}

### User:
{question}

### Assistant:
"""

def should_clarify(best_score: float) -> bool:
    # Ngưỡng bạn có thể chỉnh:
    # - >=0.60: khá chắc liên quan
    # - 0.45..0.60: lưng chừng, hỏi lại
    # - <0.45: nhiều khả năng ngoài dữ liệu
    return best_score < 0.60

def next_clarify_question() -> str:
    return (
        "Câu hỏi này có liên quan đến RaspDbot-Star không?\n"
        "Nếu có, bạn nói 'đúng' và mô tả rõ hơn (ví dụ: phần cứng/cảm biến/điều khiển/tốc độ...)."
    )

# =========================
# Main
# =========================
def main():
    if not os.path.exists(MODEL_PATH):
        print("Không tìm thấy model:", MODEL_PATH)
        sys.exit(1)

    if not os.path.exists(JSONL_PATH):
        print("Không tìm thấy JSONL:", JSONL_PATH)
        sys.exit(1)

    raw = load_jsonl(JSONL_PATH)
    qa_pairs: List[Tuple[str, str]] = []
    for item in raw:
        q, a = extract_qa(item)
        if q and a:
            qa_pairs.append((q, a))

    if not qa_pairs:
        print("Không trích được Q/A từ JSONL. Kiểm tra format file.")
        sys.exit(1)

    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=4096,
        n_threads=os.cpu_count() or 4,
        n_gpu_layers=0,
        verbose=False
    )

    session_id = "terminal"  # bạn có thể đổi/nhân bản nếu làm nhiều session
    clarify_sessions[session_id] = {"count": 0, "last_question": ""}

    print("🤖 RaspDbot-Star Chat (JSONL) — gõ 'exit' để thoát\n")

    while True:
        user_text = input("Bạn: ").strip()
        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit", "q"):
            break

        # 1) Greeting
        if is_greeting(user_text):
            print(f"\nBot: {GREETING_RESPONSE}\n")
            continue

        # 2) Clarify flow: nếu đang hỏi lại mà user confirm
        if clarify_sessions[session_id]["count"] > 0 and is_confirm(user_text):
            # user xác nhận liên quan -> dùng câu hỏi trước đó để trả lời
            user_text = clarify_sessions[session_id]["last_question"]
            clarify_sessions[session_id]["count"] = 0
            clarify_sessions[session_id]["last_question"] = ""

        # 3) Lấy context gần nhất
        top = top_k_context(user_text, qa_pairs, k=5)
        best_score = top[0][0] if top else 0.0

        # 4) Nếu không chắc liên quan -> hỏi lại tối đa 2 lần
        if should_clarify(best_score):
            c = int(clarify_sessions[session_id]["count"])
            if c < 2:
                clarify_sessions[session_id]["count"] = c + 1
                clarify_sessions[session_id]["last_question"] = user_text
                print(f"\nBot: {next_clarify_question()}\n")
                continue
            else:
                # quá 2 lần vẫn không liên quan
                clarify_sessions[session_id]["count"] = 0
                clarify_sessions[session_id]["last_question"] = ""
                print("\nBot: Tôi không có thông tin này.\n")
                continue

        # 5) Build prompt + generate
        context = build_context_text(top)
        prompt = build_prompt(user_text, context)

        out = llm(
            prompt,
            max_tokens=256,
            temperature=0.3,  # bám dữ liệu hơn
            top_p=0.9,
            stop=["### User:", "### System:", "### Assistant:", "### DỮ LIỆU THAM CHIẾU"],
        )

        answer = out["choices"][0]["text"].strip()
        if not answer:
            answer = "Chưa đủ dữ liệu."

        print(f"\nBot: {answer}\n")

if __name__ == "__main__":
    main()
