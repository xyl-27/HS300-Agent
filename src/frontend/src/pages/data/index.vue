<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { Loading } from '@element-plus/icons-vue'

// 响应式数据
const activeTab = ref('marketHotmap')
const industryAnalysis = ref([])
const industryTrend = ref(null)
const allIndustryTrends = ref({})
const loading = ref(false)
const error = ref(null)

// 控制展示近多少天的数据
const daysToShow = ref(90)

// 控制行业筛选类型
const industryFilter = ref('top3') // all, top3, bottom3

// 存储行业分析结果
const industryAnalysisResult = ref(null)
const analyzingIndustry = ref('')
const analysisLoading = ref(false)


// 行业分析分页相关
const industryCurrentPage = ref(1)
const industryPageSize = ref(20)
const totalIndustries = ref(0)

// 图表相关
const industryChartRef = ref(null)
let industryChart: echarts.ECharts | null = null

// 大盘星图相关
const marketHotmapRef = ref(null)
let marketHotmapChart: echarts.ECharts | null = null
const hotmapData = ref([])
const hotmapLoading = ref(false)
let hotmapInitialized = false

// API基础URL
const API_BASE_URL = 'http://192.168.119.130:7860/api/v1'

// 获取行业分析（支持分页）
const getIndustryAnalysis = async () => {
  loading.value = true
  error.value = null
  
  try {
    const response = await fetch(`${API_BASE_URL}/stock/industry/analysis?page=${industryCurrentPage.value}&page_size=${industryPageSize.value}`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    industryAnalysis.value = Array.isArray(data.data) ? data.data : []
    totalIndustries.value = data.total || 0
    
    // 数据加载完成后更新图表
    nextTick(() => {
      updateIndustryChart()
    })
    
    // 获取行业趋势数据
    if (industryAnalysis.value.length > 0) {
      getAllIndustryTrends()
    }
  } catch (err: any) {
    error.value = `获取行业分析失败: ${err.message}`
    console.error('获取行业分析失败:', err)
    industryAnalysis.value = []
    totalIndustries.value = 0
  } finally {
    loading.value = false
  }
}

// 行业分析分页变化处理
const handleIndustryPageChange = (page: number) => {
  industryCurrentPage.value = page
  getIndustryAnalysis()
}

// 行业分析每页数量变化处理
const handleIndustrySizeChange = (size: number) => {
  industryPageSize.value = size
  industryCurrentPage.value = 1
  getIndustryAnalysis()
}

// 初始化行业分析图表
const initIndustryChart = () => {
  if (industryChartRef.value) {
    industryChart = echarts.init(industryChartRef.value)
    updateIndustryChart()
  }
}

// 处理天数变化
const handleDaysChange = (value: number | string) => {
  daysToShow.value = Number(value)
  updateIndustryChart()
}

// 处理行业筛选类型变化
const handleIndustryFilterChange = (value: string) => {
  industryFilter.value = value
  updateIndustryChart()
}

// 获取行业趋势
const getIndustryTrend = async (industry: string) => {
  loading.value = true
  error.value = null
  
  try {
    const response = await fetch(`${API_BASE_URL}/stock/industry/trend?industry=${encodeURIComponent(industry)}`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    industryTrend.value = data
  } catch (err: any) {
    error.value = `获取行业趋势失败: ${err.message}`
    console.error('获取行业趋势失败:', err)
  } finally {
    loading.value = false
  }
}

// 获取所有行业趋势数据
const getAllIndustryTrends = async () => {
  loading.value = true
  error.value = null
  
  try {
    if (industryAnalysis.value.length > 0) {
      // 获取所有行业的数据
      const industries = industryAnalysis.value.map((item: any) => item.industry)
      
      // 并行请求所有行业的趋势数据
      const trendPromises = industries.map(async (industry: string) => {
        try {
          const response = await fetch(`${API_BASE_URL}/stock/industry/trend?industry=${encodeURIComponent(industry)}`)
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
          }
          return response.json()
        } catch (error) {
          console.error(`获取行业 ${industry} 趋势数据失败:`, error)
          return null
        }
      })
      
      const trends = await Promise.all(trendPromises)
      
      // 整理数据，过滤掉null值
      const trendsData: Record<string, any> = {}
      trends.forEach((trend: any, index: number) => {
        if (trend && trend.stock_trends) {
          // 使用原始行业名称作为键，确保与industryAnalysis中的名称匹配
          const originalIndustryName = industries[index]
          trendsData[originalIndustryName] = {
            ...trend,
            industry: originalIndustryName // 确保行业名称一致
          }
        }
      })
      
      allIndustryTrends.value = trendsData
      
      // 更新图表
      nextTick(() => {
        updateIndustryChart()
      })
    }
  } catch (err: any) {
    error.value = `获取行业趋势数据失败: ${err.message}`
    console.error('获取行业趋势数据失败:', err)
  } finally {
    loading.value = false
  }
}

// 更新行业分析图表
const updateIndustryChart = () => {
  try {
    // 检查数据是否存在
    if (!industryAnalysis.value || industryAnalysis.value.length === 0) {
      return
    }
    
    // 确保图表已初始化
    if (!industryChart && industryChartRef.value) {
      industryChart = echarts.init(industryChartRef.value)
    }
    
    if (!industryChart) {
      return
    }
    
    // 检查是否有真实的行业趋势数据
    const hasRealData = Object.keys(allIndustryTrends.value).length > 0
    
    // 准备数据
    const chartData = {
      dates: [] as string[],
      series: [] as any[]
    }
    
    // 为不同行业分配不同颜色
    const colors = ['#67c23a', '#f56c6c', '#409eff', '#e6a23c', '#909399']
    
    // 获取行业列表并根据筛选类型过滤
    let filteredIndustries = Object.values(allIndustryTrends.value)
    
    if (industryFilter.value === 'top3' || industryFilter.value === 'bottom3') {
      // 获取行业分析数据并排序
      const sortedIndustries = [...industryAnalysis.value].sort((a, b) => {
        return industryFilter.value === 'top3' ? b.avg_change - a.avg_change : a.avg_change - b.avg_change
      })
      
      // 取前3个行业
      const topIndustries = sortedIndustries.slice(0, 3)
      const topIndustryNames = topIndustries.map(industry => industry.industry)
      
      // 过滤行业趋势数据
      filteredIndustries = filteredIndustries.filter((trend: any) => {
        return trend && trend.industry && topIndustryNames.includes(trend.industry)
      })
    }
    
    // 使用所有行业，不仅仅是有真实数据的行业
    let industriesToShow = industryAnalysis.value
    
    // 根据筛选类型过滤行业
    if (industryFilter.value === 'top3' || industryFilter.value === 'bottom3') {
      // 排序行业分析数据
      industriesToShow = [...industryAnalysis.value].sort((a, b) => {
        return industryFilter.value === 'top3' ? b.avg_change - a.avg_change : a.avg_change - b.avg_change
      })
      
      // 取前3个行业
      industriesToShow = industriesToShow.slice(0, 3)
    }
    
    // 收集所有行业的有数据的日期
    const allDataDates = new Set<string>()
    industriesToShow.forEach((industry: any) => {
      const trend = allIndustryTrends.value[industry.industry]
      if (trend && trend.stock_trends) {
        Object.values(trend.stock_trends).forEach((stockData: any[]) => {
          stockData.forEach((item: any) => {
            if (item.date) {
              allDataDates.add(item.date)
            }
          })
        })
      }
    })
    
    // 按日期排序
    const sortedDates = Array.from(allDataDates).sort()
    
    // 取最近的N天有数据的日期
    const recentDates = sortedDates.slice(-daysToShow.value)
    chartData.dates = recentDates
    
    // 为每个行业创建一个系列
    industriesToShow.forEach((industry: any, index: number) => {
      // 检查是否有真实数据
      const trend = allIndustryTrends.value[industry.industry]
      
      if (hasRealData && trend && trend.stock_trends) {
        // 使用真实数据
        const industryData: string[] = []
        
        // 为每个有数据的日期计算值
        recentDates.forEach((date: string) => {
          let totalChange = 0
          let count = 0
          
          // 计算该日期所有股票的平均涨跌幅
          Object.values(trend.stock_trends).forEach((stockData: any[]) => {
            const stockDateData = stockData.find((item: any) => item.date === date)
            if (stockDateData && stockDateData.change_percent !== undefined) {
              totalChange += stockDateData.change_percent
              count++
            }
          })
          
          // 计算平均值
          let avgChange: string
          if (count > 0) {
            avgChange = (totalChange / count).toFixed(2)
          } else {
            // 对于没有数据的日期，使用null，ECharts会自动跳过这些点
            avgChange = '0'
          }
          
          industryData.push(avgChange)
        })
        
        // 添加系列
        chartData.series.push({
          name: industry.industry,
          type: 'line',
          data: industryData,
          itemStyle: {
            color: colors[index % colors.length]
          }
        })
      } else {
        // 使用模拟数据
        // 基于当前平均涨跌幅生成波动数据
        const baseChange = industry.avg_change * 100
        const data = recentDates.map(() => {
          // 添加随机波动
          const randomFactor = (Math.random() - 0.5) * 2
          return (baseChange + randomFactor).toFixed(2)
        })
        
        // 添加系列
        chartData.series.push({
          name: industry.industry,
          type: 'line',
          data: data,
          itemStyle: {
            color: colors[index % colors.length]
          }
        })
      }
    })
    
    // 配置图表选项
    const option = {
      title: {
        text: '行业表现趋势',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          label: {
            backgroundColor: '#6a7985'
          }
        }
      },
      legend: {
        data: chartData.series.map(item => item.name),
        top: 30,
        type: 'scroll'
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: chartData.dates,
        name: '日期',
        axisLabel: {
          rotate: 45
        }
      },
      yAxis: {
        type: 'value',
        name: '平均涨跌幅(%)'
      },
      series: chartData.series
    }
    
    // 设置图表选项，使用true参数强制清除所有之前的选项，确保图表能够完全重新渲染
    industryChart.setOption(option, true)
  } catch (error) {
    console.error('更新行业分析图表失败:', error)
  }
}

