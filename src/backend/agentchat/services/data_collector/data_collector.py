import os
import sys
import time
import akshare as ak
import pandas as pd
from datetime import datetime
from loguru import logger
from typing import List, Dict, Optional, Tuple

# 添加项目根目录到Python路径，确保所有模块都能被正确导入
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
# 向上一级目录: data_collector
parent_dir = os.path.dirname(os.path.abspath(__file__))
# 向上一级目录: services
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

# 确保能够导入后端的数据库模块
session_getter = None
StockInfo = None
StockDaily = None

# 使用importlib动态导入，避免循环导入问题
try:
    import importlib.util
    import sys
    
    # 直接导入stock模型文件
    stock_model_path = os.path.join(src_dir, 'backend', 'agentchat', 'database', 'models', 'stock.py')
    logger.info(f"尝试从文件导入stock模型: {stock_model_path}")
    
    if os.path.exists(stock_model_path):
        spec = importlib.util.spec_from_file_location("stock_model", stock_model_path)
        stock_model = importlib.util.module_from_spec(spec)
        sys.modules["stock_model"] = stock_model
        spec.loader.exec_module(stock_model)
        
        StockInfo = stock_model.StockInfo
        StockDaily = stock_model.StockDaily
        logger.info("成功导入StockInfo和StockDaily模型")
    else:
        logger.error(f"stock模型文件不存在: {stock_model_path}")
    
    # 导入session_getter，避免导入整个database模块
    session_path = os.path.join(src_dir, 'backend', 'agentchat', 'database', 'session.py')
    logger.info(f"尝试从文件导入session: {session_path}")
    
    if os.path.exists(session_path):
        # 读取session.py文件内容
        with open(session_path, 'r', encoding='utf-8') as f:
            session_content = f.read()
        
        # 修改导入语句，避免导入整个database模块
        # 直接创建一个简化的session_getter函数，并确保所有依赖都在作用域中
        from contextlib import contextmanager
        from sqlmodel import Session, create_engine
        from src.backend.agentchat.settings import app_settings
        import asyncio
        
        # 确保mysql配置存在
        if not app_settings.mysql:
            app_settings.mysql = {
                'endpoint': 'mysql+pymysql://root:qwe123@localhost:3306/agentchat',
                'async_endpoint': 'mysql+aiomysql://root:qwe123@localhost:3306/agentchat'
            }
        
        # 创建数据库引擎
        engine = create_engine(app_settings.mysql.get('endpoint'),
                               pool_pre_ping=True,
                               pool_recycle=3600,
                               connect_args={"charset": "utf8mb4",
                                             "use_unicode": True,
                                             "init_command": "SET SESSION time_zone = '+08:00'"})
        
        @contextmanager
        def session_getter():
            session = Session(engine)
            try:
                yield session
            except Exception as e:
                logger.error(f'Session rollback because of exception:{e}')
                session.rollback()
                raise
            finally:
                session.close()
        
        logger.info("成功创建session_getter")
    else:
        logger.error(f"session文件不存在: {session_path}")
    
except Exception as e:
    logger.error(f"导入数据库模块失败: {e}")
    # 继续执行，数据库功能可能不可用，但其他功能仍然可以使用
    import traceback
    traceback.print_exc()

