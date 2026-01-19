# -*- coding: utf-8 -*-
"""
讯飞语音转写 API
使用 raasr.xfyun.cn API + 公众号风格排版

配置方式：
1. 复制 .env.example 为 .env
2. 填入你的讯飞 APPID 和 SecretKey
"""
import base64
import hashlib
import hmac
import json
import os
import time
import requests
import urllib.parse
import re
from dotenv import load_dotenv
from progress import ProgressBar, SpinnerProgress, format_size

# 加载环境变量
load_dotenv()

# API配置（从.env读取）
XUNFEI_HOST = 'https://raasr.xfyun.cn/v2/api'
XUNFEI_APPID = os.getenv('XUNFEI_APPID', '')
XUNFEI_SECRET_KEY = os.getenv('XUNFEI_SECRET_KEY', '')

if not XUNFEI_APPID or not XUNFEI_SECRET_KEY:
    print("警告：未找到讯飞API密钥，请检查.env文件")


class RequestApi(object):
    """讯飞语音转写API请求类"""
    
    def __init__(self, appid, secret_key, upload_file_path):
        self.appid = appid
        self.secret_key = secret_key
        self.upload_file_path = upload_file_path
        self.ts = str(int(time.time()))
        self.signa = self._get_signa()

    def _get_signa(self):
        """生成签名"""
        m2 = hashlib.md5()
        m2.update((self.appid + self.ts).encode('utf-8'))
        md5 = m2.hexdigest()
        md5 = bytes(md5, encoding='utf-8')
        signa = hmac.new(self.secret_key.encode('utf-8'), md5, hashlib.sha1).digest()
        signa = base64.b64encode(signa)
        return str(signa, 'utf-8')

    def upload(self):
        """上传音频文件（带进度条）"""
        file_len = os.path.getsize(self.upload_file_path)
        file_name = os.path.basename(self.upload_file_path)
        
        param_dict = {
            'appId': self.appid,
            'signa': self.signa,
            'ts': self.ts,
            'fileSize': file_len,
            'fileName': file_name,
            'duration': '200'
        }
        
        # 显示上传进度
        progress = ProgressBar(file_len, prefix="上传中")
        progress.update(0, format_size(file_len))
        
        with open(self.upload_file_path, 'rb') as f:
            data = f.read()
        
        # 模拟上传进度（实际是一次性上传）
        progress.update(file_len // 2, f"{format_size(file_len//2)}/{format_size(file_len)}")
        
        response = requests.post(
            url=XUNFEI_HOST + '/upload' + "?" + urllib.parse.urlencode(param_dict),
            headers={"Content-type": "application/json"},
            data=data
        )
        result = json.loads(response.text)
        
        progress.finish("上传完成")
        
        if result.get('code') != '000000' and result.get('code') != 0:
            print(f"❌ 上传失败: {result.get('descInfo', '未知错误')}")
        
        return result

    def get_result(self):
        """获取转写结果（轮询，带旋转动画）"""
        uploadresp = self.upload()
        
        if 'content' not in uploadresp or 'orderId' not in uploadresp.get('content', {}):
            print(f"❌ 上传失败: {uploadresp}")
            return None
        
        orderId = uploadresp['content']['orderId']
        
        param_dict = {
            'appId': self.appid,
            'signa': self.signa,
            'ts': self.ts,
            'orderId': orderId,
            'resultType': 'transfer,predict'
        }
        
        # 等待转写（带旋转动画）
        spinner = SpinnerProgress("等待讯飞转写")
        
        retry_count = 0
        max_retries = 60
        
        while retry_count < max_retries:
            spinner.spin()
            
            response = requests.post(
                url=XUNFEI_HOST + '/getResult' + "?" + urllib.parse.urlencode(param_dict),
                headers={"Content-type": "application/json"}
            )
            result = json.loads(response.text)
            
            # 检查响应是否有效
            if 'content' not in result:
                time.sleep(5)
                retry_count += 1
                continue
            
            # 优先检查是否有转写数据（不管状态码）
            order_result = result.get('content', {}).get('orderResult', '')
            if order_result:
                spinner.done("转写完成")
                return result
            
            # 没有数据，检查状态
            order_info = result.get('content', {}).get('orderInfo', {})
            status = order_info.get('status', 3)
            
            if status == 3:
                # 还在处理中
                time.sleep(5)
                retry_count += 1
            else:
                # 状态不是3且没有数据，真正失败
                fail_type = order_info.get('failType', 0)
                spinner.done(f"转写失败 (status={status})")
                return None
        
        spinner.done("等待超时")
        return None


def extract_text(result):
    """从API结果中提取纯文本"""
    try:
        order_result_str = result.get('content', {}).get('orderResult', '{}')
        if not order_result_str:
            return ""
        
        order_result = json.loads(order_result_str)
        
        sentences = []
        for lattice in order_result.get('lattice', []):
            json_1best_str = lattice.get('json_1best', '{}')
            json_1best = json.loads(json_1best_str)
            
            for rt in json_1best.get('st', {}).get('rt', []):
                sentence = ''.join([cw.get('w', '') for ws in rt.get('ws', []) for cw in ws.get('cw', [])])
                sentences.append(sentence)
        
        return ''.join(sentences)
    except Exception as e:
        print(f"解析结果失败: {e}")
        return ""


def format_for_wechat(text):
    """
    公众号风格排版
    - 句号后换行
    - 问号/感叹号后换行  
    - 短段落（2-3句一段）
    - 段间空行
    """
    if not text:
        return ""
    
    # 检测是否为英文为主（通过字母比例判断）
    alpha_count = sum(1 for c in text if c.isalpha() and ord(c) < 128)
    total_chars = len(text.replace(' ', ''))
    is_english = (alpha_count / max(total_chars, 1)) > 0.5
    
    if is_english:
        # 英文排版
        # 保留空格，规范化多余空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 在句号、问号、感叹号后换行
        text = re.sub(r'([.!?])\s*', r'\1\n', text)
        
        # 分割成句子
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 每2-3句组成一段
        formatted = []
        paragraph = []
        for line in lines:
            paragraph.append(line)
            if len(paragraph) >= 3 or line.endswith('?') or line.endswith('!'):
                formatted.append(' '.join(paragraph))
                paragraph = []
        if paragraph:
            formatted.append(' '.join(paragraph))
        
        return '\n\n'.join(formatted)
    
    else:
        # 中文排版
        # 去除多余空格
        text = re.sub(r'\s+', '', text)
        
        # 在句号、问号、感叹号后添加换行
        text = re.sub(r'([。！？])', r'\1\n', text)
        
        # 分割成句子
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 每2-3句组成一段
        formatted = []
        paragraph = []
        for line in lines:
            paragraph.append(line)
            if len(paragraph) >= 2 or line.endswith('？') or line.endswith('！'):
                formatted.append(''.join(paragraph))
                paragraph = []
        if paragraph:
            formatted.append(''.join(paragraph))
        
        return '\n\n'.join(formatted)


def transcribe_audio_direct(audio_path, output_name=None):
    """
    直接上传完整音频文件进行转写 + 公众号排版
    
    参数:
        audio_path: 音频文件路径
        output_name: 输出文件名（不含扩展名）
    返回:
        输出文件路径
    """
    if not os.path.exists(audio_path):
        print(f"错误：音频文件不存在 - {audio_path}")
        return None
    
    # 生成输出文件名
    if not output_name:
        output_name = os.path.splitext(os.path.basename(audio_path))[0]
    output_path = f'outputs/{output_name}.txt'
    
    print("正在转写，请稍候...")
    
    try:
        # 创建API请求
        api = RequestApi(
            appid=XUNFEI_APPID,
            secret_key=XUNFEI_SECRET_KEY,
            upload_file_path=audio_path
        )
        
        # 获取结果
        result = api.get_result()
        if not result:
            return None
        
        # 提取文本
        raw_text = extract_text(result)
        if not raw_text:
            print("转写结果为空")
            return None
        
        # 公众号风格排版
        formatted_text = format_for_wechat(raw_text)
        
        # 保存结果
        os.makedirs('outputs', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(formatted_text)
        
        # 成功后由调用方打印结果
        
        return output_path
        
    except Exception as e:
        print(f"转写失败: {e}")
        import traceback
        traceback.print_exc()
        return None



