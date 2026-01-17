import os
import re
import subprocess
import glob  # 新增导入

def ensure_folders_exist(output_dir):
    if not os.path.exists("bilibili_video"):
        os.makedirs("bilibili_video")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.path.exists("outputs"):
        os.makedirs("outputs")

def download_video(bv_number):
    """
    使用yt-dlp下载B站视频。
    参数:
        bv_number: 字符串形式的BV号（不含"BV"前缀）或完整BV号
    返回:
        BV号
    """
    if not bv_number.startswith("BV"):
        bv_number = "BV" + bv_number
    video_url = f"https://www.bilibili.com/video/{bv_number}"
    output_dir = f"bilibili_video/{bv_number}"
    ensure_folders_exist(output_dir)
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
    print(f"使用yt-dlp下载视频: {video_url}")
    try:
        result = subprocess.run(
            ["yt-dlp", "-o", output_template, video_url],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("下载失败:", result.stderr)
        else:
            print(result.stdout)
            print(f"视频已成功下载到目录: {output_dir}")
            # 删除xml/danmaku文件
            xml_files = glob.glob(os.path.join(output_dir, "*.xml"))
            for xml_file in xml_files:
                os.remove(xml_file)
    except Exception as e:
        print("发生错误:", str(e))
    return bv_number

def download_audio_only(bv_number):
    """
    只下载音频（用于讯飞模式，跳过视频下载）
    
    参数:
        bv_number: BV号
    返回:
        音频文件路径
    """
    if not bv_number.startswith("BV"):
        bv_number = "BV" + bv_number
    video_url = f"https://www.bilibili.com/video/{bv_number}"
    output_dir = f"bilibili_video/{bv_number}"
    ensure_folders_exist(output_dir)
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
    
    print(f"使用yt-dlp下载音频: {video_url}")
    try:
        result = subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "mp3", "-o", output_template, video_url],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("下载失败:", result.stderr)
            return None
        else:
            print(result.stdout)
            print(f"音频已成功下载到目录: {output_dir}")
            # 删除xml文件
            xml_files = glob.glob(os.path.join(output_dir, "*.xml"))
            for xml_file in xml_files:
                os.remove(xml_file)
            # 找到下载的音频文件
            audio_files = glob.glob(os.path.join(output_dir, "*.mp3"))
            if audio_files:
                return audio_files[0]
            # 也检查其他音频格式
            for ext in ['*.m4a', '*.aac', '*.wav', '*.opus']:
                audio_files = glob.glob(os.path.join(output_dir, ext))
                if audio_files:
                    return audio_files[0]
    except Exception as e:
        print("发生错误:", str(e))
    return None
