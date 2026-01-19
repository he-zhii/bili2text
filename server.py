# -*- coding: utf-8 -*-
"""
Bili2Text 飞书机器人服务端
接收飞书消息 → 提取 BV 号 → 下载转写 → 返回结果
"""
import os
import re
import json
import threading
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 飞书配置
VERIFICATION_TOKEN = os.getenv('FEISHU_VERIFICATION_TOKEN', '')
ENCRYPT_KEY = os.getenv('FEISHU_ENCRYPT_KEY', '')

# 已处理的消息 ID（防止重复处理）
processed_messages = set()


def extract_bv_number(text):
    """从文本中提取 BV 号"""
    # 支持完整链接或纯 BV 号
    patterns = [
        r'BV[A-Za-z0-9]{10}',  # 标准 BV 号
        r'bilibili\.com/video/(BV[A-Za-z0-9]+)',  # 完整链接
        r'b23\.tv/([A-Za-z0-9]+)',  # 短链接（需要额外处理）
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1) if '(' in pattern else match.group(0)
    
    return None


def process_video(bv_number, chat_id):
    """
    处理视频转写（在后台线程中运行）
    """
    from feishu import send_processing_message, send_success_card, send_error_card
    from utils import download_audio_only
    from xunfei import transcribe_audio_direct
    from cleanup import cleanup_audio_file, cleanup_bv_folder
    
    # 发送处理中消息
    send_processing_message(chat_id, bv_number)
    
    try:
        # 1. 下载音频
        print(f"[飞书] 开始处理: {bv_number}")
        audio_path, title = download_audio_only(bv_number)
        
        if not audio_path:
            send_error_card(chat_id, bv_number, "下载失败，请检查 BV 号是否正确")
            return
        
        # 2. 讯飞转写
        print(f"[飞书] 开始转写: {title}")
        output_path = transcribe_audio_direct(audio_path, output_name=title)
        
        # 3. 清理临时文件
        cleanup_audio_file(audio_path)
        cleanup_bv_folder(bv_number)
        
        if output_path:
            # 4. 读取结果并发送
            with open(output_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            send_success_card(chat_id, bv_number, title, text_content)
            print(f"[飞书] 转写完成: {bv_number}")
        else:
            send_error_card(chat_id, bv_number, "转写失败，请稍后重试")
            
    except Exception as e:
        print(f"[飞书] 处理错误: {e}")
        send_error_card(chat_id, bv_number, str(e)[:100])


@app.route('/feishu/webhook', methods=['POST'])
def feishu_webhook():
    """飞书事件回调"""
    data = request.json
    
    # 处理加密消息
    if 'encrypt' in data:
        from feishu import decrypt_message
        data = decrypt_message(ENCRYPT_KEY, data['encrypt'])
    
    # URL 验证（首次配置时飞书会发送）
    if 'challenge' in data:
        return jsonify({"challenge": data['challenge']})
    
    # 验证 token
    if data.get('token') != VERIFICATION_TOKEN:
        return jsonify({"error": "invalid token"}), 403
    
    # 处理事件
    event = data.get('event', {})
    event_type = data.get('header', {}).get('event_type', '')
    
    if event_type == 'im.message.receive_v1':
        # 收到消息
        message = event.get('message', {})
        message_id = message.get('message_id', '')
        chat_id = message.get('chat_id', '')
        
        # 防止重复处理
        if message_id in processed_messages:
            return jsonify({"code": 0})
        processed_messages.add(message_id)
        
        # 限制缓存大小
        if len(processed_messages) > 1000:
            processed_messages.clear()
        
        # 解析消息内容
        msg_type = message.get('message_type', '')
        if msg_type == 'text':
            content = json.loads(message.get('content', '{}'))
            text = content.get('text', '')
            
            # 提取 BV 号
            bv_number = extract_bv_number(text)
            if bv_number:
                # 在后台线程中处理（避免阻塞响应）
                thread = threading.Thread(
                    target=process_video,
                    args=(bv_number, chat_id)
                )
                thread.start()
    
    return jsonify({"code": 0})


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "ok", "service": "bili2text"})


if __name__ == '__main__':
    print("=" * 50)
    print("Bili2Text 飞书机器人服务")
    print("=" * 50)
    print(f"Webhook URL: http://YOUR_IP:5000/feishu/webhook")
    print("=" * 50)
    
    # 检查配置
    if not VERIFICATION_TOKEN:
        print("⚠️  警告: FEISHU_VERIFICATION_TOKEN 未配置")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
