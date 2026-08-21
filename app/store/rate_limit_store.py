"""
RateLimitStore - bảng đếm hãm nhịp (rate limit) trên kho liên tiến trình của Xime (LMDB).

Vì sao không dùng CacheService nữa (đổi 2026-08-21, theo Xime 0.8):

1. Bộ đếm ra khỏi RAM của MỘT tiến trình. Trước đây chạy nhiều worker thì hạn mức thật bị
   nhân lên đúng bằng số tiến trình, và không ai thấy.
2. `incr()` ở đây NGUYÊN TỬ, và đó là chỗ bản cũ có một cái bẫy đã ĐO ĐƯỢC. Bản cũ đếm bằng
   `cache.get()` rồi `cache.set(n + 1)`. Với InMemoryCacheService thì không đua - không có
   await thật nào giữa hai bước nên coroutine không bị xen vào. Nhưng chính comment của bản cũ
   khuyên "đổi sang Redis khi deploy nhiều worker", mà Redis thì mỗi lệnh là một round-trip:
   đo bằng một cache có I/O thật, 20 lần `hit` song song chỉ đếm được **1**.

   Nói cách khác, bản cũ an toàn chỉ nhờ backend KHÔNG có I/O, và đúng cách khắc phục mà nó
   đề xuất sẽ làm hỏng nó - im lặng, đúng lúc hệ thống bắt đầu chịu tải thật. Kẻ dò mật khẩu
   bắn song song chứ không bắn tuần tự, nên đó là ca vận hành, không phải ca lý thuyết.

Phạm vi của kho là MỘT MÁY (bộ nhớ chia sẻ + file cục bộ, không bắc qua máy). Nhiều máy thì
tầng đó phải là Redis qua CacheService - xem docs/{vn,en}/starters.md của framework.

Dữ liệu ở đây KHÔNG có nguồn bền vững và được phép mất: máy khởi động lại thì bộ đếm về 0,
người đang bị khoá được thả sớm. Chấp nhận được; ngược lại (đơn hàng, token) thì phải nằm ở DB.

An atomic, cross-process counter table for rate limiting (Xime Store on LMDB).
"""
from __future__ import annotations

from xime.starters.lmdb import CounterStore


class RateLimitStore(
    CounterStore,
    name="rate-limit",  # bắt buộc - cũng là tên thư mục bảng trong kho
    ttl=900,            # mặc định 15 phút; mọi lời gọi trong app đều truyền ttl riêng
):
    """Đếm số lần gọi theo khóa (login sai, gửi email reset, xin OTP)."""
