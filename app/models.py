from pydantic import BaseModel
from typing import Optional

class Product(BaseModel):
    product_id: int
    name: str
    price: Optional[float] = None
    category: Optional[str] = None
    unit: Optional[int] = None
    is_available: bool = True



class User(BaseModel):
    id: int
    name:Optional[str] = None
    is_active:Optional[bool]
