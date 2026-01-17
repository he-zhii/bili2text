# -*- coding: utf-8 -*-
"""
Bili2Text 终端入口
默认：输入BV号 → 讯飞转写
可选：本地文件、Whisper引擎
"""
import os
import subprocess

def convert_to_mp3_if_needed(file_path):
    """如果文件不是讯飞支持的格式，转换为MP3"""
    supported_formats = ['.mp3', '.wav', '.m4a', '.aac', '.mp4', '.flac', '.ogg', '.wma']
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in supported_formats:
        return file_path
    
    output_path = os.path.splitext(file_path)[0] + '.mp3'
    print(f"正在转换格式: {ext} -> mp3")
    result = subprocess.run(
        ['ffmpeg', '-y', '-i', file_path, '-c:a', 'libmp3lame', '-q:a', '2', output_path],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return output_path
    else:
        print(f"转换失败: {result.stderr}")
        return None

def main():
    print("=" * 50)
    print("       Bili2Text - B站视频转文字工具")
    print("=" * 50)
    
    # 直接输入BV号（默认流程）
    print("\n直接输入BV号开始转写，或输入以下命令：")
    print("  local  - 使用本地文件")
    print("  whisper - 切换到Whisper引擎")
    
    user_input = input("\nBV号或命令: ").strip()
    
    # 判断用户输入
    use_local_file = (user_input.lower() == 'local')
    use_whisper = (user_input.lower() == 'whisper')
    
    if use_local_file:
        file_path = input("请输入文件路径: ").strip().strip('"').strip("'")
        file_identifier = os.path.splitext(os.path.basename(file_path))[0]
        bv_number = None
    elif use_whisper:
        # Whisper模式
        bv_input = input("请输入BV号: ").strip()
        import re
        pattern = r'BV[A-Za-z0-9]+'
        matches = re.findall(pattern, bv_input)
        bv_number = matches[0] if matches else ("BV" + bv_input if not bv_input.startswith("BV") else bv_input)
        file_identifier = bv_number
        file_path = None
    else:
        # 默认：BV号 + 讯飞
        import re
        pattern = r'BV[A-Za-z0-9]+'
        matches = re.findall(pattern, user_input)
        if matches:
            bv_number = matches[0]
        elif user_input.startswith("BV"):
            bv_number = user_input
        else:
            bv_number = "BV" + user_input
        file_identifier = bv_number
        file_path = None
    
    print(f"\n识别: {file_identifier}")
    
    # ========== 讯飞模式（默认） ==========
    if not use_whisper:
        from xunfei import transcribe_audio_direct
        
        if use_local_file:
            audio_path = convert_to_mp3_if_needed(file_path)
            if not audio_path:
                print("❌ 文件处理失败")
                return
        else:
            from utils import download_audio_only
            print("正在下载...")
            audio_path = download_audio_only(bv_number)
            if not audio_path:
                print("❌ 下载失败")
                return
        
        output_path = transcribe_audio_direct(audio_path, output_name=file_identifier)
    
    # ========== Whisper模式 ==========
    else:
        from utils import download_video
        from exAudio import process_audio_split
        from speech2text import load_whisper, run_analysis, is_cuda_available
        
        model = input("\nWhisper模型 (tiny/small/medium/large, 默认small): ").strip() or "small"
        
        print(f"正在加载Whisper ({model})...")
        load_whisper(model)
        
        print("正在下载...")
        file_identifier = download_video(bv_number[2:] if bv_number.startswith("BV") else bv_number)
        
        print("正在处理音频...")
        folder_name = process_audio_split(file_identifier)
        
        print("正在转写，请稍候...")
        run_analysis(folder_name, prompt="以下是普通话的句子。")
        output_path = f"outputs/{folder_name}.txt"
    
    # 最终结果
    if output_path:
        print(f"\n✅ 完成！文件已保存: {output_path}")
    else:
        print("\n❌ 转写失败")

if __name__ == "__main__":
    main()
