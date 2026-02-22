from typing import List, Dict, Optional
from loguru import logger
from src.backend.agentchat.services.data_collector.data_collector import DataCollector
from sqlmodel import Session
from src.backend.agentchat.database.models.stock import StockInfo, StockDaily

class StockService:
    def __init__(self):
        self.collector = DataCollector()
    
    def get_stock_list(self) -> List[Dict]:
        """
        获取所有股票列表
        
        Returns:
            股票列表，每个元素包含股票代码、股票名称和行业
        """
        try:
            stocks = self.collector.get_hs300_stocks()
            if not stocks:
                logger.error("无法获取股票列表")
                return []
            
            # 为每个股票添加行业信息
            result = []
            for stock in stocks:
                stock_code = stock['stock_code']
                basic_info = self.collector.get_stock_basic_info(stock_code)
                if basic_info:
                    result.append({
                        "stock_code": stock_code,
                        "stock_name": basic_info['stock_name'],
                        "industry": basic_info['industry'] or "未知"
                    })
                else:
                    result.append({
                        "stock_code": stock_code,
                        "stock_name": stock['stock_name'],
                        "industry": "未知"
                    })
            
            return result
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []
    
    def get_stock_detail(self, stock_code: str) -> Optional[Dict]:
        """
        获取股票详细信息
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票详细信息，包含基本信息和历史数据
        """
        try:
            # 获取基本信息
            basic_info = self.collector.get_stock_basic_info(stock_code)
            if not basic_info:
                logger.error(f"无法获取股票 {stock_code} 的基本信息")
                return None
            
            # 获取历史数据
            start_date = "20250101"
            end_date = "20260221"
            historical_data = self.collector.get_stock_historical_data(stock_code, start_date, end_date)
            
            # 转换历史数据为列表
            historical_list = []
            if historical_data is not None:
                for _, row in historical_data.iterrows():
                    historical_list.append({
                        "date": row['日期'],
                        "open": row['开盘'],
                        "close": row['收盘'],
                        "high": row['最高'],
                        "low": row['最低'],
                        "volume": row['成交量'],
                        "amount": row['成交额'],
                        "change_percent": row['涨跌幅']
                    })
            
            return {
                "basic_info": basic_info,
                "historical_data": historical_list
            }
        except Exception as e:
            logger.error(f"获取股票详细信息失败: {e}")
            return None
    
    def get_industry_analysis(self) -> Optional[Dict]:
        """
        获取行业分析数据
        
        Returns:
            行业分析数据，包含各行业的平均涨跌幅、波动率等指标
        """
        try:
            # 使用数据收集器的行业分析功能
            industry_df = self.collector.get_industry_analysis_data()
            if industry_df is None:
                logger.error("无法获取行业分析数据")
                return None
            
            # 转换为字典列表
            industry_list = []
            for _, row in industry_df.iterrows():
                industry_list.append({
                    "industry": row['industry'],
                    "stock_count": row['stock_count'],
                    "avg_change": row['avg_change'],
                    "avg_volatility": row['avg_volatility']
                })
            
            # 按平均涨跌幅排序
            industry_list.sort(key=lambda x: x['avg_change'], reverse=True)
            
            return {
                "industry_analysis": industry_list,
                "total_industries": len(industry_list)
            }
        except Exception as e:
            logger.error(f"获取行业分析数据失败: {e}")
            return None
    
    def get_industry_trend(self, industry: str) -> Optional[Dict]:
        """
        获取行业趋势数据
        
        Args:
            industry: 行业名称
            
        Returns:
            行业趋势数据，包含该行业所有股票的表现
        """
        try:
            # 获取行业内所有股票
            stocks = self.collector.get_hs300_stocks()
            industry_stocks = []
            
            for stock in stocks:
                basic_info = self.collector.get_stock_basic_info(stock['stock_code'])
                if basic_info and basic_info['industry'] == industry:
                    industry_stocks.append(stock['stock_code'])
            
            if not industry_stocks:
                logger.error(f"行业 {industry} 中没有股票")
                return None
            
            # 获取每个股票的历史数据
            start_date = "20250101"
            end_date = "20260221"
            stock_trends = {}
            
            for stock_code in industry_stocks:
                historical_data = self.collector.get_stock_historical_data(stock_code, start_date, end_date)
                if historical_data is not None:
                    stock_trends[stock_code] = [
                        {
                            "date": row['日期'],
                            "close": row['收盘'],
                            "change_percent": row['涨跌幅']
                        }
                        for _, row in historical_data.iterrows()
                    ]
            
            return {
                "industry": industry,
                "stock_trends": stock_trends,
                "stock_count": len(stock_trends)
            }
        except Exception as e:
            logger.error(f"获取行业趋势数据失败: {e}")
            return None
