#!/bin/bash
#
# 美股量化交易系统 - 启动脚本
# 功能: 优雅停止旧进程,启动新进程
#

set -e

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 配置
LOG_FILE="/tmp/quant_system.log"
PID_FILE="/tmp/quant_system.pid"
VENV_DIR="venv"
HOST="0.0.0.0"
PORT=8000

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查虚拟环境
check_venv() {
    log_info "检查虚拟环境..."
    if [ ! -d "$VENV_DIR" ]; then
        log_error "虚拟环境不存在: $VENV_DIR"
        log_info "请先创建虚拟环境: python -m venv $VENV_DIR"
        exit 1
    fi

    if [ ! -f "$VENV_DIR/bin/python" ]; then
        log_error "虚拟环境Python不存在: $VENV_DIR/bin/python"
        exit 1
    fi

    log_success "虚拟环境检查通过"
}

# 优雅停止旧进程
stop_old_process() {
    log_info "检查是否有运行中的进程..."

    # 方法1: 从PID文件读取
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            log_warn "发现运行中的进程 (PID: $OLD_PID)"
            
            # 发送TERM信号 (优雅退出)
            log_info "发送TERM信号 (优雅退出)..."
            kill -TERM "$OLD_PID" 2>/dev/null || true

            # 等待进程退出,最多等待10秒
            TIMEOUT=10
            COUNT=0
            while ps -p "$OLD_PID" > /dev/null 2>&1 && [ $COUNT -lt $TIMEOUT ]; do
                echo -n "."
                sleep 1
                COUNT=$((COUNT + 1))
            done
            echo ""

            # 检查是否还在运行
            if ps -p "$OLD_PID" > /dev/null 2>&1; then
                log_warn "优雅退出超时,强制终止进程..."
                kill -KILL "$OLD_PID" 2>/dev/null || true
                sleep 1
            else
                log_success "进程已优雅退出"
            fi
        else
            log_info "PID文件中的进程不存在,清理PID文件"
        fi
        rm -f "$PID_FILE"
    fi

    # 方法2: 检查端口占用
    log_info "检查端口 $PORT 占用情况..."
    PORT_PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PORT_PID" ]; then
        log_warn "端口 $PORT 被进程占用 (PID: $PORT_PID)"
        
        # 发送TERM信号
        log_info "发送TERM信号..."
        kill -TERM "$PORT_PID" 2>/dev/null || true

        # 等待进程退出
        TIMEOUT=10
        COUNT=0
        while ps -p "$PORT_PID" > /dev/null 2>&1 && [ $COUNT -lt $TIMEOUT ]; do
            echo -n "."
            sleep 1
            COUNT=$((COUNT + 1))
        done
        echo ""

        # 强制终止
        if ps -p "$PORT_PID" > /dev/null 2>&1; then
            log_warn "优雅退出超时,强制终止..."
            kill -KILL "$PORT_PID" 2>/dev/null || true
            sleep 1
        else
            log_success "端口占用进程已退出"
        fi
    fi

    log_success "旧进程清理完成"
}

# 检查依赖
check_dependencies() {
    log_info "检查Python依赖..."
    if ! "$VENV_DIR/bin/python" -c "import fastapi, pymysql" 2>/dev/null; then
        log_warn "依赖缺失,正在安装..."
        "$VENV_DIR/bin/pip" install -r requirements.txt -q
        log_success "依赖安装完成"
    else
        log_success "依赖检查通过"
    fi
}

# 启动新进程
start_new_process() {
    log_info "启动新进程..."
    log_info "日志文件: $LOG_FILE"
    log_info "监听地址: $HOST:$PORT"

    # 清空旧日志
    > "$LOG_FILE"

    # 检查是否使用模块化版本
    if [ "$USE_NEW" = "1" ] && [ -f "main_new.py" ]; then
        log_info "使用模块化版本 (main_new.py)"
        MAIN_FILE="main_new.py"
    else
        MAIN_FILE="main.py"
    fi

    # 启动服务 (后台运行)
    nohup "$VENV_DIR/bin/python" "$MAIN_FILE" >> "$LOG_FILE" 2>&1 &
    NEW_PID=$!

    # 保存PID
    echo "$NEW_PID" > "$PID_FILE"

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 3

    # 检查进程是否还在运行
    if ps -p "$NEW_PID" > /dev/null 2>&1; then
        log_success "服务启动成功 (PID: $NEW_PID)"
    else
        log_error "服务启动失败,查看日志:"
        cat "$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi

    # 检查端口是否监听
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_success "端口 $PORT 监听成功"
    else
        log_warn "端口 $PORT 似乎未正常监听,请检查日志"
    fi
}

# 显示状态
show_status() {
    echo ""
    echo "=========================================="
    echo "  服务状态"
    echo "=========================================="
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "  状态: 运行中"
            echo "  PID: $PID"
            echo "  端口: $PORT"
        else
            echo "  状态: 已停止"
            echo "  (PID文件存在但进程不存在)"
        fi
    else
        echo "  状态: 未运行"
    fi
    
    echo "  日志: $LOG_FILE"
    echo "=========================================="
    echo ""
}

# 主函数
main() {
    echo ""
    echo "=========================================="
    echo "  美股量化交易系统 - 启动脚本"
    echo "=========================================="
    echo ""

    # 检查虚拟环境
    check_venv

    # 检查依赖
    check_dependencies

    # 停止旧进程
    stop_old_process

    # 启动新进程
    start_new_process

    # 显示状态
    show_status

    # 显示最近日志
    log_info "最近的日志输出:"
    tail -20 "$LOG_FILE"

    echo ""
    log_success "启动完成! 访问: http://localhost:$PORT"
    echo ""
    log_info "查看日志: tail -f $LOG_FILE"
    log_info "停止服务: kill -TERM \$(cat $PID_FILE)"
    log_info "查看状态: curl http://localhost:$PORT/api/monitoring/status"
    echo ""
}

# 执行主函数
main "$@"
