# -*- coding: utf-8 -*-
"""
临时文件清理工具
转写完成后自动清理下载的音视频文件
"""
import os
import shutil


def cleanup_audio_file(audio_path):
    """删除单个音频文件"""
    if audio_path and os.path.exists(audio_path):
        try:
            os.remove(audio_path)
            print(f"🗑️  已清理: {os.path.basename(audio_path)}")
            return True
        except Exception as e:
            print(f"⚠️  清理失败: {e}")
            return False
    return False


def cleanup_bv_folder(bv_number):
    """删除整个 BV 号下载文件夹"""
    if not bv_number:
        return False
    
    folder = f"bilibili_video/{bv_number}"
    if os.path.exists(folder):
        try:
            shutil.rmtree(folder)
            print(f"🗑️  已清理目录: {folder}")
            return True
        except Exception as e:
            print(f"⚠️  清理目录失败: {e}")
            return False
    return False


def cleanup_temp_audio():
    """清理 audio/conv 和 audio/slice 临时目录"""
    cleaned = False
    for folder in ['audio/conv', 'audio/slice']:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                os.makedirs(folder, exist_ok=True)  # 重建空目录
                print(f"🗑️  已清理: {folder}")
                cleaned = True
            except Exception as e:
                print(f"⚠️  清理失败 {folder}: {e}")
    return cleaned


def cleanup_all():
    """清理所有临时文件（bilibili_video/ 和 audio/）"""
    cleaned = []
    
    for folder in ['bilibili_video', 'audio/conv', 'audio/slice']:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                cleaned.append(folder)
            except Exception as e:
                print(f"⚠️  清理失败 {folder}: {e}")
    
    if cleaned:
        print(f"🗑️  已清理所有临时文件: {', '.join(cleaned)}")
    
    return len(cleaned) > 0


def get_temp_size():
    """获取临时文件总大小"""
    total = 0
    for folder in ['bilibili_video', 'audio']:
        if os.path.exists(folder):
            for root, dirs, files in os.walk(folder):
                for f in files:
                    total += os.path.getsize(os.path.join(root, f))
    return total
