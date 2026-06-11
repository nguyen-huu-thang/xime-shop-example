from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    file_name: str
    file_path: str
    file_size: int
    sort: int | None = None
    target_id: int | None = None
    list_table_id: str | None = None
    uploaded_at: datetime
    is_active: bool
    description: str | None = None
