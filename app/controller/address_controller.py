from __future__ import annotations

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.address_request import AddressCreateRequest, AddressUpdateRequest
from app.dto.response.address_response import AddressResponse
from app.dto.response.token_response import MessageResponse
from app.security.current_user import require_login
from app.service.address_service import AddressService


class AddressController:
    prefix = "/api/addresses"
    tags = ["addresses"]

    def __init__(self, address_service: AddressService) -> None:
        self._svc = address_service

    @get("")
    async def list(self) -> list[AddressResponse]:
        user = require_login()
        addrs = await self._svc.get_my_addresses(user.id)
        return [AddressResponse.from_entity(a) for a in addrs]

    @post("", status_code=201)
    async def create(self, body: AddressCreateRequest) -> AddressResponse:
        user = require_login()
        addr = await self._svc.create_address(user.id, body.model_dump(by_alias=False))
        return AddressResponse.from_entity(addr)

    @put("/{id}")
    async def update(self, id: int, body: AddressUpdateRequest) -> AddressResponse:
        user = require_login()
        addr = await self._svc.update_address(
            id, user.id, body.model_dump(by_alias=False)
        )
        return AddressResponse.from_entity(addr)

    @put("/{id}/default")
    async def set_default(self, id: int) -> AddressResponse:
        user = require_login()
        addr = await self._svc.set_default(id, user.id)
        return AddressResponse.from_entity(addr)

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._svc.delete_address(id, user.id)
        return MessageResponse(message="Address deleted")
