# src/gui/components/status_panel.py
"""
상태 메시지 패널 컴포넌트
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime


class StatusPanel:
    """상태 메시지 패널 클래스"""
    
    def __init__(self, parent):
        self.parent = parent
        self.status_text = None
        
    def create_status_frame(self, root):
        """상태 메시지 프레임 생성"""
        status_frame = ttk.LabelFrame(root, text="상태", padding=3)
        status_frame.grid(row=7, column=0, padx=10, pady=5, sticky='nsew')
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)
        
        # 스크롤바가 있는 텍스트 위젯 생성
        text_frame = ttk.Frame(status_frame)
        text_frame.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        self.status_text = tk.Text(text_frame, height=15, font=('Arial', 9), state='disabled', wrap='word')
        self.status_text.grid(row=0, column=0, sticky='nsew')
        
        # 스크롤바 추가
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.status_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.status_text.config(yscrollcommand=scrollbar.set)
        
        return status_frame
    
    def append_status(self, message):
        """상태 메시지 추가"""
        def append():
            self.status_text.config(state='normal')
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.status_text.see(tk.END)
            self.status_text.config(state='disabled')
        
        # GUI 스레드에서 실행
        self.parent.after(0, append)
    
    def clear_status(self):
        """상태 메시지 초기화"""
        def clear():
            self.status_text.config(state='normal')
            self.status_text.delete(1.0, tk.END)
            self.status_text.config(state='disabled')
        
        self.parent.after(0, clear)
