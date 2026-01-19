# -*- coding: utf-8 -*-
"""
飞书机器人 API 模块
支持：
- 接收消息事件
- 发送文本/卡片消息
"""
import os
import json
import hashlib
import base64
import requests
from dotenv import load_dotenv
from Crypto.Cipher import AES

load_dotenv()

# 飞书配置
FEISHU_APP_ID = os.getenv('FEISHU_APP_ID', '')
FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET', '')
FEISHU_VERIFICATION_TOKEN = os.getenv('FEISHU_VERIFICATION_TOKEN', '')
FEISHU_ENCRYPT_KEY = os.getenv('FEISHU_ENCRYPT_KEY', '')

# API 地址
FEISHU_API_BASE = 'https://open.feishu.cn/open-apis'


class AESCipher:
    """飞书消息解密"""
    
    def __init__(self, key):
        self.key = hashlib.sha256(key.encode()).digest()
    
    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        cipher = AES.new(self.key, AES.MODE_CBC, enc[:AES.block_size])
        return self._unpad(cipher.decrypt(enc[AES.block_size:])).decode('utf-8')
    
    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]


def decrypt_message(encrypt_key, encrypt_data):
    """解密飞书消息"""
    if not encrypt_key:
        return encrypt_data
    cipher = AESCipher(encrypt_key)
    return json.loads(cipher.decrypt(encrypt_data))


def get_tenant_access_token():
    """获取 tenant_access_token"""
    url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    resp = requests.post(url, json=payload)
    data = resp.json()
    
    if data.get('code') == 0:
        return data.get('tenant_access_token')
    else:
        print(f"获取 token 失败: {data}")
        return None


def send_message(receive_id, content, receive_id_type='chat_id', msg_type='text'):
    """
    发送消息
    
    参数:
        receive_id: 接收者 ID（chat_id 或 user_id）
        content: 消息内容
        receive_id_type: 'chat_id' 或 'open_id' 或 'user_id'
        msg_type: 'text' 或 'interactive'
    """
    token = get_tenant_access_token()
    if not token:
        return False
    
    url = f"{FEISHU_API_BASE}/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    if msg_type == 'text':
        content_json = json.dumps({"text": content})
    else:
        content_json = json.dumps(content)
    
    payload = {
        "receive_id": receive_id,
        "msg_type": msg_type,
        "content": content_json
    }
    
    resp = requests.post(
        url,
        headers=headers,
        params={"receive_id_type": receive_id_type},
        json=payload
    )
    
    data = resp.json()
    if data.get('code') == 0:
        return True
    else:
        print(f"发送消息失败: {data}")
        return False


def send_text_message(chat_id, text):
    """发送文本消息到群聊"""
    return send_message(chat_id, text, 'chat_id', 'text')


def send_success_card(chat_id, bv_number, title, text_preview):
    """发送成功卡片"""
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "✅ 转写完成"},
            "template": "green"
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**BV号**\n{bv_number}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**标题**\n{title[:30]}..."}}
                ]
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**📄 内容预览**\n{text_preview[:800]}..."}
            }
        ]
    }
    return send_message(chat_id, card, 'chat_id', 'interactive')


def send_error_card(chat_id, bv_number, error_message):
    """发送错误卡片"""
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "❌ 转写失败"},
            "template": "red"
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**BV号**\n{bv_number}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**错误原因**\n{error_message}"}}
                ]
            }
        ]
    }
    return send_message(chat_id, card, 'chat_id', 'interactive')


def send_processing_message(chat_id, bv_number):
    """发送处理中消息"""
    return send_text_message(chat_id, f"⏳ 正在处理: {bv_number}\n请稍候，转写需要 30-60 秒...")
