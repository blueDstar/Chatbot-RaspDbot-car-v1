# RaspDbot-Car Chatbot (GTK4 Desktop App)

Desktop chatbot chạy local trên Ubuntu bằng **Python + GTK4** và **llama-cpp-python** (GGUF).  
App hỗ trợ:
- ✅ Giao diện chat GTK4 (không đơ UI nhờ background thread)
- ✅ Chọn model `.gguf` (dropdown, auto scan trong thư mục project)
- ✅ Menu: New chat / Load history / Save history / Export text / Quit
- ✅ Auto lưu lịch sử vào: `~/.local/share/raspdbot/history.json`
- ✅ Bot xưng **"tôi"**, gọi người dùng là **"bạn"**
- ✅ Chặn trường hợp model tự “hỏi–tự trả lời” bằng stop token + cắt output

---

## 1) Yêu cầu hệ thống

- Ubuntu Desktop 24.04 (khuyến nghị)
- Python 3.12
- GTK4 + PyGObject (cài bằng `apt`)
- Model GGUF (ví dụ):
  - `raspdbot-car.Q4_K_M.gguf`
  - `raspdbot-star.Q4_K_M.gguf`

---

## 2) Cấu trúc thư mục

Đặt các file như sau (cùng 1 thư mục):

