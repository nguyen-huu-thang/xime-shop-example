from xime.core.transaction.manager import TransactionManager

from app.entity.review import Review
from app.exception.app_exception import AppException
from app.repository.review_repository import ReviewRepository
from app.service.product_service import ProductService
from app.service.user_service import UserService


class ReviewService:
    def __init__(
        self,
        transaction: TransactionManager,
        review_repository: ReviewRepository,
        user_service: UserService,
        product_service: ProductService,
    ) -> None:
        self._transaction = transaction
        self._repo = review_repository
        self._user_svc = user_service
        self._product_svc = product_service

    async def get_all_reviews(self) -> list[Review]:
        async with self._transaction():
            return await self._repo.find_all()

    async def get_review_by_id(self, review_id: int) -> Review | None:
        async with self._transaction():
            return await self._repo.find(review_id)

    async def get_reviews_by_product(self, product_id: int) -> list[Review]:
        async with self._transaction():
            return await self._repo.find_by_product_id(product_id)

    async def get_approved_reviews_by_product(
        self, product_id: int, page: int, limit: int
    ) -> list[Review]:
        # Public listing: only approved reviews of a product (no login required)
        # Danh sách công khai: chỉ review đã duyệt của sản phẩm (không cần đăng nhập)
        async with self._transaction():
            return await self._repo.find_approved_by_product_id(product_id, page, limit)

    async def get_reviews_by_user(self, user_id: int) -> list[Review]:
        async with self._transaction():
            return await self._repo.find_by_user_id(user_id)

    async def create_review(self, data: dict) -> Review:
        # Validate user and product exist before write transaction
        # Kiểm tra user và product tồn tại trước khi ghi
        user = await self._user_svc.get_user_by_id(data["userId"])
        if not user:
            raise AppException("E1004")
        product = await self._product_svc.get_product_by_id(data["productId"])
        if not product:
            raise AppException("E10200")
        if "rating" not in data:
            raise AppException("E10711")

        async with self._transaction():
            review = Review(
                user_id=user.id,
                product_id=product.id,
                rating=int(data["rating"]),
                comment=data.get("comment"),
                is_approved=False,
            )
            return await self._repo.save(review)

    async def update_review(self, review_id: int, data: dict) -> Review:
        async with self._transaction():
            review = await self._repo.find(review_id)
            if not review:
                raise AppException("E10600")
            if "rating" in data:
                review.rating = int(data["rating"])
            if "comment" in data:
                review.comment = data["comment"]
            return await self._repo.save(review)

    async def approve_review(self, review_id: int) -> Review:
        # Set is_approved = True
        # Duyệt đánh giá
        async with self._transaction():
            review = await self._repo.find(review_id)
            if not review:
                raise AppException("E10600")
            review.is_approved = True
            return await self._repo.save(review)

    async def disapprove_review(self, review_id: int) -> Review:
        # Set is_approved = False
        # Hủy duyệt đánh giá
        async with self._transaction():
            review = await self._repo.find(review_id)
            if not review:
                raise AppException("E10600")
            review.is_approved = False
            return await self._repo.save(review)

    async def delete_review(self, review_id: int) -> None:
        async with self._transaction():
            review = await self._repo.find(review_id)
            if not review:
                raise AppException("E10600")
            await self._repo.delete(review)
