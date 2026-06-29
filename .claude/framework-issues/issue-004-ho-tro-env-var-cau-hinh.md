# Issue #4 — Hỗ trợ cấu hình qua biến môi trường (deploy cloud-native)

- **Mức độ:** Trung bình (đề xuất tính năng) - **TRẠNG THÁI: ĐANG BÀN, CHƯA QUYẾT**
- **Phase phát hiện:** Pha tối ưu (bàn về chiến lược cấu hình khi deploy)
- **Thành phần:** `xime.core.config` (`YamlConfigLoader`, `RuntimeConfig`), bootstrap

> ⚠️ Đây là vấn đề **mở để bàn thêm**, không phải đề xuất đã chốt. Ghi lại để suy nghĩ tiếp về
> hướng cấu hình cloud-native. Hiện tại đã có cách chạy được (mount file yml) nên KHÔNG khẩn cấp.

## Bối cảnh

Xime nạp cấu hình **chỉ** từ file YAML trong `resources/` (`YamlConfigLoader`):

1. `resources/application.yml` (base, commit repo)
2. `resources/application-{env}.yml` (override theo `XIME_ENV`/`APP_ENV`, deep-merge)

Loader dùng `yaml.safe_load` thuần - **không nội suy `${ENV_VAR}`**, và **không có lớp override
bằng biến môi trường**. Nghĩa là không có đường nào để giá trị từ env var chui vào config.

`.env` / `.env.example` trong dự án vì thế **vô tác dụng** (không code nào đọc, tên khóa cũng lệch
với khóa yml thật) - đã đề xuất gỡ.

## Vì sao đáng bàn (ngữ cảnh Docker/K8s)

Khi deploy container, trục quan trọng là **"nướng config vào image lúc build" vs "tiêm lúc chạy"**:

1. **Secret không được nằm trong image.** `COPY application-secret.yml` (mật khẩu DB, jwt secret
   thật) vào image -> secret bị ghi vào layer, đẩy lên registry, ai pull cũng moi ra được. Phải tiêm
   lúc runtime.
2. **Build một lần, chạy mọi nơi (12-factor).** Config nướng sẵn -> mỗi môi trường một image khác,
   mất tính tái lập. Tiêm lúc chạy -> một image đi từ dev tới prod.
3. **Nền tảng cloud nói bằng env var.** K8s `ConfigMap`/`Secret`, Cloud Run, ECS, Heroku, Fly... bơm
   cấu hình chủ yếu qua env var; nhiều chỗ không cho mount filesystem dễ dàng.

## Cách hiện tại đã chạy được (workaround, KHÔNG cần sửa framework)

Không cần `.env`. Mount file yml lúc runtime thay vì copy lúc build:

```yaml
# K8s: application-secret.yml thành Secret, mount như file vào resources/
volumeMounts:
  - name: app-secret
    mountPath: /app/resources/application-secret.yml
    subPath: application-secret.yml
```

Image chỉ chứa `application.yml` base (không nhạy cảm); secret mount lúc chạy -> không vào image,
image vẫn build-once. Hợp với Xime ngay bây giờ.

> Lưu ý: `YamlConfigLoader.load(env)` chỉ merge `application.yml` + `application-{env}.yml` (một env).
> Các file `application-secret.yml` / `application-local.yml` (đã có trong `.gitignore`) hiện chỉ được
> nạp nếu `XIME_ENV` trỏ đúng tên đó - tức không thể vừa `production` vừa `secret`. Cần xem lại liệu
> bootstrap có gộp nhiều file override không, hay chỉ một. (Câu hỏi mở.)

## Các phương án để bàn (chưa chọn)

### A. Nội suy `${ENV_VAR}` trong YAML
```yaml
database:
  url: "${DATABASE_URL}"
jwt:
  secret: "${JWT_SECRET}"
```
Khi load, thay `${VAR}` bằng `os.environ`. Quen thuộc (giống Spring Boot `${...}`), ít phá vỡ.
- Cần: cú pháp default `${VAR:-fallback}`? Báo lỗi rõ khi thiếu biến bắt buộc?

### B. Lớp override bằng env var theo convention (relaxed binding)
Ví dụ `XIME_JWT__SECRET=...` -> map sang khóa `jwt.secret` (phân tách cấp bằng `__`), đè lên yml.
Mạnh hơn A: không phải sửa yml, hợp K8s (chỉ set env). Giống `pydantic-settings` nested env /
Spring relaxed binding.
- Cần: tiền tố (`XIME_`?), quy ước phân tách cấp, thứ tự ưu tiên.

### C. Đọc `.env` (python-dotenv) nạp vào `os.environ` trước khi load config
Bổ trợ cho A hoặc B, tiện cho dev local. Bản thân nó không giải quyết được nếu thiếu A/B.

## Câu hỏi mở (cần suy nghĩ thêm)

- **Thứ tự ưu tiên** nên là gì? Đề xuất nháp: env var > `application-{env}.yml` > `application.yml`.
- **Ép kiểu:** env var luôn là string, nhưng config có `int`/`bool`/`list` (vd `jwt.access_ttl`,
  `cors.allow_origins`). Cần quy tắc parse (theo kiểu khai báo trong `RuntimeConfig`?).
- **Bảo mật:** đảm bảo không log giá trị secret khi nạp; không in ra khi báo lỗi thiếu biến.
- **Tương thích ngược:** mặc định TẮT (chỉ bật khi khai báo `${...}` hoặc set tiền tố) để app cũ
  không đổi hành vi.
- **Phạm vi:** chỉ cần A là đủ cho secret cơ bản, hay nên làm B cho cloud-native thực thụ?

## Kết luận tạm

Chưa cần làm gấp - cách mount yml đáp ứng được nhu cầu deploy an toàn hiện tại. Ghi lại để khi
chuẩn hóa pipeline Docker/K8s thì quyết phương án (nghiêng về **A** cho đơn giản, hoặc **A + C**;
cân nhắc **B** nếu đi hẳn hướng K8s-native).