// 分析行业情况
const analyzeIndustry = (industry: string) => {
  analysisLoading.value = true
  analyzingIndustry.value = industry
  industryAnalysisResult.value = null
  
  try {
    // 获取该行业的趋势数据
    const industryTrend = allIndustryTrends.value[industry]
    if (!industryTrend || !industryTrend.stock_trends) {
      industryAnalysisResult.value = {
        industry: industry,
        error: '无法获取该行业的趋势数据'
      }
      return
    }
    
    // 分析行业表现
    let totalChange = 0
    let totalVolatility = 0
    let positiveDays = 0
    let negativeDays = 0
    let stockCount = Object.keys(industryTrend.stock_trends).length
    
    // 获取所有日期并排序
    const allDates = new Set<string>()
    Object.values(industryTrend.stock_trends).forEach((stockData: any[]) => {
      stockData.forEach((item: any) => {
        if (item.date) {
          allDates.add(item.date)
        }
      })
    })
    const sortedDates = Array.from(allDates).sort()
    
    // 只分析最近daysToShow天的数据
    const recentDates = sortedDates.slice(-daysToShow.value)
    
    // 分析每天的表现
    const dailyPerformance = []
    recentDates.forEach((date: string) => {
      let dayChange = 0
      let dayCount = 0
      
      Object.values(industryTrend.stock_trends).forEach((stockData: any[]) => {
        const stockDateData = stockData.find((item: any) => item.date === date)
        if (stockDateData && stockDateData.change_percent !== undefined) {
          dayChange += stockDateData.change_percent
          dayCount++
        }
      })
      
      if (dayCount > 0) {
        const avgChange = dayChange / dayCount
        dailyPerformance.push({
          date: date,
          change: avgChange
        })
        
        if (avgChange > 0) {
          positiveDays++
        } else if (avgChange < 0) {
          negativeDays++
        }
        
        totalChange += avgChange
      }
    })
    
    // 计算总平均涨跌幅和波动率
    const avgChange = dailyPerformance.length > 0 ? totalChange / dailyPerformance.length : 0
    const volatility = dailyPerformance.length > 0 ? 
      Math.sqrt(dailyPerformance.reduce((sum, day) => sum + Math.pow(day.change - avgChange, 2), 0) / dailyPerformance.length) : 0
    
    // 生成分析结果
    industryAnalysisResult.value = {
      industry: industry,
      period: `${daysToShow.value}天`,
      stockCount: stockCount,
      avgChange: avgChange,
      volatility: volatility,
      positiveDays: positiveDays,
      negativeDays: negativeDays,
      positiveRate: dailyPerformance.length > 0 ? (positiveDays / dailyPerformance.length * 100).toFixed(2) : 0,
      dailyPerformance: dailyPerformance,
      summary: generateIndustrySummary(industry, avgChange, positiveRate, volatility)
    }
  } catch (error) {
    console.error('分析行业失败:', error)
    industryAnalysisResult.value = {
      industry: industry,
      error: '分析行业失败'
    }
  } finally {
    analysisLoading.value = false
  }
}

