# -*- coding: utf-8 -*-
"""
终端进度条工具
风格：[=========>          ] 45% (2.3MB/5.1MB)
"""
import sys
import time


class ProgressBar:
    """
    Linux 风格进度条
    [=========>          ] 45% 下载中...
    """
    
    def __init__(self, total, width=40, prefix="进度"):
        self.total = total
        self.width = width
        self.prefix = prefix
        self.current = 0
        self.start_time = time.time()
    
    def update(self, current, suffix=""):
        """更新进度"""
        self.current = current
        percent = current / self.total if self.total > 0 else 0
        filled = int(self.width * percent)
        
        # 构建进度条：[=========>          ]
        if filled < self.width:
            bar = "=" * filled + ">" + " " * (self.width - filled - 1)
        else:
            bar = "=" * self.width
        
        # 计算速度和剩余时间
        elapsed = time.time() - self.start_time
        speed = current / elapsed if elapsed > 0 else 0
        
        sys.stdout.write(f"\r{self.prefix}: [{bar}] {percent*100:.0f}% {suffix}")
        sys.stdout.flush()
        
        if current >= self.total:
            print()  # 完成后换行
    
    def increment(self, amount=1, suffix=""):
        """增量更新"""
        self.update(self.current + amount, suffix)
    
    def finish(self, message="完成"):
        """完成进度条"""
        self.update(self.total, message)


class SpinnerProgress:
    """
    等待中的旋转动画
    ⠋ 等待转写中... 已等待 30s
    """
    CHARS = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    
    def __init__(self, message="处理中"):
        self.message = message
        self.idx = 0
        self.start_time = time.time()
    
    def spin(self, extra=""):
        """显示旋转动画"""
        char = self.CHARS[self.idx % len(self.CHARS)]
        elapsed = int(time.time() - self.start_time)
        sys.stdout.write(f"\r{char} {self.message}... {extra} (已等待 {elapsed}s)")
        sys.stdout.flush()
        self.idx += 1
    
    def done(self, message="完成"):
        """完成动画"""
        sys.stdout.write(f"\r✓ {message}                              \n")
        sys.stdout.flush()


class DownloadProgress:
    """
    下载进度回调（用于 yt-dlp）
    [=========>          ] 45% 2.3MB/5.1MB 1.2MB/s
    """
    
    def __init__(self):
        self.bar = None
    
    def hook(self, d):
        """yt-dlp 进度回调钩子"""
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0) or 0
            
            if total > 0:
                if self.bar is None:
                    self.bar = ProgressBar(total, prefix="下载中")
                
                # 格式化大小
                def fmt_size(b):
                    if b < 1024:
                        return f"{b}B"
                    elif b < 1024 * 1024:
                        return f"{b/1024:.1f}KB"
                    else:
                        return f"{b/(1024*1024):.1f}MB"
                
                speed_str = f"{fmt_size(speed)}/s" if speed else ""
                suffix = f"{fmt_size(downloaded)}/{fmt_size(total)} {speed_str}"
                self.bar.update(downloaded, suffix)
        
        elif d['status'] == 'finished':
            if self.bar:
                self.bar.finish("下载完成")
            else:
                print("✓ 下载完成")


def format_size(bytes_size):
    """格式化文件大小"""
    if bytes_size < 1024:
        return f"{bytes_size}B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size/1024:.1f}KB"
    else:
        return f"{bytes_size/(1024*1024):.1f}MB"
