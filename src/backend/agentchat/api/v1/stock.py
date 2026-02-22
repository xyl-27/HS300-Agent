from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Optional
from agentchat.api.services.stock_service import StockService

router = APIRouter(prefix="/stock", tags=["stock"])
stock_service = StockService()

@router.get("/list", response_model=Dict)
def get_stock_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取股票列表（分页）
    
    Args:
        page: 页码，从1开始
        page_size: 每页数量，1-100
    
    Returns:
        分页后的股票列表，包含总数量、页码、每页数量和数据
    """
    stocks = stock_service.get_stock_list()
    if not stocks:
        raise HTTPException(status_code=404, detail="无法获取股票列表")
    
    # 计算分页
    total = len(stocks)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_stocks = stocks[start:end]
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": paginated_stocks
    }

@router.get("/detail/{stock_code}", response_model=Dict)
def get_stock_detail(stock_code: str):
    """
    获取股票详细信息
    
    Args:
        stock_code: 股票代码
        
    Returns:
        股票详细信息，包含基本信息和历史数据
    """
    stock_detail = stock_service.get_stock_detail(stock_code)
    if not stock_detail:
        raise HTTPException(status_code=404, detail=f"无法获取股票 {stock_code} 的详细信息")
    return stock_detail

@router.get("/industry/analysis", response_model=Dict)
def get_industry_analysis(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取行业分析数据（分页）
    
    Args:
        page: 页码，从1开始
        page_size: 每页数量，1-100
    
    Returns:
        分页后的行业分析数据，包含总数量、页码、每页数量和数据
    """
    analysis = stock_service.get_industry_analysis()
    if not analysis:
        raise HTTPException(status_code=404, detail="无法获取行业分析数据")
    
    # 计算分页
    industry_list = analysis.get("industry_analysis", [])
    total = len(industry_list)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_industry_list = industry_list[start:end]
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": paginated_industry_list
    }

@router.get("/industry/trend", response_model=Dict)
def get_industry_trend(industry: str = Query(..., description="行业名称")):
    """
    获取行业趋势数据
    
    Args:
        industry: 行业名称
        
    Returns:
        行业趋势数据，包含该行业所有股票的表现
    """
    trend = stock_service.get_industry_trend(industry)
    if not trend:
        raise HTTPException(status_code=404, detail=f"无法获取行业 {industry} 的趋势数据")
    return trend

@router.get("/industry/stock-hierarchy", response_model=List[Dict])
def get_industry_stock_hierarchy():
    """
    获取行业-股票层级数据，用于 treemap 可视化
    
    Returns:
        行业-股票层级数据，包含行业名称、市值、股票列表等信息
    """
    hierarchy_data = stock_service.get_industry_stock_hierarchy()
    if not hierarchy_data:
        raise HTTPException(status_code=404, detail="无法获取行业-股票层级数据")
    return hierarchy_data

@router.get("/industry/analyze", response_model=Dict)
def analyze_industry(
    industry: str = Query(..., description="行业名称"),
    days: int = Query(90, ge=1, le=365, description="分析天数")
):
    """
    分析行业情况
    
    Args:
        industry: 行业名称
        days: 分析天数
    
    Returns:
        行业分析结果，包含行业名称、分析周期、股票数量、平均涨跌幅、波动率、上涨天数、下跌天数、上涨天数占比、分析总结等
    """
    analysis_result = stock_service.analyze_industry(industry, days)
    if not analysis_result:
        raise HTTPException(status_code=404, detail=f"无法分析行业 {industry} 的情况")
    return analysis_result

@router.get("/industry/analyze/llm", response_model=Dict)
async def analyze_industry_with_llm(
    industry: str = Query(..., description="行业名称"),
    days: int = Query(90, ge=1, le=365, description="分析天数")
):
    """
    使用大模型分析单个行业
    
    Args:
        industry: 行业名称
        days: 分析天数
    
    Returns:
        大模型分析结果，包含行业名称、分析周期、股票数量、平均涨跌幅、波动率、上涨天数、下跌天数、上涨天数占比、大模型分析报告等
    """
    analysis_result = await stock_service.analyze_industry_with_llm(industry, days)
    if not analysis_result:
        raise HTTPException(status_code=404, detail=f"无法使用大模型分析行业 {industry} 的情况")
    return analysis_result

@router.get("/industry/analyze/all/llm", response_model=Dict)
async def analyze_all_industries_with_llm(
    days: int = Query(90, ge=1, le=365, description="分析天数")
):
    """
    使用大模型分析所有行业
    
    Args:
        days: 分析天数
    
    Returns:
        大模型分析结果，包含分析周期、行业数量、各行业分析数据、大模型综合分析报告等
    """
    analysis_result = await stock_service.analyze_all_industries_with_llm(days)
    if not analysis_result:
        raise HTTPException(status_code=404, detail="无法使用大模型分析所有行业的情况")
    return analysis_result