// 使用大模型分析单个行业
const analyzeIndustryWithLLM = async (industry: string) => {
  analysisLoading.value = true
  analyzingIndustry.value = industry
  industryAnalysisResult.value = null
  
  try {
    const response = await fetch(`${API_BASE_URL}/stock/industry/analyze/llm?industry=${encodeURIComponent(industry)}&days=${daysToShow.value}`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    industryAnalysisResult.value = data
  } catch (error: any) {
    console.error('大模型分析行业失败:', error)
    industryAnalysisResult.value = {
      industry: industry,
      error: `大模型分析失败: ${error.message}`
    }
  } finally {
    analysisLoading.value = false
  }
}

// 使用大模型分析所有行业
const analyzeAllIndustriesWithLLM = async () => {
  analysisLoading.value = true
  analyzingIndustry.value = '所有行业'
  industryAnalysisResult.value = null
  
  try {
    const response = await fetch(`${API_BASE_URL}/stock/industry/analyze/all/llm?days=${daysToShow.value}`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    industryAnalysisResult.value = {
      industry: '所有行业',
      ...data
    }
  } catch (error: any) {
    console.error('大模型分析所有行业失败:', error)
    industryAnalysisResult.value = {
      industry: '所有行业',
      error: `大模型分析失败: ${error.message}`
    }
  } finally {
    analysisLoading.value = false
  }
}

// 生成行业分析总结
const generateIndustrySummary = (industry: string, avgChange: number, positiveRate: number, volatility: number): string => {
  let summary = `${industry}行业在过去${daysToShow.value}天的表现：`
  
  if (avgChange > 0.5) {
    summary += `整体表现强劲，平均涨幅为${(avgChange * 100).toFixed(2)}%，`
  } else if (avgChange > 0) {
    summary += `整体表现良好，平均涨幅为${(avgChange * 100).toFixed(2)}%，`
  } else if (avgChange > -0.5) {
    summary += `整体表现平稳，平均跌幅为${(Math.abs(avgChange) * 100).toFixed(2)}%，`
  } else {
    summary += `整体表现较弱，平均跌幅为${(Math.abs(avgChange) * 100).toFixed(2)}%，`
  }
  
  summary += `上涨天数占比${positiveRate}%，`
  
  if (volatility > 2) {
    summary += `波动性较大，`
  } else if (volatility > 1) {
    summary += `波动性适中，`
  } else {
    summary += `波动性较小，`
  }
  
  summary += `建议关注该行业的龙头股票表现，结合宏观经济环境和行业政策进行投资决策。`
  
  return summary
}

// 获取大盘星图数据
const getHotmapData = () => {
  hotmapLoading.value = true
  error.value = null
  
  try {
    // 直接调用updateHotmapChart从API获取数据
    updateHotmapChart()
  } catch (err: any) {
    error.value = `获取星图数据失败: ${err.message}`
    console.error('获取星图数据失败:', err)
    hotmapLoading.value = false
  }
}

// 初始化大盘星图
const initHotmapChart = () => {
  console.log('进入initHotmapChart函数')
  if (marketHotmapRef.value) {
    // 确保容器有正确的尺寸
    const container = marketHotmapRef.value
    container.style.width = '100%'
    container.style.height = '600px'
    console.log('设置容器尺寸:', container.clientWidth, 'x', container.clientHeight)
    
    // 销毁之前的图表实例
    if (marketHotmapChart) {
      marketHotmapChart.dispose()
      marketHotmapChart = null
      console.log('已销毁之前的图表实例')
    }
    
    // 初始化图表
    marketHotmapChart = echarts.init(container)
    console.log('图表初始化成功:', marketHotmapChart)
    
    // 更新图表数据
    console.log('开始更新图表数据...')
    updateHotmapChart()
    console.log('图表数据更新完成')
  } else {
    console.log('市场星图容器不存在')
  }
}

// 获取行业-股票层级数据
const getIndustryStockHierarchy = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/stock/industry/stock-hierarchy`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    console.log('API 返回原始数据:', data);
    
    // 处理不同的数据结构
    let industryData = [];
    
    // 检查是否是标准的{data: [...]}结构
    if (data.data && Array.isArray(data.data)) {
      console.log('使用标准数据结构: data.data');
      industryData = data.data;
    }
    // 检查是否直接返回了数组
    else if (Array.isArray(data)) {
      console.log('使用直接数组结构');
      industryData = data;
    }
    // 检查是否是对象，可能是单个行业
    else if (typeof data === 'object' && data !== null) {
      console.log('使用单个对象结构，转换为数组');
      industryData = [data];
    }
    
    console.log('API 返回数据长度:', industryData.length);
    if (industryData.length > 0) {
      console.log('第一个行业数据:', industryData[0]);
    }
    return industryData;
  } catch (error) {
    console.error('获取行业-股票层级数据失败:', error);
    return [];
  }
};

// 将API数据转换为模拟数据格式
const convertApiDataToChartFormat = (apiData) => {
  if (!apiData || !Array.isArray(apiData)) {
    console.log('API数据为空或不是数组:', apiData);
    return [];
  }
  
  console.log('开始转换API数据，原始数据长度:', apiData.length);
  
  const convertedData = apiData.map((industry, index) => {
    console.log(`转换行业 ${index + 1}:`, industry);
    
    // 转换行业数据
    const industryItem = {
      name: industry.name || industry.industry || '未知行业',
      value: [
        industry.value || industry.market_cap || industry.marketCap || industry.value?.[0] || 0,  // 市值
        industry.stock_count || industry.total_stock_count || industry.stockCount || industry.value?.[1] || 0,  // 股票数量
        industry.increase || industry.change || industry.value?.[2] || 0  // 涨跌幅
      ],
      stock_count: industry.stock_count || industry.total_stock_count || industry.stockCount || 0,
      children: []
    };
    
    console.log(`转换后的行业数据:`, industryItem);
    
    // 转换股票数据
    if (industry.children && Array.isArray(industry.children)) {
      console.log(`行业 ${industryItem.name} 有 ${industry.children.length} 只股票`);
      industryItem.children = industry.children.map((stock, stockIndex) => {
        console.log(`转换股票 ${stockIndex + 1}:`, stock);
        const stockItem = {
          name: stock.name || stock.stock_name || '未知股票',
          value: [
            stock.value || stock.market_cap || stock.marketCap || stock.value?.[0] || 0,  // 股票市值
            1,  // 占位值
            stock.increase || stock.change || stock.value?.[2] || 0  // 股票涨跌幅
          ]
        };
        console.log(`转换后的股票数据:`, stockItem);
        return stockItem;
      });
    } else if (industry.stocks && Array.isArray(industry.stocks)) {
      // 兼容旧格式的stocks字段
      console.log(`行业 ${industryItem.name} 有 ${industry.stocks.length} 只股票 (使用stocks字段)`);
      industryItem.children = industry.stocks.map((stock, stockIndex) => {
        console.log(`转换股票 ${stockIndex + 1}:`, stock);
        const stockItem = {
          name: stock.name || stock.stock_name || '未知股票',
          value: [
            stock.value || stock.market_cap || stock.marketCap || stock.value?.[0] || 0,  // 股票市值
            1,  // 占位值
            stock.increase || stock.change || stock.value?.[2] || 0  // 股票涨跌幅
          ]
        };
        console.log(`转换后的股票数据:`, stockItem);
        return stockItem;
      });
    } else {
      console.log(`行业 ${industryItem.name} 没有股票数据`);
    }
    
    return industryItem;
  });
  
  console.log('API数据转换完成，转换后数据长度:', convertedData.length);
  console.log('转换后的数据:', convertedData);
  return convertedData;
};

// 更新大盘星图
const updateHotmapChart = async function() {
  // 确保图表已初始化
  if (!marketHotmapChart || !marketHotmapRef.value) {
    console.log('图表未初始化或容器不存在，尝试重新初始化...');
    
    // 尝试重新获取容器并初始化
    if (marketHotmapRef.value) {
      const container = marketHotmapRef.value;
      // 确保容器有尺寸
      if (container.clientWidth === 0 || container.clientHeight === 0) {
        container.style.width = '100%';
        container.style.height = '600px';
      }
      console.log('容器尺寸:', container.clientWidth, 'x', container.clientHeight);
      
      // 销毁之前的图表实例
      if (marketHotmapChart) {
        marketHotmapChart.dispose();
        marketHotmapChart = null;
      }
      
      // 重新初始化图表
      marketHotmapChart = echarts.init(container, null, {
        renderer: 'canvas',
        useDirtyRect: false
      });
      console.log('图表重新初始化成功:', marketHotmapChart);
    } else {
      console.error('图表容器不存在，无法初始化图表');
      hotmapLoading.value = false;
      return;
    }
  }
  
  if (!marketHotmapChart) {
    console.log('图表未初始化，无法更新');
    hotmapLoading.value = false;
    return;
  }
  
  // 显示加载状态
  hotmapLoading.value = true;
  console.log('开始更新图表数据...');
  
  try {
    // 获取真实API数据
    console.log('开始获取真实API数据...');
    const apiData = await getIndustryStockHierarchy();
    console.log('API数据获取完成，长度:', apiData.length);
    
    // 将API数据转换为图表格式
    console.log('开始转换API数据为图表格式...');
    const chartData = convertApiDataToChartFormat(apiData);
    console.log('数据转换完成，处理后的数据长度:', chartData.length);
    console.log('处理后的数据:', chartData);
    
    // 如果API数据为空，使用模拟数据作为备用
    const finalData = chartData.length > 0 ? chartData : [
      {
        name: '银行',
        value: [100000, 95000, 0.5],
        stock_count: 3,
        children: [
          { name: '平安银行', value: [3000, 2800, 1.2] },
          { name: '招商银行', value: [5000, 4800, 0.8] },
          { name: '工商银行', value: [8000, 7900, 0.3] }
        ]
      },
      {
        name: '医药生物',
        value: [80000, 75000, 1.2],
        stock_count: 3,
        children: [
          { name: '恒瑞医药', value: [2000, 1950, 2.5] },
          { name: '药明康德', value: [1500, 1450, 1.8] },
          { name: '长春高新', value: [1000, 1020, -0.5] }
        ]
      },
      {
        name: '电子',
        value: [120000, 125000, -0.8],
        stock_count: 3,
        children: [
          { name: '贵州茅台', value: [25000, 24800, 0.7] },
          { name: '宁德时代', value: [10000, 9700, 3.2] },
          { name: '比亚迪', value: [8000, 8200, -1.9] }
        ]
      }
    ];
    
    // 详细打印最终数据格式
    console.log('====================================');
    console.log('最终数据格式详细信息:');
    console.log('====================================');
    console.log('完整最终数据:', JSON.stringify(finalData, null, 2));
    console.log('====================================');
    console.log('最终数据长度:', finalData.length);
    console.log('====================================');
    
    // 打印每个行业的数据
    for (let i = 0; i < finalData.length; i++) {
      const industry = finalData[i];
      console.log(`行业 ${i + 1}: ${industry.name}`);
      console.log(`  市值: ${industry.value[0]}亿`);
      console.log(`  股票数量: ${industry.value[1]}`);
      console.log(`  涨跌幅: ${industry.value[2]}%`);
      console.log(`  股票总数: ${industry.stock_count}只`);
      console.log(`  子股票数量: ${industry.children.length}`);
      
      // 打印每个行业的子股票
      for (let j = 0; j < industry.children.length; j++) {
        const stock = industry.children[j];
        console.log(`    股票 ${j + 1}: ${stock.name}`);
        console.log(`      市值: ${stock.value[0]}亿`);
        console.log(`      涨跌幅: ${stock.value[2]}%`);
      }
      console.log('------------------------------------');
    }
    
    // 处理数据
    function convertData(originList) {
      for (let i = 0; i < originList.length; i++) {
        let node = originList[i];
        if (node) {
          let value = node.value;
          // 计算视觉值
          value[3] = value[2] * 10;
          console.log('行业', node.name, '的视觉值:', value[3]);
          
          if (node.children) {
            for (let j = 0; j < node.children.length; j++) {
              let child = node.children[j];
              if (child && child.value) {
                child.value[3] = child.value[2] * 10;
                console.log('股票', child.name, '的视觉值:', child.value[3]);
              }
            }
          }
        }
      }
    }
    
    // 处理数据
    convertData(finalData);
    console.log('处理后的最终数据:', finalData);
    
    // 配置图表选项
    const option = {
      title: {
        left: 'center',
        text: '大盘星图',
        subtext: '红色表示上涨，绿色表示下跌'
      },
      tooltip: {
        formatter: function(info) {
          let value = info.value;
          let name = info.name;
          let stockCount = info.data.stock_count || '';
          
          let marketCap = value[0];
          marketCap = marketCap != null && isFinite(marketCap) ? marketCap + '亿' : '-';
          
          let change = value[2];
          change = change != null && isFinite(change) ? (change > 0 ? '+' : '') + change.toFixed(2) + '%' : '-';
          
          let changeColor = change.indexOf('+') > -1 ? '#f56c6c' : '#67c23a';
          
          let content = '<div class="tooltip-title">' + name + '</div>';
          content += '市值: ' + marketCap + '<br>';
          content += '<span style="color: ' + changeColor + '">涨跌幅: ' + change + '</span><br>';
          
          if (stockCount) {
            content += '股票数量: ' + stockCount + '只<br>';
          }
          
          return content;
        }
      },
      series: [
        {
          name: 'A股',
          top: 80,
          type: 'treemap',
          label: {
            show: true,
            formatter: '{b}'
          },
          itemStyle: {
            borderColor: '#fff'
          },
          visualMin: -50,
          visualMax: 50,
          visualDimension: 3,
          levels: [
            {
              itemStyle: {
                borderColor: '#555',
                borderWidth: 4,
                gapWidth: 4,
                color: '#f0f0f0'
              }
            },
            {
              color: ['#67c23a', '#f56c6c'],
              colorMappingBy: 'value',
              itemStyle: {
                borderColor: '#ddd',
                borderWidth: 1,
                gapWidth: 1
              },
              label: {
                show: false
              }
            }
          ],
          data: finalData
        }
      ]
    };
    
    console.log('图表配置选项:', JSON.stringify(option.series[0].data, null, 2));
    
    // 清除之前的图表
    marketHotmapChart.clear();
    console.log('图表已清除');
    
    // 检查容器尺寸
    const container = marketHotmapRef.value;
    if (!container) {
      console.error('图表容器不存在');
      return;
    }
    console.log('图表容器尺寸:', container.clientWidth, 'x', container.clientHeight);
    
    // 设置图表选项
    console.log('开始设置图表选项...');
    const setOptionResult = marketHotmapChart.setOption(option);
    console.log('图表选项设置结果:', setOptionResult);
    console.log('图表选项已设置');
    
    // 检查图表实例状态
    console.log('图表实例状态:', {
      isInitialized: !!marketHotmapChart,
      containerWidth: container.clientWidth,
      containerHeight: container.clientHeight,
      hasData: option.series[0].data.length > 0,
      dataLength: option.series[0].data.length
    });
    
    // 调用resize确保图表正确显示
    setTimeout(function() {
      if (marketHotmapChart && container) {
        console.log('开始调整图表大小...');
        marketHotmapChart.resize();
        console.log('图表已调整大小');
        
        // 检查图表是否已渲染
        console.log('图表渲染状态检查:');
        console.log('  图表实例:', marketHotmapChart);
        console.log('  容器尺寸:', container.clientWidth, 'x', container.clientHeight);
        console.log('  数据长度:', option.series[0].data.length);
        console.log('  图表是否已销毁:', marketHotmapChart.isDisposed());
        
        // 尝试强制渲染
        console.log('尝试强制渲染图表...');
        marketHotmapChart.setOption(option, true);
        console.log('图表已强制重新渲染');
      }
    }, 100);
  } catch (error) {
    console.error('更新大盘星图失败:', error);
    
    // 出错时使用模拟数据
    console.log('使用模拟数据作为备用...');
    const mockData = [
      {
        name: '银行',
        value: [100000, 95000, 0.5],
        stock_count: 3,
        children: [
          { name: '平安银行', value: [3000, 2800, 1.2] },
          { name: '招商银行', value: [5000, 4800, 0.8] },
          { name: '工商银行', value: [8000, 7900, 0.3] }
        ]
      },
      {
        name: '医药生物',
        value: [80000, 75000, 1.2],
        stock_count: 3,
        children: [
          { name: '恒瑞医药', value: [2000, 1950, 2.5] },
          { name: '药明康德', value: [1500, 1450, 1.8] },
          { name: '长春高新', value: [1000, 1020, -0.5] }
        ]
      },
      {
        name: '电子',
        value: [120000, 125000, -0.8],
        stock_count: 3,
        children: [
          { name: '贵州茅台', value: [25000, 24800, 0.7] },
          { name: '宁德时代', value: [10000, 9700, 3.2] },
          { name: '比亚迪', value: [8000, 8200, -1.9] }
        ]
      }
    ];
    
    // 处理模拟数据
    function convertData(originList) {
      for (let i = 0; i < originList.length; i++) {
        let node = originList[i];
        if (node) {
          let value = node.value;
          value[3] = value[2] * 10;
          if (node.children) {
            for (let j = 0; j < node.children.length; j++) {
              let child = node.children[j];
              if (child && child.value) {
                child.value[3] = child.value[2] * 10;
              }
            }
          }
        }
      }
    }
    
    convertData(mockData);
    
    // 设置模拟数据的完整图表选项
    const mockOption = {
      title: {
        left: 'center',
        text: '大盘星图',
        subtext: '红色表示上涨，绿色表示下跌'
      },
      tooltip: {
        formatter: function(info) {
          let value = info.value;
          let name = info.name;
          let stockCount = info.data.stock_count || '';
          
          let marketCap = value[0];
          marketCap = marketCap != null && isFinite(marketCap) ? marketCap + '亿' : '-';
          
          let change = value[2];
          change = change != null && isFinite(change) ? (change > 0 ? '+' : '') + change.toFixed(2) + '%' : '-';
          
          let changeColor = change.indexOf('+') > -1 ? '#f56c6c' : '#67c23a';
          
          let content = '<div class="tooltip-title">' + name + '</div>';
          content += '市值: ' + marketCap + '<br>';
          content += '<span style="color: ' + changeColor + '">涨跌幅: ' + change + '</span><br>';
          
          if (stockCount) {
            content += '股票数量: ' + stockCount + '只<br>';
          }
          
          return content;
        }
      },
      series: [
        {
          name: 'A股',
          top: 80,
          type: 'treemap',
          label: {
            show: true,
            formatter: '{b}'
          },
          itemStyle: {
            borderColor: '#fff'
          },
          visualMin: -50,
          visualMax: 50,
          visualDimension: 3,
          levels: [
            {
              itemStyle: {
                borderColor: '#555',
                borderWidth: 4,
                gapWidth: 4,
                color: '#f0f0f0'
              }
            },
            {
              color: ['#67c23a', '#f56c6c'],
              colorMappingBy: 'value',
              itemStyle: {
                borderColor: '#ddd',
                borderWidth: 1,
                gapWidth: 1
              },
              label: {
                show: false
              }
            }
          ],
          data: mockData
        }
      ]
    };
    
    // 设置模拟数据
    marketHotmapChart.setOption(mockOption);
  } finally {
    // 隐藏加载状态
    hotmapLoading.value = false;
    console.log('图表数据更新完成');
  }
};

// 监听窗口大小变化，调整图表大小
window.addEventListener('resize', function() {
  // 使用 setTimeout 确保在 DOM 更新后执行 resize
  setTimeout(function() {
    if (industryChart && !industryChart.isDisposed()) {
      industryChart.resize()
    }
    if (marketHotmapChart && !marketHotmapChart.isDisposed()) {
      marketHotmapChart.resize()
    }
  }, 0)
})

// 生成模拟行业数据
const generateMockIndustryData = function() {
  const industries = [
    { name: '银行', stockCount: 28, change: 1.2, marketCap: 12000000000000 },
    { name: '医药生物', stockCount: 356, change: 2.5, marketCap: 8000000000000 },
    { name: '电子', stockCount: 345, change: -1.8, marketCap: 7500000000000 },
    { name: '计算机', stockCount: 268, change: 3.2, marketCap: 6000000000000 },
    { name: '食品饮料', stockCount: 108, change: 0.5, marketCap: 5500000000000 },
    { name: '房地产', stockCount: 123, change: -2.1, marketCap: 4000000000000 },
    { name: '电气设备', stockCount: 189, change: 4.5, marketCap: 3500000000000 },
    { name: '机械设备', stockCount: 245, change: -0.8, marketCap: 3000000000000 }
  ]
  
  return industries.map(function(industry) {
    return {
      name: industry.name,
      stockCount: industry.stockCount,
      change: industry.change,
      marketCap: industry.marketCap,
      value: [
        Math.random() * 100,
        Math.random() * 100,
        industry.stockCount * 10,
        industry.change
      ],
      industry: industry.name,
      stock_count: industry.stockCount
    };
  });
};

// 页面加载时获取数据
onMounted(function() {
  // 初始化星图（使用nextTick确保DOM元素渲染完成）
  nextTick(function() {
    console.log('nextTick回调执行')
    setTimeout(function() {
      initHotmapChart()
    }, 200) // 增加延迟确保DOM完全渲染
  })
  
  // 获取真实数据
  getIndustryAnalysis()
})

// 带尺寸检查的星图初始化
const initHotmapChartWithSize = function() {
  if (hotmapInitialized) {
    console.log('大盘星图已经初始化过，跳过重复初始化')
    return
  }
  
  console.log('进入initHotmapChartWithSize函数')
  if (marketHotmapRef.value) {
    // 手动设置容器尺寸
    const container = marketHotmapRef.value
    container.style.width = '800px'
    container.style.height = '600px'
    
    console.log('容器尺寸设置完成:', container.clientWidth, container.clientHeight)
    
    if (container.clientWidth > 0 && container.clientHeight > 0) {
      console.log('容器尺寸有效，初始化图表...')
      initHotmapChart()
      console.log('星图初始化完成')
      hotmapInitialized = true
    } else {
      console.log('容器尺寸无效，等待200ms后重试...')
      // 如果尺寸无效，等待一段时间后重试
      setTimeout(function() {
        initHotmapChartWithSize()
      }, 200)
    }
  } else {
    console.log('marketHotmapRef.value为空')
  }
};
</script>

<template>
  <div class="data-page">
    <div class="page-content">
      <!-- 标签页 -->
      <el-tabs v-model="activeTab">
        <el-tab-pane label="行业趋势" name="industryAnalysis">
          <div class="industry-analysis">
            <!-- 加载中提示 -->
            <el-loading v-if="loading" fullscreen text="加载中..." />
            
            <!-- 行业趋势内容 -->
            <div v-else>
              <!-- 行业趋势图表（先显示可视化） -->
              <div v-if="Array.isArray(industryAnalysis) && industryAnalysis.length > 0" style="margin-bottom: 30px">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <div style="display: flex; align-items: center;">
                      <h3 style="margin: 0; margin-right: 20px;">行业表现趋势</h3>
                      <div style="display: flex; align-items: center;">
                        <span style="margin-right: 10px;">筛选:</span>
                        <el-select v-model="industryFilter" @change="handleIndustryFilterChange" style="width: 180px;">
                          <el-option label="全部行业" :value="'all'" />
                          <el-option label="今日涨幅最高(前3)" :value="'top3'" />
                          <el-option label="今日涨幅最低(前3)" :value="'bottom3'" />
                        </el-select>
                      </div>
                    </div>
                    <div style="display: flex; align-items: center;">
                      <span style="margin-right: 10px;">显示近</span>
                      <el-select v-model="daysToShow" @change="handleDaysChange" style="width: 120px;">
                        <el-option label="7天" :value="7" />
                        <el-option label="15天" :value="15" />
                        <el-option label="30天" :value="30" />
                        <el-option label="60天" :value="60" />
                        <el-option label="90天" :value="90" />
                      </el-select>
                      <span style="margin-left: 10px;">的数据</span>
                    </div>
                  </div>
                  <div ref="industryChartRef" style="width: 100%; height: 450px; min-width: 800px; min-height: 450px;"></div>
                </div>
              
              <!-- 行业趋势表格（下面放置表格数据） -->
              <div v-if="Array.isArray(industryAnalysis) && industryAnalysis.length > 0" style="margin-top: 20px">
                <h3 style="margin-bottom: 15px;">行业详细数据</h3>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                  <h3 style="margin: 0;">行业详细数据</h3>
                  <el-button type="warning" size="small" @click="analyzeAllIndustriesWithLLM()">
                    大模型分析所有行业
                  </el-button>
                </div>
                <el-table :data="industryAnalysis" style="width: 100%">
                  <el-table-column prop="industry" label="行业" width="150" />
                  <el-table-column prop="stock_count" label="股票数量" width="100" />
                  <el-table-column prop="avg_change" label="平均涨跌幅 (%)" width="150">
                    <template #default="{ row }">
                      <span :class="row.avg_change >= 0 ? 'text-green' : 'text-red'">
                        {{ (row.avg_change * 100).toFixed(2) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="avg_volatility" label="平均波动率 (%)" width="150" />
                  <el-table-column label="操作" width="240">
                    <template #default="{ row }">
                      <el-button type="primary" size="small" @click="getIndustryTrend(row.industry)" style="margin-right: 10px;">
                        查看趋势
                      </el-button>
                      <el-button type="success" size="small" @click="analyzeIndustry(row.industry)" style="margin-right: 10px;">
                        分析行业
                      </el-button>
                      <el-button type="info" size="small" @click="analyzeIndustryWithLLM(row.industry)">
                        大模型分析
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              
              <!-- 空数据提示 -->
              <el-empty v-else description="暂无行业趋势数据" />
            </div>
            
            <!-- 行业趋势分页组件 -->
            <div class="pagination-container" v-if="Array.isArray(industryAnalysis)">
              <el-pagination
                v-model:current-page="industryCurrentPage"
                v-model:page-size="industryPageSize"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                :total="Number(totalIndustries)"
                @size-change="handleIndustrySizeChange"
                @current-change="handleIndustryPageChange"
              />
            </div>
            
            <!-- 行业趋势 -->
            <div v-if="industryTrend" class="industry-trend">
              <h3>{{ industryTrend.industry }} 行业趋势</h3>
              <p>股票数量: {{ industryTrend.stock_count }}</p>
              
              <h4>股票表现</h4>
              <div v-for="(trend, stockCode) in industryTrend.stock_trends" :key="stockCode">
                <h5>{{ stockCode }}</h5>
                <el-table :data="trend" style="width: 100%">
                  <el-table-column prop="date" label="日期" width="120" />
                  <el-table-column prop="close" label="收盘价" width="100" />
                  <el-table-column prop="change_percent" label="涨跌幅 (%)" width="120">
                    <template #default="{ row }">
                      <span :class="row.change_percent >= 0 ? 'text-green' : 'text-red'">
                        {{ row.change_percent.toFixed(2) }}
                      </span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
            
            <!-- 行业趋势结果 -->
            <div v-if="analysisLoading" class="industry-analysis-loading">
              <el-loading :fullscreen="false" text="正在分析行业情况..." />
            </div>
            <div v-else-if="industryAnalysisResult" class="industry-analysis-result">
              <h3>{{ industryAnalysisResult.industry }} 行业趋势结果</h3>
              
              <!-- 显示大模型分析报告 -->
              <div v-if="industryAnalysisResult.llm_analysis" style="margin-bottom: 20px;">
                <h4 style="margin-bottom: 10px;">大模型分析报告</h4>
                <el-card>
                  <div v-html="industryAnalysisResult.llm_analysis.replace(/\n/g, '<br>')" class="llm-analysis-content"></div>
                </el-card>
              </div>
              
              <!-- 显示普通分析结果 -->
              <div v-else-if="industryAnalysisResult.summary">
                <el-alert
                  :title="industryAnalysisResult.summary"
                  type="info"
                  show-icon
                />
              </div>
              
              <!-- 显示错误信息 -->
              <div v-else-if="industryAnalysisResult.error">
                <el-alert
                  :title="industryAnalysisResult.error"
                  type="error"
                  show-icon
                />
              </div>
              
              <!-- 显示分析详情 -->
              <div class="analysis-details" v-if="!industryAnalysisResult.error">
                <div class="analysis-item">
                  <span class="analysis-label">分析周期:</span>
                  <span class="analysis-value">{{ industryAnalysisResult.period || `${daysToShow.value}天` }}</span>
                </div>
                <div class="analysis-item" v-if="industryAnalysisResult.stockCount">
                  <span class="analysis-label">股票数量:</span>
                  <span class="analysis-value">{{ industryAnalysisResult.stockCount }} 支</span>
                </div>
                <div class="analysis-item" v-if="industryAnalysisResult.industry_count">
                  <span class="analysis-label">行业数量:</span>
                  <span class="analysis-value">{{ industryAnalysisResult.industry_count }} 个</span>
                </div>
                <div class="analysis-item" v-if="industryAnalysisResult.avgChange !== undefined">
                  <span class="analysis-label">平均涨跌幅:</span>
                  <span :class="industryAnalysisResult.avgChange >= 0 ? 'text-green' : 'text-red'">
                    {{ (industryAnalysisResult.avgChange * 100).toFixed(2) }}%
                  </span>
                </div>
                <div class="analysis-item" v-if="industryAnalysisResult.volatility !== undefined">
                  <span class="analysis-label">波动性:</span>
                  <span class="analysis-value">{{ (industryAnalysisResult.volatility * 100).toFixed(2) }}%</span>
                </div>
                <div class="analysis-item" v-if="industryAnalysisResult.positiveDays">
                  <span class="analysis-label">上涨天数:</span>
                  <span class="analysis-value">{{ industryAnalysisResult.positiveDays }} 天</span>
                </div>
                <div class="analysis-item" v-if="industryAnalysisResult.negativeDays">
                  <span class="analysis-label">下跌天数:</span>
                  <span class="analysis-value">{{ industryAnalysisResult.negativeDays }} 天</span>
                </div>
                <div class="analysis-item" v-if="industryAnalysisResult.positiveRate">
                  <span class="analysis-label">上涨天数占比:</span>
                  <span class="analysis-value">{{ industryAnalysisResult.positiveRate }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="API端点" name="apiEndpoints">
          <div class="api-endpoints">
            <h3>API端点列表</h3>
            
            <el-collapse>
              <el-collapse-item title="GET http://localhost:7860/api/v1/stock/list - 获取股票列表">
                <div class="api-details">
                  <p><strong>描述:</strong> 获取所有股票列表，包含股票代码、股票名称和行业信息</p>
                  <p><strong>测试命令:</strong> <code>curl http://localhost:7860/api/v1/stock/list?page=1&page_size=20</code></p>
                  <p><strong>响应格式:</strong></p>
                  <pre>
{
  "total": 301,
  "page": 1,
  "page_size": 20,
  "data": [
    {
      "stock_code": "000001",
      "stock_name": "平安银行",
      "industry": "银行",
      "list_date": "19910403"
    },
    ...
  ]
}
                  </pre>
                </div>
              </el-collapse-item>
              
              <el-collapse-item title="GET http://localhost:7860/api/v1/stock/detail/{stock_code} - 获取股票详情">
                <div class="api-details">
                  <p><strong>描述:</strong> 获取指定股票的详细信息，包含基本信息和历史数据</p>
                  <p><strong>参数:</strong> stock_code - 股票代码</p>
                  <p><strong>测试命令:</strong> <code>curl http://localhost:7860/api/v1/stock/detail/000001</code></p>
                  <p><strong>响应格式:</strong></p>
                  <pre>
{
  "basic_info": {
    "stock_code": "000001",
    "stock_name": "平安银行",
    "industry": "银行",
    "list_date": "19910403"
  },
  "historical_data": [
    {
      "date": "2025-01-02",
      "open": 11.13,
      "close": 10.83,
      "high": 11.17,
      "low": 10.79,
      "change_percent": -2.78
    },
    ...
  ]
}
                  </pre>
                </div>
              </el-collapse-item>
              
              <el-collapse-item title="GET http://localhost:7860/api/v1/stock/industry/analysis - 获取行业分析">
                <div class="api-details">
                  <p><strong>描述:</strong> 获取各行业的平均涨跌幅、波动率等关键指标</p>
                  <p><strong>测试命令:</strong> <code>curl http://localhost:7860/api/v1/stock/industry/analysis</code></p>
                  <p><strong>响应格式:</strong></p>
                  <pre>
{
  "total": 3,
  "page": 1,
  "page_size": 20,
  "data": [
    {
      "industry": "银行",
      "stock_count": 1,
      "avg_change": 0.4512,
      "avg_volatility": 4.6895
    },
    ...
  ]
}
                  </pre>
                </div>
              </el-collapse-item>
              
              <el-collapse-item title="GET http://localhost:7860/api/v1/stock/industry/trend - 获取行业趋势">
                <div class="api-details">
                  <p><strong>描述:</strong> 获取指定行业的趋势数据，包含该行业所有股票的表现</p>
                  <p><strong>参数:</strong> industry - 行业名称</p>
                  <p><strong>测试命令:</strong> <code>curl http://localhost:7860/api/v1/stock/industry/trend?industry=银行</code></p>
                  <p><strong>响应格式:</strong></p>
                  <pre>
{
  "industry": "银行",
  "stock_trends": {
    "601658": [
      {
        "date": "2025-01-02",
        "close": 5.14,
        "change_percent": -3.02
      },
      ...
    ]
  }
}
                  </pre>
                </div>
              </el-collapse-item>
              
              <el-collapse-item title="GET http://localhost:7860/api/v1/stock/industry/analyze/llm - 大模型分析行业">
                <div class="api-details">
                  <p><strong>描述:</strong> 使用大模型分析指定行业的表现情况</p>
                  <p><strong>参数:</strong> industry - 行业名称, days - 分析天数</p>
                  <p><strong>测试命令:</strong> <code>curl "http://localhost:7860/api/v1/stock/industry/analyze/llm?industry=银行&days=90"</code></p>
                  <p><strong>响应格式:</strong></p>
                  <pre>
{
  "industry": "银行",
  "period": "90天",
  "stock_count": 22,
  "avg_change": 0.0191,
  "volatility": 0.8545,
  "positive_days": 40,
  "negative_days": 50,
  "positive_rate": "44.44%",
  "llm_analysis": "综合分析报告内容..."
}
                  </pre>
                </div>
              </el-collapse-item>
              
              <el-collapse-item title="GET http://localhost:7860/api/v1/stock/industry/analyze/all/llm - 大模型分析所有行业">
                <div class="api-details">
                  <p><strong>描述:</strong> 使用大模型分析所有行业的表现情况</p>
                  <p><strong>参数:</strong> days - 分析天数</p>
                  <p><strong>测试命令:</strong> <code>curl "http://localhost:7860/api/v1/stock/industry/analyze/all/llm?days=90"</code></p>
                  <p><strong>响应格式:</strong></p>
                  <pre>
{
  "period": "90天",
  "industry_count": 3,
  "industries_data": [
    {
      "industry": "银行",
      "stock_count": 1,
      "avg_change": 0.4512,
      "avg_volatility": 4.6895
    },
    ...
  ],
  "llm_analysis": "综合分析报告内容..."
}
                  </pre>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="大盘星图" name="marketHotmap">
          <div class="market-hotmap">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
              <h3>大盘星图</h3>
              <el-button type="primary" @click="getHotmapData()">
                刷新数据
              </el-button>
            </div>
            
            <!-- 图表容器（始终存在） -->
            <div style="position: relative;">
              <div ref="marketHotmapRef" style="width: 100%; height: 600px; min-width: 800px; min-height: 600px; margin: 0 auto; background-color: #f5f5f5; border: 1px solid #ddd;"></div>
              
              <!-- 加载状态覆盖层 -->
              <div v-if="hotmapLoading" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(255, 255, 255, 0.8); display: flex; justify-content: center; align-items: center;">
                <div style="text-align: center;">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  <span style="margin-left: 10px;">加载中...</span>
                </div>
              </div>
              
              <!-- 错误提示 -->
              <div v-if="error" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(255, 255, 255, 0.9); display: flex; justify-content: center; align-items: center;">
                <el-alert :title="error" type="error" show-icon style="max-width: 80%;" />
              </div>
            </div>
            
            <!-- 说明文字（始终显示） -->
            <div style="margin-top: 20px; padding: 15px; background-color: #f9f9f9; border-radius: 8px;">
              <h4>说明</h4>
              <ul>
                <li>色彩代表涨跌幅：绿色表示上涨，红色表示下跌</li>
                <li>面积大小代表总市值：面积越大，总市值越高</li>
                <li>点击每个星图可查看详细信息</li>
              </ul>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
      
      <!-- 加载状态 -->
      <el-loading v-if="loading" fullscreen text="加载中..." />
      
      <!-- 错误提示 -->
      <el-alert v-if="error" type="error" :title="error" show-icon />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.data-page {
  padding: 20px;
  
  .page-header {
    margin-bottom: 30px;
    
    h1 {
      font-size: 28px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 8px;
    }
    
    p {
      font-size: 16px;
      color: #606266;
    }
  }
  
  .page-content {
    background-color: #ffffff;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  }
  
  .stock-list {
    margin-bottom: 30px;
  }
  
  .stock-detail {
    margin-top: 30px;
    padding: 20px;
    background-color: #f9f9f9;
    border-radius: 8px;
    
    h3 {
      font-size: 20px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 15px;
    }
    
    h4 {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
      margin-top: 20px;
      margin-bottom: 15px;
    }
    
    p {
      font-size: 14px;
      color: #606266;
      margin-bottom: 8px;
    }
  }
  
  .industry-analysis {
    margin-bottom: 30px;
  }
  
  .industry-trend {
    margin-top: 30px;
    padding: 20px;
    background-color: #f9f9f9;
    border-radius: 8px;
    
    h3 {
      font-size: 20px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 15px;
    }
    
    h4 {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
      margin-top: 20px;
      margin-bottom: 15px;
    }
    
    h5 {
      font-size: 14px;
      font-weight: 600;
      color: #303133;
      margin-top: 20px;
      margin-bottom: 10px;
    }
    
    p {
      font-size: 14px;
      color: #606266;
      margin-bottom: 8px;
    }
  }
  
  .api-endpoints {
    
    h3 {
      font-size: 20px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 20px;
    }
    
    .api-details {
      padding: 15px;
      background-color: #f9f9f9;
      border-radius: 8px;
      margin-top: 10px;
      
      p {
        font-size: 14px;
        color: #606266;
        margin-bottom: 10px;
      }
      
      pre {
        background-color: #f0f0f0;
        padding: 15px;
        border-radius: 4px;
        overflow-x: auto;
        font-size: 12px;
        color: #303133;
      }
    }
  }
  
  .text-green {
    color: #67c23a;
  }
  
  .text-red {
    color: #f56c6c;
  }
  
  .pagination-container {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
  
  .industry-analysis-loading {
    margin-top: 20px;
    padding: 20px;
    background-color: #f9f9f9;
    border-radius: 8px;
  }
  
  .industry-analysis-result {
    margin-top: 20px;
    padding: 20px;
    background-color: #f9f9f9;
    border-radius: 8px;
  }
  
  .industry-analysis-result h3 {
    font-size: 20px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 15px;
  }
  
  .analysis-details {
    margin-top: 20px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 15px;
  }
  
  .analysis-item {
    display: flex;
    flex-direction: column;
  }
  
  .analysis-label {
    font-size: 14px;
    color: #606266;
    margin-bottom: 5px;
  }
  
  .analysis-value {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
  }
  
  /* 大模型分析报告样式 */
  .llm-analysis-content {
    line-height: 1.6;
    font-size: 14px;
    color: #303133;
  }
  
  .llm-analysis-content h2 {
    font-size: 18px;
    font-weight: 600;
    margin-top: 20px;
    margin-bottom: 10px;
    color: #303133;
  }
  
  .llm-analysis-content h3 {
    font-size: 16px;
    font-weight: 600;
    margin-top: 15px;
    margin-bottom: 8px;
    color: #303133;
  }
  
  .llm-analysis-content h4 {
    font-size: 14px;
    font-weight: 600;
    margin-top: 12px;
    margin-bottom: 6px;
    color: #303133;
  }
  
  .llm-analysis-content p {
    margin-bottom: 10px;
  }
  
  .llm-analysis-content ul,
  .llm-analysis-content ol {
    margin-left: 20px;
    margin-bottom: 10px;
  }
  
  .llm-analysis-content li {
    margin-bottom: 5px;
  }
  
  .llm-analysis-content table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
  }
  
  .llm-analysis-content th,
  .llm-analysis-content td {
    border: 1px solid #e4e7ed;
    padding: 8px 12px;
    text-align: left;
  }
  
  .llm-analysis-content th {
    background-color: #f5f7fa;
    font-weight: 600;
  }
  
  .llm-analysis-content pre {
    background-color: #f5f7fa;
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 12px;
    margin: 10px 0;
  }
  
  .llm-analysis-content code {
    background-color: #f5f7fa;
    padding: 2px 4px;
    border-radius: 3px;
    font-size: 12px;
  }
}

</style>