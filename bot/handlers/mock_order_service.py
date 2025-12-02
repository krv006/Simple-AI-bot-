# mock_order_service.py
from typing import Dict, Any, Optional


class MockOrderService:

    def __init__(self) -> None:
        self._orders: Dict[int, Dict[str, Any]] = {}
        self._counter: int = 1  # auto-increment ID

    async def create_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        order_id = self._counter
        self._counter += 1

        order = {
            "id": order_id,
            "status": "new",  # hozircha default status
            **data,
        }

        self._orders[order_id] = order
        return order

    async def get_order_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        """
        Berilgan ID bo'yicha zakazni qaytaradi.
        Topilmasa None.
        """
        return self._orders.get(order_id)

    async def list_orders(self) -> Dict[int, Dict[str, Any]]:
        """
        Faqat test uchun: hamma zakazlarni ko'rish.
        """
        return self._orders

    async def reset(self) -> None:
        """
        Testlar orasida tozalash uchun.
        """
        self._orders.clear()
        self._counter = 1
