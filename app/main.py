from xime import Application

from app.shop_web_adapter import ShopWebAdapter

# Entry point - khởi động toàn bộ ứng dụng shop backend
# Entry point - starts the whole shop backend application
app = Application()

if __name__ == "__main__":
    app.use(ShopWebAdapter()).run()
