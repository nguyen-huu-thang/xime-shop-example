"""
Bảng error code — port nguyên văn từ src/Exception/ErrorCode.php của dự án PHP.

Mỗi mã có: code (int), message (vi), http_status (int).
Dùng qua AppException("Exxxx"). Xem [.claude/docs/error-code-system.md].
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorDef:
    code: int
    message: str
    http_status: int


# ── Bảng mã lỗi (copy từ ErrorCode.php) ──────────────────────────────────────
ERROR_CODES: dict[str, ErrorDef] = {
    "S0000": ErrorDef(-1, "Bạn đã đăng nhập", 303),

    # 1.1 Lỗi chung (0000–0999)
    "E0000": ErrorDef(0, "Lỗi không xác định", 500),
    "E0001": ErrorDef(1, "Dịch vụ tạm thời không hoạt động", 503),
    "E0002": ErrorDef(2, "Yêu cầu không hợp lệ", 400),
    "E0003": ErrorDef(3, "Tham số yêu cầu bị thiếu", 400),
    "E0004": ErrorDef(4, "Dữ liệu không hợp lệ", 422),
    "E0010": ErrorDef(10, "Không thể kết nối tới dịch vụ", 503),
    "E0011": ErrorDef(11, "Kết nối tới cơ sở dữ liệu thất bại", 500),
    "E0012": ErrorDef(12, "Kết nối tới API bên ngoài thất bại", 503),
    "E0013": ErrorDef(13, "Hết thời gian chờ kết nối", 504),
    "E0020": ErrorDef(20, "Không có quyền truy cập", 403),
    "E0021": ErrorDef(21, "Phiên làm việc đã hết hạn", 401),
    "E0022": ErrorDef(22, "Xác thực không thành công", 401),
    "E0030": ErrorDef(30, "Quá giới hạn số lượng yêu cầu", 429),
    "E0031": ErrorDef(31, "Tài nguyên không tìm thấy", 404),
    "E0032": ErrorDef(32, "Hành động không được phép", 403),
    "E0099": ErrorDef(99, "Lỗi hệ thống không xác định", 500),

    # 1.2 User Service (1000–1999)
    "E1000": ErrorDef(1000, "Tài khoản đã tồn tại", 409),
    "E1001": ErrorDef(1001, "Email đã tồn tại", 409),
    "E1002": ErrorDef(1002, "Số điện thoại đã tồn tại", 409),
    "E1003": ErrorDef(1003, "Tài khoản bị khóa", 403),
    "E1004": ErrorDef(1004, "Tài khoản không tồn tại", 404),
    "E1005": ErrorDef(1005, "Sai tên đăng nhập hoặc mật khẩu", 401),
    "E1006": ErrorDef(1006, "Username đã tồn tại", 409),
    "E1007": ErrorDef(1007, "Không thể xóa tài khoản", 409),
    "E1010": ErrorDef(1010, "Tên người dùng không hợp lệ", 400),
    "E1011": ErrorDef(1011, "Email không hợp lệ", 400),
    "E1012": ErrorDef(1012, "Số điện thoại không hợp lệ", 400),
    "E1013": ErrorDef(1013, "Địa chỉ không hợp lệ", 400),
    "E1014": ErrorDef(1014, "Mật khẩu không hợp lệ", 400),
    "E1015": ErrorDef(1015, "Trường dữ liệu bị thiếu", 400),
    "E1020": ErrorDef(1020, "Token không hợp lệ", 401),
    "E1021": ErrorDef(1021, "Token đã hết hạn", 401),
    "E1022": ErrorDef(1022, "Không có quyền truy cập", 403),
    "E1023": ErrorDef(1023, "Không thể xác thực", 401),
    "E1024": ErrorDef(1024, "Mật khẩu hiện tại không chính xác", 401),
    "E1030": ErrorDef(1030, "Lỗi máy chủ nội bộ", 500),
    "E1031": ErrorDef(1031, "Không thể kết nối cơ sở dữ liệu", 500),
    "E1032": ErrorDef(1032, "Thao tác không thành công", 500),
    "E1040": ErrorDef(1040, "Quá nhiều yêu cầu", 429),
    "E1041": ErrorDef(1041, "Đã đạt giới hạn tạo tài khoản", 429),
    "E1999": ErrorDef(1999, "Lỗi không xác định", 500),

    # 1.3 Authentication/Authorization Service (2000–2999)
    "E2000": ErrorDef(2000, "Tên đăng nhập hoặc mật khẩu không đúng", 401),
    "E2001": ErrorDef(2001, "Tài khoản đã bị vô hiệu hóa", 403),
    "E2002": ErrorDef(2002, "Bạn chưa đăng nhập", 403),
    "E2003": ErrorDef(2003, "Quá nhiều lần thử đăng nhập thất bại", 429),
    "E2010": ErrorDef(2010, "Token không hợp lệ", 401),
    "E2011": ErrorDef(2011, "Token đã hết hạn", 401),
    "E2012": ErrorDef(2012, "Token đã bị thu hồi", 401),
    "E2013": ErrorDef(2013, "Thiếu thông tin xác thực", 401),
    "E2014": ErrorDef(2014, "Thiếu thông tin xác thực", 401),
    "E2020": ErrorDef(2020, "Không có quyền truy cập vào tài nguyên này", 403),
    "E2021": ErrorDef(2021, "Vai trò người dùng không được phép thực hiện hành động này", 403),
    "E2022": ErrorDef(2022, "Người dùng không có quyền này", 404),
    "E2024": ErrorDef(2024, "Quyền này không tồn tại", 404),
    "E2025": ErrorDef(2025, "Cần đăng nhập để thực hiện hành động này", 401),
    "E2030": ErrorDef(2030, "Email đã được sử dụng", 409),
    "E2031": ErrorDef(2031, "Tên đăng nhập đã được sử dụng", 409),
    "E2032": ErrorDef(2032, "Mật khẩu không đáp ứng yêu cầu bảo mật", 400),
    "E2033": ErrorDef(2033, "Xác nhận mật khẩu không khớp", 400),
    "E2040": ErrorDef(2040, "Mã OTP không chính xác", 400),
    "E2041": ErrorDef(2041, "Mã OTP đã hết hạn", 400),
    "E2042": ErrorDef(2042, "Mã OTP đã được sử dụng", 400),
    "E2043": ErrorDef(2043, "2FA chưa được bật cho tài khoản", 403),
    "E2050": ErrorDef(2050, "Refresh token không hợp lệ", 401),
    "E2051": ErrorDef(2051, "Refresh token đã hết hạn", 401),
    "E2999": ErrorDef(2999, "Lỗi không xác định trong dịch vụ xác thực/phân quyền", 500),

    # 1.4 Payment Service (3000–3999)
    "E3000": ErrorDef(3000, "Giao dịch không thành công", 400),
    "E3001": ErrorDef(3001, "Số dư không đủ để thực hiện giao dịch", 402),
    "E3002": ErrorDef(3002, "Phương thức thanh toán không được hỗ trợ", 400),
    "E3003": ErrorDef(3003, "Giao dịch bị hủy bởi người dùng", 400),
    "E3004": ErrorDef(3004, "Mã giao dịch không hợp lệ", 404),
    "E3010": ErrorDef(3010, "Lỗi xác thực thẻ tín dụng/thẻ ghi nợ", 401),
    "E3011": ErrorDef(3011, "Thẻ tín dụng đã hết hạn", 402),
    "E3012": ErrorDef(3012, "Thẻ tín dụng bị từ chối", 402),
    "E3013": ErrorDef(3013, "OTP thanh toán không chính xác", 400),
    "E3014": ErrorDef(3014, "OTP thanh toán đã hết hạn", 400),
    "E3020": ErrorDef(3020, "Hệ thống thanh toán không phản hồi", 503),
    "E3021": ErrorDef(3021, "Thời gian xử lý giao dịch bị quá hạn", 504),
    "E3022": ErrorDef(3022, "Lỗi không xác định từ cổng thanh toán", 502),
    "E3023": ErrorDef(3023, "Không thể kết nối tới hệ thống ngân hàng", 503),
    "E3030": ErrorDef(3030, "Không thể thực hiện hoàn tiền", 400),
    "E3031": ErrorDef(3031, "Yêu cầu hoàn tiền không hợp lệ", 400),
    "E3032": ErrorDef(3032, "Giao dịch không đủ điều kiện hoàn tiền", 403),
    "E3033": ErrorDef(3033, "Hoàn tiền đã được thực hiện trước đó", 409),
    "E3040": ErrorDef(3040, "Đã vượt quá hạn mức giao dịch trong ngày", 429),
    "E3041": ErrorDef(3041, "Số tiền giao dịch vượt quá hạn mức cho phép", 400),
    "E3042": ErrorDef(3042, "Số lần giao dịch vượt quá giới hạn", 429),
    "E3999": ErrorDef(3999, "Lỗi không xác định trong dịch vụ thanh toán", 500),

    # 1.5 Notification Service (4000–4999)
    "E4000": ErrorDef(4000, "Gửi thông báo không thành công", 500),
    "E4001": ErrorDef(4001, "Thông tin người nhận không hợp lệ", 400),
    "E4002": ErrorDef(4002, "Nội dung thông báo bị thiếu", 400),
    "E4003": ErrorDef(4003, "Phương thức gửi thông báo không được hỗ trợ", 400),
    "E4010": ErrorDef(4010, "Không thể gửi email", 500),
    "E4011": ErrorDef(4011, "Địa chỉ email không hợp lệ", 400),
    "E4012": ErrorDef(4012, "SMTP server không phản hồi", 503),
    "E4013": ErrorDef(4013, "Quá giới hạn gửi email trong ngày", 429),
    "E4014": ErrorDef(4014, "Địa chỉ email người nhận bị từ chối", 400),
    "E4020": ErrorDef(4020, "Không thể gửi SMS", 500),
    "E4021": ErrorDef(4021, "Số điện thoại không hợp lệ", 400),
    "E4022": ErrorDef(4022, "Nhà cung cấp dịch vụ SMS không phản hồi", 503),
    "E4023": ErrorDef(4023, "Quá giới hạn gửi OTP trong ngày", 429),
    "E4024": ErrorDef(4024, "Mã OTP không được gửi thành công", 500),
    "E4030": ErrorDef(4030, "Không thể gửi thông báo đẩy", 500),
    "E4031": ErrorDef(4031, "Thiết bị nhận thông báo không hợp lệ", 400),
    "E4032": ErrorDef(4032, "Token thiết bị không hợp lệ hoặc hết hạn", 401),
    "E4033": ErrorDef(4033, "Dịch vụ thông báo đẩy không phản hồi", 503),
    "E4040": ErrorDef(4040, "Quá giới hạn số lượng thông báo gửi trong ngày", 429),
    "E4041": ErrorDef(4041, "Yêu cầu gửi thông báo bị từ chối do giới hạn", 429),
    "E4999": ErrorDef(4999, "Lỗi không xác định trong dịch vụ thông báo", 500),

    # 1.6 Data Service (5000–5999)
    "E5000": ErrorDef(5000, "Lỗi xử lý dữ liệu", 500),
    "E5001": ErrorDef(5001, "Dữ liệu đầu vào không hợp lệ", 400),
    "E5002": ErrorDef(5002, "Không thể tải dữ liệu", 500),
    "E5003": ErrorDef(5003, "Dữ liệu vượt quá kích thước cho phép", 413),
    "E5010": ErrorDef(5010, "Không thể tải tệp lên", 500),
    "E5011": ErrorDef(5011, "Định dạng tệp không được hỗ trợ", 400),
    "E5012": ErrorDef(5012, "Dung lượng tệp vượt quá giới hạn", 413),
    "E5013": ErrorDef(5013, "Thiếu dữ liệu hoặc tệp để tải lên", 400),
    "E5020": ErrorDef(5020, "Không thể tải tệp xuống", 500),
    "E5021": ErrorDef(5021, "Tệp không tồn tại", 404),
    "E5022": ErrorDef(5022, "Tệp bị hỏng hoặc không thể truy cập", 500),
    "E5023": ErrorDef(5023, "Yêu cầu tải xuống không hợp lệ", 400),
    "E5030": ErrorDef(5030, "Không đủ dung lượng lưu trữ", 507),
    "E5031": ErrorDef(5031, "Hạn mức lưu trữ đã đạt tối đa", 507),
    "E5032": ErrorDef(5032, "Không thể mở rộng dung lượng lưu trữ", 500),
    "E5040": ErrorDef(5040, "Không có quyền truy cập tệp", 403),
    "E5041": ErrorDef(5041, "Tệp bị bảo vệ hoặc quyền bị hạn chế", 403),
    "E5999": ErrorDef(5999, "Lỗi không xác định trong dịch vụ dữ liệu", 500),

    # 2.1 Web bán hàng (10000–19999)
    "E10000": ErrorDef(10000, "Lỗi không xác định trong hệ thống web bán hàng", 500),
    "E10001": ErrorDef(10001, "Yêu cầu không hợp lệ", 400),
    "E10002": ErrorDef(10002, "Tham số yêu cầu bị thiếu", 400),
    "E10003": ErrorDef(10003, "Quyền truy cập bị từ chối", 403),
    "E10100": ErrorDef(10100, "Không tìm thấy người dùng", 404),
    "E10101": ErrorDef(10101, "Người dùng không có quyền thực hiện hành động này", 403),
    "E10102": ErrorDef(10102, "Không tìm thấy nhóm", 404),
    "E10103": ErrorDef(10103, "Thành viên nhóm không hợp lệ", 400),
    "E10104": ErrorDef(10104, "Quyền hạn không hợp lệ", 400),
    "E10110": ErrorDef(10110, "Nhóm không tồn tại", 400),
    "E10200": ErrorDef(10200, "Không tìm thấy sản phẩm", 404),
    "E10201": ErrorDef(10201, "Sản phẩm đã hết hàng", 400),
    "E10202": ErrorDef(10202, "Danh mục không tồn tại", 404),
    "E10203": ErrorDef(10203, "Không thể thêm sản phẩm vào danh mục", 500),
    "E10204": ErrorDef(10204, "Sản phẩm thiếu các lựa chọn", 500),
    "E10300": ErrorDef(10300, "Không tìm thấy giỏ hàng", 404),
    "E10301": ErrorDef(10301, "Không thể thêm sản phẩm vào giỏ hàng", 500),
    "E10302": ErrorDef(10302, "Không tìm thấy danh sách yêu thích", 404),
    "E10303": ErrorDef(10303, "Không thể thêm sản phẩm vào danh sách yêu thích", 500),
    "E10400": ErrorDef(10400, "Phiếu giảm giá không tồn tại", 404),
    "E10401": ErrorDef(10401, "Phiếu giảm giá đã hết hạn", 400),
    "E10402": ErrorDef(10402, "Phiếu giảm giá không hợp lệ", 400),
    "E10403": ErrorDef(10403, "Không thể áp dụng phiếu giảm giá", 500),
    "E10500": ErrorDef(10500, "Không tìm thấy đơn hàng", 404),
    "E10501": ErrorDef(10501, "Không thể tạo đơn hàng", 500),
    "E10502": ErrorDef(10502, "Chi tiết đơn hàng không hợp lệ", 400),
    "E10503": ErrorDef(10503, "Không thể hủy đơn hàng", 400),
    "E10504": ErrorDef(10504, "Không thể xác nhận thanh toán cho đơn hàng", 500),
    "E10600": ErrorDef(10600, "Không tìm thấy đánh giá", 404),
    "E10601": ErrorDef(10601, "Người dùng không thể đánh giá sản phẩm này", 403),
    "E10602": ErrorDef(10602, "Đánh giá không hợp lệ", 400),
    "E10603": ErrorDef(10603, "Không thể thêm đánh giá", 500),
    "E10700": ErrorDef(10700, "Id người dùng là bắt buộc", 400),
    "E10701": ErrorDef(10701, "Tên file là bắt buộc", 400),
    "E10702": ErrorDef(10702, "Kích thước file là bắt buộc", 400),
    "E10710": ErrorDef(10710, "Nhập thiếu thông tin bắt buộc", 400),
    "E10711": ErrorDef(10711, "Dữ liệu đầu vào không đúng định dạng", 400),
    "E19999": ErrorDef(19999, "Lỗi không xác định trong ứng dụng", 500),

    # 2.2 Web lưu trữ dữ liệu (20000–29999)
    "E20000": ErrorDef(20000, "File vượt quá kích thước cho phép", 413),
    "E20200": ErrorDef(20200, "File không tồn tại", 404),

    # 2.3 Mạng xã hội (30000–39999)
    "E30000": ErrorDef(30000, "Người dùng bị cấm", 403),
    "E30200": ErrorDef(30200, "Bài viết không tồn tại", 404),

    # 2.4 Ứng dụng khác (40000–49999)
    "E40000": ErrorDef(40000, "Lỗi không xác định trong ứng dụng", 500),
}


def get_error(key: str) -> ErrorDef:
    """Tra ErrorDef theo key; fallback E0000 nếu không tồn tại."""
    return ERROR_CODES.get(key, ERROR_CODES["E0000"])