class DataCollector:
    def __init__(self):
        """初始化数据收集器"""
        # 修正CSV文件路径，使用项目根目录下的项目计划文件夹
        current_file = os.path.abspath(__file__)
        # 向上一级目录: data_collector
        parent_dir = os.path.dirname(current_file)
        # 向上一级目录: services
        parent_dir = os.path.dirname(parent_dir)
        # 向上一级目录: agentchat
        parent_dir = os.path.dirname(parent_dir)
        # 向上一级目录: backend
        parent_dir = os.path.dirname(parent_dir)
        # 向上一级目录: src
        parent_dir = os.path.dirname(parent_dir)
        # 向上一级目录: 项目根目录
        parent_dir = os.path.dirname(parent_dir)
        
        self.csv_file_path = os.path.join(parent_dir, "项目计划", "hs300_data.csv")
        self.cache_dir = os.path.join(os.path.dirname(current_file), "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        # 确保项目计划目录存在
        os.makedirs(os.path.dirname(self.csv_file_path), exist_ok=True)
    
    def get_stock_basic_info(self, stock_code: str) -> Optional[Dict]:
        """获取股票基本信息
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票基本信息字典，如果获取失败返回None
        """
        # 检查股票代码是否为空
        if not stock_code:
            logger.error("股票代码为空，无法获取基本信息")
            return None
        
        # 1. 优先从CSV文件读取（根据用户要求）
        logger.info(f"从CSV文件读取股票 {stock_code} 基本信息")
        if os.path.exists(self.csv_file_path):
            try:
                import pandas as pd
                df = pd.read_csv(self.csv_file_path)
                # 尝试不同的列名查找股票信息
                for _, row in df.iterrows():
                    # 尝试不同的股票代码列名
                    csv_stock_code = row.get('股票代码', '')
                    if not csv_stock_code:
                        csv_stock_code = row.get('品种代码', '')
                    if not csv_stock_code:
                        csv_stock_code = row.get('code', '')
                    
                    # 确保股票代码格式一致
                    csv_stock_code = str(csv_stock_code)
                    if len(csv_stock_code) < 6:
                        csv_stock_code = csv_stock_code.zfill(6)
                    
                    if csv_stock_code == stock_code:
                        # 提取股票信息
                        stock_name = row.get('股票名称', '')
                        if not stock_name:
                            stock_name = row.get('品种名称', '')
                        if not stock_name:
                            stock_name = row.get('name', '')
                        
                        # 提取行业信息（优先从CSV文件读取，根据用户要求）
                        industry = row.get('行业', '')
                        if not industry:
                            industry = row.get('所属行业', '')
                        if not industry:
                            industry = row.get('industry', '')
                        # 不再默认设置为"未知"，如果CSV中没有行业信息，保持为空
                        
                        list_date = row.get('上市时间', '')
                        if not list_date:
                            list_date = row.get('list_date', '')
                        if not list_date:
                            list_date = row.get('纳入日期', '')
                        
                        info_dict = {
                            "stock_code": stock_code,
                            "stock_name": stock_name or stock_code,
                            "industry": industry,
                            "list_date": list_date
                        }
                        
                        logger.info(f"从CSV文件成功读取股票 {stock_code} 基本信息: {info_dict}")
                        
                        # 保存到数据库
                        if session_getter and StockInfo:
                            try:
                                with session_getter() as db:
                                    logger.info(f"保存股票 {stock_code} 基本信息到数据库")
                                    # 检查是否已存在
                                    existing_stock = db.query(StockInfo).filter(StockInfo.stock_code == stock_code).first()
                                    if existing_stock:
                                        logger.info(f"股票 {stock_code} 基本信息已存在，更新数据")
                                        existing_stock.stock_name = info_dict['stock_name']
                                        existing_stock.industry = info_dict['industry']
                                        existing_stock.list_date = info_dict['list_date']
                                    else:
                                        logger.info(f"股票 {stock_code} 基本信息不存在，创建新记录")
                                        new_stock_info = StockInfo(
                                            stock_code=info_dict['stock_code'],
                                            stock_name=info_dict['stock_name'],
                                            industry=info_dict['industry'],
                                            list_date=info_dict['list_date']
                                        )
                                        db.add(new_stock_info)
                                    db.commit()
                                    logger.info(f"股票 {stock_code} 基本信息保存成功")
                            except Exception as e:
                                logger.error(f"保存股票基本信息到数据库失败: {e}")
                                # 只记录错误信息，不记录完整异常堆栈
                                logger.error(f"保存失败原因: {str(e)}")
                        elif session_getter:
                            logger.warning("StockInfo模型未导入，无法保存股票基本信息到数据库")
                        
                        return info_dict
            except Exception as e:
                logger.warning(f"从CSV文件读取股票基本信息失败: {e}")
                logger.exception(e)
        
        # 2. 从数据库查询
        if session_getter:
            try:
                with session_getter() as db:
                    logger.info(f"从数据库查询股票 {stock_code} 基本信息")
                    stock_info = db.query(StockInfo).filter(StockInfo.stock_code == stock_code).first()
                    if stock_info:
                        logger.info(f"数据库中存在股票 {stock_code} 的基本信息")
                        return {
                            "stock_code": stock_info.stock_code,
                            "stock_name": stock_info.stock_name,
                            "industry": stock_info.industry,
                            "list_date": stock_info.list_date
                        }
                    else:
                        logger.info(f"数据库中不存在股票 {stock_code} 的基本信息")
            except Exception as e:
                logger.error(f"数据库查询股票基本信息失败: {e}")
                logger.exception(e)
        
        # 3. 从akshare获取
        try:
            logger.info(f"从akshare获取股票 {stock_code} 基本信息")
            # 尝试使用不同的接口获取股票基本信息
            try:
                df = ak.stock_individual_info_em(symbol=stock_code)
            except Exception as e:
                logger.warning(f"stock_individual_info_em接口失败，尝试使用其他接口: {e}")
                # 尝试使用其他接口
                try:
                    df = ak.stock_basic_info_em(symbol=stock_code)
                except Exception as e2:
                    logger.warning(f"stock_basic_info_em接口失败: {e2}")
                    # 如果所有接口都失败，返回默认信息
                    info_dict = {
                        "stock_code": stock_code,
                        "stock_name": stock_code,
                        "industry": "未知",
                        "list_date": ""
                    }
                    # 保存到数据库
                    if session_getter and StockInfo:
                        try:
                            with session_getter() as db:
                                logger.info(f"保存股票 {stock_code} 基本信息到数据库")
                                logger.info(f"保存的数据: {info_dict}")
                                # 检查是否已存在
                                existing_stock = db.query(StockInfo).filter(StockInfo.stock_code == stock_code).first()
                                if existing_stock:
                                    logger.info(f"股票 {stock_code} 基本信息已存在，更新数据")
                                    existing_stock.stock_name = info_dict['stock_name']
                                    existing_stock.industry = info_dict['industry']
                                    existing_stock.list_date = info_dict['list_date']
                                else:
                                    logger.info(f"股票 {stock_code} 基本信息不存在，创建新记录")
                                    new_stock_info = StockInfo(
                                        stock_code=info_dict['stock_code'],
                                        stock_name=info_dict['stock_name'],
                                        industry=info_dict['industry'],
                                        list_date=info_dict['list_date']
                                    )
                                    db.add(new_stock_info)
                                db.commit()
                                logger.info(f"股票 {stock_code} 基本信息保存成功")
                        except Exception as e3:
                            logger.error(f"保存股票基本信息到数据库失败: {e3}")
                            # 只记录错误信息，不记录完整异常堆栈
                            logger.error(f"保存失败原因: {str(e3)}")
                    elif session_getter:
                        logger.warning("StockInfo模型未导入，无法保存股票基本信息到数据库")
                    return info_dict
            
            # 提取需要的信息
            info_dict = {
                "stock_code": stock_code,
                "stock_name": stock_code,
                "industry": "未知",
                "list_date": ""
            }
            
            # 尝试从不同的数据结构中提取信息
            try:
                # 尝试第一种数据结构
                if '项目' in df.columns and '最新价' in df.columns:
                    logger.info(f"使用第一种数据结构解析股票基本信息")
                    if '股票名称' in df['项目'].values:
                        info_dict['stock_name'] = df.loc[df['项目'] == '股票名称', '最新价'].values[0]
                    if '所属行业' in df['项目'].values:
                        info_dict['industry'] = df.loc[df['项目'] == '所属行业', '最新价'].values[0]
                    if '上市日期' in df['项目'].values:
                        info_dict['list_date'] = df.loc[df['项目'] == '上市日期', '最新价'].values[0]
                # 尝试第二种数据结构
                elif 'item' in df.columns and 'value' in df.columns:
                    logger.info(f"使用第二种数据结构解析股票基本信息")
                    if '股票名称' in df['item'].values:
                        info_dict['stock_name'] = df.loc[df['item'] == '股票名称', 'value'].values[0]
                    if '所属行业' in df['item'].values:
                        info_dict['industry'] = df.loc[df['item'] == '所属行业', 'value'].values[0]
                    if '上市日期' in df['item'].values:
                        info_dict['list_date'] = df.loc[df['item'] == '上市日期', 'value'].values[0]
                # 尝试第三种数据结构 - 直接返回的字典
                elif isinstance(df, dict):
                    logger.info(f"使用第三种数据结构解析股票基本信息")
                    info_dict['stock_name'] = df.get('股票名称', stock_code)
                    info_dict['industry'] = df.get('所属行业', '未知')
                    info_dict['list_date'] = df.get('上市日期', '')
                else:
                    logger.info(f"无法识别数据结构，使用默认值")
                    logger.info(f"数据结构: {type(df)}")
                    if hasattr(df, 'columns'):
                        logger.info(f"数据列: {df.columns.tolist()}")
                    if hasattr(df, 'head'):
                        logger.info(f"数据前5行: {df.head()}")
            except Exception as e:
                logger.warning(f"解析股票基本信息失败: {e}")
                logger.exception(e)
            
            # 保存到数据库
            if session_getter and StockInfo:
                try:
                    with session_getter() as db:
                        logger.info(f"保存股票 {stock_code} 基本信息到数据库")
                        logger.info(f"保存的数据: {info_dict}")
                        # 检查是否已存在
                        existing_stock = db.query(StockInfo).filter(StockInfo.stock_code == stock_code).first()
                        if existing_stock:
                            logger.info(f"股票 {stock_code} 基本信息已存在，更新数据")
                            existing_stock.stock_name = info_dict['stock_name']
                            existing_stock.industry = info_dict['industry']
                            existing_stock.list_date = info_dict['list_date']
                        else:
                            logger.info(f"股票 {stock_code} 基本信息不存在，创建新记录")
                            new_stock_info = StockInfo(
                                stock_code=info_dict['stock_code'],
                                stock_name=info_dict['stock_name'],
                                industry=info_dict['industry'],
                                list_date=info_dict['list_date']
                            )
                            db.add(new_stock_info)
                        db.commit()
                        logger.info(f"股票 {stock_code} 基本信息保存成功")
                except Exception as e:
                    logger.error(f"保存股票基本信息到数据库失败: {e}")
                    # 只记录错误信息，不记录完整异常堆栈
                    logger.error(f"保存失败原因: {str(e)}")
            elif session_getter:
                logger.warning("StockInfo模型未导入，无法保存股票基本信息到数据库")
            
            return info_dict
        except Exception as e:
            logger.error(f"从akshare获取股票基本信息失败: {e}")
            logger.exception(e)
        
        return None
    
    def get_stock_historical_data(self, stock_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """获取股票历史交易数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期，格式为YYYYMMDD
            end_date: 结束日期，格式为YYYYMMDD
            
        Returns:
            股票历史交易数据DataFrame，如果获取失败返回None
        """
        # 检查股票代码是否为空
        if not stock_code:
            logger.error("股票代码为空，无法获取历史数据")
            return None
        
        # 1. 先从数据库查询
        if session_getter and StockDaily:
            try:
                with session_getter() as db:
                    logger.info(f"从数据库查询股票 {stock_code} 历史数据: {start_date} 到 {end_date}")
                    stock_dailies = db.query(StockDaily).filter(
                        StockDaily.stock_code == stock_code,
                        StockDaily.trade_date >= start_date,
                        StockDaily.trade_date <= end_date
                    ).all()
                    
                    if stock_dailies:
                        logger.info(f"数据库中存在股票 {stock_code} 的历史数据，共 {len(stock_dailies)} 条记录")
                        data = []
                        for daily in stock_dailies:
                            data.append({
                                "日期": daily.trade_date,
                                "开盘": daily.open_price,
                                "收盘": daily.close_price,
                                "最高": daily.high_price,
                                "最低": daily.low_price,
                                "成交量": daily.volume,
                                "成交额": daily.amount,
                                "涨跌幅": daily.change_percent
                            })
                        return pd.DataFrame(data)
                    else:
                        logger.info(f"数据库中不存在股票 {stock_code} 的历史数据，将从akshare获取")
            except Exception as e:
                logger.error(f"数据库查询股票历史数据失败: {e}")
                logger.exception(e)
        
        # 2. 从akshare获取
        try:
            logger.info(f"从akshare获取股票 {stock_code} 历史数据: {start_date} 到 {end_date}")
            df = ak.stock_zh_a_hist(symbol=stock_code, start_date=start_date, end_date=end_date, adjust="qfq")
            if not df.empty:
                logger.info(f"从akshare获取到股票 {stock_code} 的历史数据，共 {len(df)} 条记录")
                # 保存到数据库
                if session_getter and StockDaily:
                    try:
                        with session_getter() as db:
                            logger.info(f"保存股票 {stock_code} 历史数据到数据库")
                            # 批量保存，减少数据库操作次数
                            daily_records = []
                            for _, row in df.iterrows():
                                # 检查是否已存在
                                existing_daily = db.query(StockDaily).filter(
                                    StockDaily.stock_code == stock_code,
                                    StockDaily.trade_date == row['日期']
                                ).first()
                                if not existing_daily:
                                    new_daily = StockDaily(
                                        stock_code=stock_code,
                                        trade_date=row['日期'],
                                        open_price=row['开盘'],
                                        close_price=row['收盘'],
                                        high_price=row['最高'],
                                        low_price=row['最低'],
                                        volume=row['成交量'],
                                        amount=row['成交额'],
                                        change_percent=row['涨跌幅']
                                    )
                                    daily_records.append(new_daily)
                            
                            if daily_records:
                                logger.info(f"将保存 {len(daily_records)} 条新的历史数据记录")
                                logger.info(f"第一条记录日期: {daily_records[0].trade_date}, 最后一条记录日期: {daily_records[-1].trade_date}")
                                db.add_all(daily_records)
                                db.commit()
                                # 验证保存结果
                                saved_count = db.query(StockDaily).filter(
                                    StockDaily.stock_code == stock_code
                                ).count()
                                logger.info(f"股票 {stock_code} 历史数据保存成功，数据库中该股票共有 {saved_count} 条记录")
                            else:
                                logger.info(f"股票 {stock_code} 历史数据已存在，无需保存")
                                # 检查数据库中已存在的记录数量
                                existing_count = db.query(StockDaily).filter(
                                    StockDaily.stock_code == stock_code
                                ).count()
                                logger.info(f"数据库中该股票已有 {existing_count} 条记录")
                    except Exception as e:
                        logger.error(f"保存股票历史数据到数据库失败: {e}")
                        # 只记录错误信息，不记录完整异常堆栈
                        logger.error(f"保存失败原因: {str(e)}")
                elif session_getter:
                    logger.warning("StockDaily模型未导入，无法保存股票历史数据到数据库")
                
                return df
            else:
                logger.warning(f"从akshare获取到的股票 {stock_code} 历史数据为空")
        except Exception as e:
            logger.error(f"从akshare获取股票历史数据失败: {e}")
            logger.exception(e)
        
        return None
    
    def get_hs300_stocks(self) -> List[Dict]:
        """获取沪深300成分股列表
        
        Returns:
            沪深300成分股列表，每个元素包含股票代码和股票名称
        """
        # 固定从CSV文件读取（根据用户要求）
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
                        stocks.append({
                            "stock_code": stock_code,
                            "stock_name": stock_name,
                            "list_date": list_date
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
            {"stock_code": "000001", "stock_name": "平安银行", "list_date": "1991-04-03"},
            {"stock_code": "000002", "stock_name": "万科A", "list_date": "1991-01-29"},
            {"stock_code": "000008", "stock_name": "神州高铁", "list_date": "1992-05-07"},
            {"stock_code": "000009", "stock_name": "中国宝安", "list_date": "1991-06-25"},
            {"stock_code": "000012", "stock_name": "南玻A", "list_date": "1992-02-28"}
        ]
    
    def collect_all_stock_data(self, start_year: int = 2025):
        """收集所有股票数据
        
        Args:
            start_year: 开始年份，默认从2025年开始
        """
        # 1. 固定从CSV导入stock_info
        logger.info("开始从CSV导入stock_info数据...")
        stocks = self.get_hs300_stocks()
        if not stocks:
            logger.error("获取沪深300成分股列表失败，无法继续收集数据")
            return
        
        total_stocks = len(stocks)
        current_date = datetime.now().strftime("%Y%m%d")
        
        for i, stock in enumerate(stocks):
            stock_code = stock['stock_code']
            stock_name = stock['stock_name']
            
            logger.info(f"处理第 {i+1}/{total_stocks} 只股票: {stock_code} - {stock_name}")
            
            # 获取股票基本信息（固定从CSV导入）
            basic_info = self.get_stock_basic_info(stock_code)
            if not basic_info:
                logger.warning(f"无法获取股票 {stock_code} 的基本信息，跳过")
                continue
            
            # 2. 处理stock_daily数据
            logger.info(f"处理股票 {stock_code} 的stock_daily数据")
            
            # 检查数据库中是否已有该股票的daily数据
            last_trade_date = None
            if session_getter and StockDaily:
                try:
                    with session_getter() as db:
                        # 查询该股票的最新交易日期
                        latest_daily = db.query(StockDaily).filter(
                            StockDaily.stock_code == stock_code
                        ).order_by(StockDaily.trade_date.desc()).first()
                        
                        if latest_daily:
                            last_trade_date = latest_daily.trade_date
                            logger.info(f"数据库中已有股票 {stock_code} 的daily数据，最新日期: {last_trade_date}")
                        else:
                            logger.info(f"数据库中无股票 {stock_code} 的daily数据，从20250101开始导入")
                except Exception as e:
                    logger.error(f"查询股票 {stock_code} 的daily数据失败: {e}")
                    last_trade_date = None
            
            # 确定导入日期范围
            if last_trade_date:
                # 有数据，增量导入（从最新日期的下一天开始）
                try:
                    # 解析最新日期
                    last_date = datetime.strptime(last_trade_date, "%Y-%m-%d")
                    # 从下一天开始
                    start_date = (last_date + pd.Timedelta(days=1)).strftime("%Y%m%d")
                    end_date = current_date
                    logger.info(f"增量导入股票 {stock_code} 的daily数据: {start_date} 到 {end_date}")
                except Exception as e:
                    logger.error(f"解析日期失败: {e}")
                    # 解析失败，从20250101开始导入
                    start_date = "20250101"
                    end_date = current_date
                    logger.info(f"日期解析失败，从20250101开始导入股票 {stock_code} 的daily数据")
            else:
                # 无数据，从20250101开始导入
                start_date = "20250101"
                end_date = current_date
                logger.info(f"从20250101开始导入股票 {stock_code} 的daily数据: {start_date} 到 {end_date}")
            
            # 检查日期范围是否有效
            if start_date > end_date:
                logger.info(f"股票 {stock_code} 的daily数据已最新，无需导入")
                continue
            
            # 获取并导入历史数据
            df = self.get_stock_historical_data(stock_code, start_date, end_date)
            if df is not None:
                logger.info(f"成功获取股票 {stock_code} 的daily数据，共 {len(df)} 条记录")
            else:
                logger.warning(f"获取股票 {stock_code} 的daily数据失败")
            
            # 避免请求过于频繁
            time.sleep(0.5)
    
    def get_industry_analysis_data(self) -> Optional[pd.DataFrame]:
        """获取行业分析数据
        
        Returns:
            行业分析数据DataFrame，包含行业名称、平均涨跌幅、波动率等指标
        """
        if not session_getter:
            logger.warning("数据库会话管理器未导入，无法获取行业分析数据")
            return None
        
        try:
            # 使用已导入的StockInfo和StockDaily
            if not StockInfo or not StockDaily:
                logger.warning("数据库模型未导入，无法获取行业分析数据")
                return None
            
            with session_getter() as db:
                # 从数据库获取所有股票的基本信息和日频数据
                stock_infos = db.query(StockInfo).all()
                if not stock_infos:
                    logger.warning("数据库中没有股票基本信息")
                    return None
                
                industry_data = {}
                
                for stock_info in stock_infos:
                    stock_code = stock_info.stock_code
                    industry = stock_info.industry
                    
                    if not industry:
                        continue
                    
                    # 获取该股票的日频数据
                    stock_dailies = db.query(StockDaily).filter(
                        StockDaily.stock_code == stock_code
                    ).all()
                    
                    if not stock_dailies:
                        continue
                    
                    # 计算该股票的涨跌幅和波动率
                    change_percents = [daily.change_percent for daily in stock_dailies if daily.change_percent is not None]
                    if not change_percents:
                        continue
                    
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
                            "industry": industry,
                            "stock_count": data["stock_count"],
                            "avg_change": avg_change,
                            "avg_volatility": avg_volatility
                        })
                
                if not industry_df:
                    logger.warning("无法计算行业分析数据")
                    return None
                
                return pd.DataFrame(industry_df)
        except Exception as e:
            logger.error(f"获取行业分析数据失败: {e}")
            return None
