# Cảnh báo bảo mật - kiểm toán 2026-08-01

> **Thông tin gốc nằm ở một chỗ duy nhất, đừng chép lại vào đây:**
> `D:\code\xime\xime framework\.claude\docs\kiem-toan-bao-mat-0.7.md`
>
> Ở đó có: mô hình mối đe dọa, 24 phát hiện đầy đủ kèm `file:dòng`, 12 PoC chạy
> được (`.claude/scripts/bao-mat/`), phần "đã kiểm và ĐẠT", và bảng thứ tự vá.
>
> File này chỉ trả lời một câu: **repo NÀY dính cái gì, ở dòng nào.**
>
> Trạng thái 2026-08-01: **CHƯA VÁ GÌ CẢ.** Cập nhật dòng này khi vá.

## Repo này dính những gì

| Mã | Mức | Ở đâu trong repo này | Chuyện gì |
|---|---|---|---|
| **A3** | 🟠 CAO | `backend/resources/application.yml:19 + app/service/authentication_service.py:30,79` | Ký JWT HS256 bằng `"dev-secret-CHANGE-IN-PRODUCTION-use-32chars-minimum"` - **giá trị này nằm trong git**, `application-production.yml` (cũng trong git) KHÔNG đè nó, và app đã deploy ở `shop.scime.click`. Biết secret là ký được token cho bất kỳ `uid` nào. Coi như **đã lộ**: đổi secret VÀ vô hiệu token đang sống. |
| **A5** | 🟡 TRUNG | `backend/app/security/jwt_middleware.py` (`if not auth_header: ... return`) | Không có header Authorization thì request **đi tiếp ẩn danh**; mỗi controller phải tự nhớ kiểm tra. Một route mới quên kiểm là một route công khai, và không có gì báo. |
| **A6** | 🟡 TRUNG | `backend/resources/application-production.yml:4` (chú thích) | Chú thích bảo để secret vào `application-secret.yml`. **Framework không bao giờ nạp file đó** (`YamlConfigLoader` chỉ đọc `application.yml` + `application-{env}.yml`), và file đó không tồn tại. Đây là nguyên nhân trực tiếp của A3. |
| **A4** | 🟡 TRUNG | `/resources/application.yml` (`auth.jwt.public_paths`) | `/docs`, `/redoc`, `/openapi.json` mở công khai -> toàn bộ bản đồ API đọc được không cần đăng nhập. Tự nó không phải lỗ hổng, nhưng nó rút ngắn giai đoạn thăm dò xuống gần bằng không. |
| **A2** | 🟠 CAO | `/resources/application.yml` (`cors.allow_origin_regex`) | Regex chú thích là "IP LAN" nhưng khớp **mọi IPv4 công cộng** (`http://203.0.113.66` khớp), kèm `allow_credentials: true` + `allow_methods: ["*"]`. Kẻ tấn công chỉ cần một VPS, không cần tên miền. |

> **A3 là việc gấp nhất trong toàn bộ đợt kiểm toán** (hạng 1 trong bảng thứ tự vá của
> báo cáo gốc), vì đây là app duy nhất vừa có secret trong git vừa đã deploy thật.
>
> Sửa file thôi là **chưa đủ**: mọi token đã ký bằng secret cũ vẫn hợp lệ tới khi hết
> hạn (`refresh_ttl: 5184000` = 60 ngày). Phải đổi secret **và** vô hiệu token đang sống.

## Đã kiểm và ĐẠT ở repo này, đừng lo thừa

- `validate_token` **có** ép `audience` + `issuer` + `options={"require": [...]}`, và mỗi
  app Monolithic một `aud` riêng. Nên dùng chung secret **không** khiến token của app này
  dùng được ở app kia. (Nhưng biết secret thì tự ký token đúng `aud` là xong - ép `aud`
  chặn tái sử dụng, không chặn giả mạo.)
- `application-production.yml` **có** tắt `allow_origin_regex` (`null`) và khóa CORS về
  đúng một origin. Đây là **codebase duy nhất trong 24 chỗ** làm việc này. A2 vì vậy chỉ
  còn chạm tới môi trường dev của repo này.

## Ba điều dễ hiểu nhầm, đọc trước khi sửa

1. **Đây không phải lỗi của framework Xime.** Phần lớn phát hiện ở repo này là lỗi
   *cấu hình* và *cách dùng*, không phải lỗi thư viện. Nâng phiên bản `xime` không
   sửa được gì trong bảng trên.
2. **Đừng sửa lẻ từng repo.** Hầu hết mục dưới đây là bản sao của cùng một khuôn.
   Sửa ở `Application Layer/saas-foundation/template` trước, rồi lan xuống, kẻo
   app thứ 22 lại mang y nguyên lỗi cũ.
3. **Đã có kế hoạch vá chung, đừng vá lẻ ngoài nó.**
   `D:\code\xime\xime framework\.claude\docs\ke-hoach-va-bao-mat-2026-08-01.md`
   - 5 đợt, code cụ thể từng mục, cách kiểm chứng, và 4 quyết định đã chốt của
   chủ dự án. Đổi lẻ cấu hình xác thực của một app có thể làm gãy luồng đăng
   nhập dùng chung.

   Hai điều trong kế hoạch đó ảnh hưởng trực tiếp tới repo này:
   `xime` cài **editable** và **không app nào có venv riêng**, nên một lần sửa
   framework là chạm cả 31 app ngay; và `xime.__version__` đang trả `0.6.3` trong
   khi code thật là `0.7.0`, nên **đừng dùng nó để xác nhận bản vá đã vào chưa**.
