from xime import Application

from xime.adapters.web import WebAdapter

# Entry point - khởi động toàn bộ ứng dụng shop backend
# Entry point - starts the whole shop backend application
app = Application()

if __name__ == "__main__":
    app.use(WebAdapter()).run()
