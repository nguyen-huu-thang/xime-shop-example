"""
ProductService - quản lý sản phẩm + điều phối thuộc tính/option (phân loại sản phẩm).
Port từ ProductService.php.

ProductService là service điều phối cấp cao: nó mở MỘT transaction cho mỗi thao tác và ủy thác
logic phân loại sản phẩm (thuộc tính / giá trị thuộc tính / option / liên kết option-value) cho
4 collaborator: ProductAttributeService, ProductAttributeValueService, ProductOptionService,
ProductOptionValueService. Các collaborator này transaction-agnostic (không tự mở transaction),
nên toàn bộ tạo/sửa sản phẩm + biến thể nằm trong một transaction atomic duy nhất.

ProductService is the orchestrator: it opens one transaction per operation and delegates the
product-classification logic to four transaction-agnostic collaborator services, keeping each
create/update atomic.
"""
from __future__ import annotations

import json

from xime.core.transaction.manager import TransactionManager
from xime.starters.cache import CacheService

from app.entity.product import Product
from app.entity.product_attribute import ProductAttribute
from app.entity.product_attribute_value import ProductAttributeValue
from app.entity.product_option import ProductOption
from app.entity.product_option_value import ProductOptionValue
from app.exception.app_exception import AppException
from app.repository.category_repository import CategoryRepository
from app.repository.file_repository import FileRepository
from app.repository.product_repository import ProductRepository
from app.service.product_attribute_service import ProductAttributeService
from app.service.product_attribute_value_service import ProductAttributeValueService
from app.service.product_option_service import ProductOptionService
from app.service.product_option_value_service import ProductOptionValueService
from app.service import pricing


