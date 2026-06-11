# Transaction

> Tóm tắt từ `D:\code\xime\xime framework\.claude\rules\transaction.md`, áp cho dự án đa lớp này.

## Nguyên tắc

Xime **không** dùng `@transactional`/AOP. Transaction tường minh qua async context manager.

> "Dependency nên được ẩn bởi framework, nhưng Transaction nên được thể hiện rõ trong code nghiệp vụ."

## Dùng trong Service

```python
class OrderService:
    def __init__(self, transaction: TransactionManager, order_repo: OrderRepository,
                 order_detail_repo: OrderDetailRepository):
        self._transaction = transaction
        self._order_repo = order_repo
        self._order_detail_repo = order_detail_repo

    async def create_order(self, data) -> Order:
        async with self._transaction():
            order = Order(...)
            await self._order_repo.save(order)
            for line in data.items:
                await self._order_detail_repo.save(OrderDetail(order_id=order.id, ...))
            return order
        # thoát block không lỗi → COMMIT; có exception → ROLLBACK
```

## Quy tắc

- **Mở transaction ở tầng Service**, không ở repository, không ở controller.
- Thao tác **ghi nhiều bảng** trong một nghiệp vụ → bọc chung 1 transaction (vd order + order_details).
- Thao tác **đọc thuần** → không cần transaction.
- Repository chỉ `add`/`flush`/`delete`; commit/rollback do `async with self._transaction()` lo.
- Không lồng transaction tùy tiện; nếu service gọi service khác cùng ghi, cân nhắc ai là người mở
  transaction ngoài cùng (thường service điều phối cấp cao).

## TransactionManager đến từ đâu

`TransactionManager` là interface của Xime core; implementation (`SqlAlchemyTransactionManager`) do
`xime.starters.sqlalchemy` cung cấp. Inject qua constructor như mọi dependency khác — không cần cấu
hình thêm ngoài việc bật starter SQLAlchemy.
