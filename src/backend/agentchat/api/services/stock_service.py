import os
import sys
import pandas as pd
import akshare as ak
import random
from datetime import datetime
from loguru import logger
from typing import List, Dict, Optional
import functools
import time

# 导入大模型相关模块
from agentchat.core.models.manager import ModelManager
from agentchat.prompts.industry_analysis import industry_analysis_prompt, all_industries_analysis_prompt
from langchain_core.messages import HumanMessage

# 导入数据库相关模块
from agentchat.database.session import session_getter
from agentchat.database.models.stock import StockInfo, StockDaily

# 添加缓存装饰器
def cache_result(seconds=3600):
    def decorator(func):
        cache = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 创建缓存键
            cache_key = str(args) + str(kwargs)
            
            # 检查缓存是否有效
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if time.time() - timestamp < seconds:
                    logger.info("使用缓存的行业分析数据")
                    return result
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache[cache_key] = (result, time.time())
            logger.info("缓存行业分析数据")
            return result
        
        return wrapper
    return decorator

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
# 向上一级目录: services
parent_dir = os.path.dirname(os.path.abspath(__file__))
# 向上一级目录: api
parent_dir = os.path.dirname(parent_dir)
# 向上一级目录: agentchat
parent_dir = os.path.dirname(parent_dir)
# 向上一级目录: backend
parent_dir = os.path.dirname(parent_dir)
# 向上一级目录: src
src_dir = os.path.dirname(parent_dir)
sys.path.insert(0, src_dir)
# 向上一级目录: 项目根目录
project_dir = os.path.dirname(src_dir)
sys.path.insert(0, project_dir)

