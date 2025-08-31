# crawling/gui_account_management.py
"""
계정 관리 관련 함수들을 모아놓은 모듈
기존 gui.py의 UI는 그대로 두고 내부 로직만 분리
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from crawling.config import load_config, save_config

def add_account(accounts_listbox, loaded_accounts, append_status_func):
    """
    계정을 추가합니다.
    """
    dialog = tk.Toplevel()
    dialog.title("계정 추가")
    dialog.geometry("400x300")
    dialog.transient()
    dialog.grab_set()
    
    # 중앙 정렬
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(0, weight=1)
    
    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    main_frame.columnconfigure(1, weight=1)
    
    # 사용자명
    ttk.Label(main_frame, text="인스타그램 사용자명:").grid(row=0, column=0, sticky=tk.W, pady=5)
    username_var = tk.StringVar()
    username_entry = ttk.Entry(main_frame, textvariable=username_var)
    username_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
    
    # 비밀번호
    ttk.Label(main_frame, text="비밀번호:").grid(row=1, column=0, sticky=tk.W, pady=5)
    password_var = tk.StringVar()
    password_entry = ttk.Entry(main_frame, textvariable=password_var, show="*")
    password_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
    
    # 다운로드 경로
    ttk.Label(main_frame, text="다운로드 경로:").grid(row=2, column=0, sticky=tk.W, pady=5)
    download_path_var = tk.StringVar()
    download_path_entry = ttk.Entry(main_frame, textvariable=download_path_var)
    download_path_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
    
    # 경로 선택 버튼
    def select_path():
        path = filedialog.askdirectory()
        if path:
            download_path_var.set(path)
    
    ttk.Button(main_frame, text="경로 선택", command=select_path).grid(row=2, column=2, padx=(10, 0))
    
    # 저장 버튼
    def save():
        username = username_var.get().strip()
        password = password_var.get().strip()
        download_path = download_path_var.get().strip()
        
        if not username or not password:
            messagebox.showerror("오류", "사용자명과 비밀번호를 입력하세요.")
            return
        
        if not download_path:
            messagebox.showerror("오류", "다운로드 경로를 선택하세요.")
            return
        
        # 중복 확인
        for acc in loaded_accounts:
            if acc['INSTAGRAM_USERNAME'] == username:
                messagebox.showerror("오류", "이미 존재하는 사용자명입니다.")
                return
        
        # 새 계정 추가
        new_account = {
            'INSTAGRAM_USERNAME': username,
            'INSTAGRAM_PASSWORD': password,
            'DOWNLOAD_PATH': download_path
        }
        loaded_accounts.append(new_account)
        
        # 리스트박스에 추가
        accounts_listbox.insert(tk.END, username)
        
        # 설정 저장
        config = load_config()
        config['ACCOUNTS'] = loaded_accounts
        save_config(config)
        
        append_status_func(f"계정 추가됨: {username}")
        dialog.destroy()
    
    ttk.Button(main_frame, text="저장", command=save).grid(row=3, column=0, columnspan=3, pady=20)
    
    # 포커스 설정
    username_entry.focus()

def remove_account(accounts_listbox, loaded_accounts, append_status_func):
    """
    선택된 계정을 제거합니다.
    """
    selection = accounts_listbox.curselection()
    if not selection:
        append_status_func("오류: 제거할 계정을 선택하세요.")
        return
    
    index = selection[0]
    username = accounts_listbox.get(index)
    
    result = messagebox.askyesno("확인", f"계정 '{username}'을(를) 제거하시겠습니까?")
    if not result:
        return
    
    # 계정 제거
    del loaded_accounts[index]
    accounts_listbox.delete(index)
    
    # 설정 저장
    config = load_config()
    config['ACCOUNTS'] = loaded_accounts
    save_config(config)
    
    append_status_func(f"계정 제거됨: {username}")

def remove_session(append_status_func):
    """
    세션 파일을 제거합니다.
    """
    session_dir = os.path.join(os.path.dirname(__file__), 'sessions')
    if os.path.exists(session_dir):
        try:
            import shutil
            shutil.rmtree(session_dir)
            append_status_func("세션 파일이 제거되었습니다.")
        except Exception as e:
            append_status_func(f"세션 파일 제거 중 오류: {e}")
    else:
        append_status_func("세션 파일이 존재하지 않습니다.")

def save_new_account(dialog, username_var, password_var, download_path_var, accounts_listbox, loaded_accounts, append_status_func):
    """
    새 계정을 저장합니다.
    """
    username = username_var.get().strip()
    password = password_var.get().strip()
    download_path = download_path_var.get().strip()
    
    if not username or not password:
        messagebox.showerror("오류", "사용자명과 비밀번호를 입력하세요.")
        return
    
    if not download_path:
        messagebox.showerror("오류", "다운로드 경로를 선택하세요.")
        return
    
    # 중복 확인
    for acc in loaded_accounts:
        if acc['INSTAGRAM_USERNAME'] == username:
            messagebox.showerror("오류", "이미 존재하는 사용자명입니다.")
            return
    
    # 새 계정 추가
    new_account = {
        'INSTAGRAM_USERNAME': username,
        'INSTAGRAM_PASSWORD': password,
        'DOWNLOAD_PATH': download_path
    }
    loaded_accounts.append(new_account)
    
    # 리스트박스에 추가
    accounts_listbox.insert(tk.END, username)
    
    # 설정 저장
    config = load_config()
    config['ACCOUNTS'] = loaded_accounts
    save_config(config)
    
    append_status_func(f"계정 추가됨: {username}")
    if dialog:
        dialog.destroy()
