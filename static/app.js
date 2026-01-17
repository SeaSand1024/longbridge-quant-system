// API基础URL
const API_BASE = '';

// 全局状态
let isMonitoring = false;
let accelerationChart = null;
let isMobile = window.innerWidth <= 640;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initEventListeners();
    loadInitialData();
    initAccelerationChart();
    initSSE();  // 初始化SSE连接

    // 监听窗口大小变化
    window.addEventListener('resize', () => {
        isMobile = window.innerWidth <= 640;
    });

    // 定时刷新
    setInterval(() => {
        if (document.getElementById('marketTab').classList.contains('hidden') === false) {
            loadMarketData();
        }
        if (document.getElementById('portfolioTab').classList.contains('hidden') === false) {
            loadPortfolio();
        }
        // 无论哪个tab，都更新总资产等关键数据
        loadStatistics();
        updateMonitoringStatus();
    }, 5000);
});

// SSE 连接管理
function initSSE() {
    // 获取Cookie中的token
    const getCookie = (name) => {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    };

    const token = getCookie('access_token');
    const eventSource = new EventSource(`${API_BASE}/api/events${token ? '?token=' + encodeURIComponent(token) : ''}`);

    eventSource.addEventListener('connected', (event) => {
        console.log('SSE 已连接');
    });

    eventSource.addEventListener('trade', (event) => {
        const data = JSON.parse(event.data);
        console.log('收到交易事件:', data);

        // 立即刷新账户总览和相关数据
        loadPortfolio();
        loadStatistics();
        loadTrades();  // 刷新交易记录

        // 显示通知
        const actionText = data.type === 'BUY' ? '买入' : '卖出';
        showNotification(`${actionText} ${data.symbol} ${data.quantity}股 @ $${data && data.price ? data.price.toFixed(2) : '--'}`, 'success');
    });

    eventSource.addEventListener('error', (error) => {
        console.error('SSE 错误:', error);
        // 3秒后尝试重连
        setTimeout(() => {
            initSSE();
        }, 3000);
    });
}

// 初始化标签页
function initTabs() {
    console.log('初始化标签页...');
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    console.log('找到', tabButtons.length, '个tab按钮');
    console.log('找到', tabContents.length, '个tab内容区域');

    // 初始化第一个tab的样式
    const activeTab = document.querySelector('.tab-button[data-tab="stocks"]');
    if (activeTab) {
        activeTab.classList.add('bg-blue-600', 'text-white');
        console.log('已设置第一个tab的激活样式');
    }

    tabButtons.forEach((button, index) => {
        console.log(`设置第${index}个tab的点击事件:`, button.dataset.tab);
        // 移动端优化：使用 click 事件
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const tabName = button.dataset.tab;
            console.log('点击tab:', tabName);

            // 移动端：平滑滚动到标签内容
            if (isMobile) {
                button.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            }

            // 更新按钮状态
            tabButtons.forEach(btn => btn.classList.remove('active', 'bg-blue-600', 'text-white'));
            button.classList.add('active', 'bg-blue-600', 'text-white');

            // 更新内容显示
            tabContents.forEach(content => content.classList.add('hidden'));
            const targetTab = document.getElementById(`${tabName}Tab`);
            if (targetTab) {
                targetTab.classList.remove('hidden');
                console.log('显示tab内容:', tabName);
            }

            // 加载对应数据
            if (tabName === 'market') {
                loadMarketData();
            } else if (tabName === 'portfolio') {
                loadPortfolio();
            } else if (tabName === 'trades') {
                loadTrades();
            } else if (tabName === 'orders') {
                loadOrders();
            } else if (tabName === 'settings') {
                loadSettings();
            }
        });
    });
    console.log('标签页初始化完成');
}

// 初始化事件监听
function initEventListeners() {
    // 监控开关
    document.getElementById('toggleMonitoring').addEventListener('click', toggleMonitoring);
    document.getElementById('toggleTestMode').addEventListener('click', toggleTestMode);

    // 添加股票
    document.getElementById('addStockBtn').addEventListener('click', () => {
        loadGroupsToSelect();
        document.getElementById('addStockModal').classList.remove('hidden');
    });

    // 股票列表页的同步按钮
    document.getElementById('syncWatchlistBtnInStocks').addEventListener('click', syncLongbridgeWatchlist);

    document.getElementById('closeModalBtn').addEventListener('click', closeAddStockModal);
    document.getElementById('cancelAddStockBtn').addEventListener('click', closeAddStockModal);
    document.getElementById('confirmAddStockBtn').addEventListener('click', confirmAddStock);

    // 分组相关
    document.getElementById('addNewGroupBtn').addEventListener('click', showNewGroupInput);
    document.getElementById('saveGroupBtn').addEventListener('click', saveNewGroup);
    document.getElementById('cancelGroupBtn').addEventListener('click', hideNewGroupInput);

    // 详情弹窗
    document.getElementById('closeDetailModalBtn').addEventListener('click', closeDetailModal);
    document.getElementById('detailModal').addEventListener('click', (e) => {
        if (e.target.id === 'detailModal') {
            closeDetailModal();
        }
    });

    // 统计卡片点击事件
    document.getElementById('totalAssetsCard').addEventListener('click', () => {
        document.querySelector('[data-tab="portfolio"]').click();
    });
    document.getElementById('activeStocksCard').addEventListener('click', showActiveStocksDetail);
    document.getElementById('todayTradesCard').addEventListener('click', showTodayTradesDetail);

    // 刷新按钮
    document.getElementById('refreshMarketBtn').addEventListener('click', loadMarketData);
    document.getElementById('refreshPortfolioBtn').addEventListener('click', loadPortfolio);
    document.getElementById('refreshTradesBtn').addEventListener('click', loadTrades);
    document.getElementById('refreshOrdersBtn').addEventListener('click', () => loadOrders());
    document.getElementById('filterOrdersBtn').addEventListener('click', () => loadOrders());

    // 加速度排行榜选择器
    document.getElementById('accelerationTopN').addEventListener('change', loadMarketData);

    // 保存设置
    document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);

    // 同步自选股
    document.getElementById('syncWatchlistBtn').addEventListener('click', syncLongbridgeWatchlist);
    // 同步持仓
    document.getElementById('syncPositionsBtn').addEventListener('click', syncLongbridgePositions);

    // 快速止盈目标输入框
    const profitTargetQuickInput = document.getElementById('profitTargetQuickInput');
    profitTargetQuickInput.addEventListener('change', async (e) => {
        const value = parseFloat(e.target.value);
        if (value >= 0.1 && value <= 100) {
            await updateProfitTarget(value);
        } else {
            showNotification('止盈目标应在0.1%到100%之间', 'error');
            e.target.value = '1.0';
        }
    });

    profitTargetQuickInput.addEventListener('blur', async (e) => {
        const value = parseFloat(e.target.value);
        if (value >= 0.1 && value <= 100) {
            await updateProfitTarget(value);
        }
    });
    
    // 初始化智能交易事件
    initSmartTradeEvents();
}

// 加载初始数据
async function loadInitialData() {
    await loadStocks();
    await updateMonitoringStatus();
    await loadStatistics();
    await loadSettings();  // 加载设置，包括止盈目标
}

// 加载股票列表
async function loadStocks() {
    try {
        const response = await fetch(`${API_BASE}/api/stocks`, { credentials: 'include' });
        const result = await response.json();
        
        if (result.code === 0) {
            renderStocks(result.data);
            updateActiveStocksCount(result.data);
        }
    } catch (error) {
        console.error('加载股票列表失败:', error);
        showNotification('加载股票列表失败', 'error');
    }
}

// 渲染股票列表
function renderStocks(stocks) {
    const container = document.getElementById('stocksTableBody');
    container.innerHTML = '';

    if (!stocks || stocks.length === 0) {
        container.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-8 text-gray-400">
                    <i class="fas fa-inbox text-4xl mb-3"></i>
                    <p>暂无股票，点击上方"添加股票"或"同步长桥自选股"</p>
                </td>
            </tr>
        `;
        return;
    }

    // 按类型和分组整理股票
    const typeGroups = {
        'STOCK': {},
        'OPTION': {}
    };

    stocks.forEach(stock => {
        const stockType = stock.stock_type || 'STOCK';
        const groupName = stock.group_name || '未分组';
        if (!typeGroups[stockType][groupName]) {
            typeGroups[stockType][groupName] = [];
        }
        typeGroups[stockType][groupName].push(stock);
    });

    // 渲染每个类型
    ['STOCK', 'OPTION'].forEach(stockType => {
        const groups = typeGroups[stockType];
        const typeLabel = stockType === 'STOCK' ? '正股' : '期权';
        const typeIcon = stockType === 'STOCK' ? 'fa-chart-line' : 'fa-chart-area';
        const typeColor = stockType === 'STOCK' ? 'text-blue-400' : 'text-orange-400';

        if (Object.keys(groups).length === 0) {
            return;
        }

        // 类型标题行
        const typeHeaderRow = document.createElement('tr');
        typeHeaderRow.className = 'bg-gray-800';
        typeHeaderRow.innerHTML = `
            <td colspan="5" class="py-3 px-2 sm:px-4">
                <div class="flex items-center">
                    <i class="fas ${typeIcon} ${typeColor} mr-2"></i>
                    <span class="font-bold ${typeColor}">${typeLabel}</span>
                    <span class="ml-2 px-2 py-0.5 bg-gray-700 rounded-full text-xs text-gray-300">
                        ${Object.keys(groups).length} 个分组
                    </span>
                </div>
            </td>
        `;
        container.appendChild(typeHeaderRow);

        // 渲染该类型下的每个分组
        Object.keys(groups).sort((a, b) => {
            const groupA = groups[a][0];
            const groupB = groups[b][0];
            return (groupA.group_order || 0) - (groupB.group_order || 0);
        }).forEach(groupName => {
            // 分组标题行
            const headerRow = document.createElement('tr');
            headerRow.className = 'bg-gray-750';
            headerRow.innerHTML = `
                <td colspan="5" class="py-2 px-2 sm:px-4 pl-4">
                    <div class="flex items-center">
                        <i class="fas fa-folder text-purple-400 mr-2"></i>
                        <span class="font-bold text-purple-400">${groupName}</span>
                        <span class="ml-2 px-2 py-0.5 bg-gray-700 rounded-full text-xs text-gray-300">
                            ${groups[groupName].length} 只
                        </span>
                    </div>
                </td>
            `;
            container.appendChild(headerRow);

            // 该分组的股票
            groups[groupName].forEach(stock => {
                const tr = document.createElement('tr');
                tr.className = 'border-b border-gray-700 hover:bg-gray-700 transition-colors duration-200';
                tr.innerHTML = `
                    <td class="py-3 px-2 sm:px-4 pl-8">
                        <button onclick="showStockDetail('${stock.symbol}')" class="font-medium text-sm text-blue-400 hover:text-blue-300 underline">
                            ${stock.symbol}
                        </button>
                    </td>
                    <td class="py-3 px-2 sm:px-4 text-gray-300 text-sm">${stock.name}</td>
                    <td class="py-3 px-2 sm:px-4">
                        <span class="px-2 py-1 rounded text-xs font-medium ${stock.stock_type === 'STOCK' ? 'bg-blue-600 text-white' : 'bg-orange-600 text-white'}">
                            ${stock.stock_type === 'STOCK' ? '正股' : '期权'}
                        </span>
                    </td>
                    <td class="py-3 px-2 sm:px-4 text-right">
                        <button onclick="deleteStock(${stock.id})" class="px-2 sm:px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-xs transition-colors duration-200">
                            <i class="fas fa-trash mr-1"></i><span class="hidden sm:inline">删除</span>
                        </button>
                    </td>
                `;
                container.appendChild(tr);
            });
        });
    });
}

// 删除股票
async function deleteStock(stockId) {
    if (!confirm('确定要删除这只股票吗？')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/stocks/${stockId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        const result = await response.json();
        
        if (result.code === 0) {
            showNotification('删除成功', 'success');
            await loadStocks();
        }
    } catch (error) {
        console.error('删除股票失败:', error);
        showNotification('删除失败', 'error');
    }
}

// 关闭添加股票弹窗
function closeAddStockModal() {
    document.getElementById('addStockModal').classList.add('hidden');
    document.getElementById('newStockSymbol').value = '';
    document.getElementById('newStockName').value = '';
}

// 加载分组到选择框
async function loadGroupsToSelect() {
    try {
        const response = await fetch(`${API_BASE}/api/stocks`, { credentials: 'include' });
        const result = await response.json();

        if (result.code === 0) {
            const stocks = result.data;
            const groups = {};

            // 收集所有分组
            stocks.forEach(stock => {
                const groupName = stock.group_name || '未分组';
                groups[groupName] = stock.group_order || 0;
            });

            // 按group_order排序
            const sortedGroups = Object.keys(groups).sort((a, b) => groups[a] - groups[b]);

            // 填充选择框
            const select = document.getElementById('newStockGroup');
            select.innerHTML = '';
            sortedGroups.forEach(groupName => {
                const option = document.createElement('option');
                option.value = groupName;
                option.textContent = groupName;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('加载分组失败:', error);
    }
}

// 显示新建分组输入框
function showNewGroupInput() {
    document.getElementById('newGroupInput').classList.remove('hidden');
    document.getElementById('newGroupName').focus();
}

// 隐藏新建分组输入框
function hideNewGroupInput() {
    document.getElementById('newGroupInput').classList.add('hidden');
    document.getElementById('newGroupName').value = '';
}

// 保存新分组
function saveNewGroup() {
    const groupName = document.getElementById('newGroupName').value.trim();

    if (!groupName) {
        showNotification('请输入分组名称', 'error');
        return;
    }

    const select = document.getElementById('newStockGroup');

    // 检查是否已存在
    let exists = false;
    for (let i = 0; i < select.options.length; i++) {
        if (select.options[i].value === groupName) {
            exists = true;
            break;
        }
    }

    if (!exists) {
        const option = document.createElement('option');
        option.value = groupName;
        option.textContent = groupName;
        select.appendChild(option);
        select.value = groupName;
    } else {
        select.value = groupName;
    }

    hideNewGroupInput();
    showNotification('分组已添加', 'success');
}

// 确认添加股票
async function confirmAddStock() {
    const symbol = document.getElementById('newStockSymbol').value.trim().toUpperCase();
    const name = document.getElementById('newStockName').value.trim();
    const groupName = document.getElementById('newStockGroup').value || '未分组';

    if (!symbol || !name) {
        showNotification('请填写完整信息', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/stocks`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ symbol, name, group_name: groupName })
        });
        const result = await response.json();

        if (result.code === 0) {
            showNotification('添加成功', 'success');
            closeAddStockModal();
            await loadStocks();
        }
    } catch (error) {
        console.error('添加股票失败:', error);
        showNotification('添加失败', 'error');
    }
}