class StockService:
    def __init__(self):
        # CSV文件路径
        self.csv_file_path = os.path.join(project_dir, 'data', 'hs300_stocks.csv')
        logger.info(f"CSV文件路径: {self.csv_file_path}")
    
    def get_stock_list(self) -> List[Dict]:
        """
        获取所有股票列表
        
        Returns:
            股票列表，每个元素包含股票代码、股票名称和行业
        """
        try:
            # 优先从数据库获取
            with session_getter() as db:
                stock_infos = db.query(StockInfo).all()
                if stock_infos:
                    stocks = []
                    for stock_info in stock_infos:
                        stocks.append({
                            "stock_code": stock_info.stock_code,
                            "stock_name": stock_info.stock_name,
                            "industry": stock_info.industry or "未知",
                            "list_date": stock_info.list_date or ""
                        })
                    logger.info(f"从数据库获取到 {len(stocks)} 只股票")
                    return stocks
            
            # 如果数据库中没有数据，从CSV文件获取
            stocks = self.get_hs300_stocks()
            if not stocks:
                logger.error("无法获取股票列表")
                return []
            
            logger.info(f"从CSV文件获取到 {len(stocks)} 只股票")
            return stocks
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            logger.exception(e)
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
            # 优先从数据库获取基本信息
            basic_info = None
            historical_list = []
            
            with session_getter() as db:
                # 获取基本信息
                stock_info = db.query(StockInfo).filter(StockInfo.stock_code == stock_code).first()
                if stock_info:
                    basic_info = {
                        "stock_code": stock_info.stock_code,
                        "stock_name": stock_info.stock_name,
                        "industry": stock_info.industry or "未知",
                        "list_date": stock_info.list_date or ""
                    }
                    logger.info(f"从数据库获取到股票 {stock_code} 的基本信息")
                
                # 获取历史数据
                stock_dailies = db.query(StockDaily).filter(StockDaily.stock_code == stock_code).order_by(StockDaily.trade_date).all()
                if stock_dailies:
                    for stock_daily in stock_dailies:
                        historical_list.append({
                            "date": stock_daily.trade_date,
                            "open": stock_daily.open_price,
                            "close": stock_daily.close_price,
                            "high": stock_daily.high_price,
                            "low": stock_daily.low_price,
                            "volume": stock_daily.volume,
                            "amount": stock_daily.amount,
                            "change_percent": stock_daily.change_percent
                        })
                    logger.info(f"从数据库获取到股票 {stock_code} 的 {len(historical_list)} 条历史数据")
            
            # 如果数据库中没有基本信息，从其他来源获取
            if not basic_info:
                basic_info = self.get_stock_basic_info(stock_code)
                if not basic_info:
                    logger.error(f"无法获取股票 {stock_code} 的基本信息")
                    return None
            
            # 如果数据库中没有历史数据，从akshare获取
            if not historical_list:
                start_date = "20250101"
                end_date = datetime.now().strftime("%Y%m%d")
                historical_data = self.get_stock_historical_data(stock_code, start_date, end_date)
                
                # 转换历史数据为列表
                if historical_data is not None:
                    for _, row in historical_data.iterrows():
                        # 确保所有数据类型都是Pydantic可以序列化的类型
                        historical_list.append({
                            "date": str(row['日期']),
                            "open": float(row['开盘']) if row['开盘'] is not None else None,
                            "close": float(row['收盘']) if row['收盘'] is not None else None,
                            "high": float(row['最高']) if row['最高'] is not None else None,
                            "low": float(row['最低']) if row['最低'] is not None else None,
                            "volume": int(row['成交量']) if row['成交量'] is not None else None,
                            "amount": float(row['成交额']) if row['成交额'] is not None else None,
                            "change_percent": float(row['涨跌幅']) if row['涨跌幅'] is not None else None
                        })
            
            return {
                "basic_info": basic_info,
                "historical_data": historical_list
            }
        except Exception as e:
            logger.error(f"获取股票详细信息失败: {e}")
            logger.exception(e)
            return None
    
    def get_industry_analysis(self) -> Optional[Dict]:
        """
        获取行业分析数据
        
        Returns:
            行业分析数据，包含各行业的平均涨跌幅、波动率等指标
        """
        try:
            # 优先从数据库获取数据进行分析
            with session_getter() as db:
                # 使用SQL聚合函数直接在数据库层面计算
                from sqlalchemy import func, and_
                
                # 连接查询获取行业和股票代码的对应关系
                # 然后按行业分组计算统计数据
                industry_stats = db.query(
                    StockInfo.industry,
                    func.count(StockInfo.stock_code).label('stock_count'),
                    func.avg(StockDaily.change_percent).label('avg_change'),
                    func.stddev(StockDaily.change_percent).label('avg_volatility')
                ).join(
                    StockDaily, StockInfo.stock_code == StockDaily.stock_code
                ).filter(
                    and_(
                        StockInfo.industry.isnot(None),
                        StockInfo.industry != "未知",
                        StockDaily.change_percent.isnot(None)
                    )
                ).group_by(
                    StockInfo.industry
                ).all()
                
                if industry_stats:
                    industry_list = []
                    for stat in industry_stats:
                        if stat.industry and stat.stock_count > 0:
                            industry_list.append({
                                "industry": str(stat.industry),
                                "stock_count": int(stat.stock_count),
                                "avg_change": float(stat.avg_change) if stat.avg_change else 0,
                                "avg_volatility": float(stat.avg_volatility) if stat.avg_volatility else 0
                            })
                    
                    if industry_list:
                        # 按平均涨跌幅排序
                        industry_list.sort(key=lambda x: x['avg_change'], reverse=True)
                        logger.info(f"从数据库获取到 {len(industry_list)} 个行业的分析数据")
                        return {
                            "industry_analysis": industry_list,
                            "total_industries": len(industry_list)
                        }
            
            # 如果数据库中没有足够的数据，使用批量查询优化的方法
            logger.warning("数据库中行业分析数据不足，使用优化的替代方法获取")
            
            with session_getter() as db:
                # 批量获取所有股票基本信息
                stock_infos = db.query(StockInfo).filter(
                    and_(
                        StockInfo.industry.isnot(None),
                        StockInfo.industry != "未知"
                    )
                ).all()
                
                if not stock_infos:
                    logger.warning("数据库中没有有效的股票基本信息")
                    return None
                
                # 获取所有相关的股票代码
                stock_codes = [stock.stock_code for stock in stock_infos]
                
                # 批量获取所有股票的历史数据
                stock_dailies = db.query(StockDaily).filter(
                    and_(
                        StockDaily.stock_code.in_(stock_codes),
                        StockDaily.change_percent.isnot(None)
                    )
                ).all()
                
                # 按股票代码分组历史数据
                stock_daily_map = {}
                for daily in stock_dailies:
                    if daily.stock_code not in stock_daily_map:
                        stock_daily_map[daily.stock_code] = []
                    stock_daily_map[daily.stock_code].append(daily.change_percent)
                
                # 构建股票代码到行业的映射
                stock_industry_map = {}
                for stock in stock_infos:
                    stock_industry_map[stock.stock_code] = stock.industry
                
                # 计算行业数据
                industry_data = {}
                for stock_code, changes in stock_daily_map.items():
                    industry = stock_industry_map.get(stock_code)
                    if not industry:
                        continue
                    
                    if industry not in industry_data:
                        industry_data[industry] = {
                            "stock_count": 0,
                            "total_change": 0,
                            "volatilities": []
                        }
                    
                    # 计算该股票的平均涨跌幅和波动率
                    avg_change = sum(changes) / len(changes)
                    volatility = pd.Series(changes).std() if len(changes) > 1 else 0
                    
                    industry_data[industry]["stock_count"] += 1
                    industry_data[industry]["total_change"] += avg_change
                    industry_data[industry]["volatilities"].append(volatility)
                
                # 转换为结果列表
                industry_list = []
                for industry, data in industry_data.items():
                    if data["stock_count"] > 0:
                        avg_change = data["total_change"] / data["stock_count"]
                        avg_volatility = sum(data["volatilities"]) / len(data["volatilities"])
                        
                        industry_list.append({
                            "industry": str(industry),
                            "stock_count": int(data["stock_count"]),
                            "avg_change": float(avg_change),
                            "avg_volatility": float(avg_volatility)
                        })
                
                if industry_list:
                    # 按平均涨跌幅排序
                    industry_list.sort(key=lambda x: x['avg_change'], reverse=True)
                    logger.info(f"从优化的方法获取到 {len(industry_list)} 个行业的分析数据")
                    return {
                        "industry_analysis": industry_list,
                        "total_industries": len(industry_list)
                    }
            
            logger.warning("无法获取行业分析数据")
            return None
        except Exception as e:
            logger.error(f"获取行业分析数据失败: {e}")
            logger.exception(e)
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
            # 优先从数据库获取
            with session_getter() as db:
                # 获取行业内所有股票
                stock_infos = db.query(StockInfo).filter(StockInfo.industry == industry).all()
                
                if stock_infos:
                    # 获取所有相关的股票代码
                    stock_codes = [stock.stock_code for stock in stock_infos]
                    
                    # 批量获取所有股票的历史数据
                    stock_dailies = db.query(StockDaily).filter(
                        StockDaily.stock_code.in_(stock_codes)
                    ).order_by(
                        StockDaily.stock_code,
                        StockDaily.trade_date
                    ).all()
                    
                    # 按股票代码分组历史数据
                    stock_trends = {}
                    for daily in stock_dailies:
                        if daily.stock_code not in stock_trends:
                            stock_trends[daily.stock_code] = []
                        stock_trends[daily.stock_code].append({
                            "date": daily.trade_date,
                            "close": daily.close_price,
                            "change_percent": daily.change_percent
                        })
                    
                    if stock_trends:
                        logger.info(f"从数据库获取到行业 {industry} 的 {len(stock_trends)} 只股票的趋势数据")
                        return {
                            "industry": industry,
                            "stock_trends": stock_trends,
                            "stock_count": len(stock_trends)
                        }
            
            # 如果数据库中没有数据，从其他来源获取
            # 获取行业内所有股票
            stocks = self.get_hs300_stocks()
            industry_stocks = [stock for stock in stocks if stock['industry'] == industry]
            
            if not industry_stocks:
                logger.error(f"行业 {industry} 中没有股票")
                return None
            
            # 获取每个股票的历史数据
            start_date = "20250101"
            end_date = datetime.now().strftime("%Y%m%d")
            stock_trends = {}
            
            # 并行获取股票历史数据
            import concurrent.futures
            
            def fetch_stock_data(stock):
                stock_code = stock['stock_code']
                historical_data = self.get_stock_historical_data(stock_code, start_date, end_date)
                if historical_data is not None:
                    return stock_code, [
                        {
                            "date": row['日期'],
                            "close": row['收盘'],
                            "change_percent": row['涨跌幅']
                        }
                        for _, row in historical_data.iterrows()
                    ]
                return stock_code, None
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_stock = {executor.submit(fetch_stock_data, stock): stock for stock in industry_stocks}
                for future in concurrent.futures.as_completed(future_to_stock):
                    stock_code, stock_data = future.result()
                    if stock_data:
                        stock_trends[stock_code] = stock_data
            
            if stock_trends:
                logger.info(f"从其他来源获取到行业 {industry} 的 {len(stock_trends)} 只股票的趋势数据")
                return {
                    "industry": industry,
                    "stock_trends": stock_trends,
                    "stock_count": len(stock_trends)
                }
        except Exception as e:
            logger.error(f"获取行业趋势数据失败: {e}")
            logger.exception(e)
            return None

    def get_industry_stock_hierarchy(self) -> Optional[List[Dict]]:
        """
        获取行业-股票层级数据，用于 treemap 可视化
        只读取 stock_info 和 stock_daily 两张表的数据

        Returns:
            行业-股票层级数据，包含行业名称、市值、股票列表等信息
        """
        try:
            # 只从数据库获取数据
            with session_getter() as db:
                # 获取所有股票信息
                stock_infos = db.query(StockInfo).filter(
                    StockInfo.industry.isnot(None),
                    StockInfo.industry != "未知"
                ).all()
                
                if not stock_infos:
                    logger.warning("数据库中没有有效的股票信息")
                    return None
                
                # 按行业分组股票
                industry_map = {}
                for stock_info in stock_infos:
                    industry = stock_info.industry
                    if industry not in industry_map:
                        industry_map[industry] = []
                    industry_map[industry].append(stock_info)
                
                # 构建行业-股票层级数据
                hierarchy_data = []
                for industry, stocks in industry_map.items():
                    # 获取行业内所有股票的最新涨跌幅
                    industry_stocks = []
                    industry_value = 0
                    
                    for stock in stocks:
                        # 获取股票的最新涨跌幅
                        latest_daily = db.query(StockDaily).filter(
                            StockDaily.stock_code == stock.stock_code
                        ).order_by(
                            StockDaily.trade_date.desc()
                        ).first()
                        
                        increase = 0
                        if latest_daily:
                            increase = latest_daily.change_percent or 0
                        
                        # 使用真实的总市值数据，如果没有则使用模拟数据
                        market_cap = stock.total_market_cap or random.randint(10000000000, 1000000000000)
                        # 将市值单位转换为亿
                        market_cap_yi = market_cap / 100000000  # 转换为亿
                        float_market_cap_yi = stock.float_market_cap / 100000000 if stock.float_market_cap else None
                        
                        stock_data = {
                            "name": stock.stock_name,
                            "value": market_cap_yi,  # 使用亿为单位的总市值
                            "increase": increase,
                            "pe_ttm": stock.pe_ttm,
                            "pb": stock.pb,
                            "float_market_cap": float_market_cap_yi
                        }
                        
                        industry_stocks.append(stock_data)
                        industry_value += stock_data["value"]
                    
                    # 计算行业平均涨跌幅
                    avg_increase = 0
                    if industry_stocks:
                        total_increase = sum(stock["increase"] for stock in industry_stocks)
                        avg_increase = total_increase / len(industry_stocks)
                    
                    # 构建行业数据
                    industry_data = {
                        "name": industry,
                        "value": industry_value,
                        "increase": avg_increase,
                        "stock_count": len(industry_stocks),
                        "children": industry_stocks
                    }
                    
                    hierarchy_data.append(industry_data)
                
                logger.info(f"从数据库获取到 {len(hierarchy_data)} 个行业的层级数据")
                return hierarchy_data
            
        except Exception as e:
            logger.error(f"获取行业-股票层级数据失败: {e}")
            logger.exception(e)
            return None
    
    async def analyze_hotmap_data(self) -> Optional[Dict]:
        """
        分析大盘星图数据，生成投资建议
        
        Returns:
            包含分析报告和投资建议的字典
        """
        try:
            logger.info("开始分析大盘星图数据")
            
            # 导入必要的模块
            from agentchat.prompts.hotmap_analysis import hotmap_analysis_prompt
            from datetime import datetime
            
            # 获取大盘星图数据
            logger.info("获取大盘星图数据")
            hotmap_data = self.get_industry_stock_hierarchy()
            if not hotmap_data:
                logger.error("无法获取大盘星图数据，分析失败")
                return None
            logger.info(f"成功获取大盘星图数据，包含 {len(hotmap_data)} 个行业")
            
            # 准备分析数据
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"分析时间: {current_time}")
            
            # 优化 hotmap_data，减少 prompt 大小
            logger.info("优化 hotmap_data，减少 prompt 大小")
            
            # 1. 按市值排序，取前10个行业
            sorted_by_value = sorted(hotmap_data, key=lambda x: x['value'], reverse=True)[:10]
            
            # 2. 按涨跌幅排序，取前5个和后5个行业
            sorted_by_increase = sorted(hotmap_data, key=lambda x: x['increase'], reverse=True)
            top_increase = sorted_by_increase[:5]
            bottom_increase = sorted_by_increase[-5:]
            
            # 3. 构建优化后的数据结构
            optimized_data = {
                "total_industries": len(hotmap_data),
                "top_by_value": [
                    {
                        "name": industry['name'],
                        "value": industry['value'],
                        "increase": industry['increase'],
                        "stock_count": industry['stock_count']
                    }
                    for industry in sorted_by_value
                ],
                "top_by_increase": [
                    {
                        "name": industry['name'],
                        "value": industry['value'],
                        "increase": industry['increase'],
                        "stock_count": industry['stock_count']
                    }
                    for industry in top_increase
                ],
                "bottom_by_increase": [
                    {
                        "name": industry['name'],
                        "value": industry['value'],
                        "increase": industry['increase'],
                        "stock_count": industry['stock_count']
                    }
                    for industry in bottom_increase
                ]
            }
            
            # 构建prompt
            logger.info("构建分析prompt")
            prompt = hotmap_analysis_prompt.format(
                current_time=current_time,
                hotmap_data=str(optimized_data)
            )
            logger.info(f"prompt长度: {len(prompt)}")
            
            # 尝试导入ModelManager和HumanMessage
            try:
                from agentchat.core.models.manager import ModelManager
                from langchain_core.messages import HumanMessage
                logger.info("成功导入ModelManager和HumanMessage")
            except Exception as import_error:
                logger.error(f"导入模块失败: {import_error}")
                # 由于LLM导入失败，返回一个模拟的分析结果
                result = {
                    "analysis_time": current_time,
                    "industry_count": len(hotmap_data),
                    "analysis_report": "由于模型服务暂时不可用，无法提供详细分析。建议关注以下几个方面：1. 行业分布情况；2. 涨跌行业比例；3. 市值分布特征；4. 潜在的投资机会。"
                }
                logger.info("返回模拟分析结果")
                return result
            
            # 获取大模型实例
            try:
                logger.info("获取大模型实例")
                llm = ModelManager.get_reasoning_model()
                logger.info("成功获取大模型实例")
            except Exception as model_error:
                logger.error(f"获取大模型实例失败: {model_error}")
                # 由于LLM获取失败，返回一个模拟的分析结果
                result = {
                    "analysis_time": current_time,
                    "industry_count": len(hotmap_data),
                    "analysis_report": "由于模型服务暂时不可用，无法提供详细分析。建议关注以下几个方面：1. 行业分布情况；2. 涨跌行业比例；3. 市值分布特征；4. 潜在的投资机会。"
                }
                logger.info("返回模拟分析结果")
                return result
            
            # 调用大模型进行分析
            try:
                logger.info("调用大模型进行分析")
                messages = [HumanMessage(content=prompt)]
                response_stream = await llm.astream(messages)
                
                # 处理流式响应，获取完整内容
                full_content = ""
                async for chunk in response_stream:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        full_content += chunk.choices[0].delta.content
                
                # 构建响应对象
                class MockResponse:
                    def __init__(self, content):
                        self.content = content
                
                response = MockResponse(full_content)
                logger.info("成功调用大模型进行分析")
            except Exception as invoke_error:
                logger.error(f"调用大模型失败: {invoke_error}")
                logger.exception(invoke_error)
                # 由于LLM调用失败，返回一个模拟的分析结果
                result = {
                    "analysis_time": current_time,
                    "industry_count": len(hotmap_data),
                    "analysis_report": "由于模型服务暂时不可用，无法提供详细分析。建议关注以下几个方面：1. 行业分布情况；2. 涨跌行业比例；3. 市值分布特征；4. 潜在的投资机会。"
                }
                logger.info("返回模拟分析结果")
                return result
            
            # 构建返回结果
            result = {
                "analysis_time": current_time,
                "industry_count": len(hotmap_data),
                "analysis_report": response.content
            }
            
            logger.info("大盘星图数据分析完成")
            return result
            
        except Exception as e:
            logger.error(f"分析大盘星图数据失败: {e}")
            logger.exception(e)
            return None
    
    def get_hs300_stocks(self) -> List[Dict]:
        """
        获取沪深300成分股列表
        
        Returns:
            沪深300成分股列表，每个元素包含股票代码、股票名称和行业
        """
        # 从CSV文件读取（根据用户要求）
        if os.path.exists(self.csv_file_path):
            try:
                logger.info(f"从CSV文件读取沪深300成分股列表: {self.csv_file_path}")
                df = pd.read_csv(self.csv_file_path)
                logger.info(f"CSV文件读取成功，数据形状: {df.shape}")
                logger.info(f"CSV文件列名: {df.columns.tolist()}")
                
                stocks = []
                for _, row in df.iterrows():
                    # 尝试不同的列名
                    stock_code = row.get('股票代码', '')
                    if not stock_code:
                        stock_code = row.get('品种代码', '')
                    if not stock_code:
                        stock_code = row.get('code', '')
                    
                    stock_name = row.get('股票名称', '')
                    if not stock_name:
                        stock_name = row.get('品种名称', '')
                    if not stock_name:
                        stock_name = row.get('name', '')
                    
                    industry = row.get('行业', '')
                    if not industry:
                        industry = row.get('industry', '')
                    
                    list_date = row.get('上市时间', '')
                    if not list_date:
                        list_date = row.get('list_date', '')
                    if not list_date:
                        list_date = row.get('纳入日期', '')
                    
                    # 确保股票代码是字符串类型
                    if stock_code:
                        stock_code = str(stock_code)
                        # 补全股票代码，确保格式正确
                        if len(stock_code) < 6:
                            stock_code = stock_code.zfill(6)
                        # 确保所有数据类型都是Pydantic可以序列化的类型
                        stocks.append({
                            "stock_code": str(stock_code),
                            "stock_name": str(stock_name),
                            "industry": str(industry) or "未知",
                            "list_date": str(list_date)
                        })
                
                logger.info(f"从CSV文件读取到 {len(stocks)} 只沪深300成分股")
                if stocks:
                    logger.info(f"前5只成分股: {stocks[:5]}")
                return stocks
            except Exception as e:
                logger.error(f"从CSV文件读取沪深300成分股失败: {e}")
                logger.exception(e)
        else:
            logger.error(f"CSV文件不存在: {self.csv_file_path}")
        
        # 如果CSV文件读取失败，返回默认的几只股票用于测试
        logger.warning("无法从CSV文件获取沪深300成分股列表，返回默认测试股票")
        return [
            {"stock_code": "000001", "stock_name": "平安银行", "industry": "银行", "list_date": "1991-04-03"},
            {"stock_code": "000002", "stock_name": "万科A", "industry": "房地产", "list_date": "1991-01-29"},
            {"stock_code": "000008", "stock_name": "神州高铁", "industry": "交通运输", "list_date": "1992-05-07"},
            {"stock_code": "000009", "stock_name": "中国宝安", "industry": "综合", "list_date": "1991-06-25"},
            {"stock_code": "000012", "stock_name": "南玻A", "industry": "建筑材料", "list_date": "1992-02-28"}
        ]
    
    def get_stock_basic_info(self, stock_code: str) -> Optional[Dict]:
        """
        获取股票基本信息
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票基本信息，包含股票代码、股票名称、行业等
        """
        # 从CSV文件读取（根据用户要求）
        if os.path.exists(self.csv_file_path):
            try:
                logger.info(f"从CSV文件读取股票 {stock_code} 基本信息")
                df = pd.read_csv(self.csv_file_path)
                
                # 尝试不同的列名
                code_column = None
                for col in ['股票代码', '品种代码', 'code']:
                    if col in df.columns:
                        code_column = col
                        break
                
                if code_column:
                    # 确保股票代码是字符串类型
                    df[code_column] = df[code_column].astype(str)
                    # 补全股票代码，确保格式正确
                    df[code_column] = df[code_column].apply(lambda x: x.zfill(6) if len(x) < 6 else x)
                    
                    # 查找指定股票代码的行
                    stock_row = df[df[code_column] == stock_code]
                    if not stock_row.empty:
                        row = stock_row.iloc[0]
                        
                        # 尝试不同的列名
                        stock_name = row.get('股票名称', '')
                        if not stock_name:
                            stock_name = row.get('品种名称', '')
                        if not stock_name:
                            stock_name = row.get('name', '')
                        
                        industry = row.get('行业', '')
                        if not industry:
                            industry = row.get('industry', '')
                        
                        list_date = row.get('上市时间', '')
                        if not list_date:
                            list_date = row.get('list_date', '')
                        if not list_date:
                            list_date = row.get('纳入日期', '')
                        
                        # 确保所有数据类型都是Pydantic可以序列化的类型
                        basic_info = {
                            "stock_code": str(stock_code),
                            "stock_name": str(stock_name),
                            "industry": str(industry),
                            "list_date": str(list_date)
                        }
                        
                        logger.info(f"从CSV文件成功读取股票 {stock_code} 基本信息: {basic_info}")
                        return basic_info
                    else:
                        logger.warning(f"CSV文件中不存在股票 {stock_code} 的基本信息")
                else:
                    logger.error("CSV文件中没有找到股票代码列")
            except Exception as e:
                logger.error(f"从CSV文件读取股票基本信息失败: {e}")
                logger.exception(e)
        else:
            logger.error(f"CSV文件不存在: {self.csv_file_path}")
        
        # 如果CSV文件读取失败，从默认测试股票数据中获取
        logger.warning("无法从CSV文件获取股票基本信息，尝试从默认测试股票数据中获取")
        default_stocks = [
            {"stock_code": "000001", "stock_name": "平安银行", "industry": "银行", "list_date": "1991-04-03"},
            {"stock_code": "000002", "stock_name": "万科A", "industry": "房地产", "list_date": "1991-01-29"},
            {"stock_code": "000008", "stock_name": "神州高铁", "industry": "交通运输", "list_date": "1992-05-07"},
            {"stock_code": "000009", "stock_name": "中国宝安", "industry": "综合", "list_date": "1991-06-25"},
            {"stock_code": "000012", "stock_name": "南玻A", "industry": "建筑材料", "list_date": "1992-02-28"}
        ]
        
        for stock in default_stocks:
            if stock['stock_code'] == stock_code:
                logger.info(f"从默认测试股票数据中获取股票 {stock_code} 基本信息: {stock}")
                return stock
        
        logger.error(f"无法从默认测试股票数据中获取股票 {stock_code} 的基本信息")
        return None
    
    def get_stock_historical_data(self, stock_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        获取股票历史交易数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期，格式为"YYYYMMDD"
            end_date: 结束日期，格式为"YYYYMMDD"
            
        Returns:
            股票历史交易数据，包含日期、开盘价、收盘价、最高价、最低价、成交量、成交额、涨跌幅等
        """
        try:
            logger.info(f"从akshare获取股票 {stock_code} 历史数据: {start_date} 到 {end_date}")
            df = ak.stock_zh_a_hist(symbol=stock_code, start_date=start_date, end_date=end_date, adjust="qfq")
            if not df.empty:
                logger.info(f"从akshare获取到股票 {stock_code} 的历史数据，共 {len(df)} 条记录")
                return df
            else:
                logger.warning(f"从akshare获取到的股票 {stock_code} 历史数据为空")
        except Exception as e:
            logger.error(f"从akshare获取股票历史数据失败: {e}")
            logger.exception(e)
        
        return None
    
    @cache_result(seconds=3600)  # 添加缓存装饰器，缓存1小时
    def get_industry_analysis_data(self) -> Optional[pd.DataFrame]:
        """
        获取行业分析数据
        
        Returns:
            行业分析数据DataFrame，包含行业名称、平均涨跌幅、波动率等指标
        """
        try:
            # 优先从数据库获取数据进行分析
            with session_getter() as db:
                # 获取所有股票基本信息
                stock_infos = db.query(StockInfo).all()
                if not stock_infos:
                    logger.error("无法获取股票列表，无法计算行业分析数据")
                    return None
                
                # 批量查询所有股票的历史数据，减少数据库查询次数
                stock_codes = [stock_info.stock_code for stock_info in stock_infos]
                all_stock_dailies = db.query(StockDaily).filter(StockDaily.stock_code.in_(stock_codes)).all()
                
                # 按股票代码分组历史数据，提高查询效率
                stock_daily_map = {}
                for stock_daily in all_stock_dailies:
                    if stock_daily.stock_code not in stock_daily_map:
                        stock_daily_map[stock_daily.stock_code] = []
                    stock_daily_map[stock_daily.stock_code].append(stock_daily)
                
                # 计算行业数据
                industry_data = {}
                for stock_info in stock_infos:
                    if not stock_info.industry or stock_info.industry == "未知":
                        continue
                    
                    industry = stock_info.industry
                    stock_code = stock_info.stock_code
                    
                    # 从映射中获取该股票的历史数据，避免重复查询
                    stock_dailies = stock_daily_map.get(stock_code, [])
                    if not stock_dailies:
                        continue
                    
                    # 计算该股票的涨跌幅和波动率
                    change_percents = []
                    for stock_daily in stock_dailies:
                        if stock_daily.change_percent is not None:
                            change_percents.append(stock_daily.change_percent)
                    
                    if not change_percents:
                        continue
                    
                    # 计算平均值和波动率
                    avg_change = sum(change_percents) / len(change_percents)
                    volatility = pd.Series(change_percents).std()
                    
                    # 累加行业数据
                    if industry not in industry_data:
                        industry_data[industry] = {
                            "stock_count": 0,
                            "total_change": 0,
                            "volatilities": []
                        }
                    
                    industry_data[industry]["stock_count"] += 1
                    industry_data[industry]["total_change"] += avg_change
                    industry_data[industry]["volatilities"].append(volatility)
                
                # 计算行业平均指标
                industry_df = []
                for industry, data in industry_data.items():
                    if data["stock_count"] > 0:
                        avg_change = data["total_change"] / data["stock_count"]
                        avg_volatility = sum(data["volatilities"]) / len(data["volatilities"])
                        
                        industry_df.append({
                            "industry": str(industry),
                            "stock_count": int(data["stock_count"]),
                            "avg_change": float(avg_change),
                            "avg_volatility": float(avg_volatility)
                        })
                
                if industry_df:
                    logger.info(f"从数据库获取到 {len(industry_df)} 个行业的分析数据")
                    return pd.DataFrame(industry_df)
            
            logger.warning("数据库中行业分析数据不足")
            return None
        except Exception as e:
            logger.error(f"获取行业分析数据失败: {e}")
            logger.exception(e)
            return None

    def analyze_industry(self, industry: str, days: int = 90) -> Optional[Dict]:
        """
        分析行业情况
        
        Args:
            industry: 行业名称
            days: 分析天数
            
        Returns:
            行业分析结果，包含行业名称、分析周期、股票数量、平均涨跌幅、波动率、上涨天数、下跌天数、上涨天数占比、分析总结等
        """
        try:
            logger.info(f"分析 {industry} 行业情况，周期 {days} 天")
            
            # 获取该行业的趋势数据
            industry_trend = self.get_industry_trend(industry)
            if not industry_trend or not industry_trend.get("stock_trends"):
                logger.error(f"无法获取 {industry} 行业的趋势数据")
                return None
            
            # 分析行业表现
            total_change = 0
            positive_days = 0
            negative_days = 0
            stock_count = len(industry_trend.get("stock_trends", {}))
            
            # 获取所有日期并排序
            all_dates = set()
            for stock_data in industry_trend.get("stock_trends", {}).values():
                for item in stock_data:
                    if item.get("date"):
                        all_dates.add(item.get("date"))
            sorted_dates = sorted(list(all_dates))
            
            # 只分析最近days天的数据
            recent_dates = sorted_dates[-days:] if len(sorted_dates) > days else sorted_dates
            
            # 分析每天的表现
            daily_performance = []
            for date in recent_dates:
                day_change = 0
                day_count = 0
                
                for stock_data in industry_trend.get("stock_trends", {}).values():
                    for item in stock_data:
                        if item.get("date") == date and item.get("change_percent") is not None:
                            day_change += item.get("change_percent")
                            day_count += 1
                            break
                
                if day_count > 0:
                    avg_change = day_change / day_count
                    daily_performance.append({
                        "date": date,
                        "change": avg_change
                    })
                    
                    if avg_change > 0:
                        positive_days += 1
                    elif avg_change < 0:
                        negative_days += 1
                    
                    total_change += avg_change
            
            # 计算总平均涨跌幅和波动率
            avg_change = total_change / len(daily_performance) if daily_performance else 0
            volatility = pd.Series([item["change"] for item in daily_performance]).std() if daily_performance else 0
            positive_rate = (positive_days / len(daily_performance) * 100) if daily_performance else 0
            
            # 生成分析总结
            summary = f"{industry}行业在过去{days}天的表现："
            
            if avg_change > 0.5:
                summary += f"整体表现强劲，平均涨幅为{(avg_change * 100):.2f}%，"
            elif avg_change > 0:
                summary += f"整体表现良好，平均涨幅为{(avg_change * 100):.2f}%，"
            elif avg_change > -0.5:
                summary += f"整体表现平稳，平均跌幅为{abs(avg_change * 100):.2f}%，"
            else:
                summary += f"整体表现较弱，平均跌幅为{abs(avg_change * 100):.2f}%，"
            
            summary += f"上涨天数占比{positive_rate:.2f}%，"
            
            if volatility > 2:
                summary += "波动性较大，"
            elif volatility > 1:
                summary += "波动性适中，"
            else:
                summary += "波动性较小，"
            
            summary += "建议关注该行业的龙头股票表现，结合宏观经济环境和行业政策进行投资决策。"
            
            # 生成分析结果
            analysis_result = {
                "industry": industry,
                "period": f"{days}天",
                "stock_count": stock_count,
                "avg_change": float(avg_change),
                "volatility": float(volatility),
                "positive_days": positive_days,
                "negative_days": negative_days,
                "positive_rate": f"{positive_rate:.2f}%",
                "daily_performance": daily_performance,
                "summary": summary
            }
            
            logger.info(f"完成 {industry} 行业分析")
            return analysis_result
        except Exception as e:
            logger.error(f"分析行业失败: {e}")
            logger.exception(e)
            return None
    
    async def analyze_industry_with_llm(self, industry: str, days: int = 90) -> Optional[Dict]:
        """
        使用大模型分析单个行业
        
        Args:
            industry: 行业名称
            days: 分析天数
            
        Returns:
            大模型分析结果，包含行业名称、分析周期、股票数量、平均涨跌幅、波动率、上涨天数、下跌天数、上涨天数占比、大模型分析报告等
        """
        try:
            logger.info(f"使用大模型分析 {industry} 行业情况，周期 {days} 天")
            
            # 获取行业分析数据
            industry_data = self.analyze_industry(industry, days)
            if not industry_data:
                logger.error(f"无法获取 {industry} 行业的分析数据")
                return None
            
            # 准备大模型输入
            prompt = industry_analysis_prompt.format(
                industry_name=industry,
                days=days,
                industry_data=str(industry_data)
            )
            
            # 获取大模型实例
            llm = ModelManager.get_conversation_model()
            
            # 调用大模型进行分析
            messages = [HumanMessage(content=prompt)]
            response = await llm.ainvoke(messages)
            
            # 生成分析结果
            analysis_result = {
                "industry": industry,
                "period": f"{days}天",
                "stock_count": industry_data.get("stock_count", 0),
                "avg_change": industry_data.get("avg_change", 0),
                "volatility": industry_data.get("volatility", 0),
                "positive_days": industry_data.get("positive_days", 0),
                "negative_days": industry_data.get("negative_days", 0),
                "positive_rate": industry_data.get("positive_rate", "0%"),
                "llm_analysis": response.content
            }
            
            logger.info(f"完成 {industry} 行业大模型分析")
            return analysis_result
        except Exception as e:
            logger.error(f"使用大模型分析行业失败: {e}")
            logger.exception(e)
            return None
    
    async def analyze_all_industries_with_llm(self, days: int = 90) -> Optional[Dict]:
        """
        使用大模型分析所有行业
        
        Args:
            days: 分析天数
            
        Returns:
            大模型分析结果，包含分析周期、行业数量、各行业分析数据、大模型综合分析报告等
        """
        try:
            logger.info(f"使用大模型分析所有行业情况，周期 {days} 天")
            
            # 获取所有行业分析数据
            industry_analysis = self.get_industry_analysis()
            if not industry_analysis or not industry_analysis.get("industry_analysis"):
                logger.error("无法获取行业分析数据")
                return None
            
            # 准备大模型输入
            industries_data = industry_analysis.get("industry_analysis", [])
            prompt = all_industries_analysis_prompt.format(
                days=days,
                industries_data=str(industries_data)
            )
            
            # 获取大模型实例
            llm = ModelManager.get_conversation_model()
            
            # 调用大模型进行分析
            messages = [HumanMessage(content=prompt)]
            response = await llm.ainvoke(messages)
            
            # 生成分析结果
            analysis_result = {
                "period": f"{days}天",
                "industry_count": len(industries_data),
                "industries_data": industries_data,
                "llm_analysis": response.content
            }
            
            logger.info("完成所有行业大模型分析")
            return analysis_result
        except Exception as e:
            logger.error(f"使用大模型分析所有行业失败: {e}")
            logger.exception(e)
            return None
