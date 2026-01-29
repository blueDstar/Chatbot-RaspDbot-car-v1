import os
from typing import List, Dict, Optional
from llama_cpp import Llama

# =========================
# Greetings (chặn bằng code)
# =========================
GREETINGS = {
    "hi", "hello", "hey", "alo", "chào", "xin chào", "chào bạn", "yo"
}

# =========================
# Keywords cần dữ liệu realtime
# =========================
NEED_DATA_KEYWORDS = [
    "vị trí", "gps", "tốc độ hiện tại", "tốc độ",
    "imu", "lidar", "camera", "log", "pin", "battery"
]

# =========================
# Prompt / Stop tokens
# =========================
SYSTEM_PROMPT = (
    "Bạn là trợ lý kỹ thuật cho xe tự hành RaspDbot-Car.\n"
    "KHI TRẢ LỜI:\n"
    "- Luôn xưng là \"tôi\" và gọi người dùng là \"bạn\".\n"
    "- Trả lời ngắn gọn, đúng trọng tâm; ưu tiên gạch đầu dòng khi liệt kê.\n"
    "\n"
    "QUY TẮC BẮT BUỘC:\n"
    "1) Chỉ trả lời dựa trên thông tin bạn cung cấp hoặc kiến thức chung về robot/xe tự hành.\n"
    "2) Nếu câu hỏi cần dữ liệu cụ thể (vị trí xe, tốc độ hiện tại, cảm biến, log, cấu hình) "
    "mà bạn chưa đưa dữ liệu => trả lời: \"Tôi chưa có dữ liệu đó\" và hỏi bạn cần cung cấp gì.\n"
    "3) Không được tự bịa số liệu/địa điểm (ví dụ: \"5.000m\", \"đường 1\", GPS...) nếu không có dữ liệu.\n"
    "4) Nếu bạn chào hỏi ngắn (vd: \"alo\", \"hi\"), tôi chỉ chào lại và gợi ý bạn hỏi về RaspDbot-Car.\n"
)

# Stop tokens có newline để chặn multi-turn "### Assistant:" sinh lại
STOP_TOKENS = ["\n### User:", "\n### System:", "\n### Assistant:"]


def build_prompt(history: List[Dict[str, str]]) -> str:
    parts: List[str] = []
    parts.append("### System:\n" + SYSTEM_PROMPT.strip() + "\n")

    for m in history:
        if m["role"] == "user":
            parts.append("### User:\n" + m["content"].strip() + "\n")
        else:
            parts.append("### Assistant:\n" + m["content"].strip() + "\n")

    parts.append("### Assistant:\n")
    return "\n".join(parts)


class RaspDbotEngine:
    def __init__(
        self,
        model_path: str,
        n_ctx: int = 2048,
        n_threads: Optional[int] = None,
        n_gpu_layers: int = 0,
    ):
        self.model_path = model_path
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Không tìm thấy model: {self.model_path}")

        self.llm = Llama(
            model_path=self.model_path,
            n_ctx=n_ctx,
            n_threads=n_threads or (os.cpu_count() or 4),
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )
        self.history: List[Dict[str, str]] = []

    def ask(self, user_text: str) -> str:
        user_text = (user_text or "").strip()
        if not user_text:
            return "Bạn hãy nhập câu hỏi trước nhé."

        low = user_text.lower()

        # 1) Greeting: trả lời ngay, không gọi LLM
        if low in GREETINGS:
            return "Xin chào 👋 Tôi đây. Bạn muốn hỏi gì về RaspDbot-Car?"

        # 2) Realtime data: trả lời chắc chắn, không gọi LLM
        if any(k in low for k in NEED_DATA_KEYWORDS):
            return (
                "Tôi chưa có dữ liệu realtime của xe (GPS/tốc độ/cảm biến/log).\n"
                "Bạn hãy gửi một trong các thông tin sau để tôi phân tích:\n"
                "- Log/telemetry (JSON/text)\n"
                "- Thông số cảm biến\n"
                "- Trạng thái hiện tại (vị trí/tốc độ/pin)\n"
            )

        self.history.append({"role": "user", "content": user_text})
        prompt = build_prompt(self.history)

        out = self.llm(
            prompt,
            max_tokens=256,
            temperature=0.35,
            top_p=0.9,
            top_k=50,
            repeat_penalty=1.15,
            stop=STOP_TOKENS,
        )

        answer = (out["choices"][0]["text"] or "").strip()
        if not answer:
            answer = "(Tôi không sinh được câu trả lời — bạn thử tăng max_tokens hoặc đổi prompt template.)"

        # 3) Cắt sạch nếu model lỡ in marker hoặc tự chat tiếp
        for cut in ["\n### ", "### Assistant:", "### User:", "### System:"]:
            idx = answer.find(cut)
            if idx != -1:
                answer = answer[:idx].strip()
                break

        # 4) Ép nhẹ xưng hô
        answer = (
            answer.replace("Mình ", "Tôi ")
                  .replace("mình ", "tôi ")
                  .replace("Tớ ", "Tôi ")
                  .replace("tớ ", "tôi ")
        )

        self.history.append({"role": "assistant", "content": answer})
        return answer

    def reset(self):
        self.history = []

    def export_text(self) -> str:
        lines = []
        for m in self.history:
            prefix = "👤 Bạn" if m["role"] == "user" else "🤖 Tôi"
            lines.append(f"{prefix}: {m['content']}")
        return "\n\n".join(lines)

    def to_json(self) -> dict:
        return {
            "model_path": self.model_path,
            "history": self.history,
        }

    def load_json(self, data: dict):
        hist = data.get("history", [])
        if isinstance(hist, list):
            self.history = [
                {"role": str(m.get("role", "")), "content": str(m.get("content", ""))}
                for m in hist
                if isinstance(m, dict)
            ]