// 加载市场数据
async function loadMarketData() {
    try {
        const response = await fetch(`${API_BASE}/api/market-data`, { credentials: 'include' });
        const result = await response.json();

        if (result.code === 0) {
            // 确保 data 存在，如果不存在则使用空对象
            const data = result.data || {};
            renderMarketData(data);
            renderAccelerationTop(data);
            updateAccelerationChart(data);
        } else {
            showNotification('加载市场数据失败: ' + (result.message || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('加载市场数据失败:', error);
        showNotification('加载市场数据失败: ' + error.message, 'error');
    }
}

// 渲染市场数据（按分组展示）
function renderMarketData(groupedData) {
    const container = document.getElementById('marketDataContainer');
    container.innerHTML = '';

    // 检查数据格式
    if (!groupedData) {
        container.innerHTML = `
            <div class="col-span-full text-center py-12">
                <i class="fas fa-chart-line text-6xl text-gray-600 mb-4"></i>
                <p class="text-gray-400 text-lg">暂无市场数据</p>
                <p class="text-gray-500 text-sm mt-2">请确保有活跃的股票，并启动监控以获取实时行情</p>
            </div>
        `;
        return;
    }

    // 如果数据是数组格式（旧格式），转换为分组格式
    if (Array.isArray(groupedData)) {
        const convertedData = {
            '未分组': {
                group_name: '未分组',
                group_order: 0,
                stocks: groupedData
            }
        };
        groupedData = convertedData;
    }

    if (typeof groupedData !== 'object' || Object.keys(groupedData).length === 0) {
        container.innerHTML = `
            <div class="col-span-full text-center py-12">
                <i class="fas fa-chart-line text-6xl text-gray-600 mb-4"></i>
                <p class="text-gray-400 text-lg">暂无市场数据</p>
                <p class="text-gray-500 text-sm mt-2">请确保有活跃的股票，并启动监控以获取实时行情</p>
            </div>
        `;
        return;
    }

    // 为每个分组创建容器
    Object.entries(groupedData).forEach(([groupName, groupInfo]) => {
        if (!groupInfo || !groupInfo.stocks || groupInfo.stocks.length === 0) {
            return;
        }

        // 创建分组容器
        const groupContainer = document.createElement('div');
        groupContainer.className = 'col-span-full mb-6';
        
        // 分组标题
        const groupHeader = document.createElement('div');
        groupHeader.className = 'flex items-center justify-between mb-4 cursor-pointer group-header';
        groupHeader.setAttribute('data-group', groupName);
        
        const stockCount = groupInfo.stocks.length;
        const activeStocks = groupInfo.stocks.filter(stock => stock.price !== null).length;
        
        groupHeader.innerHTML = `
            <div class="flex items-center">
                <i class="fas fa-chevron-down text-blue-400 mr-2 transition-transform duration-200 group-toggle-icon"></i>
                <h3 class="text-lg font-bold text-white">${groupName}</h3>
                <span class="ml-2 text-sm text-gray-400">(${activeStocks}/${stockCount})</span>
            </div>
            <div class="text-sm text-gray-400">
                点击展开/收起
            </div>
        `;

        // 股票网格容器
        const stocksGrid = document.createElement('div');
        stocksGrid.className = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 group-stocks';
        stocksGrid.setAttribute('data-group', groupName);

        // 渲染分组内的股票
        groupInfo.stocks.forEach(stock => {
            const card = document.createElement('div');
            card.className = 'bg-gray-900 rounded-lg p-3 sm:p-4 hover:shadow-xl transition-shadow duration-200';

            if (stock.price !== null) {
                const changePctClass = stock.change_pct >= 0 ? 'text-green-400' : 'text-red-400';
                const accelerationClass = stock.acceleration >= 0 ? 'text-green-400' : 'text-red-400';
                const changeIcon = stock.change_pct >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';

                card.innerHTML = `
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <h3 class="text-base sm:text-lg font-bold">${stock.symbol}</h3>
                            <p class="text-xs text-gray-400 truncate">${stock.name || ''}</p>
                            <p class="text-xl sm:text-2xl font-bold mt-1">$${stock.price.toFixed(2)}</p>
                        </div>
                        <i class="fas ${changeIcon} ${changePctClass} text-lg sm:text-xl"></i>
                    </div>
                    <div class="space-y-2">
                        <div class="flex justify-between items-center">
                            <span class="text-gray-400 text-sm">涨跌幅</span>
                            <span class="${changePctClass} font-semibold">${stock.change_pct >= 0 ? '+' : ''}${stock.change_pct.toFixed(2)}%</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-gray-400 text-sm">加速度</span>
                            <span class="${accelerationClass} font-semibold">${stock.acceleration ? stock.acceleration.toFixed(4) : '--'}</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-gray-400 text-sm">成交量</span>
                            <span class="text-white text-sm">${stock.volume ? formatVolume(stock.volume) : '--'}</span>
                        </div>
                    </div>
                `;
            } else {
                // 无行情数据的股票
                card.innerHTML = `
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <h3 class="text-base sm:text-lg font-bold">${stock.symbol}</h3>
                            <p class="text-xs text-gray-400 truncate">${stock.name || ''}</p>
                            <p class="text-xl sm:text-2xl font-bold mt-1 text-gray-500">--</p>
                        </div>
                        <i class="fas fa-pause text-gray-500 text-lg sm:text-xl"></i>
                    </div>
                    <div class="space-y-2">
                        <div class="flex justify-between items-center">
                            <span class="text-gray-400 text-sm">涨跌幅</span>
                            <span class="text-gray-500 font-semibold">--</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-gray-400 text-sm">加速度</span>
                            <span class="text-gray-500 font-semibold">--</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-gray-400 text-sm">状态</span>
                            <span class="text-gray-500 text-sm">无数据</span>
                        </div>
                    </div>
                `;
            }

            stocksGrid.appendChild(card);
        });

        groupContainer.appendChild(groupHeader);
        groupContainer.appendChild(stocksGrid);
        container.appendChild(groupContainer);
    });

    // 添加分组展开/收起功能
    addGroupToggleListeners();
}

// 添加分组展开/收起监听器
function addGroupToggleListeners() {
    document.querySelectorAll('.group-header').forEach(header => {
        header.addEventListener('click', function() {
            const groupName = this.getAttribute('data-group');
            const stocksGrid = document.querySelector(`.group-stocks[data-group="${groupName}"]`);
            const toggleIcon = this.querySelector('.group-toggle-icon');
            
            if (stocksGrid.style.display === 'none') {
                stocksGrid.style.display = 'grid';
                toggleIcon.style.transform = 'rotate(0deg)';
                localStorage.setItem(`group-${groupName}-collapsed`, 'false');
            } else {
                stocksGrid.style.display = 'none';
                toggleIcon.style.transform = 'rotate(-90deg)';
                localStorage.setItem(`group-${groupName}-collapsed`, 'true');
            }
        });
        
        // 恢复之前的展开/收起状态
        const groupName = header.getAttribute('data-group');
        const isCollapsed = localStorage.getItem(`group-${groupName}-collapsed`) === 'true';
        if (isCollapsed) {
            const stocksGrid = document.querySelector(`.group-stocks[data-group="${groupName}"]`);
            const toggleIcon = header.querySelector('.group-toggle-icon');
            stocksGrid.style.display = 'none';
            toggleIcon.style.transform = 'rotate(-90deg)';
        }
    });
}

// 格式化成交量显示
function formatVolume(volume) {
    if (volume >= 1000000) {
        return (volume / 1000000).toFixed(1) + 'M';
    } else if (volume >= 1000) {
        return (volume / 1000).toFixed(1) + 'K';
    }
    return volume.toString();
}
// 渲染加速度排行榜
function renderAccelerationTop(data) {
    const container = document.getElementById('accelerationTopContainer');
    if (!container) return;
    
    const topNElement = document.getElementById('accelerationTopN');
    const topN = topNElement ? (parseInt(topNElement.value) || 10) : 10;
    container.innerHTML = '';

    // 将分组数据转换为扁平数组
    let flatData = [];
    
    // 安全检查
    if (!data) {
        // 数据为空
    } else if (Array.isArray(data)) {
        // 如果是数组格式（旧格式）
        flatData = data.filter(stock => stock && stock.price !== null);
    } else if (typeof data === 'object') {
        // 如果是分组格式（新格式）
        try {
            Object.values(data).forEach(group => {
                if (group && group.stocks && Array.isArray(group.stocks)) {
                    flatData = flatData.concat(group.stocks.filter(stock => stock && stock.price !== null));
                }
            });
        } catch (e) {
            console.error('处理分组数据时出错:', e);
        }
    }

    if (!flatData || flatData.length === 0) {
        container.innerHTML = `
            <div class="col-span-full text-center py-8">
                <p class="text-white/70 text-sm">暂无数据</p>
            </div>
        `;
        return;
    }

    // 按加速度降序排序
    const sortedData = [...flatData].sort((a, b) => b.acceleration - a.acceleration).slice(0, topN);

    sortedData.forEach((item, index) => {
        const card = document.createElement('div');
        card.className = 'bg-white/10 rounded-lg p-3 backdrop-blur-sm hover:bg-white/20 transition-colors duration-200 cursor-pointer';
        card.onclick = () => showStockDetail(item.symbol);

        const rankColors = [
            'text-yellow-400',
            'text-gray-400',
            'text-orange-400',
            'text-white',
            'text-white'
        ];
        const rankColor = rankColors[index] || 'text-white';
        const accelerationClass = item.acceleration >= 0 ? 'text-green-400' : 'text-red-400';

        card.innerHTML = `
            <div class="flex items-center space-x-2 mb-2">
                <span class="text-xl font-bold ${rankColor}">#${index + 1}</span>
                <h4 class="text-sm font-bold text-white truncate flex-1">${item.symbol}</h4>
            </div>
            <div class="text-center">
                <p class="text-2xl font-bold ${accelerationClass}">
                    ${item.acceleration >= 0 ? '+' : ''}${item.acceleration.toFixed(4)}
                </p>
                <p class="text-xs text-white/70 mt-1">
                    $${item.price.toFixed(2)} (${item.change_pct >= 0 ? '+' : ''}${item.change_pct.toFixed(2)}%)
                </p>
            </div>
        `;

        container.appendChild(card);
    });
}

// 初始化加速度图表
function initAccelerationChart() {
    const chartDom = document.getElementById('accelerationChart');
    accelerationChart = echarts.init(chartDom);
    
    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            borderColor: '#3b82f6',
            textStyle: {
                color: '#fff'
            }
        },
        legend: {
            data: [],
            textStyle: {
                color: '#9ca3af'
            }
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
            data: [],
            axisLine: {
                lineStyle: {
                    color: '#4b5563'
                }
            },
            axisLabel: {
                color: '#9ca3af'
            }
        },
        yAxis: {
            type: 'value',
            name: '加速度',
            axisLine: {
                lineStyle: {
                    color: '#4b5563'
                }
            },
            axisLabel: {
                color: '#9ca3af'
            },
            splitLine: {
                lineStyle: {
                    color: '#374151'
                }
            }
        },
        series: []
    };
    
    accelerationChart.setOption(option);
}

// 更新加速度图表
function updateAccelerationChart(data) {
    if (!accelerationChart) return;
    
    // 将分组数据转换为扁平数组
    let flatData = [];
    
    // 安全检查
    if (!data) {
        // 数据为空
    } else if (Array.isArray(data)) {
        // 如果是数组格式（旧格式）
        flatData = data.filter(stock => stock && stock.price !== null);
    } else if (typeof data === 'object') {
        // 如果是分组格式（新格式）
        try {
            Object.values(data).forEach(group => {
                if (Array.isArray(group)) {
                    flatData = flatData.concat(group.filter(stock => stock && stock.price !== null));
                } else if (group && group.stocks && Array.isArray(group.stocks)) {
                    flatData = flatData.concat(group.stocks.filter(stock => stock && stock.price !== null));
                }
            });
        } catch (e) {
            console.error('处理图表数据时出错:', e);
        }
    }
    
    if (!flatData || flatData.length === 0) return;
    
    const symbols = flatData.map(item => item.symbol);
    const series = symbols.map(symbol => {
        const item = flatData.find(d => d.symbol === symbol);
        return {
            name: symbol,
            type: 'line',
            smooth: true,
            data: [item.acceleration],
            itemStyle: {
                color: getRandomColor()
            }
        };
    });
    
    accelerationChart.setOption({
        legend: {
            data: symbols
        },
        xAxis: {
            data: [new Date().toLocaleTimeString()]
        },
        series: series
    });
}

// 加载交易记录
async function loadTrades() {
    try {
        const response = await fetch(`${API_BASE}/api/trades?limit=50`);
        const result = await response.json();
        
        if (result.code === 0) {
            renderTrades(result.data);
        }
    } catch (error) {
        console.error('加载交易记录失败:', error);
    }
}

// 渲染交易记录
function renderTrades(trades) {
    const tbody = document.getElementById('tradesTableBody');
    tbody.innerHTML = '';
    
    if (trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-gray-400">暂无交易记录</td></tr>';
        return;
    }
    
    trades.forEach(trade => {
        const tr = document.createElement('tr');
        tr.className = 'border-b border-gray-700 hover:bg-gray-700 transition-colors duration-200';
        
        const actionClass = trade.action === 'BUY' ? 'text-green-400' : 'text-red-400';
        const statusClass = trade.status === 'SUCCESS' ? 'bg-green-600' : trade.status === 'FAILED' ? 'bg-red-600' : 'bg-yellow-600';
        
        tr.innerHTML = `
            <td class="py-3 px-2 sm:px-4 text-xs sm:text-sm text-gray-300 whitespace-nowrap">${formatDateTime(trade.trade_time)}</td>
            <td class="py-3 px-2 sm:px-4 font-medium text-sm">${trade.symbol}</td>
            <td class="py-3 px-2 sm:px-4 ${actionClass} font-medium text-sm">${trade.action === 'BUY' ? '买入' : '卖出'}</td>
            <td class="py-3 px-2 sm:px-4 text-right text-sm">$${trade && trade.price ? trade.price.toFixed(2) : '--'}</td>
            <td class="py-3 px-2 sm:px-4 text-right text-sm">${trade && trade.quantity ? trade.quantity : '--'}</td>
            <td class="py-3 px-2 sm:px-4 text-right text-sm">$${trade && trade.amount ? trade.amount.toFixed(2) : '--'}</td>
            <td class="py-3 px-2 sm:px-4 text-right text-sm whitespace-nowrap">${trade && trade.acceleration ? trade.acceleration.toFixed(4) : '--'}</td>
            <td class="py-3 px-2 sm:px-4">
                <span class="px-2 py-1 rounded-full text-xs ${statusClass}">${trade.status}</span>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// K线图相关变量
let stockKlineChart = null;

// 加载并显示股票K线图
async function loadStockKline(symbol, period = '1d') {
    try {
        const response = await fetch(`${API_BASE}/api/stock/history/${symbol}?period=${period}&count=200`, { credentials: 'include' });
        const result = await response.json();

        if (result.code === 0 && result.data.length > 0) {
            renderStockKline(result.data, symbol);
        }
    } catch (error) {
        console.error('加载K线数据失败:', error);
    }
}

// 渲染K线图
function renderStockKline(data, symbol) {
    const chartDom = document.getElementById('stockKlineChart');
    if (!chartDom) return;

    // 如果已存在图表实例，先销毁
    if (stockKlineChart) {
        stockKlineChart.dispose();
    }

    stockKlineChart = echarts.init(chartDom);

    // 转换数据格式为 [时间, 开盘, 收盘, 最低, 最高]
    const chartData = data.map(item => {
        const date = new Date(item.timestamp);
        return [
            date.getTime(),
            parseFloat(item.open),
            parseFloat(item.close),
            parseFloat(item.low),
            parseFloat(item.high)
        ];
    });

    const volumes = data.map(item => {
        return [
            new Date(item.timestamp).getTime(),
            parseFloat(item.volume),
            parseFloat(item.close) >= parseFloat(item.open) ? 1 : -1
        ];
    });

    const option = {
        backgroundColor: '#111827',
        title: {
            text: `${symbol} - K线图`,
            textStyle: { color: '#fff', fontSize: 14 },
            left: 'center'
        },
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(0,0,0,0.8)',
            borderColor: '#333',
            textStyle: { color: '#fff' },
            axisPointer: {
                type: 'cross'
            }
        },
        legend: {
            data: ['K线', '成交量'],
            textStyle: { color: '#9ca3af' },
            top: 30
        },
        grid: [
            {
                left: '10%',
                right: '8%',
                height: '50%'
            },
            {
                left: '10%',
                right: '8%',
                top: '63%',
                height: '16%'
            }
        ],
        xAxis: [
            {
                type: 'time',
                scale: true,
                boundaryGap: false,
                axisLine: { lineStyle: { color: '#374151' } },
                splitLine: { show: false },
                axisLabel: { color: '#9ca3af' },
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
                axisLabel: { color: '#9ca3af' },
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
                top: '85%',
                start: 50,
                end: 100
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
                }
            },
            {
                name: '成交量',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: volumes,
                itemStyle: {
                    color: function(params) {
                        return params.data[2] > 0 ? '#ef444433' : '#22c55e33';
                    }
                }
            }
        ]
    };

    stockKlineChart.setOption(option);

    // 响应式调整
    window.addEventListener('resize', () => {
        stockKlineChart.resize();
    });
}

// 修改showStockDetail函数，在内容加载后调用K线图
async function showStockDetailWithKline(symbol) {
    // 先调用原有的showStockDetail
    await showStockDetail(symbol);

    // 加载K线图
    setTimeout(() => {
        loadStockKline(symbol, '1d');

        // 绑定周期切换事件
        document.querySelectorAll('.period-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const period = this.getAttribute('data-period');

                // 更新按钮样式
                document.querySelectorAll('.period-btn').forEach(b => {
                    b.classList.remove('bg-blue-600');
                    b.classList.add('bg-gray-700');
                });
                this.classList.remove('bg-gray-700');
                this.classList.add('bg-blue-600');

                // 加载新周期的K线数据
                loadStockKline(symbol, period);
            });
        });
    }, 500);
}

// 加载账户总览
async function loadPortfolio() {
    try {
        const response = await fetch(`${API_BASE}/api/portfolio`, { credentials: 'include' });
        const result = await response.json();

        if (result.code === 0) {
            const data = result.data;

            // 更新总资产
            document.getElementById('totalAssets').textContent = formatCurrency(data.total_assets);

            // 更新多币种资产
            if (data.multi_currency) {
                document.getElementById('totalAssetsUSD').textContent = formatCurrency((data.multi_currency.USD && data.multi_currency.USD.total_assets) || 0, false, 'USD');
                document.getElementById('totalAssetsCNY').textContent = formatCurrency((data.multi_currency.CNY && data.multi_currency.CNY.total_assets) || 0, false, 'CNY');
                document.getElementById('totalAssetsHKD').textContent = formatCurrency((data.multi_currency.HKD && data.multi_currency.HKD.total_assets) || 0, false, 'HKD');
            }

            // 更新现金
            document.getElementById('availableCash').textContent = formatCurrency(data.available_cash);

            // 更新持仓市值
            document.getElementById('positionMarketValue').textContent = formatCurrency(data.position_market_value);

            // 更新持仓盈亏
            const plElement = document.getElementById('positionProfitLoss');
            const plPctElement = document.getElementById('positionProfitLossPct');
            const plIcon = document.getElementById('positionPLOffset');

            plElement.textContent = formatCurrency(data.position_profit_loss, true);
            plPctElement.textContent = (data.position_profit_loss_pct >= 0 ? '+' : '') + (data && data.position_profit_loss_pct ? data.position_profit_loss_pct.toFixed(2) : '0.00') + '%';

            const isProfitable = data.position_profit_loss >= 0;
            plElement.className = `text-xl sm:text-2xl font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`;
            plPctElement.className = `text-xs mt-1 ${isProfitable ? 'text-green-400' : 'text-red-400'}`;
            plIcon.className = `fas fa-balance-scale ${isProfitable ? 'text-green-400' : 'text-red-400'}`;

            // 更新当日盈亏
            const dailyPlElement = document.getElementById('dailyProfitLoss');
            const dailyPlPctElement = document.getElementById('dailyProfitLossPct');
            const dailyPlIcon = document.getElementById('dailyPLOffset');

            dailyPlElement.textContent = formatCurrency(data.daily_profit_loss, true);
            dailyPlPctElement.textContent = (data.daily_profit_loss_pct >= 0 ? '+' : '') + (data && data.daily_profit_loss_pct ? data.daily_profit_loss_pct.toFixed(2) : '0.00') + '%';

            const dailyProfitable = data.daily_profit_loss >= 0;
            dailyPlElement.className = `text-xl sm:text-2xl font-bold ${dailyProfitable ? 'text-green-400' : 'text-red-400'}`;
            dailyPlPctElement.className = `text-xs mt-1 ${dailyProfitable ? 'text-green-400' : 'text-red-400'}`;
            dailyPlIcon.className = `fas fa-calendar-day ${dailyProfitable ? 'text-green-400' : 'text-red-400'}`;

            // 更新持仓明细
            renderPositions(data.positions);

            // 更新今日交易汇总
            document.getElementById('todayTradeCount').textContent = data.today_trades.count;
            document.getElementById('todayBuyCount').textContent = data.today_trades.buy_count;
            document.getElementById('todaySellCount').textContent = data.today_trades.sell_count;
            document.getElementById('todayTradeVolume').textContent = formatCurrency(data.today_trades.volume);
        }
    } catch (error) {
        console.error('加载账户总览失败:', error);
        showNotification('加载账户总览失败', 'error');
    }
}

// 渲染持仓明细
function renderPositions(positions) {
    const tbody = document.getElementById('positionsTableBody');
    const noPositions = document.getElementById('noPositions');

    tbody.innerHTML = '';

    if (!positions || positions.length === 0) {
        noPositions.classList.remove('hidden');
        return;
    }

    noPositions.classList.add('hidden');

    positions.forEach(pos => {
        const tr = document.createElement('tr');
        tr.className = 'border-b border-gray-700 hover:bg-gray-700 transition-colors duration-200';

        const isProfitable = pos.profit_loss >= 0;
        const plClass = isProfitable ? 'text-green-400' : 'text-red-400';

        tr.innerHTML = `
            <td class="py-3 px-4 font-medium text-sm">${pos.symbol}</td>
            <td class="py-3 px-4 text-right text-sm">${pos.quantity}</td>
            <td class="py-3 px-4 text-right text-sm">$${pos && pos.cost ? pos.cost.toFixed(2) : '--'}</td>
            <td class="py-3 px-4 text-right text-sm">$${pos && pos.current_price ? pos.current_price.toFixed(2) : '--'}</td>
            <td class="py-3 px-4 text-right text-sm">$${pos && pos.market_value ? pos.market_value.toFixed(2) : '--'}</td>
            <td class="py-3 px-4 text-right text-sm ${plClass}">${pos && pos.profit_loss ? formatCurrency(pos.profit_loss, true) : '--'}</td>
            <td class="py-3 px-4 text-right text-sm ${plClass}">${pos && pos.profit_loss_pct >= 0 ? '+' : ''}${pos && pos.profit_loss_pct ? pos.profit_loss_pct.toFixed(2) : '--'}%</td>
        `;
        tbody.appendChild(tr);
    });
}

// 加载设置
async function loadSettings() {
    try {
        const response = await fetch(`${API_BASE}/api/config`, { credentials: 'include' });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();

        if (result.code === 0 && result.data) {
            const config = result.data;
            // 正确读取配置值：后端返回的数据结构是 {values: {...}, definitions: {...}, defaults: {...}}
            if (config.values) {
                const profitTarget = config.values.profit_target || '1.0';
                const profitTargetInput = document.getElementById('profitTargetInput');
                const profitTargetQuickInput = document.getElementById('profitTargetQuickInput');
                
                if (profitTargetInput) {
                    profitTargetInput.value = profitTarget;
                }
                if (profitTargetQuickInput) {
                    profitTargetQuickInput.value = profitTarget;
                }

                const maxConcurrentPositions = config.values.max_concurrent_positions || '1';
                const maxConcurrentPositionsInput = document.getElementById('maxConcurrentPositionsInput');
                if (maxConcurrentPositionsInput) {
                    maxConcurrentPositionsInput.value = maxConcurrentPositions;
                }
            }
        } else {
            console.error('加载配置失败，API返回错误:', result);
        }

        // 加载长桥配置
        try {
            const lbResponse = await fetch(`${API_BASE}/api/longbridge/config`, { credentials: 'include' });
            const lbResult = await lbResponse.json();
            if (lbResult.code === 0) {
                const lbConfig = lbResult.data;
                updateLongBridgeStatus(lbConfig);
                
                // 如果已配置，自动填充输入框（显示脱敏后的值）
                if (lbConfig.is_configured) {
                    const appKeyInput = document.getElementById('appKeyInput');
                    if (appKeyInput && lbConfig.app_key) {
                        appKeyInput.value = lbConfig.app_key;
                        appKeyInput.placeholder = '已配置（如需修改请重新输入）';
                    }
                    const appSecretInput = document.getElementById('appSecretInput');
                    if (appSecretInput && lbConfig.has_secret) {
                        appSecretInput.placeholder = '已配置（如需修改请重新输入）';
                    }
                    const accessTokenInput = document.getElementById('accessTokenInput');
                    if (accessTokenInput && lbConfig.has_token) {
                        accessTokenInput.placeholder = '已配置（如需修改请重新输入）';
                    }
                }
            }
        } catch (lbError) {
            console.error('加载长桥配置失败:', lbError);
        }
        
        // 加载智能交易配置
        await loadSmartTradeSettings();
    } catch (error) {
        console.error('加载设置失败:', error);
    }
}

// ==================== 智能交易功能 ====================

// 加载智能交易设置
async function loadSmartTradeSettings() {
    try {
        const response = await fetch(`${API_BASE}/api/smart-trade/status`, { credentials: 'include' });
        const result = await response.json();
        
        if (result.code === 0 && result.data) {
            const { status, today_predictions, today_stats } = result.data;
            
            // 更新开关状态
            const enabledCheckbox = document.getElementById('smartTradeEnabled');
            const statusText = document.getElementById('smartTradeStatusText');
            if (enabledCheckbox) {
                enabledCheckbox.checked = status.enabled;
                statusText.textContent = status.enabled ? '已启用' : '已关闭';
            }
            
            // 更新配置表单
            document.getElementById('smartMaxDailyTrades').value = status.max_daily_trades || 3;
            document.getElementById('smartBuyAmount').value = status.buy_amount || 200000;
            document.getElementById('smartMinScore').value = status.min_prediction_score || 60;
            document.getElementById('smartBaseProfit').value = status.base_profit_target || 1.0;
            document.getElementById('smartTrailingStop').value = status.trailing_stop || 0.5;
            document.getElementById('smartMaxHoldDays').value = status.max_hold_days || 5;
            document.getElementById('smartDynamicStop').checked = status.dynamic_stop_profit !== false;
            
            // 更新LLM配置
            const llmEnabled = document.getElementById('llmEnabled');
            if (llmEnabled) {
                llmEnabled.checked = status.llm_enabled || false;
            }
            const llmProvider = document.getElementById('llmProvider');
            if (llmProvider) {
                llmProvider.value = status.llm_provider || 'openai';
            }
            const llmApiBase = document.getElementById('llmApiBase');
            if (llmApiBase) {
                llmApiBase.value = status.llm_api_base || 'https://api.openai.com/v1';
            }
            const llmModel = document.getElementById('llmModel');
            if (llmModel) {
                llmModel.value = status.llm_model || 'gpt-4o-mini';
            }
            const llmWeight = document.getElementById('llmWeight');
            if (llmWeight) {
                llmWeight.value = status.llm_weight || 0.3;
                const weightValue = document.getElementById('llmWeightValue');
                if (weightValue) {
                    weightValue.textContent = status.llm_weight || 0.3;
                }
            }
            
            // 显示LLM配置状态
            updateLlmConfigStatus(status.llm_enabled, status.llm_configured);
            
            // 显示今日预测结果
            if (today_predictions && today_predictions.length > 0) {
                displayPredictionResults(today_predictions);
            }
        }
    } catch (error) {
        console.error('加载智能交易设置失败:', error);
    }
}

// 更新LLM配置状态显示
function updateLlmConfigStatus(enabled, configured) {
    const section = document.getElementById('llmConfigSection');
    if (section) {
        section.style.opacity = enabled ? '1' : '0.5';
    }
}

// 显示预测结果
function displayPredictionResults(predictions) {
    const section = document.getElementById('predictionResultsSection');
    const container = document.getElementById('predictionResults');
    
    if (!predictions || predictions.length === 0) {
        section.classList.add('hidden');
        return;
    }
    
    section.classList.remove('hidden');
    container.innerHTML = '';
    
    predictions.forEach((pred, index) => {
        const scoreColor = pred.technical_score >= 70 ? 'text-green-400' : 
                          pred.technical_score >= 50 ? 'text-yellow-400' : 'text-red-400';
        const rankColor = index < 3 ? 'text-yellow-400' : 'text-gray-400';
        
        // LLM建议标签
        let llmBadge = '';
        if (pred.llm_recommendation) {
            const badgeColor = pred.llm_recommendation === 'buy' ? 'bg-green-600' : 
                              pred.llm_recommendation === 'sell' ? 'bg-red-600' : 'bg-gray-600';
            const badgeText = pred.llm_recommendation === 'buy' ? '买入' : 
                             pred.llm_recommendation === 'sell' ? '卖出' : '持有';
            llmBadge = `<span class="ml-2 px-2 py-0.5 ${badgeColor} rounded text-xs">AI:${badgeText}</span>`;
        }
        
        // LLM得分显示
        let llmScoreHtml = '';
        if (pred.llm_score !== null && pred.llm_score !== undefined) {
            const llmScoreColor = pred.llm_score >= 70 ? 'text-pink-400' : 
                                 pred.llm_score >= 50 ? 'text-pink-300' : 'text-pink-200';
            llmScoreHtml = `
                <div class="text-right">
                    <div class="text-xs text-gray-400">AI得分</div>
                    <div class="${llmScoreColor} font-bold">${pred.llm_score?.toFixed(1) || '--'}</div>
                </div>
            `;
        }
        
        const item = document.createElement('div');
        item.className = 'flex items-center justify-between p-3 bg-gray-800 rounded-lg hover:bg-gray-750 transition-colors';
        item.innerHTML = `
            <div class="flex items-center space-x-3">
                <span class="text-lg font-bold ${rankColor}">#${index + 1}</span>
                <div>
                    <span class="font-medium">${pred.symbol}</span>
                    ${llmBadge}
                    <span class="text-xs text-gray-400 ml-2">${pred.stock_name || ''}</span>
                </div>
            </div>
            <div class="flex items-center space-x-4">
                <div class="text-right">
                    <div class="text-xs text-gray-400">技术得分</div>
                    <div class="${scoreColor} font-bold">${pred.technical_score?.toFixed(1) || '--'}</div>
                </div>
                ${llmScoreHtml}
                <div class="text-right">
                    <div class="text-xs text-gray-400">预测收益</div>
                    <div class="${pred.predicted_return >= 0 ? 'text-green-400' : 'text-red-400'} font-bold">
                        ${pred.predicted_return >= 0 ? '+' : ''}${(pred.predicted_return * 100)?.toFixed(2) || '--'}%
                    </div>
                </div>
                ${pred.actual_return !== null ? `
                <div class="text-right">
                    <div class="text-xs text-gray-400">实际收益</div>
                    <div class="${pred.actual_return >= 0 ? 'text-green-400' : 'text-red-400'} font-bold">
                        ${pred.actual_return >= 0 ? '+' : ''}${pred.actual_return?.toFixed(2) || '--'}%
                    </div>
                </div>
                ` : ''}
            </div>
        `;
        
        // 如果有LLM分析，添加可展开的详情
        if (pred.llm_analysis) {
            item.classList.add('cursor-pointer');
            item.title = '点击查看AI分析';
            item.onclick = () => {
                showNotification(`AI分析: ${pred.llm_analysis}`, 'info', 5000);
            };
        }
        
        container.appendChild(item);
    });
}

// 保存智能交易设置
async function saveSmartTradeSettings() {
    const config = {
        enabled: document.getElementById('smartTradeEnabled').checked,
        max_daily_trades: parseInt(document.getElementById('smartMaxDailyTrades').value) || 3,
        buy_amount: parseFloat(document.getElementById('smartBuyAmount').value) || 200000,
        min_score: parseFloat(document.getElementById('smartMinScore').value) || 60,
        base_profit: parseFloat(document.getElementById('smartBaseProfit').value) || 1.0,
        trailing_stop: parseFloat(document.getElementById('smartTrailingStop').value) || 0.5,
        max_hold_days: parseInt(document.getElementById('smartMaxHoldDays').value) || 5,
        dynamic_stop: document.getElementById('smartDynamicStop').checked,
        // LLM配置
        llm_enabled: document.getElementById('llmEnabled')?.checked || false,
        llm_provider: document.getElementById('llmProvider')?.value || 'openai',
        llm_api_base: document.getElementById('llmApiBase')?.value || 'https://api.openai.com/v1',
        llm_api_key: document.getElementById('llmApiKey')?.value || '',
        llm_model: document.getElementById('llmModel')?.value || 'gpt-4o-mini',
        llm_weight: parseFloat(document.getElementById('llmWeight')?.value) || 0.3
    };
    
    try {
        const response = await fetch(`${API_BASE}/api/smart-trade/config`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (result.code === 0) {
            showNotification('智能交易配置已保存', 'success');
            // 更新状态文字
            document.getElementById('smartTradeStatusText').textContent = config.enabled ? '已启用' : '已关闭';
            // 更新LLM状态
            updateLlmConfigStatus(config.llm_enabled, !!config.llm_api_key);
        } else {
            showNotification('保存失败: ' + (result.message || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('保存智能交易设置失败:', error);
        showNotification('保存失败', 'error');
    }
}

// 运行预测
async function runPrediction() {
    try {
        showNotification('正在运行股票预测...', 'info');
        
        const response = await fetch(`${API_BASE}/api/smart-trade/run-prediction`, {
            method: 'POST',
            credentials: 'include'
        });
        
        const result = await response.json();
        
        if (result.code === 0) {
            showNotification(`预测完成，共分析${result.data.total}只股票`, 'success');
            displayPredictionResults(result.data.predictions);
        } else {
            showNotification('预测失败: ' + (result.message || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('运行预测失败:', error);
        showNotification('运行预测失败', 'error');
    }
}

// 手动执行智能买入
async function executeSmartBuy() {
    if (!confirm('确定要立即执行智能买入吗？系统将根据预测结果买入最优股票。')) {
        return;
    }
    
    try {
        showNotification('正在执行智能买入...', 'info');
        
        const response = await fetch(`${API_BASE}/api/smart-trade/execute-buy`, {
            method: 'POST',
            credentials: 'include'
        });
        
        const result = await response.json();
        
        if (result.code === 0) {
            showNotification('智能买入执行完成', 'success');
            // 刷新数据
            loadPositions();
            loadTrades();
            loadStatistics();
        } else {
            showNotification(result.message || '执行失败', 'error');
        }
    } catch (error) {
        console.error('执行智能买入失败:', error);
        showNotification('执行失败', 'error');
    }
}

// 初始化智能交易事件监听
function initSmartTradeEvents() {
    // 保存配置按钮
    const saveBtn = document.getElementById('saveSmartTradeBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveSmartTradeSettings);
    }
    
    // 运行预测按钮
    const predictionBtn = document.getElementById('runPredictionBtn');
    if (predictionBtn) {
        predictionBtn.addEventListener('click', runPrediction);
    }
    
    // 手动买入按钮
    const buyBtn = document.getElementById('manualSmartBuyBtn');
    if (buyBtn) {
        buyBtn.addEventListener('click', executeSmartBuy);
    }
    
    // 开关切换
    const enabledCheckbox = document.getElementById('smartTradeEnabled');
    if (enabledCheckbox) {
        enabledCheckbox.addEventListener('change', function() {
            document.getElementById('smartTradeStatusText').textContent = this.checked ? '已启用' : '已关闭';
        });
    }
    
    // LLM权重滑块
    const llmWeight = document.getElementById('llmWeight');
    if (llmWeight) {
        llmWeight.addEventListener('input', function() {
            const weightValue = document.getElementById('llmWeightValue');
            if (weightValue) {
                weightValue.textContent = this.value;
            }
        });
    }
    
    // LLM启用开关
    const llmEnabled = document.getElementById('llmEnabled');
    if (llmEnabled) {
        llmEnabled.addEventListener('change', function() {
            updateLlmConfigStatus(this.checked, true);
        });
    }
    
    // LLM提供商切换时自动更新API Base
    const llmProvider = document.getElementById('llmProvider');
    if (llmProvider) {
        llmProvider.addEventListener('change', function() {
            const apiBase = document.getElementById('llmApiBase');
            const model = document.getElementById('llmModel');
            if (apiBase && model) {
                switch(this.value) {
                    case 'openai':
                        apiBase.value = 'https://api.openai.com/v1';
                        model.value = 'gpt-4o-mini';
                        break;
                    case 'deepseek':
                        apiBase.value = 'https://api.deepseek.com/v1';
                        model.value = 'deepseek-chat';
                        break;
                    case 'zhipu':
                        apiBase.value = 'https://open.bigmodel.cn/api/paas/v4';
                        model.value = 'glm-4-flash';
                        break;
                    case 'ollama':
                        apiBase.value = 'http://localhost:11434/v1';
                        model.value = 'llama3';
                        break;
                }
            }
        });
    }
}

// 更新止盈目标
async function updateProfitTarget(value) {
    try {
        const response = await fetch(`${API_BASE}/api/config`, {
            method: 'PUT',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                config_key: 'profit_target',
                config_value: value.toString()
            })
        });
        const result = await response.json();

        if (result.code === 0) {
            // 同步更新设置页面的输入框
            document.getElementById('profitTargetInput').value = value;
            showNotification('止盈目标已更新', 'success');
        }
    } catch (error) {
        console.error('更新止盈目标失败:', error);
        showNotification('更新失败', 'error');
    }
}

// 保存设置
async function saveSettings() {
    const profitTarget = document.getElementById('profitTargetInput').value;
    const maxConcurrentPositions = document.getElementById('maxConcurrentPositionsInput').value;
    const appKey = document.getElementById('appKeyInput').value.trim();
    const appSecret = document.getElementById('appSecretInput').value.trim();
    const accessToken = document.getElementById('accessTokenInput').value.trim();

    // 验证止盈目标范围
    const targetValue = parseFloat(profitTarget);
    if (isNaN(targetValue) || targetValue < 0.1 || targetValue > 100) {
        showNotification('止盈目标应在0.1%到100%之间', 'error');
        return;
    }

    try {
        // 保存止盈目标
        const response = await fetch(`${API_BASE}/api/config`, {
            method: 'PUT',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                config_key: 'profit_target',
                config_value: profitTarget
            })
        });
        const result = await response.json();

        // 保存最大并发持仓数量
        const concurrentResponse = await fetch(`${API_BASE}/api/config`, {
            method: 'PUT',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                config_key: 'max_concurrent_positions',
                config_value: maxConcurrentPositions
            })
        });
        const concurrentResult = await concurrentResponse.json();

        if (result.code === 0) {
            // 同步更新顶部卡片的输入框
            document.getElementById('profitTargetQuickInput').value = profitTarget;
        }

        // 如果填写了长桥配置，则保存
        if (appKey && appSecret && accessToken) {
            const lbResponse = await fetch(`${API_BASE}/api/longbridge/config`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    app_key: appKey,
                    app_secret: appSecret,
                    access_token: accessToken,
                    http_url: 'https://openapi.longbridgeapp.com',
                    quote_ws_url: 'wss://openapi-quote.longbridgeapp.com',
                    trade_ws_url: 'wss://openapi-trade.longbridgeapp.com'
                })
            });
            const lbResult = await lbResponse.json();

            if (lbResult.code === 0) {
                showNotification('设置已保存，长桥SDK已' + (lbResult.data.use_real_sdk ? '启用真实模式' : '切换到模拟模式'), 'success');
                // 重新加载配置状态
                await loadSettings();
            } else {
                showNotification('长桥配置保存失败', 'error');
            }
        } else {
            showNotification('设置已保存', 'success');
        }
    } catch (error) {
        console.error('保存设置失败:', error);
        showNotification('保存失败', 'error');
    }
}

// 更新长桥SDK状态显示
function updateLongBridgeStatus(config) {
    const settingsTab = document.getElementById('settingsTab');
    const longbridgeConfigSection = document.getElementById('longbridgeConfigSection');

    // 查找或创建状态显示区域
    let statusDiv = settingsTab.querySelector('.longbridge-status');
    if (!statusDiv) {
        statusDiv = document.createElement('div');
        statusDiv.className = 'longbridge-status bg-gray-900 rounded-lg p-4 mb-4';

        // 插入到长桥配置区域之前
        if (longbridgeConfigSection) {
            longbridgeConfigSection.parentNode.insertBefore(statusDiv, longbridgeConfigSection);
        }
    }

    const statusIcon = config.use_real_sdk ?
        '<i class="fas fa-check-circle text-green-400"></i>' :
        '<i class="fas fa-exclamation-triangle text-yellow-400"></i>';

    const statusText = config.use_real_sdk ?
        '<span class="text-green-400 font-medium">真实模式</span>' :
        '<span class="text-yellow-400 font-medium">模拟模式</span>';

    const sdkAvailableText = config.sdk_available ?
        '<span class="text-green-400">已安装</span>' :
        '<span class="text-red-400">未安装</span>';

    statusDiv.innerHTML = `
        <div class="flex items-center justify-between mb-3">
            <h5 class="text-sm font-bold text-gray-400">长桥SDK状态</h5>
            ${statusIcon}
        </div>
        <div class="space-y-2 text-sm">
            <div class="flex justify-between">
                <span class="text-gray-400">SDK库:</span>
                ${sdkAvailableText}
            </div>
            <div class="flex justify-between">
                <span class="text-gray-400">运行模式:</span>
                ${statusText}
            </div>
            <div class="flex justify-between">
                <span class="text-gray-400">配置状态:</span>
                <span class="${config.is_configured ? 'text-green-400' : 'text-gray-400'}">${config.is_configured ? '已配置' : '未配置'}</span>
            </div>
        </div>
        ${!config.use_real_sdk ? `
        <div class="mt-3 p-3 bg-yellow-900 bg-opacity-30 border border-yellow-600 rounded-lg">
            <p class="text-xs text-yellow-200">
                <i class="fas fa-info-circle mr-1"></i>
                ${config.sdk_available ? '请配置长桥API凭证以启用真实交易' : '当前使用模拟数据运行(服务器Python版本不支持longbridge SDK)'}
            </p>
        </div>
        ` : `
        <div class="mt-3 p-3 bg-green-900 bg-opacity-30 border border-green-600 rounded-lg">
            <p class="text-xs text-green-200">
                <i class="fas fa-check-circle mr-1"></i>
                长桥SDK已连接，正在使用真实行情和交易功能
            </p>
        </div>
        `}
    `;
}

// 切换测试模式
async function toggleTestMode() {
    try {
        // 先获取当前状态
        const statusResponse = await fetch(`${API_BASE}/api/monitoring/status`, { credentials: 'include' });
        const statusResult = await statusResponse.json();
        const currentTestMode = statusResult.data?.test_mode || false;
        const newTestMode = !currentTestMode;
        
        // 更新配置
        const response = await fetch(`${API_BASE}/api/config`, {
            method: 'PUT',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                config_key: 'test_mode',
                config_value: String(newTestMode).toLowerCase()
            })
        });
        const result = await response.json();

        if (result.code === 0) {
            await updateMonitoringStatus();
            showNotification(`测试模式已${newTestMode ? '开启' : '关闭'}`, 'success');
        } else {
            showNotification(result.message || '操作失败', 'error');
        }
    } catch (error) {
        console.error('切换测试模式失败:', error);
        showNotification('操作失败', 'error');
    }
}

// 切换监控状态
async function toggleMonitoring() {
    try {
        const endpoint = isMonitoring ? '/api/monitoring/stop' : '/api/monitoring/start';

        let requestBody = null;
        if (!isMonitoring) {
            // 启动监控时，提示输入买入金额
            const currentConfig = await (await fetch(`${API_BASE}/api/config`, { credentials: 'include' })).json();
            const currentBuyAmount = currentConfig.data.values.buy_amount || '200000';

            const buyAmount = prompt(
                '请输入单笔买入金额（美元）：',
                currentBuyAmount
            );

            // 取消启动
            if (buyAmount === null) {
                return;
            }

            // 验证输入
            const amount = parseFloat(buyAmount);
            if (isNaN(amount) || amount < 1000) {
                showNotification('买入金额必须大于等于1000美元', 'error');
                return;
            }

            if (amount > 1000000) {
                showNotification('买入金额不能超过100万美元', 'error');
                return;
            }

            requestBody = { buy_amount: amount.toString() };
        }

        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: requestBody ? JSON.stringify(requestBody) : null
        });
        const result = await response.json();

        if (result.code === 0) {
            await updateMonitoringStatus();
            // 如果是启动操作，刷新配置显示
            if (!isMonitoring) {
                await loadConfig();
            }
            showNotification(result.message, 'success');
        } else {
            showNotification(result.message || '操作失败', 'error');
        }
    } catch (error) {
        console.error('切换监控状态失败:', error);
        showNotification('操作失败', 'error');
    }
}

// 更新监控状态
async function updateMonitoringStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/monitoring/status`, { credentials: 'include' });
        const result = await response.json();

        if (result.code === 0) {
            isMonitoring = result.data.is_monitoring;

            const indicator = document.getElementById('statusIndicator');
            const statusText = document.getElementById('statusText');
            const toggleBtn = document.getElementById('toggleMonitoring');

            if (isMonitoring) {
                indicator.className = 'w-3 h-3 rounded-full bg-green-500 animate-pulse';
                const modeText = result.data.sdk_mode ? ` (${result.data.sdk_mode})` : '';
                statusText.textContent = '监控中' + modeText;
                toggleBtn.innerHTML = '<i class="fas fa-stop mr-1 sm:mr-2"></i><span class="hidden sm:inline">停止监控</span><span class="sm:hidden">停止</span>';
                toggleBtn.className = 'px-3 py-1.5 sm:px-4 sm:py-2 bg-red-600 hover:bg-red-700 rounded-lg transition-colors duration-200 text-xs sm:text-sm font-medium';
            } else {
                indicator.className = 'w-3 h-3 rounded-full bg-gray-500';
                statusText.textContent = '未启动';
                toggleBtn.innerHTML = '<i class="fas fa-play mr-1 sm:mr-2"></i><span class="hidden sm:inline">启动监控</span><span class="sm:hidden">启动</span>';
                toggleBtn.className = 'px-3 py-1.5 sm:px-4 sm:py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors duration-200 text-xs sm:text-sm font-medium';
            }
            
            // 更新测试模式按钮状态
            const testModeBtn = document.getElementById('toggleTestMode');
            if (testModeBtn && result.data.test_mode !== undefined) {
                if (result.data.test_mode) {
                    testModeBtn.className = 'px-3 py-1.5 sm:px-4 sm:py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors duration-200 text-xs sm:text-sm font-medium';
                    testModeBtn.innerHTML = '<i class="fas fa-check mr-1 sm:mr-2"></i><span class="hidden sm:inline">测试模式: 开启</span><span class="sm:hidden">测试: 开</span>';
                } else {
                    testModeBtn.className = 'px-3 py-1.5 sm:px-4 sm:py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg transition-colors duration-200 text-xs sm:text-sm font-medium';
                    testModeBtn.innerHTML = '<i class="fas fa-flask mr-1 sm:mr-2"></i><span class="hidden sm:inline">测试模式: 关闭</span><span class="sm:hidden">测试: 关</span>';
                }
            }
            
            // 更新当前持仓（多并发模式，显示持仓数量）
            const positionSymbol = document.getElementById('currentPositionSymbol');
            if (result.data.current_position_count !== undefined) {
                positionSymbol.textContent = `${result.data.current_position_count}/${result.data.max_concurrent_positions || 1}`;
            } else {
                positionSymbol.textContent = '--';
            }
        }
    } catch (error) {
        console.error('更新监控状态失败:', error);
    }
}

// 加载统计数据
async function loadStatistics() {
    try {
        // 加载账户总览（包含总资产）
        const portfolioResponse = await fetch(`${API_BASE}/api/portfolio`, { credentials: 'include' });
        const portfolioResult = await portfolioResponse.json();
        if (portfolioResult.code === 0) {
            document.getElementById('totalAssetsCount').textContent = formatCurrency(portfolioResult.data.total_assets);
        }

        // 加载活跃股票数
        const stocksResponse = await fetch(`${API_BASE}/api/stocks`, { credentials: 'include' });
        const stocksResult = await stocksResponse.json();
        if (stocksResult.code === 0) {
            updateActiveStocksCount(stocksResult.data);
        }

        // 加载今日交易数
        const tradesResponse = await fetch(`${API_BASE}/api/trades?limit=100`, { credentials: 'include' });
        const tradesResult = await tradesResponse.json();
        if (tradesResult.code === 0) {
            const today = new Date().toISOString().split('T')[0];
            const todayTrades = tradesResult.data.filter(trade =>
                trade.trade_time && trade.trade_time.startsWith(today)
            );
            document.getElementById('todayTradesCount').textContent = todayTrades.length;
        }
    } catch (error) {
        console.error('加载统计数据失败:', error);
    }
}

// 更新活跃股票数
function updateActiveStocksCount(stocks) {
    const activeCount = stocks.filter(stock => stock.stock_type === 'STOCK').length;
    document.getElementById('activeStocksCount').textContent = activeCount;
}

// 工具函数
function formatCurrency(num, showSign = false, currency = 'USD') {
    const currencySymbols = {
        'USD': '$',
        'CNY': '¥',
        'HKD': 'HK$'
    };

    const symbol = currencySymbols[currency] || '$';
    const value = Number(num);

    if (!Number.isFinite(value)) {
        return '--';
    }

    if (showSign && value >= 0) {
        return '+' + symbol + value.toFixed(2);
    } else if (value < 0) {
        return '-' + symbol + Math.abs(value).toFixed(2);
    }
    return symbol + value.toFixed(2);
}

function formatNumber(num) {
    const value = Number(num);
    if (!Number.isFinite(value)) {
        return '--';
    }

    if (Math.abs(value) >= 1000000) {
        return (value / 1000000).toFixed(2) + 'M';
    } else if (Math.abs(value) >= 1000) {
        return (value / 1000).toFixed(2) + 'K';
    }
    return value.toString();
}

function formatDateTime(dateTimeStr) {
    if (!dateTimeStr) return '--';
    const date = new Date(dateTimeStr);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

function getRandomColor() {
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6'];
    return colors[Math.floor(Math.random() * colors.length)];
}

function showNotification(message, type = 'info') {
    // 简单的通知实现，移动端优化
    const notification = document.createElement('div');
    const isMobile = window.innerWidth <= 640;
    notification.className = `fixed ${isMobile ? 'bottom-4 left-4 right-4' : 'top-4 right-4'} px-6 py-3 rounded-lg shadow-lg text-white z-50 ${
        type === 'success' ? 'bg-green-600' : type === 'error' ? 'bg-red-600' : 'bg-blue-600'
    }`;
    notification.textContent = message;

    document.body.appendChild(notification);

    // 3秒后移除
    setTimeout(() => {
        notification.remove();
    }, 3000);
}


async function syncLongbridgeWatchlist() {
    const btn = document.getElementById('syncWatchlistBtn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>同步中...';

    try {
        const response = await fetch(`${API_BASE}/api/longbridge/sync-watchlist`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        const result = await response.json();

        if (result.code === 0) {
            const { total, added, skipped } = result.data;
            if (added > 0) {
                showNotification(`同步成功: 新增 ${added} 只, 跳过 ${skipped} 只`, 'success');
                await loadStocks();
                await loadMarketData();
                await loadStatistics();
            } else if (skipped > 0) {
                showNotification(`所有股票已存在（共 ${total} 只）`, 'info');
            } else {
                showNotification('没有同步任何股票', 'info');
            }
        } else {
            showNotification(result.message || '同步失败', 'error');
        }
    } catch (error) {
        console.error('同步自选股失败:', error);
        showNotification('同步失败: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// 同步长桥持仓
async function syncLongbridgePositions() {
    const btn = document.getElementById('syncPositionsBtn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>同步中...';

    try {
        const response = await fetch(`${API_BASE}/api/longbridge/sync-positions`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        const result = await response.json();

        if (result.code === 0) {
            const positions = result.data || [];
            showNotification(`同步成功，当前持仓 ${positions.length} 只`, 'success');
            await loadPortfolio();
            await loadStatistics();
        } else {
            showNotification(result.message || '同步失败', 'error');
        }
    } catch (error) {
        console.error('同步持仓失败:', error);
        showNotification('同步失败: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// 关闭详情弹窗
function closeDetailModal() {
    document.getElementById('detailModal').classList.add('hidden');
}

// 移动端优化：关闭弹窗时重置滚动位置
function closeAllModals() {
    const modals = ['addStockModal', 'detailModal'];
    modals.forEach(modalId => {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('hidden');
        }
    });
}

// 显示活跃股票详情
async function showActiveStocksDetail() {
    try {
        const response = await fetch(`${API_BASE}/api/stocks`, { credentials: 'include' });
        const result = await response.json();

        if (result.code === 0) {
            const activeStocks = result.data.filter(stock => stock.stock_type === 'STOCK');

            const content = `
                <div class="space-y-4">
                    <div class="bg-gradient-to-r from-blue-600 to-blue-800 rounded-lg p-4">
                        <h4 class="text-lg font-bold mb-2">股票总览</h4>
                        <p class="text-3xl font-bold">${activeStocks.length} 只</p>
                        <p class="text-sm text-blue-200 mt-2">当前系统中的正股数量</p>
                    </div>

                    <div class="space-y-3">
                        ${activeStocks.length > 0 ? activeStocks.map(stock => `
                            <div class="bg-gray-900 rounded-lg p-4 hover:bg-gray-700 transition-colors duration-200 cursor-pointer stock-detail-btn"
                                 onclick="closeDetailModal(); showStockDetail('${stock.symbol}')">
                                <div class="flex justify-between items-start">
                                    <div>
                                        <h5 class="text-lg font-bold text-blue-400">${stock.symbol}</h5>
                                        <p class="text-sm text-gray-400 mt-1">${stock.name}</p>
                                    </div>
                                    <span class="px-3 py-1 bg-blue-600 text-white rounded-full text-xs font-medium">
                                        正股
                                    </span>
                                </div>
                                <div class="mt-3 pt-3 border-t border-gray-700 flex justify-between items-center">
                                    <p class="text-xs text-gray-400">添加时间: ${formatDateTime(stock.created_at)}</p>
                                    <p class="text-xs text-blue-400">
                                        <i class="fas fa-chevron-right mr-1"></i>点击查看详情
                                    </p>
                                </div>
                            </div>
                        `).join('') : '<p class="text-center text-gray-400 py-8">暂无股票</p>'}
                    </div>
                </div>
            `;

            document.getElementById('detailModalTitle').innerHTML = '<i class="fas fa-chart-bar mr-2 text-blue-400"></i>股票详情';
            document.getElementById('detailModalContent').innerHTML = content;
            document.getElementById('detailModal').classList.remove('hidden');
        }
    } catch (error) {
        console.error('加载股票详情失败:', error);
        showNotification('加载详情失败', 'error');
    }
}

// 显示今日交易详情
async function showTodayTradesDetail() {
    try {
        const response = await fetch(`${API_BASE}/api/trades?limit=100`, { credentials: 'include' });
        const result = await response.json();
        
        if (result.code === 0) {
            const today = new Date().toISOString().split('T')[0];
            const todayTrades = result.data.filter(trade => 
                trade.trade_time && trade.trade_time.startsWith(today)
            );
            
            // 统计数据
            const buyTrades = todayTrades.filter(t => t.action === 'BUY');
            const sellTrades = todayTrades.filter(t => t.action === 'SELL');
            const successTrades = todayTrades.filter(t => t.status === 'SUCCESS');
            const totalAmount = todayTrades.reduce((sum, t) => sum + t.amount, 0);
            
            const content = `
                <div class="space-y-4">
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div class="bg-gradient-to-br from-green-600 to-green-800 rounded-lg p-3">
                            <p class="text-xs text-green-200 mb-1">总交易</p>
                            <p class="text-2xl font-bold">${todayTrades.length}</p>
                        </div>
                        <div class="bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg p-3">
                            <p class="text-xs text-blue-200 mb-1">买入</p>
                            <p class="text-2xl font-bold">${buyTrades.length}</p>
                        </div>
                        <div class="bg-gradient-to-br from-orange-600 to-orange-800 rounded-lg p-3">
                            <p class="text-xs text-orange-200 mb-1">卖出</p>
                            <p class="text-2xl font-bold">${sellTrades.length}</p>
                        </div>
                        <div class="bg-gradient-to-br from-purple-600 to-purple-800 rounded-lg p-3">
                            <p class="text-xs text-purple-200 mb-1">成功率</p>
                            <p class="text-2xl font-bold">${todayTrades && todayTrades.length > 0 ? ((successTrades.length / todayTrades.length) * 100).toFixed(0) : 0}%</p>
                        </div>
                    </div>
                    
                    <div class="bg-gray-900 rounded-lg p-4">
                        <h5 class="text-sm font-bold text-gray-400 mb-2">交易总额</h5>
                        <p class="text-3xl font-bold text-green-400">$${totalAmount ? totalAmount.toFixed(2) : '0.00'}</p>
                    </div>
                    
                    <div class="space-y-2">
                        <h5 class="text-sm font-bold text-gray-400">交易明细</h5>
                        <div class="max-h-96 overflow-y-auto space-y-2">
                            ${todayTrades.length > 0 ? todayTrades.map(trade => {
                                const actionClass = trade.action === 'BUY' ? 'text-green-400' : 'text-red-400';
                                const actionBg = trade.action === 'BUY' ? 'bg-green-600' : 'bg-red-600';
                                const statusClass = trade.status === 'SUCCESS' ? 'bg-green-600' : trade.status === 'FAILED' ? 'bg-red-600' : 'bg-yellow-600';
                                
                                return `
                                    <div class="bg-gray-900 rounded-lg p-3 hover:bg-gray-700 transition-colors duration-200">
                                        <div class="flex justify-between items-start mb-2">
                                            <div>
                                                <h6 class="font-bold text-white">${trade.symbol}</h6>
                                                <p class="text-xs text-gray-400">${formatDateTime(trade.trade_time)}</p>
                                            </div>
                                            <div class="flex space-x-2">
                                                <span class="px-2 py-1 ${actionBg} rounded text-xs font-medium">
                                                    ${trade.action === 'BUY' ? '买入' : '卖出'}
                                                </span>
                                                <span class="px-2 py-1 ${statusClass} rounded text-xs font-medium">
                                                    ${trade.status}
                                                </span>
                                            </div>
                                        </div>
                                        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                                            <div>
                                                <span class="text-gray-400">价格:</span>
                                                <span class="text-white font-medium ml-1">$${trade && trade.price ? trade.price.toFixed(2) : '--'}</span>
                                            </div>
                                            <div>
                                                <span class="text-gray-400">数量:</span>
                                                <span class="text-white font-medium ml-1">${trade && trade.quantity ? trade.quantity : '--'}</span>
                                            </div>
                                            <div>
                                                <span class="text-gray-400">金额:</span>
                                                <span class="text-white font-medium ml-1">$${trade && trade.amount ? trade.amount.toFixed(2) : '--'}</span>
                                            </div>
                                            <div>
                                                <span class="text-gray-400">加速度:</span>
                                                <span class="${actionClass} font-medium ml-1">${trade && trade.acceleration ? trade.acceleration.toFixed(4) : '--'}</span>
                                            </div>
                                        </div>
                                    </div>
                                `;
                            }).join('') : '<p class="text-center text-gray-400 py-8">今日暂无交易记录</p>'}
                        </div>
                    </div>
                </div>
            `;
            
            document.getElementById('detailModalTitle').innerHTML = '<i class="fas fa-exchange-alt mr-2 text-green-400"></i>今日交易详情';
            document.getElementById('detailModalContent').innerHTML = content;
            document.getElementById('detailModal').classList.remove('hidden');
        }
    } catch (error) {
        console.error('加载今日交易详情失败:', error);
        showNotification('加载详情失败', 'error');
    }
}

// 将市场数据（分组或数组）扁平化
function flattenMarketData(data) {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (typeof data === 'object') {
        let flat = [];
        try {
            Object.values(data).forEach(group => {
                if (Array.isArray(group)) {
                    flat = flat.concat(group);
                } else if (group && group.stocks && Array.isArray(group.stocks)) {
                    flat = flat.concat(group.stocks);
                }
            });
        } catch (e) {
            console.error('flattenMarketData error:', e);
        }
        return flat;
    }
    return [];
}

// 显示当前持仓详情
async function showCurrentPositionDetail() {
    try {
        const [statusResponse, positionsResponse, marketResponse] = await Promise.all([
            fetch(`${API_BASE}/api/monitoring/status`),
            fetch(`${API_BASE}/api/positions`),
            fetch(`${API_BASE}/api/market-data`)
        ]);
        
        const statusResult = await statusResponse.json();
        const positionsResult = await positionsResponse.json();
        const marketResult = await marketResponse.json();
        
        if (statusResult.code === 0 && positionsResult.code === 0) {
            const currentPosition = statusResult.data.current_position;
            const positions = positionsResult.data;
            const currentPositionData = positions.find(p => p.symbol === currentPosition && p.status === 'HOLDING');
            
            let content = '';
            
            if (currentPositionData) {
                // 获取当前市场价格
                const marketFlat = flattenMarketData(marketResult.code === 0 ? marketResult.data : []);
                const marketData = marketFlat.find(m => m.symbol === currentPosition);
                const currentPrice = marketData ? marketData.price : currentPositionData.current_price;
                const profitLoss = currentPrice ? (currentPrice - currentPositionData.buy_price) * currentPositionData.quantity : 0;
                const profitLossPct = currentPrice ? ((currentPrice - currentPositionData.buy_price) / currentPositionData.buy_price * 100) : 0;
                const isProfitable = profitLoss >= 0;
                
                content = `
                    <div class="space-y-4">
                        <div class="bg-gradient-to-r from-purple-600 to-purple-800 rounded-lg p-4">
                            <h4 class="text-lg font-bold mb-2">当前持仓</h4>
                            <p class="text-4xl font-bold">${currentPosition}</p>
                            <p class="text-sm text-purple-200 mt-2">正在持有中</p>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-3">
                            <div class="bg-gray-900 rounded-lg p-3">
                                <p class="text-xs text-gray-400 mb-1">买入价格</p>
                                <p class="text-xl font-bold text-blue-400">$${currentPositionData && currentPositionData.buy_price ? currentPositionData.buy_price.toFixed(2) : '--'}</p>
                            </div>
                            <div class="bg-gray-900 rounded-lg p-3">
                                <p class="text-xs text-gray-400 mb-1">当前价格</p>
                                <p class="text-xl font-bold text-white">$${currentPrice ? currentPrice.toFixed(2) : '--'}</p>
                            </div>
                            <div class="bg-gray-900 rounded-lg p-3">
                                <p class="text-xs text-gray-400 mb-1">持仓数量</p>
                                <p class="text-xl font-bold text-white">${currentPositionData && currentPositionData.quantity ? currentPositionData.quantity : '--'}</p>
                            </div>
                            <div class="bg-gray-900 rounded-lg p-3">
                                <p class="text-xs text-gray-400 mb-1">持仓成本</p>
                                <p class="text-xl font-bold text-white">$${currentPositionData && currentPositionData.cost ? currentPositionData.cost.toFixed(2) : '--'}</p>
                            </div>
                        </div>
                        
                        <div class="bg-gray-900 rounded-lg p-4">
                            <div class="flex justify-between items-center mb-2">
                                <h5 class="text-sm font-bold text-gray-400">盈亏情况</h5>
                                <span class="px-3 py-1 ${isProfitable ? 'bg-green-600' : 'bg-red-600'} rounded-full text-xs font-medium">
                                    ${isProfitable ? '盈利' : '亏损'}
                                </span>
                            </div>
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <p class="text-xs text-gray-400 mb-1">盈亏金额</p>
                                    <p class="text-2xl font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}">
                                        ${isProfitable ? '+' : ''}$${profitLoss ? profitLoss.toFixed(2) : '0.00'}
                                    </p>
                                </div>
                                <div>
                                    <p class="text-xs text-gray-400 mb-1">盈亏比例</p>
                                    <p class="text-2xl font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}">
                                        ${isProfitable ? '+' : ''}${profitLossPct ? profitLossPct.toFixed(2) : '0.00'}%
                                    </p>
                                </div>
                            </div>
                        </div>
                        
                        <div class="bg-gray-900 rounded-lg p-4">
                            <h5 class="text-sm font-bold text-gray-400 mb-3">持仓信息</h5>
                            <div class="space-y-2 text-sm">
                                <div class="flex justify-between">
                                    <span class="text-gray-400">买入时间:</span>
                                    <span class="text-white">${formatDateTime(currentPositionData.buy_time)}</span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-gray-400">买入加速度:</span>
                                    <span class="text-green-400">${currentPositionData.buy_acceleration ? currentPositionData.buy_acceleration.toFixed(4) : '--'}</span>
                                </div>
                                ${marketData ? `
                                <div class="flex justify-between">
                                    <span class="text-gray-400">当前涨跌幅:</span>
                                    <span class="${marketData && marketData.change_pct >= 0 ? 'text-green-400' : 'text-red-400'}">
                                        ${marketData && marketData.change_pct >= 0 ? '+' : ''}${marketData && marketData.change_pct ? marketData.change_pct.toFixed(2) : '--'}%
                                    </span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-gray-400">当前加速度:</span>
                                    <span class="${marketData && marketData.acceleration >= 0 ? 'text-green-400' : 'text-red-400'}">
                                        ${marketData && marketData.acceleration >= 0 ? '+' : ''}${marketData && marketData.acceleration ? marketData.acceleration.toFixed(4) : '--'}
                                    </span>
                                </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `;
            } else {
                // 显示历史持仓
                const historicalPositions = positions.filter(p => p.status === 'CLOSED').slice(0, 10);
                
                content = `
                    <div class="space-y-4">
                        <div class="bg-gradient-to-r from-gray-600 to-gray-800 rounded-lg p-4 text-center">
                            <i class="fas fa-inbox text-4xl text-gray-400 mb-2"></i>
                            <h4 class="text-lg font-bold mb-2">暂无持仓</h4>
                            <p class="text-sm text-gray-300">当前没有持有任何股票</p>
                        </div>
                        
                        ${historicalPositions.length > 0 ? `
                        <div class="space-y-2">
                            <h5 class="text-sm font-bold text-gray-400">历史持仓记录</h5>
                            <div class="space-y-2 max-h-96 overflow-y-auto">
                                ${historicalPositions.map(pos => {
                                    const profitLoss = pos.sell_price ? (pos.sell_price - pos.buy_price) * pos.quantity : 0;
                                    const profitLossPct = pos.sell_price ? ((pos.sell_price - pos.buy_price) / pos.buy_price * 100) : 0;
                                    const isProfitable = profitLoss >= 0;
                                    
                                    return `
                                        <div class="bg-gray-900 rounded-lg p-3 hover:bg-gray-700 transition-colors duration-200">
                                            <div class="flex justify-between items-start mb-2">
                                                <div>
                                                    <h6 class="font-bold text-white">${pos.symbol}</h6>
                                                    <p class="text-xs text-gray-400">${formatDateTime(pos.buy_time)}</p>
                                                </div>
                                                <span class="px-2 py-1 ${isProfitable ? 'bg-green-600' : 'bg-red-600'} rounded text-xs font-medium">
                                                    ${isProfitable ? '+' : ''}${profitLossPct ? profitLossPct.toFixed(2) : '0.00'}%
                                                </span>
                                            </div>
                                            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                                                <div>
                                                    <span class="text-gray-400">买入:</span>
                                                    <span class="text-white font-medium ml-1">$${pos && pos.buy_price ? pos.buy_price.toFixed(2) : '--'}</span>
                                                </div>
                                                <div>
                                                    <span class="text-gray-400">卖出:</span>
                                                    <span class="text-white font-medium ml-1">$${pos && pos.sell_price ? pos.sell_price.toFixed(2) : '--'}</span>
                                                </div>
                                                <div>
                                                    <span class="text-gray-400">数量:</span>
                                                    <span class="text-white font-medium ml-1">${pos && pos.quantity ? pos.quantity : '--'}</span>
                                                </div>
                                                <div>
                                                    <span class="text-gray-400">盈亏:</span>
                                                    <span class="${isProfitable ? 'text-green-400' : 'text-red-400'} font-medium ml-1">
                                                        ${isProfitable ? '+' : ''}$${profitLoss ? profitLoss.toFixed(2) : '0.00'}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    `;
                                }).join('')}
                            </div>
                        </div>
                        ` : ''}
                    </div>
                `;
            }
            
            document.getElementById('detailModalTitle').innerHTML = '<i class="fas fa-briefcase mr-2 text-purple-400"></i>持仓详情';
            document.getElementById('detailModalContent').innerHTML = content;
            document.getElementById('detailModal').classList.remove('hidden');
        }
    } catch (error) {
        console.error('加载持仓详情失败:', error);
        showNotification('加载详情失败', 'error');
    }
}

// 显示股票详情
async function showStockDetail(symbol) {
    try {
        document.getElementById('detailModalTitle').innerHTML = '<i class="fas fa-chart-line mr-2 text-blue-400"></i>股票详情 - ' + symbol;
        document.getElementById('detailModalContent').innerHTML = '<div class="text-center py-8"><i class="fas fa-spinner fa-spin text-4xl text-blue-400"></i><p class="mt-4 text-gray-400">加载中...</p></div>';
        document.getElementById('detailModal').classList.remove('hidden');

        // 获取股票信息和行情数据
        const [stocksResponse, marketResponse, positionsResponse, tradesResponse] = await Promise.all([
            fetch(`${API_BASE}/api/stocks`),
            fetch(`${API_BASE}/api/market-data`),
            fetch(`${API_BASE}/api/positions`),
            fetch(`${API_BASE}/api/trades?limit=50`)
        ]);

        const stocksResult = await stocksResponse.json();
        const marketResult = await marketResponse.json();
        const positionsResult = await positionsResponse.json();
        const tradesResult = await tradesResponse.json();

        // 查找股票信息
        const stock = stocksResult.code === 0 ? stocksResult.data.find(s => s.symbol === symbol) : null;
        const marketFlat = flattenMarketData(marketResult.code === 0 ? marketResult.data : []);
        const marketData = marketFlat.find(m => m.symbol === symbol);
        const position = positionsResult.code === 0 ? positionsResult.data.find(p => p.symbol === symbol) : null;
        const stockTrades = tradesResult.code === 0 ? tradesResult.data.filter(t => t.symbol === symbol) : [];

        if (!stock) {
            document.getElementById('detailModalContent').innerHTML = `
                <div class="text-center py-12">
                    <i class="fas fa-exclamation-circle text-6xl text-red-400 mb-4"></i>
                    <h3 class="text-xl font-bold text-red-400 mb-2">股票未找到</h3>
                    <p class="text-gray-400">无法找到股票 ${symbol} 的信息</p>
                </div>
            `;
            return;
        }

        const isProfitable = marketData && marketData.change_pct >= 0;

        const content = `
            <div class="space-y-6">
                <!-- 股票头部信息 -->
                <div class="bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl p-6">
                    <div class="flex justify-between items-start">
                        <div>
                            <h2 class="text-3xl sm:text-4xl font-bold mb-2">${stock.symbol}</h2>
                            <p class="text-blue-200 text-lg">${stock.name}</p>
                        </div>
                        <span class="px-4 py-2 bg-blue-600 rounded-full text-sm font-medium">
                            <i class="fas fa-chart-line mr-1"></i>正股
                        </span>
                    </div>
                </div>

                ${marketData ? `
                <!-- 实时行情卡片 -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div class="bg-gray-900 rounded-lg p-4 hover:bg-gray-800 transition-colors duration-200">
                        <div class="flex items-center justify-between mb-2">
                            <p class="text-gray-400 text-xs">当前价格</p>
                            <i class="fas fa-dollar-sign ${isProfitable ? 'text-green-400' : 'text-red-400'}"></i>
                        </div>
                        <p class="text-2xl sm:text-3xl font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}">
                            $${marketData && marketData.price ? marketData.price.toFixed(2) : '--'}
                        </p>
                        <p class="text-xs mt-2 ${isProfitable ? 'text-green-400' : 'text-red-400'}">
                            ${isProfitable ? '+' : ''}${marketData && marketData.change_pct ? marketData.change_pct.toFixed(2) : '--'}%
                        </p>
                    </div>

                    <div class="bg-gray-900 rounded-lg p-4 hover:bg-gray-800 transition-colors duration-200">
                        <div class="flex items-center justify-between mb-2">
                            <p class="text-gray-400 text-xs">成交量</p>
                            <i class="fas fa-chart-bar text-blue-400"></i>
                        </div>
                        <p class="text-2xl sm:text-3xl font-bold text-white">
                            ${marketData && marketData.volume ? formatNumber(marketData.volume) : '--'}
                        </p>
                        <p class="text-xs mt-2 text-gray-400">实时</p>
                    </div>

                    <div class="bg-gray-900 rounded-lg p-4 hover:bg-gray-800 transition-colors duration-200">
                        <div class="flex items-center justify-between mb-2">
                            <p class="text-gray-400 text-xs">涨幅加速度</p>
                            <i class="fas fa-rocket ${marketData && marketData.acceleration >= 0 ? 'text-green-400' : 'text-red-400'}"></i>
                        </div>
                        <p class="text-2xl sm:text-3xl font-bold ${marketData && marketData.acceleration >= 0 ? 'text-green-400' : 'text-red-400'}">
                            ${marketData && marketData.acceleration >= 0 ? '+' : ''}${marketData && marketData.acceleration ? marketData.acceleration.toFixed(4) : '--'}
                        </p>
                        <p class="text-xs mt-2 ${marketData && marketData.acceleration >= 0 ? 'text-green-400' : 'text-red-400'}">
                            ${marketData && marketData.acceleration >= 0 ? '加速上涨' : '加速下跌'}
                        </p>
                    </div>

                    <div class="bg-gray-900 rounded-lg p-4 hover:bg-gray-800 transition-colors duration-200">
                        <div class="flex items-center justify-between mb-2">
                            <p class="text-gray-400 text-xs">更新时间</p>
                            <i class="fas fa-clock text-purple-400"></i>
                        </div>
                        <p class="text-lg font-bold text-white">
                            ${new Date(marketData.timestamp).toLocaleTimeString('zh-CN')}
                        </p>
                        <p class="text-xs mt-2 text-gray-400">实时数据</p>
                    </div>
                </div>
                ` : `
                <!-- 无行情数据 -->
                <div class="bg-gray-900 rounded-lg p-8 text-center">
                    <i class="fas fa-chart-line-slash text-5xl text-gray-600 mb-4"></i>
                    <p class="text-gray-400">暂无实时行情数据</p>
                    <p class="text-sm text-gray-500 mt-2">该股票可能处于非交易时间或未启用监控</p>
                </div>
                `}

                ${position ? `
                <!-- 持仓信息 -->
                <div class="bg-gray-900 rounded-lg p-6">
                    <h3 class="text-lg font-bold mb-4 flex items-center">
                        <i class="fas fa-briefcase mr-2 text-purple-400"></i>持仓信息
                    </h3>
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        <div>
                            <p class="text-gray-400 text-xs mb-1">持仓数量</p>
                            <p class="text-xl font-bold text-white">${position && position.quantity ? position.quantity : '--'}</p>
                        </div>
                        <div>
                            <p class="text-gray-400 text-xs mb-1">买入价格</p>
                            <p class="text-xl font-bold text-blue-400">$${position && position.buy_price ? position.buy_price.toFixed(2) : '--'}</p>
                        </div>
                        <div>
                            <p class="text-gray-400 text-xs mb-1">持仓成本</p>
                            <p class="text-xl font-bold text-white">$${position && position.cost ? position.cost.toFixed(2) : '--'}</p>
                        </div>
                        <div>
                            <p class="text-gray-400 text-xs mb-1">买入时间</p>
                            <p class="text-sm text-white">${formatDateTime(position.buy_time)}</p>
                        </div>
                    </div>
                    ${marketData ? `
                    <div class="mt-4 pt-4 border-t border-gray-700">
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-gray-400 text-xs mb-1">当前市值</p>
                                <p class="text-2xl font-bold text-white">$${marketData && marketData.price && position.quantity ? (marketData.price * position.quantity).toFixed(2) : '--'}</p>
                            </div>
                            <div>
                                <p class="text-gray-400 text-xs mb-1">持仓盈亏</p>
                                <p class="text-2xl font-bold ${position && position.profit_loss >= 0 ? 'text-green-400' : 'text-red-400'}">
                                    ${position && position.profit_loss >= 0 ? '+' : ''}$${position && position.profit_loss ? position.profit_loss.toFixed(2) : '--'}
                                </p>
                                <p class="text-sm ${position && position.profit_loss >= 0 ? 'text-green-400' : 'text-red-400'}">
                                    (${position && position.profit_loss_pct >= 0 ? '+' : ''}${position && position.profit_loss_pct ? position.profit_loss_pct.toFixed(2) : '--'}%)
                                </p>
                            </div>
                        </div>
                    </div>
                    ` : ''}
                </div>
                ` : ''}

                <!-- 交易历史 -->
                <div class="bg-gray-900 rounded-lg p-6">
                    <h3 class="text-lg font-bold mb-4 flex items-center">
                        <i class="fas fa-history mr-2 text-green-400"></i>交易历史
                    </h3>
                    ${stockTrades.length > 0 ? `
                    <div class="space-y-3 max-h-96 overflow-y-auto">
                        ${stockTrades.map(trade => {
                            const actionClass = trade.action === 'BUY' ? 'text-green-400' : 'text-red-400';
                            const actionBg = trade.action === 'BUY' ? 'bg-green-600' : 'bg-red-600';
                            const statusClass = trade.status === 'SUCCESS' ? 'bg-green-600' : trade.status === 'FAILED' ? 'bg-red-600' : 'bg-yellow-600';

                            return `
                                <div class="bg-gray-800 rounded-lg p-4 hover:bg-gray-700 transition-colors duration-200">
                                    <div class="flex justify-between items-start mb-3">
                                        <div>
                                            <div class="flex items-center space-x-2 mb-1">
                                                <span class="px-3 py-1 ${actionBg} rounded text-xs font-bold">
                                                    ${trade.action === 'BUY' ? '买入' : '卖出'}
                                                </span>
                                                <span class="px-3 py-1 ${statusClass} rounded text-xs font-medium">
                                                    ${trade.status}
                                                </span>
                                            </div>
                                            <p class="text-xs text-gray-400">${formatDateTime(trade.trade_time)}</p>
                                        </div>
                                        <p class="text-xl font-bold ${actionClass}">$${trade && trade.amount ? trade.amount.toFixed(2) : '--'}</p>
                                    </div>
                                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                                        <div>
                                            <span class="text-gray-400">价格:</span>
                                            <span class="text-white font-medium ml-1">$${trade && trade.price ? trade.price.toFixed(2) : '--'}</span>
                                        </div>
                                        <div>
                                            <span class="text-gray-400">数量:</span>
                                            <span class="text-white font-medium ml-1">${trade.quantity}</span>
                                        </div>
                                        <div>
                                            <span class="text-gray-400">金额:</span>
                                            <span class="text-white font-medium ml-1">$${trade.amount.toFixed(2)}</span>
                                        </div>
                                        <div>
                                            <span class="text-gray-400">加速度:</span>
                                            <span class="${actionClass} font-medium ml-1">
                                                ${trade.acceleration ? trade.acceleration.toFixed(4) : '--'}
                                            </span>
                                        </div>
                                    </div>
                                    ${trade.message ? `
                                    <div class="mt-3 pt-3 border-t border-gray-700">
                                        <p class="text-xs text-gray-400"><i class="fas fa-info-circle mr-1"></i>${trade.message}</p>
                                    </div>
                                    ` : ''}
                                </div>
                            `;
                        }).join('')}
                    </div>
                    ` : `
                    <div class="text-center py-8">
                        <i class="fas fa-history text-4xl text-gray-600 mb-3"></i>
                        <p class="text-gray-400">暂无交易记录</p>
                    </div>
                    `}
                </div>

                <!-- 股票信息 -->
                <div class="bg-gray-900 rounded-lg p-6">
                    <h3 class="text-lg font-bold mb-4 flex items-center">
                        <i class="fas fa-info-circle mr-2 text-blue-400"></i>股票信息
                    </h3>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                        <div class="flex justify-between">
                            <span class="text-gray-400">股票代码:</span>
                            <span class="text-white font-medium">${stock.symbol}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">公司名称:</span>
                            <span class="text-white font-medium">${stock.name}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">股票类型:</span>
                            <span class="text-white font-medium">${stock.stock_type === 'STOCK' ? '正股' : '期权'}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">添加时间:</span>
                            <span class="text-white">${formatDateTime(stock.created_at)}</span>
                        </div>
                        <div class="flex justify-between sm:col-span-2">
                            <span class="text-gray-400">交易次数:</span>
                            <span class="text-white font-medium">${stockTrades.length} 次</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.getElementById('detailModalContent').innerHTML = content;

    } catch (error) {
        console.error('加载股票详情失败:', error);
        document.getElementById('detailModalContent').innerHTML = `
            <div class="text-center py-12">
                <i class="fas fa-exclamation-circle text-6xl text-red-400 mb-4"></i>
                <h3 class="text-xl font-bold text-red-400 mb-2">加载失败</h3>
                <p class="text-gray-400">无法加载股票 ${symbol} 的详情</p>
                <p class="text-sm text-gray-500 mt-2">${error.message}</p>
            </div>
        `;
    }
}

// 加载历史订单
async function loadOrders() {
    try {
        const symbolFilter = document.getElementById('orderSymbolFilter').value.trim();
        const daysFilter = document.getElementById('orderDaysFilter').value;
        let url = `${API_BASE}/api/orders?days=${daysFilter}`;

        if (symbolFilter) {
            url += `&symbol=${symbolFilter}`;
        }

        const response = await fetch(url);
        const result = await response.json();

        if (result.code === 0) {
            // 调试：打印第一条订单数据
            if (result.data && result.data.length > 0) {
                console.log('第一条订单数据:', result.data[0]);
                console.log('status字段值:', result.data[0].status, '类型:', typeof result.data[0].status);
                console.log('side字段值:', result.data[0].side, '类型:', typeof result.data[0].side);
            }
            renderOrders(result.data);
            // 更新订单数量显示
            const ordersCount = document.getElementById('ordersCount');
            const ordersTotalCount = document.getElementById('ordersTotalCount');
            if (result.data && result.data.length > 0) {
                ordersCount.classList.remove('hidden');
                ordersTotalCount.textContent = result.data.length;
            } else {
                ordersCount.classList.add('hidden');
            }
            showNotification(result.message || `成功获取 ${result.data.length} 条订单记录`, 'success');
        } else {
            showNotification(result.message || '加载订单失败', 'error');
        }
    } catch (error) {
        console.error('加载历史订单失败:', error);
        showNotification('加载订单失败: ' + error.message, 'error');
    }
}

// 渲染历史订单
function renderOrders(orders) {
    const tbody = document.getElementById('ordersTableBody');
    const noOrders = document.getElementById('noOrders');

    tbody.innerHTML = '';

    if (!orders || orders.length === 0) {
        noOrders.classList.remove('hidden');
        return;
    }

    noOrders.classList.add('hidden');

    orders.forEach((order, index) => {
        const tr = document.createElement('tr');
        tr.className = 'border-b border-gray-700 hover:bg-gray-700 transition-colors duration-200';

        // 解析订单方向（后端已转换为字符串）
        // 安全处理：可能是字符串、对象或其他类型
        let sideName = 'Unknown';
        if (typeof order.side === 'string' && order.side) {
            sideName = order.side.trim();
        } else if (order.side && typeof order.side === 'object' && order.side.name) {
            sideName = order.side.name;
        } else {
            console.warn(`订单 ${index} 的 side 字段异常:`, order.side);
        }

        const isBuy = sideName === 'Buy';
        const sideClass = isBuy ? 'text-green-400' : 'text-red-400';
        const sideText = isBuy ? '买入' : (sideName === 'Sell' ? '卖出' : sideName || '未知');

        // 解析订单状态（后端已转换为字符串）
        // 安全处理：可能是字符串、对象或其他类型
        let statusName = 'Unknown';
        if (typeof order.status === 'string' && order.status) {
            statusName = order.status.trim();
        } else if (order.status && typeof order.status === 'object' && order.status.name) {
            statusName = order.status.name;
        } else {
            console.warn(`订单 ${index} 的 status 字段异常:`, order.status);
        }

        let statusClass = 'bg-gray-600';
        switch(statusName) {
            case 'Filled':
                statusClass = 'bg-green-600';
                break;
            case 'New':
            case 'WaitToNew':
                statusClass = 'bg-blue-600';
                break;
            case 'PartialFilled':
                statusClass = 'bg-yellow-600';
                break;
            case 'Canceled':
            case 'WaitToCancel':
                statusClass = 'bg-red-600';
                break;
            case 'Rejected':
                statusClass = 'bg-red-800';
                break;
            default:
                statusClass = 'bg-gray-600';
        }

        tr.innerHTML = `
            <td class="py-3 px-2 sm:px-4 text-xs sm:text-sm font-mono text-gray-300">${order.order_id || '--'}</td>
            <td class="py-3 px-2 sm:px-4 font-medium text-sm">${order.symbol || '--'}</td>
            <td class="py-3 px-2 sm:px-4 text-sm ${sideClass}">${sideText}</td>
            <td class="py-3 px-2 sm:px-4 text-right text-sm">${order.submitted_price && order.submitted_price > 0 ? '$' + order.submitted_price.toFixed(2) : '--'}</td>
            <td class="py-3 px-2 sm:px-4 text-right text-sm">${order.executed_price && order.executed_price > 0 ? '$' + order.executed_price.toFixed(2) : '--'}</td>
            <td class="py-3 px-2 sm:px-4 text-right text-sm">${order.submitted_quantity || 0}</td>
            <td class="py-3 px-2 sm:px-4 text-right text-sm">${order.executed_quantity || 0}</td>
            <td class="py-3 px-2 sm:px-4 text-sm">
                <span class="px-2 py-1 ${statusClass} rounded text-xs font-medium">
                    ${statusName}
                </span>
            </td>
            <td class="py-3 px-2 sm:px-4 text-xs text-gray-400 whitespace-nowrap">
                ${order.updated_at ? formatDateTime(order.updated_at) : '--'}
            </td>
        `;
        tbody.appendChild(tr);
    });
}


