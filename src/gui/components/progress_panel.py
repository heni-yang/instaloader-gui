# src/gui/components/progress_panel.py
"""
진행률 표시 패널 컴포넌트
"""
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta


class ProgressPanel:
    """진행률 표시 패널 클래스"""
    
    def __init__(self, parent):
        self.parent = parent
        self.progress_bar = None
        self.progress_label = None
        self.eta_label = None
        self.start_time = None
        
    def create_progress_frame(self, root):
        """진행률 프레임 생성"""
        progress_frame = ttk.LabelFrame(root, text="진행률", padding=5)
        progress_frame.grid(row=5, column=0, padx=10, pady=5, sticky='ew')
        progress_frame.columnconfigure(0, weight=1)
        
        # 진행률 표시
        progress_display_frame = ttk.Frame(progress_frame)
        progress_display_frame.grid(row=0, column=0, sticky='ew', pady=(0, 5))
        progress_display_frame.columnconfigure(1, weight=1)
        
        ttk.Label(progress_display_frame, text="진행률:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.progress_bar = ttk.Progressbar(progress_display_frame, mode='determinate', length=300)
        self.progress_bar.grid(row=0, column=1, sticky='ew', padx=(0, 5))
        self.progress_label = ttk.Label(progress_display_frame, text="0/0")
        self.progress_label.grid(row=0, column=2, sticky='w')
        
        # ETA 표시
        eta_frame = ttk.Frame(progress_frame)
        eta_frame.grid(row=1, column=0, sticky='ew')
        eta_frame.columnconfigure(0, weight=1)
        
        self.eta_label = ttk.Label(eta_frame, text="예상 완료 시간: --:--:--")
        self.eta_label.grid(row=0, column=0, sticky='w')
        
        return progress_frame
    
    def update_progress(self, current, total, current_term=""):
        """진행률 업데이트"""
        if total > 0:
            progress_percent = (current / total) * 100
            self.progress_bar['value'] = progress_percent
            
            if current_term:
                self.progress_label.config(text=f"{current}/{total} ({current_term})")
            else:
                self.progress_label.config(text=f"{current}/{total}")
    
    def reset_progress(self):
        """진행률 초기화"""
        self.progress_bar['value'] = 0
        self.progress_label.config(text="0/0")
        self.eta_label.config(text="예상 완료 시간: --:--:--")
        self.start_time = None
    
    def update_eta(self, start_time, current, total):
        """예상 완료 시간 업데이트"""
        if not start_time or total <= 0 or current <= 0:
            return
        
        elapsed_time = datetime.now() - start_time
        if current > 0:
            avg_time_per_item = elapsed_time / current
            remaining_items = total - current
            estimated_remaining_time = avg_time_per_item * remaining_items
            estimated_completion_time = datetime.now() + estimated_remaining_time
            
            eta_str = estimated_completion_time.strftime("%H:%M:%S")
            self.eta_label.config(text=f"예상 완료 시간: {eta_str}")
    
    def set_start_time(self, start_time):
        """시작 시간 설정"""
        self.start_time = start_time
