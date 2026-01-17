"""
快速API测试脚本 - 用于验证API端点是否正常工作
"""
import requests
import sys
import time
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

BASE_URL = "http://localhost:8000"

class APITester:
    """API测试器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.results = []
        self.logged_in = False
    
    def test(self, name, method, endpoint, expected_codes=None, **kwargs):
        """执行单个测试"""
        if expected_codes is None:
            expected_codes = [200]
        
        url = f"{BASE_URL}{endpoint}"
        
        try:
            response = getattr(self.session, method.lower())(url, timeout=10, **kwargs)
            success = response.status_code in expected_codes
            
            result = {
                'name': name,
                'success': success,
                'status_code': response.status_code,
                'expected': expected_codes
            }
            
            if not success:
                try:
                    result['response'] = response.json()
                except:
                    result['response'] = response.text[:200]
        
        except Exception as e:
            result = {
                'name': name,
                'success': False,
                'error': str(e)
            }
        
        self.results.append(result)
        
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        print(f"  {status}: {name}")
        
        if not result['success']:
            if 'error' in result:
                print(f"        Error: {result['error']}")
            else:
                print(f"        Got: {result['status_code']}, Expected: {result['expected']}")
        
        return result
    
    def register_and_login(self):
        """注册并登录测试用户"""
        username = f"apitest_{int(time.time())}"
        
        # 注册
        reg_response = self.session.post(
            f"{BASE_URL}/api/auth/register",
            json={"username": username, "email": f"{username}@test.com", "password": "TestPass123"},
            timeout=10
        )
        
        # 登录 (使用cookie认证)
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": username, "password": "TestPass123"},
            timeout=10
        )
        
        if login_response.status_code == 200:
            self.logged_in = True
            return True
        return False
    
    def summary(self):
        """输出测试摘要"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r['success'])
        failed = total - passed
        
        print("\n" + "="*50)
        print(f"测试结果: {passed}/{total} 通过")
        if failed > 0:
            print(f"失败测试:")
            for r in self.results:
                if not r['success']:
                    print(f"  - {r['name']}")
        print("="*50)
        
        return failed == 0


def run_tests():
    """运行所有API测试"""
    tester = APITester()
    
    print("\n=== 量化交易系统 API 测试 ===\n")
    
    # 1. 基础连接测试
    print("1. 基础连接测试")
    tester.test("API服务可访问", "GET", "/docs", [200])
    
    # 2. 认证模块测试
    print("\n2. 认证模块测试")
    test_username = f"testuser_{int(time.time())}"
    
    tester.test(
        "用户注册", "POST", "/api/auth/register",
        [200],
        json={"username": test_username, "email": f"{test_username}@test.com", "password": "TestPass123"}
    )
    
    tester.test(
        "用户登录", "POST", "/api/auth/login",
        [200],
        json={"username": test_username, "password": "TestPass123"}
    )
    
    tester.test(
        "无效登录", "POST", "/api/auth/login",
        [401],
        json={"username": "nonexistent", "password": "wrong"}
    )
    
    # 保持登录状态用于后续测试
    tester.register_and_login()
    
    tester.test("获取当前用户（已认证）", "GET", "/api/auth/me", [200])
    
    # 测试未认证访问 - 新session
    new_session = requests.Session()
    resp = new_session.get(f"{BASE_URL}/api/auth/me", timeout=10)
    result = {
        'name': "未认证访问保护接口",
        'success': resp.status_code == 401,
        'status_code': resp.status_code,
        'expected': [401]
    }
    tester.results.append(result)
    status = "✅ PASS" if result['success'] else "❌ FAIL"
    print(f"  {status}: {result['name']}")
    
    # 3. 股票管理测试
    print("\n3. 股票管理测试")
    tester.test("获取股票列表", "GET", "/api/stocks", [200])
    tester.test("添加股票", "POST", "/api/stocks", [200, 400], json={"symbol": "AAPL", "name": "Apple Inc."})
    
    # 4. 持仓管理测试  
    print("\n4. 持仓管理测试")
    tester.test("获取持仓列表", "GET", "/api/positions", [200])
    
    # 5. 交易记录测试
    print("\n5. 交易记录测试")
    tester.test("获取交易历史", "GET", "/api/trades", [200])
    
    # 6. 市场数据测试
    print("\n6. 市场数据测试")
    tester.test("获取市场数据", "GET", "/api/market-data", [200])
    
    # 7. 智能交易测试
    print("\n7. 智能交易测试")
    tester.test("获取智能交易状态", "GET", "/api/smart-trade/status", [200])
    tester.test("获取预测历史", "GET", "/api/smart-trade/predictions", [200])
    
    # 8. 监控模块测试
    print("\n8. 监控模块测试")
    tester.test("获取系统状态", "GET", "/api/monitoring/status", [200])
    
    # 9. 配置模块测试
    print("\n9. 配置模块测试")
    tester.test("获取系统配置", "GET", "/api/config", [200])
    
    # 10. 登出测试
    print("\n10. 登出测试")
    tester.test("用户登出", "POST", "/api/auth/logout", [200])
    
    # 输出摘要
    return tester.summary()


if __name__ == "__main__":
    try:
        # 检查服务是否运行
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code != 200:
            print("错误: API服务未运行")
            sys.exit(1)
    except Exception as e:
        print(f"错误: 无法连接到API服务 - {e}")
        print("请先运行: python main.py")
        sys.exit(1)
    
    success = run_tests()
    sys.exit(0 if success else 1)
