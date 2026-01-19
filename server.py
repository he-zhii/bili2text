# -*- coding: utf-8 -*-
"""
Bili2Text 飞书机器人服务端
使用官方 lark_oapi SDK
"""
import os
import re
import json
import threading
from flask import Flask
from dotenv import load_dotenv
import lark_oapi as lark
from lark_oapi.adapter.flask import parse_req, parse_resp
from lark_oapi.api.im.v1 import *

load_dotenv()

app = Flask(__name__)

# 飞书配置（空值时返回 None，SDK 要求）
ENCRYPT_KEY = os.getenv('FEISHU_ENCRYPT_KEY') or None
VERIFICATION_TOKEN = os.getenv('FEISHU_VERIFICATION_TOKEN') or None
APP_ID = os.getenv('FEISHU_APP_ID') or None
APP_SECRET = os.getenv('FEISHU_APP_SECRET') or None

# 已处理的消息 ID（防止重复处理）
processed_messages = set()


def extract_bv_number(text):
    """从文本中提取 BV 号"""
    patterns = [
        r'BV[A-Za-z0-9]{10}',
        r'bilibili\.com/video/(BV[A-Za-z0-9]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1) if '(' in pattern else match.group(0)
    
    return None


def process_video(bv_number, chat_id):
    """处理视频转写（在后台线程中运行）"""
    from feishu import send_processing_message, send_success_card, send_error_card
    from utils import download_audio_only
    from xunfei import transcribe_audio_direct
    from cleanup import cleanup_audio_file, cleanup_bv_folder
    
    send_processing_message(chat_id, bv_number)
    
    try:
        print(f"[飞书] 开始处理: {bv_number}")
        audio_path, title = download_audio_only(bv_number)
        
        if not audio_path:
            send_error_card(chat_id, bv_number, "下载失败，请检查 BV 号是否正确")
            return
        
        print(f"[飞书] 开始转写: {title}")
        output_path = transcribe_audio_direct(audio_path, output_name=title)
        
        cleanup_audio_file(audio_path)
        cleanup_bv_folder(bv_number)
        
        if output_path:
            with open(output_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            send_success_card(chat_id, bv_number, title, text_content)
            print(f"[飞书] 转写完成: {bv_number}")
        else:
            send_error_card(chat_id, bv_number, "转写失败，请稍后重试")
            
    except Exception as e:
        print(f"[飞书] 处理错误: {e}")
        send_error_card(chat_id, bv_number, str(e)[:100])


def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    """处理收到消息事件 (v2.0 版本)"""
    print(f"[飞书] 收到消息事件")
    
    try:
        message = data.event.message
        message_id = message.message_id
        chat_id = message.chat_id
        
        # 防止重复处理
        if message_id in processed_messages:
            return
        processed_messages.add(message_id)
        
        # 限制缓存大小
        if len(processed_messages) > 1000:
            processed_messages.clear()
        
        # 解析消息内容
        if message.message_type == 'text':
            content = json.loads(message.content)
            text = content.get('text', '')
            print(f"[飞书] 收到文本: {text}")
            
            # 提取 BV 号
            bv_number = extract_bv_number(text)
            if bv_number:
                print(f"[飞书] 检测到 BV 号: {bv_number}")
                # 在后台线程中处理
                thread = threading.Thread(
                    target=process_video,
                    args=(bv_number, chat_id)
                )
                thread.start()
                
    except Exception as e:
        print(f"[飞书] 消息处理错误: {e}")
        import traceback
        traceback.print_exc()


# 创建事件处理器
handler = lark.EventDispatcherHandler.builder(
    ENCRYPT_KEY, 
    VERIFICATION_TOKEN, 
    lark.LogLevel.DEBUG
).register_p2_im_message_receive_v1(do_p2_im_message_receive_v1).build()


@app.route("/feishu/webhook", methods=["POST"])
def event():
    """飞书事件回调入口"""
    resp = handler.do(parse_req())
    return parse_resp(resp)


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return {"status": "ok", "service": "bili2text"}


if __name__ == '__main__':
    print("=" * 50)
    print("Bili2Text 飞书机器人服务")
    print("=" * 50)
    print(f"Webhook URL: http://YOUR_IP:5000/feishu/webhook")
    print("=" * 50)
    
    if not VERIFICATION_TOKEN:
        print("⚠️  警告: FEISHU_VERIFICATION_TOKEN 未配置")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
