"""
ShopJwtKeyProvider - nguồn khóa JWT của shop, định địa chỉ bằng `kid` (RFC 7515 4.1.4).

Vì sao cần (đổi 2026-08-21, theo Xime 0.7.2+):

Một khóa tĩnh KHÔNG sống qua được lúc xoay khóa. Trong lúc đổi khóa thì token ký bằng khóa cũ
vẫn còn hạn (refresh token của shop có TTL 60 ngày) còn token ký bằng khóa mới đã tới, nên bên
verify phải giữ nhiều khóa cùng lúc và chọn theo từng token. `kid` là cách chuẩn để nói khóa
nào đã ký; không có nó thì không xoay được khóa mà không cắt dịch vụ - tức là mọi người dùng bị
đăng xuất, và đó đúng là lý do một khóa bị lộ vẫn nằm im hàng tháng trời.

Đây là điều kiện tiên quyết để vá được cảnh báo bảo mật 2026-08-01 (chuỗi ký HS256 nằm trong
git, app đã deploy): có chỗ này rồi thì đổi khóa là một lần deploy có gối đầu, không phải một
lần cắt dịch vụ.

Class này implement Protocol `JwtKeyProvider` của framework (một method `keys(kid)`), nên khi
nào shop chuyển sang middleware JWT của framework thì cắm thẳng vào `configure_jwt(...,
key_provider=ShopJwtKeyProvider)` mà không phải viết lại.

Hợp đồng của Protocol: `keys()` chỉ ĐỌC BỘ NHỚ, không bao giờ gọi mạng - nó chạy ở mọi request
đã xác thực. Ở đây khóa đọc từ application.yml lúc khởi động nên điều đó là hiển nhiên.

Key source for JWT verification, addressed by `kid`, implementing Xime's JwtKeyProvider.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence

from xime.core.config.runtime import RuntimeConfig
from xime.starters.jwt import KeyContext

logger = logging.getLogger(__name__)

# Thuật toán mặc định. Giữ HS256 như bản PHP gốc; đổi sang RS256/EdDSA thì khai jwt.algorithm
# và điền private_key_pem/public_key_pem thay cho secret.
# Default algorithm, unchanged from the original PHP implementation.
_DEFAULT_ALGORITHM = "HS256"
_DEFAULT_KEY_ID = "k1"


class ShopJwtKeyProvider:
    """Giữ khóa ĐANG ký + các khóa CŨ chỉ dùng để verify trong lúc xoay."""

    def __init__(self, config: RuntimeConfig) -> None:
        algorithm: str = config.get("jwt.algorithm", _DEFAULT_ALGORITHM)
        secret: str = config.get("jwt.secret", "dev-secret-CHANGE-IN-PRODUCTION")
        key_id: str = config.get("jwt.key_id", _DEFAULT_KEY_ID)

        # Khóa đang ký. `key_id` trở thành header `kid` của mọi token phát ra từ giờ.
        # The signing key; its key_id becomes the `kid` header of every new token.
        self._signing_key = KeyContext(algorithm=algorithm, secret=secret, key_id=key_id)

        # Khóa cũ: CHỈ verify, không bao giờ ký. Rỗng lúc bình thường; điền trong cửa sổ xoay
        # khóa rồi xóa đi khi mọi token cũ đã hết hạn (tối đa jwt.refresh_ttl).
        # Retired keys: verification only, populated only during a rotation window.
        self._by_kid: dict[str, KeyContext] = {key_id: self._signing_key}
        for entry in config.get("jwt.previous_keys", []) or []:
            old_kid = entry.get("kid")
            old_secret = entry.get("secret")
            if not old_kid or not old_secret:
                # Khai thiếu thì nói ra, đừng bỏ qua im lặng: một khóa cũ bị rơi nghĩa là một
                # nhóm người dùng bị đăng xuất mà không ai hiểu vì sao.
                # A dropped retired key logs out a group of users with no visible cause.
                logger.warning("jwt.previous_keys: bỏ qua mục thiếu kid hoặc secret: %r", entry)
                continue
            if old_kid == key_id:
                logger.warning(
                    "jwt.previous_keys chứa kid '%s' trùng với jwt.key_id đang ký - bỏ qua mục cũ",
                    old_kid,
                )
                continue
            self._by_kid[old_kid] = KeyContext(
                algorithm=entry.get("algorithm", algorithm),
                secret=old_secret,
                key_id=old_kid,
            )

        # Token phát TRƯỚC lần nâng cấp này không mang `kid`. Chấp nhận chúng cho tới khi hết
        # hạn, nếu không thì ngay lần deploy đầu tiên mọi phiên đang mở đều bị đăng xuất.
        # Tắt (accept_unkeyed: false) sau khi đã qua jwt.refresh_ttl kể từ lần deploy đó.
        # Accept tokens minted before this upgrade (no `kid`) until they expire.
        self._accept_unkeyed: bool = config.get("jwt.accept_unkeyed", True)

    @property
    def signing_key(self) -> KeyContext:
        """Khóa dùng để KÝ. Chỉ có một, luôn là khóa mới nhất."""
        return self._signing_key

    def keys(self, kid: str | None) -> Sequence[KeyContext]:
        """Trả về các khóa ứng viên cho một `kid`.

        Dãy rỗng nghĩa là "tôi không biết kid này" -> request bị từ chối. Đó không phải lỗi và
        không được thử lại (hợp đồng của JwtKeyProvider).
        An empty sequence means "unknown kid" and the caller rejects the request.
        """
        if kid is None:
            # Không có kid: token cũ trước khi xoay khóa được bật. Trả MỌI khóa đang giữ để
            # thử lần lượt - chi phí là vài phép kiểm chữ ký, chỉ trong cửa sổ chuyển tiếp.
            return tuple(self._by_kid.values()) if self._accept_unkeyed else ()
        found = self._by_kid.get(kid)
        return (found,) if found else ()
