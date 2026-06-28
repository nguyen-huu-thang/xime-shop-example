"""
ProductService - quản lý sản phẩm + thuộc tính + option.
Port từ ProductService.php.

Lưu ý: create_product / updateOrCreate dùng repositories trực tiếp (single transaction).
Các sub-service được inject để dùng ở các thao tác đơn lẻ từ controller.
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
from app.repository.product_attribute_repository import ProductAttributeRepository
from app.repository.product_attribute_value_repository import ProductAttributeValueRepository
from app.repository.product_option_repository import ProductOptionRepository
from app.repository.product_option_value_repository import ProductOptionValueRepository
from app.repository.product_repository import ProductRepository


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
        product_attribute_repository: ProductAttributeRepository,
        product_attribute_value_repository: ProductAttributeValueRepository,
        product_option_repository: ProductOptionRepository,
        product_option_value_repository: ProductOptionValueRepository,
    ) -> None:
        self._transaction = transaction
        self._cache = cache
        self._product_repo = product_repository
        self._category_repo = category_repository
        self._attr_repo = product_attribute_repository
        self._attr_val_repo = product_attribute_value_repository
        self._option_repo = product_option_repository
        self._option_val_repo = product_option_value_repository

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

    async def _invalidate_product_cache(self, product_id: int | None = None) -> None:
        # Xóa cache danh sách tổng + cache chi tiết của product bị thay đổi.
        # Drop the full-list cache + the changed product's detail cache.
        await self._cache.delete(self._CACHE_ALL)
        if product_id is not None:
            await self._cache.delete(self._product_key(product_id))

    # ─── Read helpers ──────────────────────────────────────────────

    # Các _helper dưới đây KHÔNG tự mở transaction - chúng phải chạy bên trong một
    # transaction do method đọc cấp trên mở. Trước đây mỗi helper mở transaction riêng
    # trong vòng lặp gây N+1 (mỗi product cần nhiều transaction); nay gom về 1 transaction.
    # The _helpers below do NOT open their own transaction - they must run inside one
    # opened by the calling read method (gom N+1 về một transaction duy nhất).

    async def _get_attributes_dict(self, product_id: int) -> dict[str, list[str]]:
        """Return {attr_name: [value, ...]} for a product. Chạy trong transaction đang mở."""
        attrs = await self._attr_repo.find_by_product_id(product_id)
        result: dict[str, list[str]] = {}
        for attr in attrs:
            vals = await self._attr_val_repo.find_by_attribute_id(attr.id)
            result[attr.name] = [v.value for v in vals]
        return result

    async def _find_option_default(self, product_id: int) -> ProductOption | None:
        """Return the 'default' option (only 1 option, or the one with no option_values).
        Trả về option mặc định. Chạy trong transaction đang mở.
        """
        options = await self._option_repo.find_by_product_id(product_id)
        if len(options) == 1:
            return options[0]
        for opt in options:
            values = await self._option_val_repo.find_by_option_id(opt.id)
            if not values:
                return opt
        return None

    async def _get_price_and_stock(self, product_id: int) -> dict:
        """Tính giá + tồn kho. Chạy trong transaction đang mở."""
        options = await self._option_repo.find_by_product_id(product_id)
        if len(options) == 1:
            price = options[0].price
            return {
                "prices": float(price) if price is not None else None,
                "stock": options[0].stock,
            }

        # Filter out default (no-value) option from price calculation
        # Bỏ option mặc định (không có value) khỏi tính giá
        priced_options: list[ProductOption] = []
        for opt in options:
            vals = await self._option_val_repo.find_by_option_id(opt.id)
            if vals:
                priced_options.append(opt)

        prices = [float(o.price) for o in priced_options if o.price is not None]
        total_stock = sum(o.stock for o in priced_options)
        return {
            "prices": min(prices) if prices else None,
            "stock": total_stock,
        }

    async def _to_dto(self, product: Product) -> dict:
        """Serialize product to dict. Chạy trong transaction đang mở (không tự mở)."""
        attributes = await self._get_attributes_dict(product.id)
        price_stock = await self._get_price_and_stock(product.id)
        return {
            "id": product.id,
            "name": product.name,
            "locationAddress": product.location_address,
            "categoryId": product.category_id,
            "description": product.description,
            "price": price_stock["prices"],
            "stock": price_stock["stock"],
            "attribute": attributes,
            "discountPercentage": product.discount_percentage,
        }

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
            result = [await self._to_dto(p) for p in products if not p.is_delete]
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
            return [await self._to_dto(p) for p in products]

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

    async def get_products_by_category_id(self, category_id: int) -> list[dict]:
        async with self._transaction():
            products = await self._product_repo.find_by_category_id(category_id)
            return [await self._to_dto(p) for p in products if not p.is_delete]

    async def search_products_by_keywords(self, keywords: str) -> list[dict]:
        async with self._transaction():
            products = await self._product_repo.search_by_keywords(keywords)
            return [await self._to_dto(p) for p in products]

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
            opt = await self._option_repo.find(option_id)
            if not opt:
                raise AppException("E10502")
            product = await self._product_repo.find(opt.product_id)

            option_vals: dict[str, str] = {}
            opt_values = await self._option_val_repo.find_by_option_id(option_id)
            for ov in opt_values:
                pav = await self._attr_val_repo.find(ov.attribute_value_id)
                if not pav:
                    continue
                attr = await self._attr_repo.find(pav.attribute_id)
                if attr:
                    option_vals[attr.name] = pav.value

            return {
                "productId": opt.product_id,
                "productName": product.name if product else None,
                "price": float(opt.price) if opt.price is not None else None,
                "optionValues": option_vals,
            }

    async def get_values_by_option_id(self, option_id: int) -> dict[str, str]:
        """Return {attr_name: value} for an option (một transaction duy nhất).
        Trả về {tên thuộc tính: giá trị} cho một option.
        """
        async with self._transaction():
            opt = await self._option_repo.find(option_id)
            if not opt:
                raise AppException("E10502")
            option_vals = await self._option_val_repo.find_by_option_id(option_id)
            result: dict[str, str] = {}
            for ov in option_vals:
                pav = await self._attr_val_repo.find(ov.attribute_value_id)
                if not pav:
                    continue
                attr = await self._attr_repo.find(pav.attribute_id)
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

            # Create attributes and attribute values
            # Tạo thuộc tính và giá trị thuộc tính
            attribute_data: dict = data.get("attribute") or {}
            for attr_name, values in attribute_data.items():
                if not isinstance(values, list):
                    raise AppException("E10203")
                attr = ProductAttribute(product_id=product.id, name=attr_name)
                attr = await self._attr_repo.save(attr)
                for val in values:
                    pav = ProductAttributeValue(attribute_id=attr.id, value=str(val))
                    await self._attr_val_repo.save(pav)

            # Create default ProductOption (no option_values)
            # Tạo ProductOption mặc định (không có option_values)
            price = data.get("price")
            if price is not None and price < 0:
                price = None
            stock = data.get("stock") or 0
            if stock < 0:
                stock = 0
            opt = ProductOption(product_id=product.id, price=price, stock=stock)
            await self._option_repo.save(opt)

        await self._invalidate_product_cache(product.id)
        return await self.to_dto(product)

    async def update_product(self, product_id: int, data: dict) -> dict:
        product = await self.get_product_by_id(product_id)

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
                    raise AppException("E10300")
                db_product.category_id = category_id

            await self._product_repo.save(db_product)

            # Update default option price/stock
            # Cập nhật giá + tồn kho của option mặc định
            options = await self._option_repo.find_by_product_id(product_id)
            default_opt: ProductOption | None = None
            if len(options) == 1:
                default_opt = options[0]
            else:
                for opt in options:
                    vals = await self._option_val_repo.find_by_option_id(opt.id)
                    if not vals:
                        default_opt = opt
                        break

            if default_opt:
                if data.get("price") is not None:
                    default_opt.price = data["price"]
                if data.get("stock") is not None:
                    default_opt.stock = data["stock"]
                await self._option_repo.save(default_opt)

            # Update/add attributes
            # Cập nhật / thêm thuộc tính
            attribute_data: dict = data.get("attribute") or {}
            for attr_name, values in attribute_data.items():
                attr = await self._attr_repo.find_by_name_and_product_id(attr_name, product_id)
                if not attr:
                    attr = ProductAttribute(product_id=product_id, name=attr_name)
                    attr = await self._attr_repo.save(attr)

                current_vals = await self._attr_val_repo.find_by_attribute_id(attr.id)
                existing = {v.value: v for v in current_vals}

                for val_str in values:
                    if val_str not in existing:
                        pav = ProductAttributeValue(attribute_id=attr.id, value=str(val_str))
                        await self._attr_val_repo.save(pav)

                for v in current_vals:
                    if v.value not in values:
                        await self._attr_val_repo.delete(v)

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
        """Sync attributes + options from structured data.
        Đồng bộ thuộc tính + option từ dữ liệu có cấu trúc.

        Input format: {
          "attribute": ["size", "color"],
          "value": [
            [["S", "red"], [price, stock]],
            [["M", "blue"], [price, stock]],
          ]
        }
        """
        product = await self.get_product_by_id(product_id)

        attributes: list[str] = json_data.get("attribute") or []
        values: list = json_data.get("value") or []
        if not attributes or not values:
            raise AppException("E10203")

        async with self._transaction():
            # Ensure ProductAttribute rows exist
            # Đảm bảo các ProductAttribute tồn tại
            attr_entities: list[ProductAttribute] = []
            for attr_name in attributes:
                attr = await self._attr_repo.find_by_name_and_product_id(attr_name, product_id)
                if not attr:
                    attr = ProductAttribute(product_id=product_id, name=attr_name)
                    attr = await self._attr_repo.save(attr)
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
                    pav = await self._attr_val_repo.find_by_value_and_attribute_id(str(val), attr.id)
                    if not pav:
                        pav = ProductAttributeValue(attribute_id=attr.id, value=str(val))
                        pav = await self._attr_val_repo.save(pav)
                    else:
                        pav.value = str(val)
                        pav = await self._attr_val_repo.save(pav)
                    pav_entities.append(pav)

                # Find or create matching ProductOption
                # Tìm hoặc tạo ProductOption phù hợp
                pav_ids = {p.id for p in pav_entities}
                options = await self._option_repo.find_by_product_id(product_id)
                existing_option: ProductOption | None = None
                for opt in options:
                    opt_vals = await self._option_val_repo.find_by_option_id(opt.id)
                    if {ov.attribute_value_id for ov in opt_vals} == pav_ids:
                        existing_option = opt
                        break

                if not existing_option:
                    opt = ProductOption(product_id=product_id, price=price, stock=stock)
                    opt = await self._option_repo.save(opt)
                else:
                    existing_option.price = price
                    existing_option.stock = stock
                    opt = await self._option_repo.save(existing_option)

                # Link option ↔ attribute_values
                # Liên kết option với attribute_values
                for pav in pav_entities:
                    exists = await self._option_val_repo.find_by_value_and_option(pav.id, opt.id)
                    if not exists:
                        pov = ProductOptionValue(
                            option_id=opt.id, attribute_value_id=pav.id
                        )
                        await self._option_val_repo.save(pov)

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
                attr = await self._attr_repo.find_by_name_and_product_id(
                    attr_name, product.id
                )
                if not attr:
                    raise AppException("E10203")
                pav = await self._attr_val_repo.find_by_value_and_attribute_id(
                    str(attr_value), attr.id
                )
                if not pav:
                    raise AppException("E10203")
                pav_ids.append(pav.id)

            target = set(pav_ids)
            options = await self._option_repo.find_by_product_id(product.id)
            for opt in options:
                opt_vals = await self._option_val_repo.find_by_option_id(opt.id)
                if {ov.attribute_value_id for ov in opt_vals} == target:
                    return opt

        raise AppException("E10204")
