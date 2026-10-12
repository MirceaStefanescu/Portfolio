from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    price_cents: int = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1)
    description: str | None = None
    price_cents: int | None = Field(None, gt=0)
    currency: str | None = Field(None, min_length=3, max_length=3)


class Product(BaseModel):
    id: str
    name: str
    description: str | None
    price_cents: int
    currency: str
    created_at: str
    updated_at: str
