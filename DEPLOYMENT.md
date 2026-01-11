# 腾讯云轻量应用服务器部署说明

## 服务器信息

- **地域**: ap-singapore (新加坡)
- **实例ID**: lhins-9nowtk7j
- **公网IP**: 43.152.67.232
- **系统**: CentOS 7
- **项目路径**: `/root/longbridge-quant-system_20260111114910`
- **访问地址**: http://43.152.67.232:8000

## 部署状态

### ✅ 已完成

1. [x] 项目文件上传到服务器
2. [x] Rust工具链安装 (v1.92.0)
3. [x] MariaDB数据库安装
4. [x] Python依赖安装 (已安装FastAPI、pymysql等)
5. [x] 数据库初始化 (创建quant_system数据库和表结构)
6. [x] 服务启动 (运行在0.0.0.0:8000)
7. [x] 配置防火墙规则 (开放8000端口)

### ⏸ 待处理

8. [ ] 配置长桥SDK凭证 (环境变量或前端配置)

## 数据库配置

- MySQL数据库: quant_system
- 用户名: root
- 密码: root123
- 端口: 3306

## 环境变量

当前系统使用模拟模式运行，无需长桥SDK凭证。

如需切换到真实交易模式，请在系统设置中配置：
- LONGBRIDGE_APP_KEY
- LONGBRIDGE_APP_SECRET
- LONGBRIDGE_ACCESS_TOKEN

## 服务管理

### 查看服务状态
```bash
# 检查进程
ps aux | grep uvicorn

# 查看日志
tail -f /tmp/quant_system.log

# 检查端口
ss -tulpn | grep 8000
```

### 重启服务
```bash
cd /root/longbridge-quant-system_20260111114910
pkill -f 'python.*uvicorn'
MYSQL_PASSWORD=root123 nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/quant_system.log 2>&1 &
echo $! > /tmp/quant_system.pid
```

### 停止服务
```bash
pkill -f 'python.*uvicorn'
```

### 1. 检查Python依赖安装状态

```bash
cd /root/longbridge-quant-system_20260111010307
source $HOME/.cargo/env
python3 -m pip list | grep longbridge
```

### 2. 如果依赖未安装完成,手动安装

```bash
cd /root/longbridge-quant-system_20260111010307
source $HOME/.cargo/env
python3 -m pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
cd /root/longbridge-quant-system_20260111010307
systemctl start mariadb
mysql -u root -e "CREATE DATABASE IF NOT EXISTS quant_system;"
python3 scripts/init_db.py
```

### 4. 配置环境变量

创建 `.env` 文件或设置环境变量:

```bash
# MySQL数据库配置
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
export MYSQL_DB=quant_system

# 长桥SDK配置(真实交易需要)
export LONGBRIDGE_APP_KEY=your_app_key
export LONGBRIDGE_APP_SECRET=your_app_secret
export LONGBRIDGE_ACCESS_TOKEN=your_access_token
```

### 5. 启动服务

```bash
cd /root/longbridge-quant-system_20260111010307
source $HOME/.cargo/env
nohup python3 main.py > /tmp/quant_system.log 2>&1 &
```

### 6. 检查服务状态

```bash
# 查看进程
ps aux | grep main.py

# 查看日志
tail -f /tmp/quant_system.log

# 测试API
curl http://localhost:8000/api/monitoring/status
```

### 7. 配置防火墙

```bash
# 如果需要从外网访问,开放8000端口
firewall-cmd --zone=public --add-port=8000/tcp --permanent
firewall-cmd --reload
```

## 访问地址

服务启动成功后,可通过以下地址访问:

- **本地**: http://localhost:8000
- **公网**: http://43.152.67.232:8000

## 监控和日志

### 查看实时日志
```bash
tail -f /tmp/quant_system.log
```

### 重启服务
```bash
# 优雅停止
kill -TERM $(cat /tmp/quant_system.pid)

# 重新启动
cd /root/longbridge-quant-system_20260111010307
source $HOME/.cargo/env
nohup python3 main.py > /tmp/quant_system.log 2>&1 &
```

## 注意事项

⚠️ **重要提示**:

1. **数据库安全**: 建议为MySQL设置强密码
2. **长桥SDK**: 真实交易需要配置有效的API凭证
3. **测试模式**: 建议先在测试模式下运行
4. **网络访问**: 确保防火墙规则正确配置
5. **资源监控**: 使用 `top`, `htop` 等工具监控服务器资源

## 常见问题

### Q: longbridge SDK安装失败
A: 确保Rust已安装并source环境变量:
```bash
source $HOME/.cargo/env
```

### Q: 数据库连接失败
A: 检查MariaDB服务状态:
```bash
systemctl status mariadb
systemctl start mariadb
```

### Q: 服务启动失败
A: 查看详细日志:
```bash
cat /tmp/quant_system.log
```

### Q: 外网无法访问
A: 检查防火墙和腾讯云安全组规则

## 进度跟踪

当前部署进度: 50%

- 项目文件: ✅ 已上传
- 开发环境: ✅ Rust已安装
- 数据库: ✅ MariaDB已安装
- Python依赖: ⏳ 编译中...
- 数据库初始化: ⏸ 待处理
- 服务启动: ⏸ 待处理
