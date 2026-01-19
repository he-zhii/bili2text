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
    patterns = [
        r'BV[A-Za-z0-9]{10}',
        r'bilibili\.com/video/(BV[A-Za-z0-9]+)',
        r'b23\.tv/([A-Za-z0-9]+)',
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


@app.route('/feishu/webhook', methods=['POST'])
def feishu_webhook():
    """飞书事件回调"""
    try:
        # 获取原始请求体（用于调试）
        raw_data = request.get_data(as_text=True)
        print(f"[飞书] Content-Type: {request.content_type}")
        print(f"[飞书] 原始请求: {raw_data[:500]}")

        # 尝试解析 JSON
        data = request.json
        if not data:
            print("[飞书] JSON 解析失败")
            return jsonify({"code": -1, "msg": "invalid json"}), 400

        # 处理加密消息
        if 'encrypt' in data:
            from feishu import decrypt_message
            data = decrypt_message(ENCRYPT_KEY, data['encrypt'])

        # URL 验证（首次配置时飞书会发送 challenge）
        if 'challenge' in data:
            challenge = data['challenge']
            print(f"[飞书] 验证请求，返回 challenge: {challenge}")
            return jsonify({"challenge": challenge}), 200

        # 检查 schema 字段（新版飞书 API 格式）
        if data.get('schema') == '2.0':
            header = data.get('header', {})
            if 'token' in header and VERIFICATION_TOKEN:
                if header.get('token') != VERIFICATION_TOKEN:
                    print(f"[飞书] token 验证失败")
                    return jsonify({"code": -1, "msg": "invalid token"}), 403

        # 处理事件
        event = data.get('event', {})
        event_type = data.get('header', {}).get('event_type', '')
        
        if event_type == 'im.message.receive_v1':
            message = event.get('message', {})
            message_id = message.get('message_id', '')
            chat_id = message.get('chat_id', '')

            if message_id in processed_messages:
                return jsonify({"code": 0})

            processed_messages.add(message_id)
            if len(processed_messages) > 1000:
                processed_messages.clear()

            msg_type = message.get('message_type', '')
            if msg_type == 'text':
                content = json.loads(message.get('content', '{}'))
                text = content.get('text', '')

                bv_number = extract_bv_number(text)
                if bv_number:
                    thread = threading.Thread(
                        target=process_video,
                        args=(bv_number, chat_id)
                    )
                    thread.start()

        return jsonify({"code": 0})

    except Exception as e:
        print(f"[飞书] Webhook 异常: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"code": -1, "msg": "server error"}), 500


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
    
    if not VERIFICATION_TOKEN:
        print("⚠️  警告: FEISHU_VERIFICATION_TOKEN 未配置")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
