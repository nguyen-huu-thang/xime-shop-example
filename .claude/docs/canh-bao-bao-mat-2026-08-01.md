# Cảnh báo bảo mật - kiểm toán 2026-08-01

> **Thông tin gốc nằm ở một chỗ duy nhất, đừng chép lại vào đây:**
> `D:\code\xime\xime framework\.claude\docs\kiem-toan-bao-mat-0.7.md`
>
> Ở đó có: mô hình mối đe dọa, 24 phát hiện đầy đủ kèm `file:dòng`, 12 PoC chạy
> được (`.claude/scripts/bao-mat/`), phần "đã kiểm và ĐẠT", và bảng thứ tự vá.
>
> File này chỉ trả lời một câu: **repo NÀY dính cái gì, ở dòng nào.**
>
> Trạng thái 2026-08-01: **CHƯA VÁ GÌ CẢ.**
> Trạng thái **2026-08-21**: xem mục "Cập nhật 2026-08-21" ở cuối file. Tóm tắt: **A3 vẫn CHƯA
> VÁ** (secret vẫn là chuỗi trong git), nhưng nay đã có **đường vá không cắt dịch vụ**; A6 đã
> vá và mở rộng; A5, A4, A2 giữ nguyên.

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


---

## Cập nhật 2026-08-21 (đợt nâng theo Xime 0.8)

Chi tiết kỹ thuật: [`nang-cap-xime-0.8.md`](nang-cap-xime-0.8.md).

| Mã | Trạng thái | Ghi chú |
|---|---|---|
| **A3** | 🟠 **CHƯA VÁ**, nhưng đã rẻ đi nhiều | Secret vẫn là chuỗi nằm trong git. Cái đã đổi là **khả năng vá**: token nay mang `kid`, và `jwt.previous_keys` cho phép giữ khóa cũ trong lúc chuyển - nên đổi khóa là **một lần deploy có gối đầu**, không còn là một lần đăng xuất toàn bộ người dùng. Muốn vô hiệu ngay token đang sống thì đổi `key_id` **và** đặt `accept_unkeyed: false`, không cần đợi hết 60 ngày |
| **A6** | ✅ **ĐÃ VÁ, và rộng hơn báo cáo gốc** | Chú thích trỏ sang `application-secret.yml` đã bỏ. Đo thêm được: **`application-local.yml` cũng chỉ được nạp khi `XIME_ENV=local`** (`ld.load(None)` đọc ra `k1`, `ld.load("local")` mới đọc ra giá trị trong file local). Cả README, bốn tài liệu và ba dòng chú thích YAML của repo này đều đang dạy dùng file đó như một override mặc định - **đã sửa hết**, kèm cách đúng cho máy chủ (ghi đè `application-production.yml` lúc deploy) |
| **A5** | 🟡 **CHƯA VÁ** (quyết định thiết kế đang treo) | `JwtMiddleware` vẫn fail-open: không có header `Authorization` thì đi tiếp ẩn danh, controller tự gọi `require_login()`. Đây là chủ đích (catalog công khai), nhưng "một route mới quên kiểm là một route công khai" vẫn đúng. Chuyển sang middleware của framework thì phải liệt kê `public_paths` **khớp chính xác từng đường dẫn** - cần một lượt rà riêng, xem mục 4 của tài liệu nâng cấp |
| **A4** | 🟡 CHƯA VÁ | `/docs`, `/redoc`, `/openapi.json` vẫn công khai |
| **A2** | 🟠 CHƯA VÁ (chỉ chạm dev) | `cors.allow_origin_regex` vẫn khớp mọi IPv4 công cộng ở `application.yml`; `application-production.yml` vẫn tắt nó bằng `null` |

⚠ **Một dòng của báo cáo gốc nay đã lỗi thời:** *"`xime.__version__` đang trả `0.6.3` trong khi
code thật là `0.7.0`"*. Framework hiện là **0.8.0** và `xime.__version__` trên máy này đọc ra
đúng `0.8.0`. Cơ chế thì không đổi: giá trị đó đóng băng ở lần `pip install -e .` cuối, nên vẫn
đừng dùng nó một mình để xác nhận một bản vá đã vào hay chưa.

📌 Và một điểm của báo cáo gốc vẫn đúng nguyên: **nâng phiên bản `xime` không vá được gì trong
bảng trên.** Đợt này nâng theo 0.8 chỉ làm cho A3 **vá được rẻ hơn**; bản thân việc vá vẫn là
một quyết định vận hành chưa ai bấm nút.
