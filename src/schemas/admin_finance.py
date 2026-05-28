from datetime import date, datetime

from pydantic import BaseModel


class AdminRevenueSummaryResponse(BaseModel):
    revenue_total: float
    transactions: int
    ticket_average: float


class AdminRevenueProductResponse(BaseModel):
    product_name: str
    quantity: float
    revenue: float


class AdminRevenueSalesByHourResponse(BaseModel):
    hour: int
    revenue: float
    transactions: int


class AdminRevenueSalesByDayResponse(BaseModel):
    date: date
    revenue: float
    transactions: int


class AdminRevenuePaymentInsightResponse(BaseModel):
    type: str
    revenue: float
    transactions: int


class AdminRevenueTransactionItemResponse(BaseModel):
    product_name: str
    quantity: float
    unit_price: float
    total: float


class AdminRevenueTransactionResponse(BaseModel):
    transaction_id: str
    date: date
    datetime: datetime | None
    subtotal: float
    discount: float
    total: float
    transaction_type: str | None
    origin: str | None
    items: list[AdminRevenueTransactionItemResponse]


class AdminRevenueResponse(BaseModel):
    summary: AdminRevenueSummaryResponse
    transactions: list[AdminRevenueTransactionResponse]
    top_products: list[AdminRevenueProductResponse]
    sales_by_hour: list[AdminRevenueSalesByHourResponse]
    sales_by_day: list[AdminRevenueSalesByDayResponse]
    payment_insights: list[AdminRevenuePaymentInsightResponse]
    start_date: date
    end_date: date
    source: str
