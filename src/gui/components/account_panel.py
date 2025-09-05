# src/gui/components/account_panel.py
"""
계정 관리 패널 컴포넌트
"""
import tkinter as tk
from tkinter import ttk
from ..dialogs.account_management import add_account, remove_account, remove_session, save_new_account


class AccountPanel:
    """계정 관리 패널 클래스"""
    
    def __init__(self, root, config, loaded_accounts):
        self.root = root
        self.config = config
        self.loaded_accounts = loaded_accounts
        self.accounts_listbox = None
        self.account_scrollbar = None
        self.account_buttons_frame = None
        self.append_status_func = None
        
    def set_append_status_func(self, append_status_func):
        """상태 메시지 함수 설정"""
        self.append_status_func = append_status_func
        
    def create_account_frame(self, top_frame):
        """계정 정보 프레임 생성"""
        account_frame = ttk.LabelFrame(top_frame, text="계정 정보", padding=5)
        account_frame.grid(row=0, column=0, padx=(0, 10), pady=5, sticky='nsew')
        account_frame.columnconfigure(0, weight=1)
        account_frame.rowconfigure(0, weight=1)
        
        # 계정 목록
        self.accounts_listbox = tk.Listbox(account_frame, height=3, font=('Arial', 10))
        self.accounts_listbox.grid(row=0, column=0, sticky='nsew', padx=(0,5), pady=5)
        self.account_scrollbar = ttk.Scrollbar(account_frame, orient="vertical", command=self.accounts_listbox.yview)
        self.account_scrollbar.grid(row=0, column=1, sticky='ns')
        self.accounts_listbox.config(yscrollcommand=self.account_scrollbar.set)
        
        # 계정 버튼 프레임
        self.account_buttons_frame = ttk.Frame(account_frame)
        self.account_buttons_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky='ew')
        self.account_buttons_frame.columnconfigure(0, weight=1)
        self.account_buttons_frame.columnconfigure(1, weight=1)
        self.account_buttons_frame.columnconfigure(2, weight=1)
        
        self._create_account_buttons()
        self._load_accounts()
        
        return account_frame
    
    def _create_account_buttons(self):
        """계정 관리 버튼 생성"""
        add_account_btn = ttk.Button(self.account_buttons_frame, text="계정 추가", 
                                    command=self._add_account_wrapper, width=8)
        add_account_btn.grid(row=0, column=0, padx=5, pady=2, sticky='ew')
        
        remove_account_btn = ttk.Button(self.account_buttons_frame, text="계정 제거", 
                                       command=self._remove_account_wrapper, width=8)
        remove_account_btn.grid(row=0, column=1, padx=5, pady=2, sticky='ew')
        
        remove_session_btn = ttk.Button(self.account_buttons_frame, text="세션 삭제", 
                                       command=self._remove_session_wrapper, width=8)
        remove_session_btn.grid(row=0, column=2, padx=5, pady=2, sticky='ew')
    
    def _load_accounts(self):
        """저장된 계정 목록 로드"""
        self.accounts_listbox.delete(0, tk.END)
        for account in self.loaded_accounts:
            if isinstance(account, dict):
                username = account.get('INSTAGRAM_USERNAME', 'Unknown')
                self.accounts_listbox.insert(tk.END, username)
            else:
                self.accounts_listbox.insert(tk.END, str(account))
    
    def _add_account_wrapper(self):
        """계정 추가 래퍼 함수"""
        if self.append_status_func:
            add_account(self.accounts_listbox, self.loaded_accounts, self.append_status_func)
        else:
            add_account(self.accounts_listbox, self.loaded_accounts, lambda x: None)
        self._load_accounts()  # 목록 새로고침
    
    def _remove_account_wrapper(self):
        """계정 삭제 래퍼 함수"""
        if self.append_status_func:
            remove_account(self.accounts_listbox, self.loaded_accounts, self.append_status_func)
        else:
            remove_account(self.accounts_listbox, self.loaded_accounts, lambda x: None)
        self._load_accounts()  # 목록 새로고침
    
    def _remove_session_wrapper(self):
        """세션 삭제 래퍼 함수"""
        if self.append_status_func:
            remove_session(self.append_status_func, self.accounts_listbox)
        else:
            remove_session(lambda x: None, self.accounts_listbox)
    
    def get_accounts(self):
        """현재 계정 목록 반환"""
        # loaded_accounts에서 실제 계정 정보 반환
        return self.loaded_accounts
    
    def refresh_accounts(self):
        """계정 목록 새로고침"""
        self._load_accounts()
