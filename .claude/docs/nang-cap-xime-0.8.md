# Nâng cấp dự án theo Xime 0.8.0 (2026-08-21)

> Bối cảnh: framework nhảy từ nhánh 0.6.x lên **0.8.0** (bản **alpha cuối**; 0.9 sang beta, API
> coi như đã chốt). Tài liệu này ghi những gì ĐÃ LÀM ở shop backend, đo được ra sao, và những
> gì còn nợ.

## 1. Đo tương thích trước khi đụng vào bất cứ thứ gì

| Phép đo | Kết quả |
|---|---|
| `python -m pytest` trên xime 0.8.0, trước mọi thay đổi | **166 passed** |
| `xime check config` | CLEAN |
| `xime check module-level` | CLEAN |

**Không có breaking nào ép shop phải sửa.** Các thay đổi phá tương thích của 0.8 đều trượt qua,
và lý do đáng ghi lại vì nó nói cho ta biết quyết định cũ nào đang trả cổ tức:

| Thay đổi của framework | Vì sao shop không dính |
|---|---|
| `host`/`port`/`ssl` bỏ hẳn khỏi constructor web/gRPC/socket | shop dùng `WebAdapter()` trơn - công của việc gỡ `ShopWebAdapter` (2026-06-29) |
| `ServerConfig` rời core; `runtime.get("server.host")` trả `None` khi YAML không khai | shop không đọc `runtime.server` ở đâu cả |
| `current_app_id()` / `PEER_APP_ID` gỡ hẳn (0.7.1) | shop không dùng |
| `Adapter` thành Protocol thật, `scaling=` bắt buộc | shop không tự viết adapter nào |
| `SchedulerRunner` thành `SchedulerAdapter(scaling="singleton")` | framework TỰ đăng ký khi đã `configure_scheduler()`; `app/config/scheduler.py` không phải sửa |

## 2. Những gì đã đổi

### 2.1 JWT: ký/verify đi qua starter của framework, và token có `kid`

Trước: `AuthenticationService` gọi thẳng `pyjwt.encode/decode`, HS256, một secret cố định,
**không `kid`**. Hệ quả: không xoay được khóa mà không đăng xuất toàn bộ người dùng - và đó
đúng là lý do một khóa bị lộ vẫn nằm im hàng tháng (cảnh báo bảo mật 2026-08-01: chuỗi ký nằm
trong git, app đã deploy).

Sau:

- `app/security/jwt_key_provider.py` - `ShopJwtKeyProvider` implement Protocol `JwtKeyProvider`
  của framework: giữ khóa đang ký + các khóa cũ chỉ để verify, định địa chỉ bằng `kid`.
- `AuthenticationService` inject `JwtTokenSigner` / `JwtTokenVerifier`, thêm `leeway` (dung sai
  đồng hồ, chống 401 chập chờn khi hai máy lệch giây), `algorithms` là danh sách trắng, và
  `require=["jti","exp","iss","aud"]` (PyJWT chỉ kiểm `exp` khi claim tồn tại, nên token không
  mang `exp` sẽ không bao giờ hết hạn).
- Khối `jwt:` trong `application.yml` có thêm `key_id`, `algorithm`, `leeway`, `previous_keys`,
  `accept_unkeyed`.

**Cố ý KHÔNG gọi `configure_jwt()`**: nó sẽ gắn middleware JWT của framework, trong khi
`JwtMiddleware` của shop còn phải kiểm blacklist, nạp user và chặn refresh token dùng thay
access token. Ta chỉ mượn tầng ký/verify. Đổi sang middleware framework là một quyết định
riêng, xem mục 4.

**Quy trình xoay khóa (không cắt dịch vụ):**

1. Sinh secret mới. Chuyển cặp `secret` + `key_id` hiện tại xuống `jwt.previous_keys`.
2. Đặt `secret`/`key_id` mới (k1 sang k2), deploy. Token cũ vẫn verify được; token mới ký bằng
   khóa mới.
3. Sau khi qua `refresh_ttl` (60 ngày) thì xóa mục cũ khỏi `previous_keys`.

`accept_unkeyed: true` để token phát TRƯỚC lần nâng cấp này (không mang `kid`) còn dùng được
tới khi hết hạn. Đặt `false` sau 60 ngày kể từ lần deploy này.

**Regression:** `test/test_jwt_rotation.py` - 4 test. Ba trong số đó đỏ với bản cũ (token không
có `kid`; token ký bằng khóa đã nghỉ hưu; token mang `kid` lạ mà bản cũ vẫn nhận vì nó không
đọc `kid`).

**Kiểm chứng đầu-cuối** (không chỉ test): khởi động thật `python -m app.main`, login `admin`,
đọc header token ra `kid = k1`, gọi `/api/users` kèm token trả 200, token rác trả 401.

### 2.2 Hãm nhịp chuyển sang Xime Store (LMDB)

