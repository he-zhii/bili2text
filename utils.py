# -*- coding: utf-8 -*-
"""
下载工具模块
支持多源下载：原生 API（优先） + yt-dlp（备用）
"""
import os
import re
import subprocess
import glob
import json
import requests
import warnings
from progress import ProgressBar, SpinnerProgress

# 禁用 SSL 警告
warnings.filterwarnings('ignore', category=requests.packages.urllib3.exceptions.InsecureRequestWarning)


def ensure_folders_exist(output_dir):
    """确保必要的目录存在"""
    for folder in ["bilibili_video", output_dir, "outputs"]:
        if not os.path.exists(folder):
            os.makedirs(folder)


def download_audio_native(bv_number, output_dir):
    """
    使用原生 requests 直接下载 B 站音频
    绕过 SSL 问题，国内网络更稳定
    
    返回:
        (音频路径, 视频标题) 或 (None, None)
    """
    if not bv_number.startswith("BV"):
        bv_number = "BV" + bv_number
    
    print(f"📥 下载音频: {bv_number}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'https://www.bilibili.com/video/{bv_number}',
        'Origin': 'https://www.bilibili.com',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # 添加 Cookie 支持 (关键修复 412 错误)
    cookie = os.getenv('BILIBILI_COOKIE')
    if cookie:
        headers['Cookie'] = cookie
    
    try:
        # 1. 获取视频页面
        spinner = SpinnerProgress("获取视频信息")
        spinner.spin()
        
        url = f"https://www.bilibili.com/video/{bv_number}"
        resp = requests.get(url, headers=headers, timeout=30, verify=False)
        resp.raise_for_status()
        
        html = resp.text
        spinner.done("视频信息获取成功")
        
        # 2. 提取视频标题
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html)
        if title_match:
            title = title_match.group(1).replace('_哔哩哔哩_bilibili', '').strip()
        else:
            title = bv_number
        print(f"📺 标题: {title}")
        
        # 3. 提取 playinfo
        playinfo_match = re.search(r'window\.__playinfo__\s*=\s*(\{.+?\})\s*</script>', html)
        if not playinfo_match:
            print("❌ 无法提取 playinfo，可能需要登录")
            return None, None
        
        playinfo = json.loads(playinfo_match.group(1))
        
        # 4. 获取音频流 URL
        audio_streams = playinfo.get('data', {}).get('dash', {}).get('audio', [])
        if not audio_streams:
            print("❌ 找不到音频流")
            return None, None
        
        # 选择最高音质
        audio_url = audio_streams[0]['baseUrl']
        
        # 5. 准备输出文件
        os.makedirs(output_dir, exist_ok=True)
        safe_title = "".join(c for c in title if c not in r'\/:*?"<>|')[:80]
        audio_path = f"{output_dir}/{safe_title}.m4a"
        
        # 6. 下载音频
        audio_resp = requests.get(audio_url, headers=headers, timeout=120, verify=False, stream=True)
        audio_resp.raise_for_status()
        
        total_size = int(audio_resp.headers.get('content-length', 0))
        downloaded = 0
        
        if total_size > 0:
            progress = ProgressBar(total_size, prefix="下载中")
        
        with open(audio_path, 'wb') as f:
            for chunk in audio_resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        size_str = f"{downloaded // 1024}KB/{total_size // 1024}KB"
                        progress.update(downloaded, size_str)
        
        print(f"✓ 下载成功")
        return audio_path, title
        
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL 错误: {e}")
        return None, None
    except requests.exceptions.Timeout:
        print("❌ 下载超时")
        return None, None
    except Exception as e:
        print(f"❌ 下载错误: {e}")
        return None, None


def download_audio_with_ytdlp(bv_number, output_dir):
    """
    使用 yt-dlp 下载音频（备用方案）
    
    返回:
        (音频路径, 视频标题) 或 (None, None)
    """
    video_url = f"https://www.bilibili.com/video/{bv_number}"
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
    
    print(f"📥 使用 yt-dlp 下载: {video_url}")
    
    try:
        result = subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "mp3", 
             "--no-check-certificate",  # 跳过 SSL 验证
             "-o", output_template, video_url],
            capture_output=True, text=True, timeout=300
        )
        
        if result.returncode == 0:
            # 清理 xml 文件
            xml_files = glob.glob(os.path.join(output_dir, "*.xml"))
            for xml_file in xml_files:
                os.remove(xml_file)
            
            return find_audio_file(output_dir)
        else:
            print(f"❌ yt-dlp 下载失败")
            return None, None
            
    except FileNotFoundError:
        print("❌ yt-dlp 未安装")
        return None, None
    except subprocess.TimeoutExpired:
        print("❌ yt-dlp 下载超时")
        return None, None
    except Exception as e:
        print(f"❌ yt-dlp 错误: {e}")
        return None, None


def find_audio_file(output_dir):
    """
    在目录中查找音频文件
    
    返回:
        (文件路径, 标题) 或 (None, None)
    """
    # 按优先级查找音频格式
    for ext in ['*.m4a', '*.mp3', '*.aac', '*.wav', '*.opus', '*.flac']:
        audio_files = glob.glob(os.path.join(output_dir, ext))
        if audio_files:
            audio_path = audio_files[0]
            title = os.path.splitext(os.path.basename(audio_path))[0]
            return audio_path, title
    
    return None, None


def download_audio_only(bv_number):
    """
    下载 B 站视频的音频（多源：原生 API 优先，yt-dlp 备用）
    
    参数:
        bv_number: BV 号（支持带或不带 "BV" 前缀）
    返回:
        (音频文件路径, 视频标题) 元组，失败返回 (None, None)
    """
    # 标准化 BV 号
    if not bv_number.startswith("BV"):
        bv_number = "BV" + bv_number
    
    output_dir = f"bilibili_video/{bv_number}"
    ensure_folders_exist(output_dir)
    
    # 方案1: 优先使用原生 API（更稳定）
    audio_path, title = download_audio_native(bv_number, output_dir)
    if audio_path:
        return audio_path, title
    
    # 方案2: 原生 API 失败，尝试 yt-dlp
    print("\n⚠️  原生下载失败，尝试备用方案 yt-dlp...")
    audio_path, title = download_audio_with_ytdlp(bv_number, output_dir)
    if audio_path:
        return audio_path, title
    
    # 都失败了
    print("\n❌ 所有下载方案均失败")
    print("💡 建议:")
    print("   1. 检查网络连接")
    print("   2. 确认 BV 号是否正确")
    print("   3. 部分视频可能需要登录观看")
    
    return None, None


def download_video(bv_number):
    """
    下载 B 站视频（用于 Whisper 模式）
    
    参数:
        bv_number: BV号（不含"BV"前缀）或完整BV号
    返回:
        BV号
    """
    if not bv_number.startswith("BV"):
        bv_number = "BV" + bv_number
    
    video_url = f"https://www.bilibili.com/video/{bv_number}"
    output_dir = f"bilibili_video/{bv_number}"
    ensure_folders_exist(output_dir)
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
    
    print(f"📥 下载视频: {video_url}")
    
    try:
        result = subprocess.run(
            ["yt-dlp", "--no-check-certificate", "-o", output_template, video_url],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("下载失败:", result.stderr)
        else:
            print(f"✓ 视频已下载到: {output_dir}")
            # 删除弹幕文件
            xml_files = glob.glob(os.path.join(output_dir, "*.xml"))
            for xml_file in xml_files:
                os.remove(xml_file)
    except Exception as e:
        print("发生错误:", str(e))
    
    return bv_number
