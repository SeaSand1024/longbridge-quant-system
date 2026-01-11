// 股票K线图增强功能

// K线图实例映射
const stockKlineCharts = {};

// 加载并显示股票K线图
async function loadStockKline(symbol, period, chartId) {
    period = period || '1d';
    chartId = chartId || 'stockKlineChart';
    
    try {
        const response = await fetch(API_BASE + '/api/stock/history/' + symbol + '?period=' + period + '&count=200', { credentials: 'include' });
        const result = await response.json();

        if (result.code === 0 && result.data.length > 0) {
            renderStockKline(result.data, symbol, chartId);
        }
    } catch (error) {
        console.error('加载K线数据失败:', error);
    }
}

// 渲染K线图
function renderStockKline(data, symbol, chartId) {
    const chartDom = document.getElementById(chartId);
    if (!chartDom) {
        console.warn('找不到图表容器: ' + chartId);
        return;
    }

    // 如果已存在图表实例，先销毁
    if (stockKlineCharts[chartId]) {
        stockKlineCharts[chartId].dispose();
    }

    stockKlineCharts[chartId] = echarts.init(chartDom);

    // 转换数据格式为 [时间, 开盘, 收盘, 最低, 最高]
    const chartData = [];
    for (let i = 0; i < data.length; i++) {
        const item = data[i];
        const date = new Date(item.timestamp);
        chartData.push([
            date.getTime(),
            parseFloat(item.open),
            parseFloat(item.close),
            parseFloat(item.low),
            parseFloat(item.high)
        ]);
    }

    const volumes = [];
    for (let i = 0; i < data.length; i++) {
        const item = data[i];
        const date = new Date(item.timestamp);
        const closePrice = parseFloat(item.close);
        const openPrice = parseFloat(item.open);
        volumes.push([
            date.getTime(),
            parseFloat(item.volume),
            closePrice >= openPrice ? 1 : -1
        ]);
    }

    // 计算MA均线
    const ma5 = calculateMA(5, chartData);
    const ma10 = calculateMA(10, chartData);
    const ma20 = calculateMA(20, chartData);

    const option = {
        backgroundColor: '#111827',
        title: {
            text: symbol + ' - K线走势图',
            textStyle: { color: '#fff', fontSize: 16 },
            left: 'center',
            top: 10
        },
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(17, 24, 39, 0.9)',
            borderColor: '#374151',
            textStyle: { color: '#fff', fontSize: 12 },
            axisPointer: {
                type: 'cross'
            },
            formatter: function(params) {
                let result = '';
                const date = new Date(params[0].axisValue);
                result += '<div style="padding: 8px;">';
                result += '<div style="margin-bottom: 8px; color: #9ca3af;">' + date.toLocaleDateString('zh-CN') + ' ' + date.toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'}) + '</div>';

                for (let i = 0; i < params.length; i++) {
                    const param = params[i];
                    if (param.seriesName === 'K线') {
                        const data = param.data;
                        result += '<div style="margin-bottom: 4px;">';
                        result += '<span style="color: #9ca3af;">开盘:</span> $' + (data && data[1] ? data[1].toFixed(2) : '--') + ' ';
                        result += '<span style="margin-left: 10px; color: #9ca3af;">收盘:</span> $' + (data && data[2] ? data[2].toFixed(2) : '--') + '</div>';
                        result += '<div style="margin-bottom: 4px;">';
                        result += '<span style="color: #9ca3af;">最低:</span> $' + (data && data[3] ? data[3].toFixed(2) : '--') + ' ';
                        result += '<span style="margin-left: 10px; color: #9ca3af;">最高:</span> $' + (data && data[4] ? data[4].toFixed(2) : '--') + '</div>';
                    } else if (param.seriesName.indexOf('MA') >= 0 && param.data !== '-') {
                        result += '<div style="margin-bottom: 4px;">';
                        result += '<span style="color: #9ca3af;">' + param.seriesName + ':</span> $' + (param.data ? parseFloat(param.data).toFixed(2) : '--') + '</div>';
                    } else if (param.seriesName === '成交量') {
                        result += '<div style="margin-bottom: 4px;">';
                        result += '<span style="color: #9ca3af;">成交量:</span> ' + formatNumber(param.data[1]) + '</div>';
                    }
                }

                result += '</div>';
                return result;
            }
        },
        legend: {
            data: ['K线', 'MA5', 'MA10', 'MA20', '成交量'],
            textStyle: { color: '#9ca3af', fontSize: 12 },
            top: 45
        },
        grid: [
            {
                left: '8%',
                right: '8%',
                height: '45%'
            },
            {
                left: '8%',
                right: '8%',
                top: '58%',
                height: '15%'
            }
        ],
        xAxis: [
            {
                type: 'time',
                scale: true,
                boundaryGap: false,
                axisLine: { lineStyle: { color: '#374151' } },
                splitLine: { show: false },
                axisLabel: { color: '#9ca3af', fontSize: 10 },
                min: 'dataMin',
                max: 'dataMax'
            },
            {
                type: 'time',
                gridIndex: 1,
                scale: true,
                boundaryGap: false,
                axisLine: { lineStyle: { color: '#374151' } },
                splitLine: { show: false },
                axisLabel: { show: false },
                min: 'dataMin',
                max: 'dataMax'
            }
        ],
        yAxis: [
            {
                scale: true,
                splitLine: { lineStyle: { color: '#1f2937' } },
                axisLabel: { color: '#9ca3af', fontSize: 10 },
                splitArea: { show: true, areaStyle: { color: ['rgba(239, 241, 245, 0.02)', 'rgba(255, 255, 255, 0.02)'] } }
            },
            {
                scale: true,
                gridIndex: 1,
                splitNumber: 2,
                axisLabel: { show: false },
                axisLine: { show: false },
                axisTick: { show: false },
                splitLine: { show: false }
            }
        ],
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: [0, 1],
                start: 50,
                end: 100
            },
            {
                show: true,
                xAxisIndex: [0, 1],
                type: 'slider',
                top: '78%',
                start: 50,
                end: 100,
                borderColor: '#374151',
                backgroundColor: '#1f2937',
                fillerColor: 'rgba(59, 130, 246, 0.2)',
                handleStyle: { color: '#3b82f6' }
            }
        ],
        series: [
            {
                name: 'K线',
                type: 'candlestick',
                data: chartData,
                itemStyle: {
                    color: '#ef4444',
                    color0: '#22c55e',
                    borderColor: '#ef4444',
                    borderColor0: '#22c55e'
                },
                z: 10
            },
            {
                name: 'MA5',
                type: 'line',
                data: ma5,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 2, color: '#f59e0b' },
                z: 11
            },
            {
                name: 'MA10',
                type: 'line',
                data: ma10,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 2, color: '#8b5cf6' },
                z: 11
            },
            {
                name: 'MA20',
                type: 'line',
                data: ma20,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 2, color: '#ec4899' },
                z: 11
            },
            {
                name: '成交量',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: volumes,
                itemStyle: {
                    color: function(params) {
                        return params.data[2] > 0 ? 'rgba(239, 68, 68, 0.6)' : 'rgba(34, 197, 94, 0.6)';
                    }
                },
                z: 5
            }
        ]
    };

    stockKlineCharts[chartId].setOption(option);

    // 响应式调整
    window.addEventListener('resize', function() {
        stockKlineCharts[chartId].resize();
    });
}