`RateLimiterService` không còn dựa vào `CacheService` (dict trong RAM một tiến trình) mà dùng
`app/store/rate_limit_store.py` - một `CounterStore` trên LMDB, dùng chung giữa mọi tiến trình
của **một máy**.

⚠ **Một đối chứng đã đo, và nó chỉnh lại chính lý do ban đầu của tôi:** bản cũ đếm bằng
`get()` rồi `set(n+1)`. Qua `InMemoryCacheService` thì **không đua** - giữa hai bước không có
`await` thật nào để coroutine khác chen vào. Nhưng comment của bản cũ khuyên *"đổi sang Redis
khi deploy nhiều worker"*, và Redis thì mỗi lệnh là một round-trip: đo bằng một cache mô phỏng
I/O thật, **20 lần `hit` song song chỉ đếm được 1**.

> Bản cũ an toàn chỉ nhờ backend KHÔNG có I/O, và đúng cách khắc phục mà nó đề xuất sẽ làm hỏng
> nó, im lặng, vào đúng lúc hệ thống bắt đầu chịu tải thật.

`incr()` của `CounterStore` là nguyên tử nên cả hai tầng cùng đóng.

Kèm theo: `StoreCleanupJob` của framework đăng ký vào scheduler (10 phút một lần) để thu hồi chỗ
của bản ghi hết hạn. Từ 0.8 scheduler là adapter hạng đơn nhất nên nó chỉ chạy ở tiến trình
primary.

Cấu hình: khối `lmdb:` (dev Windows `runtime/store` - đã gitignore; production
`/dev/shm/shop-store`). Framework cố ý không có mặc định cho `lmdb.path`: nhiều service Xime
chung một máy, một mặc định dùng chung sẽ âm thầm trộn bảng của chúng.

**Câu tự kiểm trước khi đặt thêm thứ gì vào kho này:** *máy khởi động lại, bảng này rỗng trơn,
app còn chạy đúng không?* Không thì dữ liệu đó thuộc **database**.

### 2.3 Upload không còn tin `Content-Type` của client

`file_service.upload_file` trước đây truyền `content_type=upload_file.content_type` cho
`save_upload`. Bản vá F2 của Xime 0.7.1 cố ý **bỏ qua** header đó vì kẻ gọi điều khiển được nó
(một "avatar.png" khai `text/html` là XSS lưu trữ khi backend S3 trả lại y nguyên lúc tải về);
truyền tay lại đúng giá trị đó là mở lại cửa vừa đóng. Nay để framework suy từ TÊN FILE.

### 2.4 `main.py` theo khuôn 0.8, và `add_config` tường minh

`app.use(...)` và `app.add_config(config)` chuyển lên **mức module**; `app/config/__init__.py`
khai tường minh thứ tự chạy. Hôm nay shop vẫn một tiến trình nên hành vi không đổi, nhưng đây
là **điều kiện cần** để sau này thêm `share_load()`: tiến trình con chạy lại `main.py` với
`__name__` là `__mp_main__` nên khối `if` không kích hoạt, và cơ chế dò config cũ (qua
`__main__.__spec__.parent`) tìm sai chỗ rồi **im lặng** rơi xuống một DI rỗng.

⚠ Kèm luật đi cùng hình dạng này: **mức module chỉ để KHAI BÁO, không để LÀM**. Mọi thứ ngoài
khối `if __name__` chạy N+1 lần khi có N tiến trình con.

### 2.5 Vệ sinh

- `pyproject.toml` ghim `xime[web,sqlalchemy,scheduler,mail,lmdb,jwt]>=0.8,<0.9`. Trước đây
  không khai gì, nên không file nào nói app cần bản framework nào trong khi nó được cài editable.
- `application.yml` thêm khối `logging:` (không khai thì root logger ở WARNING, mọi dòng INFO bị
  nuốt, kể cả dòng bind mới của 0.8 có ghi **chế độ bảo mật** ngay cạnh địa chỉ).
- Bỏ dấu gạch dài trong các file cấu hình đã đụng tới.

### 2.6 Một phát hiện ngoài kế hoạch: `application-local.yml` gần như không bao giờ được nạp

Trong lúc sửa chú thích về chỗ đặt secret, đo thẳng vào loader của framework:

```text
YamlConfigLoader("resources")
  load(None)          -> jwt.key_id = k1                       (đọc application.yml)
  load("local")       -> jwt.key_id = PROBE-local-file-duoc-nap (đọc application-local.yml)
  load("production")  -> jwt.key_id = k1                       (application-production.yml không khai khóa này)
```

Framework chỉ nạp `application.yml` + `application-{env}.yml`, với `env` lấy từ
`XIME_ENV`/`APP_ENV`. Nghĩa là `application-local.yml` **chỉ có tác dụng khi chạy với
`XIME_ENV=local`** - không đặt biến đó thì file nằm im trên đĩa, không một dòng nào được đọc và
**không một dòng cảnh báo nào**.

