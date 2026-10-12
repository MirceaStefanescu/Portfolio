from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    order_id: str = Field(..., min_length=1)
    amount_cents: int = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    customer_id: str | None = None


class Payment(BaseModel):
    id: str
    order_id: str
    status: str
    amount_cents: int
    currency: str
    created_at: str