class ProductService:
    # Cache keys cho catalog đọc nhiều. TTL ngắn để dữ liệu không quá cũ.
    # Cache keys for hot catalog reads. Short TTL so data is never too stale.
    _CACHE_ALL = "product:all"
    _CACHE_TTL = 300  # giây / seconds

    def __init__(
        self,
        transaction: TransactionManager,
        cache: CacheService,
        product_repository: ProductRepository,
        category_repository: CategoryRepository,
        file_repository: FileRepository,
        product_attribute_service: ProductAttributeService,
        product_attribute_value_service: ProductAttributeValueService,
        product_option_service: ProductOptionService,
        product_option_value_service: ProductOptionValueService,
    ) -> None:
        self._transaction = transaction
        self._cache = cache
        self._product_repo = product_repository
        self._category_repo = category_repository
        self._file_repo = file_repository
        self._attr_svc = product_attribute_service
        self._attr_val_svc = product_attribute_value_service
        self._option_svc = product_option_service
        self._option_val_svc = product_option_value_service

    # ─── Cache helpers ──────────────────────────────────────────────

    @staticmethod
    def _product_key(product_id: int) -> str:
        return f"product:{product_id}"

    async def _cache_get_json(self, key: str):
        raw = await self._cache.get(key)
        return json.loads(raw) if raw is not None else None

    async def _cache_set_json(self, key: str, value) -> None:
        # default=float: an toàn nếu DTO lỡ chứa Decimal (Numeric column).
        # default=float: safe if a DTO happens to carry a Decimal value.
        payload = json.dumps(value, default=float).encode("utf-8")
        await self._cache.set(key, payload, ttl=self._CACHE_TTL)

    async def invalidate_cache(self, product_id: int | None = None) -> None:
        """Public: xóa cache danh sách + chi tiết một sản phẩm. Gọi từ nơi khác (vd OrderService)
        khi tồn kho đổi do đặt/hủy đơn, để `GET /products` không hiển thị tồn kho cũ."""
        await self._invalidate_product_cache(product_id)

    async def _invalidate_product_cache(self, product_id: int | None = None) -> None:
        # Xóa cache danh sách tổng + cache chi tiết của product bị thay đổi.
        # Drop the full-list cache + the changed product's detail cache.
        await self._cache.delete(self._CACHE_ALL)
        if product_id is not None:
            await self._cache.delete(self._product_key(product_id))

    # ─── Read helpers ──────────────────────────────────────────────

    # Các _helper dưới đây KHÔNG tự mở transaction - chúng phải chạy bên trong một
    # transaction do method đọc cấp trên mở (gom N+1 về một transaction duy nhất).
    # The _helpers below run inside a transaction opened by the calling read method.

    @staticmethod
    def _build_attributes(
        attrs: list[ProductAttribute],
        vals_by_attr: dict[int, list[ProductAttributeValue]],
    ) -> dict[str, list[str]]:
        """Return {attr_name: [value, ...]} từ map đã nạp sẵn (thuần RAM, 0 query).
        Logic giống hệt _get_attributes_dict cũ, chỉ đọc từ map thay vì query từng attribute."""
        result: dict[str, list[str]] = {}
        for attr in attrs:
            vals = vals_by_attr.get(attr.id, [])
            result[attr.name] = [v.value for v in vals]
        return result

    async def _find_option_default(self, product_id: int) -> ProductOption | None:
        """Return the 'default' option (only 1 option, or the one with no option_values).
        Trả về option mặc định. Chạy trong transaction đang mở.
        """
        options = await self._option_svc.find_by_product_id(product_id)
        if len(options) == 1:
            return options[0]
        for opt in options:
            values = await self._option_val_svc.find_by_option_id(opt.id)
            if not values:
                return opt
        return None

    @staticmethod
    def _calc_price_stock(
        options: list[ProductOption],
        optvals_by_option: dict[int, list[ProductOptionValue]],
    ) -> dict:
        """Tính giá + tồn kho từ map đã nạp sẵn (thuần RAM, 0 query).
        Logic giống hệt _get_price_and_stock cũ."""
        if len(options) == 1:
            price = options[0].price
            return {
                "prices": float(price) if price is not None else None,
                "stock": options[0].stock,
            }

        # Filter out default (no-value) option from price calculation
        # Bỏ option mặc định (không có value) khỏi tính giá
        priced_options: list[ProductOption] = [
            opt for opt in options if optvals_by_option.get(opt.id)
        ]

        prices = [float(o.price) for o in priced_options if o.price is not None]
        total_stock = sum(o.stock for o in priced_options)
        return {
            "prices": min(prices) if prices else None,
            "stock": total_stock,
        }

    async def _to_dtos(self, products: list[Product]) -> list[dict]:
        """Serialize nhiều product trong MỘT lượt batch (chống N+1). Chạy trong transaction đang mở.

        Thay vì query thuộc tính/option theo từng sản phẩm (N+1), nạp tất cả bằng 4 query
        `WHERE ... IN (...)` rồi ráp DTO trong RAM. DTO trả ra giống hệt _to_dto từng-cái cũ.

        Serialize many products in one batch (avoid N+1): four IN-queries then assemble in RAM.
        """
        if not products:
            return []

        product_ids = {p.id for p in products}

        # 4 batch query: attributes -> values, options -> option_values
        attrs = await self._attr_svc.find_by_product_ids(product_ids)
        attr_ids = {a.id for a in attrs}
        vals = await self._attr_val_svc.find_by_attribute_ids(attr_ids)
        options = await self._option_svc.find_by_product_ids(product_ids)
        option_ids = {o.id for o in options}
        optvals = await self._option_val_svc.find_by_option_ids(option_ids)

        # Gom theo khóa cha để tra trong RAM
        # Group by parent key for in-memory lookup
        attrs_by_product: dict[int, list[ProductAttribute]] = {}
        for a in attrs:
            attrs_by_product.setdefault(a.product_id, []).append(a)
        vals_by_attr: dict[int, list[ProductAttributeValue]] = {}
        for v in vals:
            vals_by_attr.setdefault(v.attribute_id, []).append(v)
        opts_by_product: dict[int, list[ProductOption]] = {}
        for o in options:
            opts_by_product.setdefault(o.product_id, []).append(o)
        optvals_by_option: dict[int, list[ProductOptionValue]] = {}
        for ov in optvals:
            optvals_by_option.setdefault(ov.option_id, []).append(ov)

        # Ảnh đại diện mỗi sản phẩm: file đang hoạt động đầu tiên (theo sort) - 1 batch query.
        # Primary image per product: the first active file (by sort) - single batch query.
        images = await self._file_repo.find_active_by_targets("products", product_ids)
        image_by_product: dict[int, str] = {}
        for f in images:
            if f.target_id is not None and f.target_id not in image_by_product:
                image_by_product[f.target_id] = f.file_path

        result: list[dict] = []
        for product in products:
            attributes = self._build_attributes(
                attrs_by_product.get(product.id, []), vals_by_attr
            )
            price_stock = self._calc_price_stock(
                opts_by_product.get(product.id, []), optvals_by_option
            )
            result.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "locationAddress": product.location_address,
                    "categoryId": product.category_id,
                    "description": product.description,
                    "price": price_stock["prices"],
                    "stock": price_stock["stock"],
                    "attribute": attributes,
                    "discountPercentage": product.discount_percentage,
                    # Đường dẫn ảnh đại diện (file_path); FE dựng URL qua /media/{path}. None nếu chưa có ảnh.
                    # Primary image path; the FE builds the URL via /media/{path}.
                    "imageUrl": image_by_product.get(product.id),
                }
            )
        return result

    async def _to_dto(self, product: Product) -> dict:
        """Serialize một product. Ủy thác cho _to_dtos để dùng chung logic (tránh lệch)."""
        dtos = await self._to_dtos([product])
        return dtos[0]

    async def to_dto(self, product: Product) -> dict:
        """Serialize product to dict trong MỘT transaction (dùng sau các write method)."""
        async with self._transaction():
            return await self._to_dto(product)

    # ─── Public read methods ────────────────────────────────────────

    async def get_all_product_dtos(self) -> list[dict]:
        cached = await self._cache_get_json(self._CACHE_ALL)
        if cached is not None:
            return cached
        async with self._transaction():
            products = await self._product_repo.find_all()
            result = await self._to_dtos([p for p in products if not p.is_delete])
        await self._cache_set_json(self._CACHE_ALL, result)
        return result

    async def count_products(self) -> int:
        # Total non-deleted products (for FE pagination).
        # Tổng sản phẩm chưa xóa mềm (phục vụ phân trang FE).
        async with self._transaction():
            return await self._product_repo.count_active()

    async def get_paginated_product_dtos(self, page: int, limit: int) -> list[dict]:
        async with self._transaction():
            products = await self._product_repo.find_all_paginated(page, limit)
            return await self._to_dtos(products)

    async def get_managed_product_dtos(
        self, allowed_category_ids: set[int] | None, page: int, limit: int
    ) -> list[dict]:
        """Danh sách sản phẩm cho quản trị, lọc theo mảng category được phép.
        allowed_category_ids None = không lọc (superadmin/toàn quyền)."""
        async with self._transaction():
            if allowed_category_ids is None:
                products = await self._product_repo.find_all_paginated(page, limit)
            else:
                products = await self._product_repo.find_paginated_in_categories(
                    allowed_category_ids, page, limit
                )
            return await self._to_dtos(products)

    async def count_managed_products(self, allowed_category_ids: set[int] | None) -> int:
        async with self._transaction():
            if allowed_category_ids is None:
                return await self._product_repo.count_active()
            return await self._product_repo.count_active_in_categories(allowed_category_ids)

    async def get_product_by_id(self, product_id: int) -> Product:
        async with self._transaction():
            product = await self._product_repo.find(product_id)
        if not product or product.is_delete:
            raise AppException("E10200")
        return product

    async def get_product_dto_by_id(self, product_id: int) -> dict:
        key = self._product_key(product_id)
        cached = await self._cache_get_json(key)
        if cached is not None:
            return cached
        async with self._transaction():
            product = await self._product_repo.find(product_id)
            if not product or product.is_delete:
                raise AppException("E10200")
            dto = await self._to_dto(product)
        await self._cache_set_json(key, dto)
        return dto

    async def find_products_by_category_id(self, category_id: int) -> list[Product]:
        async with self._transaction():
            return await self._product_repo.find_by_category_id(category_id)

    async def get_product_dtos_by_ids(self, ordered_ids: list[int]) -> list[dict]:
        """Dựng DTO cho danh sách product_id, GIỮ NGUYÊN thứ tự truyền vào, bỏ id không tồn tại/đã xóa.
        Dùng cho gợi ý (đã xem gần đây / thịnh hành / for-you) - đã batch nên không N+1."""
        if not ordered_ids:
            return []
        async with self._transaction():
            products = await self._product_repo.find_by_ids(set(ordered_ids))
            dtos = await self._to_dtos(products)
        by_id = {d["id"]: d for d in dtos}
        return [by_id[i] for i in ordered_ids if i in by_id]

    async def get_products_by_category_id(self, category_id: int) -> list[dict]:
        async with self._transaction():
            products = await self._product_repo.find_by_category_id(category_id)
            return await self._to_dtos([p for p in products if not p.is_delete])

    async def search_products_by_keywords(self, keywords: str) -> list[dict]:
        async with self._transaction():
            products = await self._product_repo.search_by_keywords(keywords)
            return await self._to_dtos(products)

    async def get_option_default(self, product: Product) -> dict:
        async with self._transaction():
            opt = await self._find_option_default(product.id)
        if not opt:
            raise AppException("E10204")
        return {"id": opt.id, "prices": opt.price, "stock": opt.stock}

    async def get_cart_item_detail(self, option_id: int) -> dict:
        """Return product name + option price + option values for a cart line.
        Trả về tên sản phẩm + đơn giá option + các giá trị option cho một dòng giỏ hàng.
        Gom trong MỘT transaction để tránh N+1 khi render giỏ hàng.
        """
        async with self._transaction():
            opt = await self._option_svc.find_by_id(option_id)
            if not opt:
                raise AppException("E10502")
            product = await self._product_repo.find(opt.product_id)

            option_vals: dict[str, str] = {}
            opt_values = await self._option_val_svc.find_by_option_id(option_id)
            for ov in opt_values:
                pav = await self._attr_val_svc.find_by_id(ov.attribute_value_id)
                if not pav:
                    continue
                attr = await self._attr_svc.find_by_id(pav.attribute_id)
                if attr:
                    option_vals[attr.name] = pav.value

            # Đơn giá hiển thị ở giỏ = giá option đã trừ % giảm giá sản phẩm (khớp giá tính tiền).
            # Cart display unit price = option price after the product percent discount.
            if opt.price is None:
                unit_price = None
            else:
                discount = product.discount_percentage if product else 0
                unit_price = float(pricing.apply_percent_discount(opt.price, discount))
            return {
                "productId": opt.product_id,
                "productName": product.name if product else None,
                "price": unit_price,
                "optionValues": option_vals,
            }

    async def get_values_by_option_id(self, option_id: int) -> dict[str, str]:
        """Return {attr_name: value} for an option (một transaction duy nhất).
        Trả về {tên thuộc tính: giá trị} cho một option.
        """
        async with self._transaction():
            opt = await self._option_svc.find_by_id(option_id)
            if not opt:
                raise AppException("E10502")
            option_vals = await self._option_val_svc.find_by_option_id(option_id)
            result: dict[str, str] = {}
            for ov in option_vals:
                pav = await self._attr_val_svc.find_by_id(ov.attribute_value_id)
                if not pav:
                    continue
                attr = await self._attr_svc.find_by_id(pav.attribute_id)
                if attr:
                    result[attr.name] = pav.value
            return result

    # ─── Write methods ──────────────────────────────────────────────

    async def create_product(self, data: dict) -> dict:
        """Create product + default option (atomic single transaction).
        Tạo sản phẩm + option mặc định trong một transaction.
        """
        name = data.get("name") or ""
        if not name:
            raise AppException("E0003")   # Required parameter missing
        location = data.get("locationAddress") or ""
        if not location:
            raise AppException("E0003")   # Required parameter missing

        category_id: int | None = data.get("categoryId") or data.get("category_id")
        if category_id:
            async with self._transaction():
                cat = await self._category_repo.find(category_id)
            if not cat:
                raise AppException("E10202")  # Category not found

        async with self._transaction():
            product = Product(
                name=name,
                location_address=location,
                description=data.get("description"),
                category_id=category_id,
                discount_percentage=data.get("discountPercentage", 0),
            )
            product = await self._product_repo.save(product)

            # Create attributes and attribute values (delegate to collaborators)
            # Tạo thuộc tính và giá trị thuộc tính (ủy thác cho collaborator)
            attribute_data: dict = data.get("attribute") or {}
            for attr_name, values in attribute_data.items():
                if not isinstance(values, list):
                    raise AppException("E10203")
                attr = await self._attr_svc.create_product_attribute(product.id, attr_name)
                for val in values:
                    await self._attr_val_svc.create_product_attribute_value(attr.id, str(val))

            # Create default ProductOption (no option_values)
            # Tạo ProductOption mặc định (không có option_values)
            price = data.get("price")
            if price is not None and price < 0:
                price = None
            stock = data.get("stock") or 0
            if stock < 0:
                stock = 0
            await self._option_svc.create_product_option(product.id, price, stock)

        await self._invalidate_product_cache(product.id)
        return await self.to_dto(product)

    async def update_product(self, product_id: int, data: dict) -> dict:
        await self.get_product_by_id(product_id)  # validate tồn tại + chưa xóa mềm

        async with self._transaction():
            db_product = await self._product_repo.find(product_id)
            if not db_product:
                raise AppException("E10200")

            if data.get("name"):
                db_product.name = data["name"]
            if data.get("locationAddress"):
                db_product.location_address = data["locationAddress"]
            if data.get("description"):
                db_product.description = data["description"]
            if "discountPercentage" in data:
                db_product.discount_percentage = data["discountPercentage"]

            category_id = data.get("categoryId") or data.get("category_id")
            if category_id:
                cat = await self._category_repo.find(category_id)
                if not cat:
                    raise AppException("E10202")  # Danh mục không tồn tại (404)
                db_product.category_id = category_id

            await self._product_repo.save(db_product)

            # Update default option price/stock (delegate)
            # Cập nhật giá + tồn kho của option mặc định (ủy thác)
            default_opt = await self._find_option_default(product_id)
            if default_opt:
                await self._option_svc.update_product_option(
                    default_opt, data.get("price"), data.get("stock")
                )

            # Update/add attributes (delegate)
            # Cập nhật / thêm thuộc tính (ủy thác)
            attribute_data: dict = data.get("attribute") or {}
            for attr_name, values in attribute_data.items():
                attr = await self._attr_svc.find_by_name_and_product_id(attr_name, product_id)
                if not attr:
                    attr = await self._attr_svc.create_product_attribute(product_id, attr_name)

                current_vals = await self._attr_val_svc.find_by_attribute_id(attr.id)
                existing = {v.value: v for v in current_vals}

                for val_str in values:
                    if val_str not in existing:
                        await self._attr_val_svc.create_product_attribute_value(
                            attr.id, str(val_str)
                        )

                for v in current_vals:
                    if v.value not in values:
                        await self._attr_val_svc.delete_product_attribute_value(v.id)

        await self._invalidate_product_cache(product_id)
        return await self.to_dto(db_product)

    async def delete_product(self, product_id: int) -> None:
        """Soft delete (is_delete=True). Port từ PHP deleteProduct."""
        async with self._transaction():
            product = await self._product_repo.find(product_id)
        if not product or product.is_delete:
            raise AppException("E10200")
        async with self._transaction():
            db_product = await self._product_repo.find(product_id)
            if db_product:
                db_product.is_delete = True
                await self._product_repo.save(db_product)
        await self._invalidate_product_cache(product_id)

    async def update_or_create_product_attributes_and_options(
        self, product_id: int, json_data: dict
    ) -> None:
        """Sync attributes + options from structured data (atomic). Ủy thác cho collaborator.
        Đồng bộ thuộc tính + option từ dữ liệu có cấu trúc.

        Input format: {
          "attribute": ["size", "color"],
          "value": [
            [["S", "red"], [price, stock]],
            [["M", "blue"], [price, stock]],
          ]
        }
        """
        await self.get_product_by_id(product_id)  # validate tồn tại

        attributes: list[str] = json_data.get("attribute") or []
        values: list = json_data.get("value") or []
        if not attributes or not values:
            raise AppException("E10203")

        async with self._transaction():
            # Ensure ProductAttribute rows exist
            # Đảm bảo các ProductAttribute tồn tại
            attr_entities: list[ProductAttribute] = []
            for attr_name in attributes:
                attr = await self._attr_svc.find_by_name_and_product_id(attr_name, product_id)
                if not attr:
                    attr = await self._attr_svc.create_product_attribute(product_id, attr_name)
                attr_entities.append(attr)

            for value_set in values:
                attr_values: list = value_set[0] if len(value_set) > 0 else []
                option_data: list = value_set[1] if len(value_set) > 1 else []
                price = option_data[0] if len(option_data) > 0 else None
                stock = option_data[1] if len(option_data) > 1 else 0

                if len(attr_values) != len(attributes) or price is None or stock is None:
                    raise AppException("E10203")

                # Ensure ProductAttributeValue rows exist
                # Đảm bảo các ProductAttributeValue tồn tại
                pav_entities: list[ProductAttributeValue] = []
                for idx, val in enumerate(attr_values):
                    attr = attr_entities[idx]
                    pav = await self._attr_val_svc.find_by_value_and_attribute_id(
                        str(val), attr.id
                    )
                    if not pav:
                        pav = await self._attr_val_svc.create_product_attribute_value(
                            attr.id, str(val)
                        )
                    else:
                        pav = await self._attr_val_svc.update_product_attribute_value(
                            pav, str(val)
                        )
                    pav_entities.append(pav)

                # Find or create matching ProductOption
                # Tìm hoặc tạo ProductOption phù hợp
                pav_ids = {p.id for p in pav_entities}
                options = await self._option_svc.find_by_product_id(product_id)
                existing_option: ProductOption | None = None
                for opt in options:
                    opt_vals = await self._option_val_svc.find_by_option_id(opt.id)
                    if {ov.attribute_value_id for ov in opt_vals} == pav_ids:
                        existing_option = opt
                        break

                if not existing_option:
                    opt = await self._option_svc.create_product_option(
                        product_id, price, stock
                    )
                else:
                    opt = await self._option_svc.update_product_option(
                        existing_option, price, stock
                    )

                # Link option ↔ attribute_values
                # Liên kết option với attribute_values
                for pav in pav_entities:
                    exists = await self._option_val_svc.find_by_value_and_option(pav.id, opt.id)
                    if not exists:
                        await self._option_val_svc.create_product_option_value(opt.id, pav.id)

        await self._invalidate_product_cache(product_id)

    async def find_product_option_by_json(
        self, product: Product, data: dict
    ) -> ProductOption:
        """Find ProductOption matching the given attribute_name→value dict.
        Tìm ProductOption khớp dict {tên_thuộc_tính: giá_trị}.
        """
        async with self._transaction():
            pav_ids: list[int] = []
            for attr_name, attr_value in data.items():
                attr = await self._attr_svc.find_by_name_and_product_id(
                    attr_name, product.id
                )
                if not attr:
                    raise AppException("E10203")
                pav = await self._attr_val_svc.find_by_value_and_attribute_id(
                    str(attr_value), attr.id
                )
                if not pav:
                    raise AppException("E10203")
                pav_ids.append(pav.id)

            target = set(pav_ids)
            options = await self._option_svc.find_by_product_id(product.id)
            # Batch nạp toàn bộ option_values của các option trong 1 query (chống N+1),
            # gom theo option rồi so set trong RAM thay vì query từng option.
            # Batch load all option_values in one query then compare sets in RAM.
            option_ids = {o.id for o in options}
            optvals = await self._option_val_svc.find_by_option_ids(option_ids)
            vals_by_option: dict[int, set[int]] = {}
            for ov in optvals:
                vals_by_option.setdefault(ov.option_id, set()).add(
                    ov.attribute_value_id
                )
            for opt in options:
                if vals_by_option.get(opt.id, set()) == target:
                    return opt

        raise AppException("E10204")