// 计算移动平均线
function calculateMA(dayCount, data) {
    const result = [];
    for (let i = 0, len = data.length; i < len; i++) {
        if (i < dayCount) {
            result.push('-');
            continue;
        }
        let sum = 0;
        for (let j = 0; j < dayCount; j++) {
            sum += data[i - j][2]; // 使用收盘价
        }
        result.push((sum / dayCount).toFixed(2));
    }
    return result;
}

// 增强股票详情页面，添加K线图
function enhanceStockDetailModal() {
    const modalContent = document.getElementById('detailModalContent');
    if (!modalContent) return;

    // 创建K线图容器
    const klineContainer = document.createElement('div');
    klineContainer.className = 'bg-gray-900 rounded-lg p-6';
    klineContainer.innerHTML = 
        '<div class="flex justify-between items-center mb-4">' +
            '<h3 class="text-lg font-bold flex items-center">' +
                '<i class="fas fa-chart-candlestick mr-2 text-blue-400"></i>K线走势图' +
            '</h3>' +
            '<div class="flex space-x-2" id="periodButtons">' +
                '<button class="stock-period-btn px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm font-medium active" data-period="1d">日K</button>' +
                '<button class="stock-period-btn px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm font-medium" data-period="1w">周K</button>' +
                '<button class="stock-period-btn px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm font-medium" data-period="1M">月K</button>' +
            '</div>' +
        '</div>' +
        '<div id="stockKlineChart" class="w-full h-96"></div>';

    // 插入到模态框内容中
    const contentDivs = modalContent.children;
    if (contentDivs.length > 2) {
        modalContent.insertBefore(klineContainer, contentDivs[2]);
    }

    // 获取股票代码
    const title = document.getElementById('detailModalTitle').textContent;
    const symbolMatch = title.match(/([A-Z]+)/);
    const symbol = symbolMatch ? symbolMatch[0] : '';
    
    if (symbol) {
        loadStockKline(symbol, '1d');

        // 绑定周期切换事件
        document.querySelectorAll('.stock-period-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                const period = this.getAttribute('data-period');

                // 更新按钮样式
                document.querySelectorAll('.stock-period-btn').forEach(function(b) {
                    b.classList.remove('bg-blue-600', 'active');
                    b.classList.add('bg-gray-700');
                });
                this.classList.remove('bg-gray-700');
                this.classList.add('bg-blue-600', 'active');

                // 加载新周期的K线数据
                loadStockKline(symbol, period);
            });
        });
    }
}

// 监听模态框打开事件
const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.target.id === 'detailModal' && !mutation.target.classList.contains('hidden')) {
            // 延迟执行，等待内容加载完成
            setTimeout(function() {
                enhanceStockDetailModal();
            }, 300);
        }
    });
});

// 开始观察
const detailModal = document.getElementById('detailModal');
if (detailModal) {
    observer.observe(detailModal, { attributes: true, attributeFilter: ['class'] });
}
