from xime import Application
from xime.adapters.web import WebAdapter

from app import config

# Entry point - khởi động toàn bộ ứng dụng shop backend
# Entry point - starts the whole shop backend application
#
# ⚠ `use()` và `add_config()` nằm ở MỨC MODULE có chủ đích (khuôn main.py của Xime 0.8): tiến
# trình con chạy lại chính file này để dựng lại ứng dụng, và ở đó `__name__` là `__mp_main__`
# nên khối `if` bên dưới KHÔNG kích hoạt. Đặt chúng vào trong khối đó thì con có một ứng dụng
# không adapter nào và DI rỗng - hỏng im lặng. Hôm nay shop chạy một tiến trình nên hình dạng
# này chưa đổi gì; nó là điều kiện cần để sau này thêm `share_load()` mà không phải sửa lại.
#
# ⚠ Mức module chỉ để KHAI BÁO, không để LÀM: mọi thứ ngoài khối `if` chạy N+1 lần khi có N
# tiến trình con. Không mở kết nối, không đọc file, không sinh giá trị ngẫu nhiên ở đây.
app = Application()
app.add_config(config)
app.use(WebAdapter())

if __name__ == "__main__":
    app.run()
