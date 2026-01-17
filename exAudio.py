from moviepy.editor import VideoFileClip
from pydub import AudioSegment
import os
import time
import subprocess

def check_video_integrity(file_path):
    """使用 FFmpeg 验证视频文件完整性"""
    result = subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', file_path, '-f', 'null', '-'],
        stderr=subprocess.PIPE,
        text=True
    )
    if result.stderr:
        print(f"视频文件可能损坏: {file_path}")
        print(f"FFmpeg 错误信息: {result.stderr}")
        return False
    return True

def convert_m4s_to_mp3(input_path, output_path):
    """使用 FFmpeg 将 M4S 文件转换为 MP3"""
    print(f"正在转换 M4S 文件: {input_path}")
    result = subprocess.run(
        ['ffmpeg', '-y', '-i', input_path, '-c:a', 'libmp3lame', '-q:a', '2', output_path],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"FFmpeg 转换失败: {result.stderr}")
        return False
    print(f"M4S 转换成功: {output_path}")
    return True

def convert_flv_to_mp3(name, target_name=None, folder='bilibili_video'):
    import shutil
    input_path = None
    is_audio = False
    is_m4s = False
    
    # 先尝试直接拼接 .mp4
    direct_path = f'{folder}/{name}.mp4'
    if os.path.exists(direct_path):
        input_path = direct_path
    else:
        # 如果不存在，尝试在文件夹下查找媒体文件
        dir_path = f'{folder}/{name}'
        if os.path.isdir(dir_path):
            # 先查找音频文件（优先）
            for file in os.listdir(dir_path):
                if file.endswith(('.mp3', '.m4a', '.aac', '.wav')):
                    input_path = os.path.join(dir_path, file)
                    is_audio = True
                    break
            # 查找 M4S 文件
            if not input_path:
                for file in os.listdir(dir_path):
                    if file.endswith('.m4s'):
                        input_path = os.path.join(dir_path, file)
                        is_m4s = True
                        break
            # 再查找视频文件
            if not input_path:
                for file in os.listdir(dir_path):
                    if file.endswith(('.mp4', '.flv', '.mkv', '.avi', '.webm')):
                        input_path = os.path.join(dir_path, file)
                        break
            if not input_path:
                raise FileNotFoundError(f"目录下未找到媒体文件: {dir_path}")
        else:
            raise FileNotFoundError(f"视频文件不存在: {direct_path}")
    
    os.makedirs("audio/conv", exist_ok=True)
    output_name = target_name if target_name else name
    output_path = f"audio/conv/{output_name}.mp3"
    
    if is_m4s:
        # M4S 文件需要用 FFmpeg 转换
        if not convert_m4s_to_mp3(input_path, output_path):
            raise ValueError(f"M4S 文件转换失败: {input_path}")
    elif is_audio:
        # 如果是音频文件，直接复制
        print(f"检测到音频文件，直接复制: {input_path}")
        shutil.copy2(input_path, output_path)
    else:
        # 如果是视频文件，提取音频
        if not check_video_integrity(input_path):
            raise ValueError(f"视频文件损坏: {input_path}")
        clip = VideoFileClip(input_path)
        audio = clip.audio
        audio.write_audiofile(output_path)
        clip.close()

def split_mp3(filename, folder_name, slice_length=45000, target_folder="audio/slice"):
    audio = AudioSegment.from_mp3(filename)
    total_slices = (len(audio)+ slice_length - 1) // slice_length
    target_dir = os.path.join(target_folder, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    for i in range(total_slices):
        start = i * slice_length
        end = start + slice_length
        slice_audio = audio[start:end]
        slice_path = os.path.join(target_dir, f"{i+1}.mp3")
        slice_audio.export(slice_path, format="mp3")
        print(f"Slice {i+1} saved: {slice_path}")

def process_audio_split(name, folder='bilibili_video'):
    """处理音频分割，支持指定文件夹"""
    folder_name = time.strftime('%Y%m%d%H%M%S')
    convert_flv_to_mp3(name, target_name=folder_name, folder=folder)
    conv_path = f"audio/conv/{folder_name}.mp3"
    if not os.path.exists(conv_path):
        raise FileNotFoundError(f"转换后的音频文件不存在: {conv_path}")
    split_mp3(conv_path, folder_name)
    return folder_name

def process_local_file(file_path):
    """
    处理本地文件（支持 mp4, mp3, m4s 等格式）
    
    参数:
        file_path: 本地文件的完整路径
    返回:
        folder_name: 切片文件夹名
    """
    import shutil
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    folder_name = time.strftime('%Y%m%d%H%M%S')
    os.makedirs("audio/conv", exist_ok=True)
    output_path = f"audio/conv/{folder_name}.mp3"
    
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.m4s':
        # M4S 文件用 FFmpeg 转换
        if not convert_m4s_to_mp3(file_path, output_path):
            raise ValueError(f"M4S 文件转换失败: {file_path}")
    elif file_ext in ['.mp3']:
        # MP3 直接复制
        print(f"检测到 MP3 文件，直接复制: {file_path}")
        shutil.copy2(file_path, output_path)
    elif file_ext in ['.m4a', '.aac', '.wav', '.flac']:
        # 其他音频格式用 FFmpeg 转换
        print(f"正在转换音频文件: {file_path}")
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', file_path, '-c:a', 'libmp3lame', '-q:a', '2', output_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise ValueError(f"音频转换失败: {result.stderr}")
    elif file_ext in ['.mp4', '.flv', '.mkv', '.avi', '.webm']:
        # 视频文件提取音频
        print(f"正在从视频提取音频: {file_path}")
        clip = VideoFileClip(file_path)
        audio = clip.audio
        audio.write_audiofile(output_path)
        clip.close()
    else:
        raise ValueError(f"不支持的文件格式: {file_ext}")
    
    # 分割音频
    if not os.path.exists(output_path):
        raise FileNotFoundError(f"转换后的音频文件不存在: {output_path}")
    
    split_mp3(output_path, folder_name)
    print(f"本地文件处理完成，切片文件夹: audio/slice/{folder_name}")
    return folder_name


