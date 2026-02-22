from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class StockInfo(SQLModel, table=True, extend_existing=True):
    """股票基本信息表"""
    __tablename__ = "stock_info"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    stock_code: str = Field(..., index=True, description="股票代码")
    stock_name: str = Field(..., description="股票名称")
    industry: Optional[str] = Field(default=None, description="所属行业")
    list_date: Optional[str] = Field(default=None, description="上市日期")
    pe_ttm: Optional[float] = Field(default=None, description="市盈率-动态")
    pb: Optional[float] = Field(default=None, description="市净率")
    total_market_cap: Optional[float] = Field(default=None, description="总市值")
    float_market_cap: Optional[float] = Field(default=None, description="流通市值")
    create_time: datetime = Field(default_factory=datetime.now, description="创建时间")
    update_time: datetime = Field(default_factory=datetime.now, description="更新时间")

class StockDaily(SQLModel, table=True, extend_existing=True):
    """股票日频数据表"""
    __tablename__ = "stock_daily"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    stock_code: str = Field(..., index=True, description="股票代码")
    trade_date: str = Field(..., index=True, description="交易日期")
    open_price: Optional[float] = Field(default=None, description="开盘价")
    close_price: Optional[float] = Field(default=None, description="收盘价")
    high_price: Optional[float] = Field(default=None, description="最高价")
    low_price: Optional[float] = Field(default=None, description="最低价")
    volume: Optional[float] = Field(default=None, description="成交量")
    amount: Optional[float] = Field(default=None, description="成交额")
    change_percent: Optional[float] = Field(default=None, description="涨跌幅")
    create_time: datetime = Field(default_factory=datetime.now, description="创建时间")
    update_time: datetime = Field(default_factory=datetime.now, description="更新时间")
