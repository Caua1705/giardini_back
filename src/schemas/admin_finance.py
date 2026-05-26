from datetime import date

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


class AdminRevenueResponse(BaseModel):
    summary: AdminRevenueSummaryResponse
    top_products: list[AdminRevenueProductResponse]
    sales_by_hour: list[AdminRevenueSalesByHourResponse]
    sales_by_day: list[AdminRevenueSalesByDayResponse]
    payment_insights: list[AdminRevenuePaymentInsightResponse]
    start_date: date
    end_date: date
    source: str
