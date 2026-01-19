# -*- coding: utf-8 -*-
"""
模拟飞书发送请求的测试脚本
用于验证 server.py 是否正常工作，自动处理签名验证
使用方法：
python mock_feishu.py
"""
import requests
import json
import hashlib
import time
import os
from dotenv import load_dotenv

# 加载 .env 获取配置（模拟飞书端，所以需要知道 key）
load_dotenv()

# 请确保 .env 中填入了以下信息，或者直接修改这里
ENCRYPT_KEY = os.getenv('FEISHU_ENCRYPT_KEY', 'b2Mm2NKCIOQ9PGhOClNa3eCLjtrXphGW')
VERIFICATION_TOKEN = os.getenv('FEISHU_VERIFICATION_TOKEN', 'cp4M9zG3qytrb1v1XjttPcxxdEifEMpx')
TARGET_URL = "http://localhost:5000/feishu/webhook"

def calculate_signature(timestamp, nonce, encrypt_key, body):
    """计算签名"""
    string_to_sign = str(timestamp) + str(nonce) + str(encrypt_key) + body
    sha256 = hashlib.sha256(string_to_sign.encode('utf-8'))
    return sha256.hexdigest()

def send_challenge():
    """发送 URL 验证请求 (Challenge)"""
    print("\n[测试] 发送 Challenge 验证请求...")
    
    timestamp = str(int(time.time()))
    nonce = "12345"
    
    data = {
        "challenge": "test_challenge_123",
        "token": VERIFICATION_TOKEN,
        "type": "url_verification"
    }
    body = json.dumps(data)
    
    headers = {
        "Content-Type": "application/json",
        "X-Lark-Request-Timestamp": timestamp,
        "X-Lark-Request-Nonce": nonce
    }
    
    # 如果配置了加密密钥，需要计算签名
    if ENCRYPT_KEY:
        signature = calculate_signature(timestamp, nonce, ENCRYPT_KEY, body)
        headers["X-Lark-Signature"] = signature
        print(f"密钥已配置，生成签名: {signature}")
    else:
        print("未配置密钥，跳过签名")

    try:
        response = requests.post(TARGET_URL, data=body, headers=headers)
        print(f"状态码: {response.status_code}")
        print(f"响应体: {response.text}")
        
        if response.status_code == 200 and json.loads(response.text).get("challenge") == "test_challenge_123":
            print("✅ Challenge 验证通过！")
        else:
            print("❌ Challenge 验证失败")
            
    except Exception as e:
        print(f"❌ 请求发送失败: {e}")

if __name__ == "__main__":
    print(f"目标地址: {TARGET_URL}")
    print(f"加密密钥: {ENCRYPT_KEY[:4]}******")
    
    send_challenge()
