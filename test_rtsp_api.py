#!/usr/bin/env python3
"""
RTSP API测试脚本
用于测试新实现的标准RTSP拉流功能
"""

import requests
import json
import time

# 测试配置
BASE_URL = "http://localhost:8000"  # 后端服务地址
API_PREFIX = "/ws/rtsp"

# 测试设备信息（请根据实际情况修改）
TEST_DEVICE = {
    "ip_address": "10.83.242.53",  # 您的设备IP
    "port": 554,
    "username": "admin",  # 请填入实际用户名
    "password": "admin123",  # 请填入实际密码
    "channel": 1,
    "subtype": 0  # 主码流
}

def test_rtsp_connection():
    """测试RTSP连接"""
    print("=" * 60)
    print("测试RTSP连接")
    print("=" * 60)
    
    url = f"{BASE_URL}{API_PREFIX}/test-rtsp-connection"
    
    try:
        response = requests.post(url, json=TEST_DEVICE, timeout=30)
        print(f"状态码: {response.status_code}, 响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print("✅ RTSP连接测试成功")
                print(f"媒体信息: {json.dumps(result['media_info'], indent=2, ensure_ascii=False)}")
                return True
            else:
                print(f"❌ RTSP连接测试失败: {result['error']}")
                return False
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

def test_start_rtsp_stream():
    """测试启动RTSP流"""
    print("\n" + "=" * 60)
    print("测试启动RTSP流")
    print("=" * 60)
    
    url = f"{BASE_URL}{API_PREFIX}/start-stream"
    
    # 生成唯一的流ID
    stream_id = f"test_stream_{int(time.time())}"
    
    request_data = {
        "stream_id": stream_id,
        **TEST_DEVICE,
        "client_port_start": 63088
    }
    
    try:
        response = requests.post(url, json=request_data, timeout=30)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print("✅ RTSP流启动成功")
                print(f"流ID: {result['data']['stream_id']}")
                print(f"会话ID: {result['data']['session_id']}")
                print(f"客户端端口: {result['data']['client_ports']}")
                print(f"服务器端口: {result['data']['server_ports']}")
                print(f"媒体信息: {json.dumps(result['data']['media_info'], indent=2, ensure_ascii=False)}")
                return stream_id
            else:
                print(f"❌ RTSP流启动失败: {result['error']}")
                return None
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return None

def test_stop_rtsp_stream(stream_id):
    """测试停止RTSP流"""
    print("\n" + "=" * 60)
    print("测试停止RTSP流")
    print("=" * 60)
    
    url = f"{BASE_URL}{API_PREFIX}/stop-stream"
    
    request_data = {"stream_id": stream_id}
    
    try:
        response = requests.post(url, json=request_data, timeout=10)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print("✅ RTSP流停止成功")
                return True
            else:
                print(f"❌ RTSP流停止失败: {result['error']}")
                return False
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

def main():
    """主测试函数"""
    print("开始RTSP API功能测试")
    print(f"测试设备: {TEST_DEVICE['ip_address']}:{TEST_DEVICE['port']}")
    print(f"通道: {TEST_DEVICE['channel']}, 码流类型: {TEST_DEVICE['subtype']}")
    print(f"用户名: {TEST_DEVICE['username']}")
    print("-" * 60)
    
    # 1. 测试RTSP连接
    if not test_rtsp_connection():
        print("❌ RTSP连接测试失败，跳过后续测试")
        return
    
    # 2. 测试启动RTSP流
    stream_id = test_start_rtsp_stream()
    if not stream_id:
        print("❌ RTSP流启动失败，跳过后续测试")
        return
    
    # 等待一段时间让流稳定
    print("\n等待5秒让流稳定...")
    time.sleep(5)
    
    # 5. 测试停止RTSP流
    test_stop_rtsp_stream(stream_id)
    
    # 6. 验证流已停止
    print("\n" + "=" * 60)
    print("验证流已停止")
    print("=" * 60)
    
    time.sleep(2)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