⚠ Đây là cùng khuôn phát hiện **A6** của kiểm toán 2026-08-01 (*"chú thích bảo để secret vào
`application-secret.yml`, mà framework không bao giờ nạp file đó"*), nhưng rộng hơn: `README.md`,
bốn tài liệu trong `.claude/docs/` và ba dòng chú thích trong YAML của repo này đều đang dạy
dùng `application-local.yml` như một override mặc định.

📌 Và nó giải thích một chuyện đã kéo dài: secret thật **chưa bao giờ rời khỏi git** không phải
vì ai đó lười, mà vì đường thoát mà tài liệu chỉ ra **không dẫn tới đâu cả**.

Đã sửa: cả bảy chỗ, kèm cách đúng cho máy chủ (ghi đè `application-production.yml` lúc deploy,
không commit) và cho máy dev (`XIME_ENV=local`). Chú thích trỏ sang `application-secret.yml`
trong `application-production.yml` đã bỏ - tức A6 coi như đã vá.

⚠ Kèm một chỗ lỗi thời khác đã sửa trong `database-connection.md`: nó khuyên *"đọc từ
`DATABASE_URL` / `.env`"*, trong khi Xime **không nội suy `${VAR}`** và **không override từng
khóa bằng biến môi trường** - env chỉ chọn file profile.

## 3. Trạng thái sau thay đổi

| | |
|---|---|
| Test | **171 passed** (166 trước đó cộng 5 test mới) |
| `xime check config` | CLEAN (logging, server, cors, lmdb) |
| Khởi động thật | OK - kho LMDB lên, 3 job đăng ký, web bind 0.0.0.0:8088 |

## 4. Còn nợ (chưa làm, có chủ đích)

| Việc | Vì sao chưa làm |
|---|---|
| **Đổi khóa JWT thật và đưa secret ra khỏi git** | Là quyết định vận hành (chọn secret mới, deploy). Đường đi đã sẵn sàng: mục 2.1 cho cách xoay, mục 2.6 cho chỗ đặt secret sao cho nó thật sự được nạp. Nên làm sớm - app đang chạy bằng chuỗi nằm trong lịch sử git. Muốn vô hiệu ngay token đang sống: đổi `key_id` **và** đặt `accept_unkeyed: false` |
| **Tắt `accept_unkeyed`** | Sau 60 ngày kể từ lần deploy có `kid` |
| **Cache catalog dùng chung giữa tiến trình** | `InMemoryCacheService` là dict trong RAM một tiến trình; đa tiến trình thì invalidate ở A không tới B. Đường đi: bind sang backend Redis (`xime.starters.redis`) kèm khối `redis:`. Cần Redis chạy nên chưa bật ở dev |
| **`CategoryTreeCache` khi đa tiến trình** | Nó có nguồn bền vững (bảng categories), ghi hiếm và thay trọn gói, nên đúng hạng **`RefData`** của framework (primary nạp và publish, mọi tiến trình đọc), không phải `Store` |
| **`share_load()`** | Chỉ bật sau khi hai dòng trên xong. `main.py` đã đúng hình dạng |
| **Chuyển hẳn sang middleware JWT của framework** | Phải liệt kê `public_paths`, và nó so khớp **chính xác từng đường dẫn**, không theo tiền tố. Shop có nhiều endpoint công khai (catalog, `/media/{key}`) nên đây là việc rủi ro, cần rà riêng chứ không ghép vào đợt này |
| **Fail-open ở `JwtMiddleware`** | Request không có header `Authorization` đi tiếp ẩn danh (có chủ đích: catalog công khai), controller tự gọi `require_login()`. Đây là điểm cảnh báo 2026-08-01 nêu, và nó là quyết định thiết kế chứ không phải lỗi cài đặt - cần một lượt rà riêng để chốt |
| **`configure_health()`** | 0.8 cấp `/healthz` và `/readyz` chuẩn (kèm trạng thái từng adapter, cố ý không xác thực). Shop đang dùng `/api/health` tự viết. Đáng thêm khi rà lại cấu hình systemd/LB |

## 5. Bảng chọn ba chiều (ghi lại để khỏi tra lại)

| Cần gì | Dùng | Phạm vi |
|---|---|---|
| State KHÔNG có nguồn bền vững, được phép mất (hãm nhịp, chống lặp) | **`Store`** (LMDB) | một máy |
| Dữ liệu CÓ nguồn bền vững, đọc nhiều, ghi hiếm (khóa JWT, cây category) | **`RefData`** | một máy |
| Nhiều MÁY phải cùng thấy | **`CacheService`** sang Redis | nhiều máy |

Mọi thứ framework tự cấp (`RefData`, `Store`, `ProcessLink`) là **một máy, luôn luôn**.
