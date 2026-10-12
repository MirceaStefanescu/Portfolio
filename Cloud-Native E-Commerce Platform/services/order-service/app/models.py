from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    product_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)


class OrderCreate(BaseModel):
    customer_id: str = Field(..., min_length=1)
    items: list[OrderItemCreate]


class OrderItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    price_cents: int


class Order(BaseModel):
    id: str
    customer_id: str
    status: str
    total_cents: int
    currency: str
    items: list[OrderItem]
    created_at: str
    updated_at: str
