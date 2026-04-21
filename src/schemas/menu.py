from pydantic import BaseModel


class MenuItemResponse(BaseModel):
    """Schema representing a row from the public menu view."""
    main_category: str
    subcategory: str
    product_name: str
    product_slug: str
    description: str | None = None
    badge: str | None = None
    image_url: str | None = None
    price: float | None = None
    has_variants: bool
    variant_name: str | None = None
    variant_price: float | None = None