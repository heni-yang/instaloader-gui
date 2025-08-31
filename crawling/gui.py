# crawling/gui.py
import os
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from queue import Queue, Empty
from datetime import datetime
import configparser
import subprocess
import shutil

from crawling.config import load_config, save_config
from crawling.downloader import crawl_and_download
from crawling.post_processing import process_images
from crawling.utils import create_dir_if_not_exists

# 프로젝트 루트 및 기본 다운로드 경로 설정
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
DEFAULT_DOWNLOAD_PATH = os.path.join(PROJECT_ROOT, 'download')
SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')

def main_gui():
    """
    인스타그램 크롤러 및 분류 프로그램의 GUI를 생성 및 실행합니다.
    """
    print("GUI 시작...")
    root = tk.Tk()
    root.title("인스타그램 이미지 크롤링 프로그램 (Instaloader 기반)")
    root.geometry("900x1100")
    root.minsize(900, 1100)
    root.columnconfigure(0, weight=1)

    # 스타일 설정
    style = ttk.Style(root)
    style.configure('TButton', font=('Arial', 10))
    style.configure('TLabel', font=('Arial', 10))
    style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

    header = ttk.Label(root, text="인스타그램 이미지 크롤링 프로그램", style='Header.TLabel')
    header.grid(row=0, column=0, pady=10, padx=10, sticky='ew')

    # 상단 프레임: 계정 정보 및 검색 유형 선택
    top_frame = ttk.Frame(root)
    top_frame.grid(row=1, column=0, padx=10, pady=5, sticky='ew')
    top_frame.columnconfigure(0, weight=1)
    top_frame.columnconfigure(1, weight=1)

    # 계정 정보 영역
    account_frame = ttk.LabelFrame(top_frame, text="계정 정보", padding=5)
    account_frame.grid(row=0, column=0, padx=(0, 10), pady=5, sticky='nsew')
    account_frame.columnconfigure(0, weight=1)
    account_frame.rowconfigure(0, weight=1)

    accounts_listbox = tk.Listbox(account_frame, height=3, font=('Arial', 10))
    accounts_listbox.grid(row=0, column=0, sticky='nsew', padx=(0,5), pady=5)
    account_scrollbar = ttk.Scrollbar(account_frame, orient="vertical", command=accounts_listbox.yview)
    account_scrollbar.grid(row=0, column=1, sticky='ns')
    accounts_listbox.config(yscrollcommand=account_scrollbar.set)

    account_buttons_frame = ttk.Frame(account_frame)
    account_buttons_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky='ew')
    account_buttons_frame.columnconfigure(0, weight=1)
    account_buttons_frame.columnconfigure(1, weight=1)

    # 설정 로드 및 계정 불러오기
    config = load_config()
    loaded_accounts = config['ACCOUNTS'][:]
    loaded_searchtype = config['LAST_SEARCH_TYPE'][:]
    
    # 마지막 다운로드 경로 불러오기
    last_download_path = config.get('LAST_DOWNLOAD_PATH', DEFAULT_DOWNLOAD_PATH)
    
    # 상태 메시지 출력 영역
    status_frame = ttk.LabelFrame(root, text="상태", padding=3)
    status_frame.grid(row=7, column=0, padx=10, pady=5, sticky='nsew')
    status_frame.columnconfigure(0, weight=1)
    status_frame.rowconfigure(0, weight=1)
    status_text = tk.Text(status_frame, height=12, font=('Arial', 10), state='disabled')
    status_text.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

    def append_status(message):
        """
        상태 텍스트 위젯에 메시지를 추가합니다.
        """
        def append():
            status_text.configure(state='normal')
            status_text.insert(tk.END, message + '\n')
            status_text.see(tk.END)
            status_text.configure(state='disabled')
        root.after(0, append)

    # 리스트박스 항목을 텍스트 위젯에 추가하는 함수들
    def add_items_from_listbox(listbox, text_widget, item_label):
        indices = listbox.curselection()
        items = [listbox.get(i) for i in indices]
        if not items:
            append_status(f"정보: 추가할 {item_label}를 선택하세요.")
            return
        current_text = text_widget.get("1.0", tk.END).strip()
        new_text = "\n".join(items)
        updated_text = current_text + "\n" + new_text if current_text else new_text
        text_widget.delete("1.0", tk.END)
        text_widget.insert(tk.END, updated_text)
        append_status(f"성공: {len(items)}개의 {item_label} 추가됨.")

    def add_all_items_from_listbox(listbox, text_widget, item_label):
        items = listbox.get(0, tk.END)
        if not items:
            append_status(f"정보: 추가할 {item_label}가 없습니다.")
            return
        current_text = text_widget.get("1.0", tk.END).strip()
        new_text = "\n".join(items)
        updated_text = current_text + "\n" + new_text if current_text else new_text
        text_widget.delete("1.0", tk.END)
        text_widget.insert(tk.END, updated_text)
        append_status(f"성공: 모든 {item_label} 추가됨.")

    # 계정 추가/삭제/세션 삭제 함수 (세부 로직 동일)
    def add_account():
        add_window = tk.Toplevel(root)
        add_window.title("계정 추가")
        add_window.geometry("430x250")
        add_window.resizable(False, False)
        ttk.Label(add_window, text="히스토리:").grid(row=0, column=0, sticky='w', pady=(10,2), padx=10)
        history_var = tk.StringVar()
        history_values = [item['username'] for item in config.get('LOGIN_HISTORY', [])]
        history_combo = ttk.Combobox(add_window, textvariable=history_var, values=history_values, state='readonly', width=35)
        history_combo.grid(row=0, column=1, pady=(10,2), padx=10)
        def on_history_select(event):
            selected_username = history_var.get()
            for item in config.get('LOGIN_HISTORY', []):
                if item['username'] == selected_username:
                    new_username_entry.delete(0, tk.END)
                    new_username_entry.insert(0, item['username'])
                    new_password_entry.delete(0, tk.END)
                    new_password_entry.insert(0, item['password'])
                    download_directory_var_add.set(item['download_path'])
                    break
        history_combo.bind("<<ComboboxSelected>>", on_history_select)
        def delete_history():
            selected = history_var.get()
            if not selected:
                append_status("히스토리에서 삭제할 계정을 선택하세요.")
                return
            new_history = [item for item in config.get('LOGIN_HISTORY', []) if item['username'] != selected]
            config['LOGIN_HISTORY'] = new_history
            save_config(config)
            append_status(f"히스토리에서 {selected} 삭제됨.")
            history_combo['values'] = [item['username'] for item in new_history]
            history_var.set("")
        ttk.Button(add_window, text="히스토리 삭제", command=delete_history).grid(row=1, column=1, sticky='e', padx=10, pady=(0,10))
        ttk.Label(add_window, text="아이디:").grid(row=2, column=0, sticky='w', pady=(10,2), padx=10)
        new_username_entry = ttk.Entry(add_window, width=40, font=('Arial', 10))
        new_username_entry.grid(row=2, column=1, pady=(10,10), padx=10)
        ttk.Label(add_window, text="비밀번호:").grid(row=3, column=0, sticky='w', pady=(5,2), padx=10)
        new_password_entry = ttk.Entry(add_window, show="*", width=40, font=('Arial', 10))
        new_password_entry.grid(row=3, column=1, pady=(5,10), padx=10)
        ttk.Label(add_window, text="다운로드 경로:").grid(row=4, column=0, sticky='w', pady=(5,2), padx=10)
        download_dir_frame = ttk.Frame(add_window)
        download_dir_frame.grid(row=4, column=1, pady=(5,10), padx=10, sticky='ew')
        download_directory_var_add = tk.StringVar(value=last_download_path)
        download_dir_entry = ttk.Entry(download_dir_frame, textvariable=download_directory_var_add, width=30, font=('Arial', 10))
        download_dir_entry.pack(side='left', padx=(0,5), fill='x', expand=True)
        def select_download_directory_add():
            directory = filedialog.askdirectory(initialdir=last_download_path)
            if directory:
                download_directory_var_add.set(directory)
        ttk.Button(download_dir_frame, text="경로 선택", command=select_download_directory_add, width=10).pack(side='left')
        def save_new_account():
            username = new_username_entry.get().strip()
            password = new_password_entry.get().strip()
            download_path = download_directory_var_add.get().strip()
            if not username or not password:
                append_status("오류: 아이디와 비밀번호를 입력하세요.")
                return
            accounts_listbox.insert(tk.END, username)
            loaded_accounts.append({
                'INSTAGRAM_USERNAME': username,
                'INSTAGRAM_PASSWORD': password,
                'DOWNLOAD_PATH': download_path
            })
            config['ACCOUNTS'] = loaded_accounts
            found = False
            for item in config.get('LOGIN_HISTORY', []):
                if item['username'] == username:
                    item['password'] = password
                    item['download_path'] = download_path
                    found = True
                    break
            if not found:
                config.setdefault('LOGIN_HISTORY', []).append({
                    'username': username,
                    'password': password,
                    'download_path': download_path
                })
            # 마지막 다운로드 경로 업데이트
            config['LAST_DOWNLOAD_PATH'] = download_path
            save_config(config)
            append_status(f"새로운 계정 {username} 추가됨.")
            add_window.destroy()
            load_existing_directories()
        ttk.Button(add_window, text="추가", command=save_new_account).grid(row=5, column=0, columnspan=2, pady=10)

    def remove_account():
        indices = accounts_listbox.curselection()
        if not indices:
            append_status("오류: 제거할 계정을 선택하세요.")
            return
        for index in reversed(indices):
            username = accounts_listbox.get(index)
            accounts_listbox.delete(index)
            loaded_accounts[:] = [acc for acc in loaded_accounts if acc['INSTAGRAM_USERNAME'] != username]
            config['ACCOUNTS'] = loaded_accounts
            save_config(config)
            append_status(f"계정 {username} 제거됨.")
        load_existing_directories()

    def remove_session():
        selected_indices = accounts_listbox.curselection()
        if not selected_indices:
            append_status("오류: 세션 삭제할 계정 선택하세요.")
            return
        for index in reversed(selected_indices):
            username = accounts_listbox.get(index)
            session_file = os.path.join(SESSION_DIR, f"{username}.session")
            if os.path.isfile(session_file):
                os.remove(session_file)
                append_status(f"{username} 계정 세션 파일 삭제됨.")
            else:
                append_status(f"{username} 계정 세션 파일 없음.")

    add_account_button = ttk.Button(account_buttons_frame, text="계정 추가", command=add_account, width=8)
    add_account_button.grid(row=0, column=0, padx=5, pady=2, sticky='ew')
    remove_account_button = ttk.Button(account_buttons_frame, text="계정 제거", command=remove_account, width=8)
    remove_account_button.grid(row=0, column=1, padx=5, pady=2, sticky='ew')
    remove_session_button = ttk.Button(account_buttons_frame, text="세션 삭제", command=remove_session, width=8)
    remove_session_button.grid(row=0, column=2, padx=5, pady=2, sticky='ew')

    # 검색 유형 및 옵션 영역
    search_type_frame = ttk.LabelFrame(top_frame, text="검색 유형 선택", padding=5)
    search_type_frame.grid(row=0, column=1, padx=(10,0), pady=5, sticky='nsew')
    search_type_frame.columnconfigure(0, weight=1)
    search_type_frame.columnconfigure(1, weight=1)

    search_type_var = tk.StringVar(value="hashtag")
    # 해시태그 검색 영역 (수정된 부분)
    hashtag_frame = ttk.Frame(search_type_frame)
    hashtag_frame.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
    hashtag_frame.columnconfigure(0, weight=1)
    hashtag_frame.columnconfigure(1, weight=1)
    ttk.Radiobutton(hashtag_frame, text="해시태그 검색", variable=search_type_var, value="hashtag")\
        .grid(row=0, column=0, columnspan=2, sticky='w')

    # BooleanVar 변수 생성
    include_images_var_hashtag = tk.BooleanVar(value=True)    
    include_videos_var_hashtag = tk.BooleanVar(value=False)
    include_human_classify_var_hashtag = tk.BooleanVar(value=False)
    upscale_var_hashtag = tk.BooleanVar(value=False)

    # 1행: 이미지, 영상 체크박스
    include_images_check_hashtag = ttk.Checkbutton(hashtag_frame, text="이미지", variable=include_images_var_hashtag)
    include_images_check_hashtag.grid(row=1, column=0, sticky='w', padx=5, pady=2)
    include_videos_check_hashtag = ttk.Checkbutton(hashtag_frame, text="영상", variable=include_videos_var_hashtag)
    include_videos_check_hashtag.grid(row=1, column=1, sticky='w', padx=5, pady=2)

    # 2행: 인물 분류, 업스케일링 체크박스
    include_human_classify_check_hashtag = ttk.Checkbutton(hashtag_frame, text="인물 분류", variable=include_human_classify_var_hashtag)
    include_human_classify_check_hashtag.grid(row=2, column=0, sticky='w', padx=5, pady=2)
    upscale_checkbox_hashtag = ttk.Checkbutton(hashtag_frame, text="업스케일링", variable=upscale_var_hashtag)
    upscale_checkbox_hashtag.grid(row=2, column=1, sticky='w', padx=5, pady=2)
    # 초기에는 인물 분류가 선택되지 않았으므로 업스케일링 체크박스 비활성화
    upscale_checkbox_hashtag.configure(state='disabled')

    # 인물 분류 체크박스 값에 따라 업스케일링 체크박스 활성/비활성 제어
    def toggle_upscale_hashtag(*args):
        if include_human_classify_var_hashtag.get():
            upscale_checkbox_hashtag.configure(state='normal')
        else:
            upscale_var_hashtag.set(False)
            upscale_checkbox_hashtag.configure(state='disabled')
    include_human_classify_var_hashtag.trace_add('write', toggle_upscale_hashtag)


    # 사용자 ID 검색 영역 (수정된 부분)
    user_id_frame = ttk.Frame(search_type_frame)
    user_id_frame.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')
    user_id_frame.columnconfigure(0, weight=1)
    user_id_frame.columnconfigure(1, weight=1)
    ttk.Radiobutton(user_id_frame, text="사용자 ID 검색", variable=search_type_var, value="user")\
        .grid(row=0, column=0, columnspan=2, sticky='w')

    # BooleanVar 변수 생성
    include_images_var_user = tk.BooleanVar(value=True)
    include_reels_var_user = tk.BooleanVar(value=False)
    include_human_classify_var_user = tk.BooleanVar(value=False)
    upscale_var_user = tk.BooleanVar(value=False)

    # 1행: 이미지, 릴스 체크박스
    include_images_check_user = ttk.Checkbutton(user_id_frame, text="이미지", variable=include_images_var_user)
    include_images_check_user.grid(row=1, column=0, sticky='w', padx=5, pady=2)
    include_reels_check_user = ttk.Checkbutton(user_id_frame, text="릴스", variable=include_reels_var_user)
    include_reels_check_user.grid(row=1, column=1, sticky='w', padx=5, pady=2)

    # 2행: 인물 분류, 업스케일링 체크박스
    include_human_classify_check_user = ttk.Checkbutton(user_id_frame, text="인물 분류", variable=include_human_classify_var_user)
    include_human_classify_check_user.grid(row=2, column=0, sticky='w', padx=5, pady=2)
    upscale_checkbox_user = ttk.Checkbutton(user_id_frame, text="업스케일링", variable=upscale_var_user)
    upscale_checkbox_user.grid(row=2, column=1, sticky='w', padx=5, pady=2)
    upscale_checkbox_user.configure(state='disabled')
    include_images_var_user.trace_add('write',
        lambda *args: toggle_human_classify(user_id_frame, include_images_var_user, include_human_classify_var_user)
)
    # 인물 분류 체크박스 값에 따라 업스케일링 체크박스 활성/비활성 제어
    def toggle_upscale_user(*args):
        if include_human_classify_var_user.get():
            upscale_checkbox_user.configure(state='normal')
        else:
            upscale_var_user.set(False)
            upscale_checkbox_user.configure(state='disabled')
    include_human_classify_var_user.trace_add('write', toggle_upscale_user)


    allow_duplicate_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(search_type_frame, text="중복 다운로드 허용", variable=allow_duplicate_var).grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=5)
    
    # Rate Limiting 설정
    rate_limit_frame = ttk.LabelFrame(search_type_frame, text="속도 제한 설정", padding=5)
    rate_limit_frame.grid(row=4, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
    
    ttk.Label(rate_limit_frame, text="요청 간 대기 시간 (초):").grid(row=0, column=0, sticky='w', padx=5, pady=2)
    wait_time_var = tk.StringVar(value=str(config.get('RATE_LIMIT_MIN_SLEEP', 3.0)))
    wait_time_entry = ttk.Entry(rate_limit_frame, textvariable=wait_time_var, width=10)
    wait_time_entry.grid(row=0, column=1, sticky='w', padx=5, pady=2)
    
    ttk.Label(rate_limit_frame, text="최대 대기 시간 (초):").grid(row=1, column=0, sticky='w', padx=5, pady=2)
    max_wait_time_var = tk.StringVar(value=str(config.get('RATE_LIMIT_MAX_SLEEP', 10.0)))
    max_wait_time_entry = ttk.Entry(rate_limit_frame, textvariable=max_wait_time_var, width=10)
    max_wait_time_entry.grid(row=1, column=1, sticky='w', padx=5, pady=2)

    def toggle_human_classify(parent_frame, img_var, human_var):
        if img_var.get():
            if parent_frame == hashtag_frame:
                include_human_classify_check_hashtag.configure(state='normal')
            else:
                include_human_classify_check_user.configure(state='normal')
        else:
            human_var.set(False)
            if parent_frame == hashtag_frame:
                include_human_classify_check_hashtag.configure(state='disabled')
            else:
                include_human_classify_check_user.configure(state='disabled')
                
    include_images_var_hashtag.trace_add('write',
        lambda *args: toggle_human_classify(hashtag_frame, include_images_var_hashtag, include_human_classify_var_hashtag)
)                              
    def on_search_type_change(*args):
        stype = search_type_var.get()
        if stype == "hashtag":
            include_images_check_hashtag.configure(state='normal')
            include_videos_check_hashtag.configure(state='normal')
            toggle_human_classify(hashtag_frame, include_images_var_hashtag, include_human_classify_var_hashtag)
            include_images_check_user.configure(state='disabled')
            include_reels_check_user.configure(state='disabled')
            include_human_classify_var_user.set(False)
            include_human_classify_check_user.configure(state='disabled')
        else:
            include_images_check_user.configure(state='normal')
            include_reels_check_user.configure(state='normal')
            toggle_human_classify(user_id_frame, include_images_var_user, include_human_classify_var_user)
            include_images_check_hashtag.configure(state='disabled')
            include_videos_check_hashtag.configure(state='disabled')
            include_human_classify_var_hashtag.set(False)
            include_human_classify_check_hashtag.configure(state='disabled')
    search_type_var.trace_add('write', on_search_type_change)

    search_frame = ttk.LabelFrame(root, text="검색 설정", padding=5)
    search_frame.grid(row=2, column=0, padx=10, pady=5, sticky='ew')
    search_frame.columnconfigure(1, weight=1)
    ttk.Label(search_frame, text="검색할 해시태그 / 사용자 ID (여러 개는 개행 또는 쉼표로 구분):", wraplength=300).grid(row=0, column=0, sticky='ne', pady=2, padx=10)
    word_text = scrolledtext.ScrolledText(search_frame, width=50, height=5, font=('Arial', 10))
    word_text.grid(row=0, column=1, pady=2, padx=10, sticky='ew')
    ttk.Label(search_frame, text="수집할 게시글 수 (0: 전체):").grid(row=1, column=0, sticky='e', pady=2, padx=10)
    post_count_entry = ttk.Entry(search_frame, width=20, font=('Arial', 10))
    post_count_entry.grid(row=1, column=1, sticky='w', pady=2, padx=10)
    post_count_entry.insert(0, "0")

    download_dir_frame = ttk.LabelFrame(root, text="전체 다운로드 경로 설정", padding=5)
    download_dir_frame.grid(row=3, column=0, padx=10, pady=5, sticky='ew')
    download_dir_frame.columnconfigure(1, weight=1)
    ttk.Label(download_dir_frame, text="기본 저장 경로:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
    download_directory_var = tk.StringVar(value=last_download_path)
    download_dir_entry = ttk.Entry(download_dir_frame, textvariable=download_directory_var, width=50, font=('Arial', 10))
    download_dir_entry.grid(row=0, column=1, sticky='ew', padx=10, pady=5)
    
    def open_download_directory():
        """
        '폴더 열기' 버튼 클릭 시, 다운로드 경로가 없으면 생성 후 엽니다.
        """
        d = download_directory_var.get()
        if not os.path.isdir(d):
            # 디렉토리가 없으면 생성
            create_dir_if_not_exists(d)
            append_status(f"다운로드 경로 생성됨: {d}")
        if os.name == 'nt':
            os.startfile(d)
        else:
            subprocess.Popen(["open", d])

    def select_download_directory_main():
        d = filedialog.askdirectory(initialdir=last_download_path)
        if d:
            download_directory_var.set(d)
            load_existing_directories()
            for acc in loaded_accounts:
                acc['DOWNLOAD_PATH'] = d
            # 마지막 다운로드 경로 업데이트
            config['LAST_DOWNLOAD_PATH'] = d
            save_config(config)
            append_status("다운로드 경로 변경됨.")
            print("다운로드 경로 업데이트됨.")

    ttk.Button(download_dir_frame, text="경로 선택", command=select_download_directory_main, width=12).grid(row=0, column=2, padx=5, pady=5)
    ttk.Button(download_dir_frame, text="폴더 열기", command=open_download_directory, width=12).grid(row=0, column=3, padx=5, pady=5)

    existing_dirs_frame = ttk.LabelFrame(root, text="기존 다운로드 디렉토리", padding=5)
    existing_dirs_frame.grid(row=4, column=0, padx=10, pady=10, sticky='nsew')
    for i in range(3):
        existing_dirs_frame.columnconfigure(i, weight=1)
    existing_dirs_frame.rowconfigure(0, weight=1)
    hashtag_list_frame = ttk.Frame(existing_dirs_frame)
    hashtag_list_frame.grid(row=0, column=0, padx=10, pady=5, sticky='nsew')
    hashtag_list_frame.columnconfigure(0, weight=1)
    ttk.Label(hashtag_list_frame, text="해시태그 목록").pack(anchor='w')
    hashtag_listbox = tk.Listbox(hashtag_list_frame, height=5, font=('Arial', 10), selectmode=tk.EXTENDED)
    hashtag_listbox.pack(side='left', fill='both', expand=True, padx=(0,5), pady=5)
    hashtag_scrollbar = ttk.Scrollbar(hashtag_list_frame, orient="vertical", command=hashtag_listbox.yview)
    hashtag_scrollbar.pack(side='left', fill='y')
    hashtag_listbox.config(yscrollcommand=hashtag_scrollbar.set)
    user_id_list_frame = ttk.Frame(existing_dirs_frame)
    user_id_list_frame.grid(row=0, column=1, padx=10, pady=5, sticky='nsew')
    user_id_list_frame.columnconfigure(0, weight=1)
    ttk.Label(user_id_list_frame, text="사용자 ID 목록").pack(anchor='w')
    user_id_listbox = tk.Listbox(user_id_list_frame, height=5, font=('Arial', 10), selectmode=tk.EXTENDED)
    user_id_listbox.pack(side='left', fill='both', expand=True, padx=(0,5), pady=5)
    user_id_scrollbar = ttk.Scrollbar(user_id_list_frame, orient="vertical", command=user_id_listbox.yview)
    user_id_scrollbar.pack(side='left', fill='y')
    user_id_listbox.config(yscrollcommand=user_id_scrollbar.set)
    selection_buttons_frame = ttk.Frame(existing_dirs_frame)
    selection_buttons_frame.grid(row=0, column=2, padx=10, pady=5, sticky='nsew')
    selection_buttons_frame.columnconfigure(0, weight=1)
    selection_buttons_frame.columnconfigure(1, weight=1)
    ttk.Button(selection_buttons_frame, text="선택된 해시태그 추가",
               command=lambda: add_items_from_listbox(hashtag_listbox, word_text, "해시태그")
    ).grid(row=0, column=0, padx=5, pady=2, sticky='ew')
    ttk.Button(selection_buttons_frame, text="모든 해시태그 추가",
               command=lambda: add_all_items_from_listbox(hashtag_listbox, word_text, "해시태그")
    ).grid(row=0, column=1, padx=5, pady=2, sticky='ew')
    ttk.Button(selection_buttons_frame, text="선택된 사용자 ID 추가",
               command=lambda: add_items_from_listbox(user_id_listbox, word_text, "사용자 ID")
    ).grid(row=1, column=0, padx=5, pady=2, sticky='ew')
    ttk.Button(selection_buttons_frame, text="모든 사용자 ID 추가",
               command=lambda: add_all_items_from_listbox(user_id_listbox, word_text, "사용자 ID")
    ).grid(row=1, column=1, padx=5, pady=2, sticky='ew')
    
    # 삭제 버튼 추가
    ttk.Button(selection_buttons_frame, text="선택된 대상 삭제",
               command=lambda: delete_selected_items(), width=15
    ).grid(row=2, column=0, columnspan=2, padx=5, pady=2, sticky='ew')

    user_ids_cached = []

    def delete_selected_items():
        """
        선택된 해시태그와 사용자 ID와 관련된 모든 디렉토리를 삭제합니다.
        """
        # 해시태그 선택 확인
        hashtag_indices = hashtag_listbox.curselection()
        user_id_indices = user_id_listbox.curselection()
        
        if not hashtag_indices and not user_id_indices:
            append_status("오류: 삭제할 대상을 선택하세요.")
            return
        
        selected_hashtags = [hashtag_listbox.get(i) for i in hashtag_indices]
        selected_user_ids = [user_id_listbox.get(i) for i in user_id_indices]
        
        # 확인 대화상자 메시지 구성
        confirm_parts = []
        if selected_hashtags:
            confirm_parts.append(f"해시태그:\n" + "\n".join(selected_hashtags))
        if selected_user_ids:
            confirm_parts.append(f"사용자 ID:\n" + "\n".join(selected_user_ids))
        
        confirm_message = f"선택된 대상과 관련된 모든 디렉토리를 삭제하시겠습니까?\n\n" + "\n\n".join(confirm_parts)
        result = messagebox.askyesno("삭제 확인", confirm_message)
        
        if not result:
            append_status("삭제가 취소되었습니다.")
            return
        
        main_download_dir = download_directory_var.get()
        deleted_count = 0
        
        # 해시태그 삭제
        if selected_hashtags:
            sorted_hashtag_indices = sorted(hashtag_indices, reverse=True)
            for hashtag in selected_hashtags:
                try:
                    # 해시태그 관련 디렉토리들 삭제
                    dirs_to_delete = [
                        os.path.join(main_download_dir, "unclassified", "hashtag", hashtag),
                        os.path.join(main_download_dir, "Reels", "hashtag", hashtag),
                        os.path.join(main_download_dir, "인물", f"hashtag_{hashtag}"),
                        os.path.join(main_download_dir, "비인물", f"hashtag_{hashtag}")
                    ]
                    
                    for dir_path in dirs_to_delete:
                        if os.path.exists(dir_path):
                            shutil.rmtree(dir_path)
                            append_status(f"삭제됨: {dir_path}")
                            deleted_count += 1
                    
                except Exception as e:
                    append_status(f"오류: {hashtag} 삭제 중 오류 발생 - {e}")
            
            # 해시태그 리스트박스에서 선택된 항목들 제거 (역순으로)
            for index in sorted_hashtag_indices:
                hashtag_listbox.delete(index)
        
        # 사용자 ID 삭제
        if selected_user_ids:
            sorted_user_id_indices = sorted(user_id_indices, reverse=True)
            for user_id in selected_user_ids:
                try:
                    # 사용자 ID 관련 디렉토리들 삭제
                    dirs_to_delete = [
                        os.path.join(main_download_dir, "unclassified", "ID", user_id),
                        os.path.join(main_download_dir, "Reels", "ID", user_id),
                        os.path.join(main_download_dir, "인물", f"user_{user_id}"),
                        os.path.join(main_download_dir, "비인물", f"user_{user_id}")
                    ]
                    
                    for dir_path in dirs_to_delete:
                        if os.path.exists(dir_path):
                            shutil.rmtree(dir_path)
                            append_status(f"삭제됨: {dir_path}")
                            deleted_count += 1
                    
                except Exception as e:
                    append_status(f"오류: {user_id} 삭제 중 오류 발생 - {e}")
            
            # 사용자 ID 리스트박스에서 선택된 항목들 제거 (역순으로)
            for index in sorted_user_id_indices:
                user_id_listbox.delete(index)
        
        append_status(f"삭제 완료: {deleted_count}개의 디렉토리가 삭제되었습니다.")

    def load_existing_directories():
        """
        다운로드 경로에 있는 기존 디렉토리들을 불러옵니다.
        다운로드 경로가 없으면 생성합니다.
        
        - 해시태그 관련 디렉토리는 '인물' 폴더 내에서 'hashtag_'로 시작하는 디렉토리를 찾아,
          접두어 'hashtag_'를 제거한 나머지 부분을 해시태그 목록에 추가합니다.
        - 사용자 ID 관련 디렉토리는 '인물' 폴더 내에서 'user_'로 시작하는 디렉토리를 찾아 목록에 추가합니다.
        """
        main_download_dir = download_directory_var.get()
        if not os.path.isdir(main_download_dir):
            append_status(f"오류: 다운로드 경로가 존재하지 않습니다: {main_download_dir}")
            return
        # '인물' 폴더는 해시태그와 사용자 디렉토리 모두 포함하는 상위 폴더입니다.
        people_dir = os.path.join(main_download_dir, '인물')
        create_dir_if_not_exists(people_dir)
        
        # 해시태그 목록 새로고침: 'hashtag_'로 시작하는 디렉토리들만 추가
        hashtag_listbox.delete(0, tk.END)
        for d in os.listdir(people_dir):
            full_path = os.path.join(people_dir, d)
            if os.path.isdir(full_path) and d.startswith("hashtag_"):
                # 접두어 'hashtag_' 제거 후 남은 부분을 목록에 추가
                hashtag_listbox.insert(tk.END, d[len("hashtag_"):])
        
        # 사용자 ID 목록 새로고침: 'user_'로 시작하는 디렉토리들만 추가
        user_id_listbox.delete(0, tk.END)
        nonlocal user_ids_cached
        user_ids_cached = []
        for d in os.listdir(people_dir):
            full_path = os.path.join(people_dir, d)
            if os.path.isdir(full_path) and d.startswith("user_"):
                actual_uid = d[len("user_"):]
                try:
                    ct = os.path.getctime(full_path)
                    mt = os.path.getmtime(full_path)
                    user_ids_cached.append((actual_uid, ct, mt))
                except Exception as e:
                    append_status(f"경고: {d} 생성/수정일 오류: {e}")
        for uid, _, _ in sorted(user_ids_cached, key=lambda x: x[1], reverse=True):
            user_id_listbox.insert(tk.END, uid)

    def sort_user_ids_by_creation_desc():
        user_id_listbox.delete(0, tk.END)
        for uid, ct, mt in sorted(user_ids_cached, key=lambda x: x[1], reverse=True):
            user_id_listbox.insert(tk.END, uid)
        append_status("사용자 ID가 생성일 내림차순 정렬됨.")

    def sort_user_ids_by_creation_asc():
        user_id_listbox.delete(0, tk.END)
        for uid, ct, mt in sorted(user_ids_cached, key=lambda x: x[1]):
            user_id_listbox.insert(tk.END, uid)
        append_status("사용자 ID가 생성일 오름차순 정렬됨.")

    def sort_user_ids_by_modified_asc():
        ini_path = os.path.join(os.path.dirname(__file__), 'latest-stamps-images.ini')
        if not os.path.isfile(ini_path):
            append_status("오류: latest-stamps-images.ini 없음.")
            return
        parser = configparser.ConfigParser()
        parser.read(ini_path, encoding='utf-8')
        ini_ts = {}
        for section in parser.sections():
            if parser[section].get('post-timestamp'):
                raw = parser[section]['post-timestamp'].strip()
                dt = None
                try:
                    dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S.%f%z")
                except ValueError:
                    try:
                        dt = datetime.fromisoformat(raw)
                    except Exception:
                        pass
                if dt:
                    ini_ts[section] = dt
        uids_dirs = {uid for uid, _, _ in user_ids_cached}
        uids_ini = set(ini_ts.keys())
        combined = uids_dirs.union(uids_ini)
        user_list = [(uid, ini_ts.get(uid)) for uid in combined]
        with_ts = [item for item in user_list if item[1] is not None]
        without_ts = [item for item in user_list if item[1] is None]
        with_ts.sort(key=lambda x: x[1])
        final_sorted = with_ts + without_ts
        user_id_listbox.delete(0, tk.END)
        for uid, _ in final_sorted:
            user_id_listbox.insert(tk.END, uid)
        append_status("INI 기준 오름차순 정렬 완료.")
    
    def manage_non_existent_profiles():
        """
        존재하지 않는 프로필 목록을 관리하는 창을 엽니다.
        """
        non_existent_window = tk.Toplevel(root)
        non_existent_window.title("존재하지 않는 프로필 관리")
        non_existent_window.geometry("500x400")
        non_existent_window.resizable(False, False)
        
        # 프레임 생성
        main_frame = ttk.Frame(non_existent_window, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="존재하지 않는 프로필 목록:", font=('Arial', 12, 'bold')).pack(anchor='w', pady=(0, 10))
        
        # 리스트박스와 스크롤바
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        non_existent_listbox = tk.Listbox(list_frame, height=15, font=('Arial', 10), selectmode=tk.EXTENDED)
        non_existent_listbox.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=non_existent_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        non_existent_listbox.config(yscrollcommand=scrollbar.set)
        
        # 버튼 프레임
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 10))
        
        def refresh_list():
            """리스트를 새로고침합니다."""
            non_existent_listbox.delete(0, tk.END)
            non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
            for profile in non_existent_profiles:
                non_existent_listbox.insert(tk.END, profile)
            append_status(f"존재하지 않는 프로필 목록 새로고침: {len(non_existent_profiles)}개")
        
        def remove_selected():
            """선택된 프로필을 목록에서 제거합니다."""
            indices = non_existent_listbox.curselection()
            if not indices:
                append_status("오류: 제거할 프로필을 선택하세요.")
                return
            
            selected_profiles = [non_existent_listbox.get(i) for i in indices]
            confirm_message = f"선택된 프로필을 목록에서 제거하시겠습니까?\n\n{', '.join(selected_profiles)}"
            result = messagebox.askyesno("제거 확인", confirm_message)
            
            if result:
                non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
                for profile in selected_profiles:
                    if profile in non_existent_profiles:
                        non_existent_profiles.remove(profile)
                
                config['NON_EXISTENT_PROFILES'] = non_existent_profiles
                save_config(config)
                refresh_list()
                append_status(f"프로필 {len(selected_profiles)}개가 목록에서 제거되었습니다.")
        
        def clear_all():
            """모든 프로필을 목록에서 제거합니다."""
            non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
            if not non_existent_profiles:
                append_status("제거할 프로필이 없습니다.")
                return
            
            confirm_message = f"모든 프로필을 목록에서 제거하시겠습니까?\n\n총 {len(non_existent_profiles)}개"
            result = messagebox.askyesno("전체 제거 확인", confirm_message)
            
            if result:
                config['NON_EXISTENT_PROFILES'] = []
                save_config(config)
                refresh_list()
                append_status("모든 프로필이 목록에서 제거되었습니다.")
        
        def add_manual():
            """수동으로 프로필을 추가합니다."""
            add_window = tk.Toplevel(non_existent_window)
            add_window.title("프로필 추가")
            add_window.geometry("300x150")
            add_window.resizable(False, False)
            
            ttk.Label(add_window, text="추가할 프로필명:").pack(pady=(20, 5))
            entry = ttk.Entry(add_window, width=30)
            entry.pack(pady=(0, 20))
            entry.focus()
            
            def add_profile():
                profile_name = entry.get().strip()
                if not profile_name:
                    append_status("오류: 프로필명을 입력하세요.")
                    return
                
                non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
                if profile_name not in non_existent_profiles:
                    non_existent_profiles.append(profile_name)
                    config['NON_EXISTENT_PROFILES'] = non_existent_profiles
                    save_config(config)
                    refresh_list()
                    append_status(f"프로필 '{profile_name}'이 목록에 추가되었습니다.")
                else:
                    append_status(f"프로필 '{profile_name}'은 이미 목록에 있습니다.")
                
                add_window.destroy()
            
            ttk.Button(add_window, text="추가", command=add_profile).pack(pady=(0, 10))
            entry.bind('<Return>', lambda e: add_profile())
        
        # 버튼들
        ttk.Button(button_frame, text="새로고침", command=refresh_list, width=12).pack(side='left', padx=(0, 5))
        ttk.Button(button_frame, text="선택 제거", command=remove_selected, width=12).pack(side='left', padx=(0, 5))
        ttk.Button(button_frame, text="전체 제거", command=clear_all, width=12).pack(side='left', padx=(0, 5))
        ttk.Button(button_frame, text="수동 추가", command=add_manual, width=12).pack(side='left')
        
        # 초기 로드
        refresh_list()
    
    sort_buttons_frame = ttk.Frame(existing_dirs_frame)
    sort_buttons_frame.grid(row=1, column=1, padx=5, pady=2, sticky='nsew')
    sort_buttons_frame.columnconfigure(0, weight=1)
    sort_buttons_frame.columnconfigure(1, weight=1)
    ttk.Button(sort_buttons_frame, text="생성일 내림차순", command=sort_user_ids_by_creation_desc).grid(row=0, column=0, padx=5, pady=2, sticky='ew')
    ttk.Button(sort_buttons_frame, text="(INI) 오름차순", command=sort_user_ids_by_modified_asc).grid(row=0, column=1, padx=5, pady=2, sticky='ew')
    ttk.Button(sort_buttons_frame, text="생성일 오름차순", command=sort_user_ids_by_creation_asc).grid(row=1, column=0, padx=5, pady=2, sticky='ew')
    ttk.Button(existing_dirs_frame, text="새로 고침", command=load_existing_directories, width=15).grid(row=1, column=0, pady=5)
    
    # 존재하지 않는 프로필 관리 버튼 추가
    ttk.Button(existing_dirs_frame, text="존재하지 않는 프로필 관리", 
               command=lambda: manage_non_existent_profiles(), width=20).grid(row=1, column=2, pady=5)

    progress_frame = ttk.Frame(root)
    progress_frame.grid(row=6, column=0, padx=10, pady=5, sticky='ew')
    progress_frame.columnconfigure(0, weight=1)
    progress_label_var = tk.StringVar()
    progress_label = ttk.Label(progress_frame, textvariable=progress_label_var)
    progress_label.grid(row=0, column=0, sticky='w', padx=10, pady=(0,5))
    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
    progress_bar.grid(row=1, column=0, sticky='ew', padx=10, pady=5)
    global_stop_event = threading.Event()

    main_search_terms = []
    main_search_type = ""

    def process_queue(q):
        try:
            while True:
                msg = q.get_nowait()
                if msg[0] == "term_start":
                    append_status(f"시작: {msg[1]} (계정: {msg[2]})")
                elif msg[0] == "term_progress":
                    append_status(f"진행: {msg[1]} - {msg[2]} (계정: {msg[3]})")
                elif msg[0] == "term_complete":
                    append_status(f"완료: {msg[1]} (계정: {msg[2]})")
                elif msg[0] == "term_error":
                    # 프로필이 존재하지 않는 경우 유사한 프로필 정보도 표시
                    if "does not exist" in msg[2]:
                        append_status(f"프로필이 존재하지 않음: {msg[1]}")
                        if "The most similar profiles are:" in msg[2]:
                            # 유사한 프로필 정보 추출
                            similar_profiles = msg[2].split("The most similar profiles are:")[1].strip()
                            append_status(f"유사한 프로필: {similar_profiles}")
                    else:
                        append_status(f"오류: {msg[1]} - {msg[2]} (계정: {msg[3]})")
                elif msg[0] == "account_switch":
                    append_status(f"계정 전환: {msg[1]}")
                elif msg[0] == "account_relogin":
                    append_status(f"재로그인 시도: {msg[1]}")
        except Empty:
            pass
        root.after(100, lambda: process_queue(q))

    def reclassify_classified_images(stop_evt):
        stop_evt.clear()
        append_status("분류된 이미지 재분류 시작.")
        d_path = download_directory_var.get().strip()
        classified_dir = os.path.join(d_path, "인물")
        dirs_to_reclassify = []
        for idx in hashtag_listbox.curselection():
            tag = hashtag_listbox.get(idx)
            dir_name = "hashtag_" + tag
            img_dir = os.path.join(classified_dir, dir_name)
            if os.path.isdir(img_dir):
                dirs_to_reclassify.append((tag, 'hashtag', img_dir))
            else:
                append_status(f"경고: {img_dir} 없음.")
        for idx in user_id_listbox.curselection():
            uid = user_id_listbox.get(idx)
            dir_name = "user_" + uid
            img_dir = os.path.join(classified_dir, dir_name)
            if os.path.isdir(img_dir):
                dirs_to_reclassify.append((uid, 'user', img_dir))
            else:
                append_status(f"경고: {img_dir} 없음.")
        if not dirs_to_reclassify:
            append_status("분류된 이미지 선택 없음.")
            return
        total = len(dirs_to_reclassify)
        root.after(0, lambda: progress_var.set(0))
        append_status("재분류 진행 중...")
        def worker():
            for i, (term, stype, img_dir) in enumerate(dirs_to_reclassify, start=1):
                if stop_evt.is_set():
                    append_status("중지: 재분류 중지됨.")
                    return
                success = process_images(
                    root, append_status, download_directory_var,
                    term, "", config['LAST_SEARCH_TYPE'], stop_evt,
                    upscale=False,
                    classified=True
                )
                root.after(0, lambda p=(i/total)*100: progress_var.set(p))
                if success:
                    append_status(f"완료: {term} 재분류 완료.")
                else:
                    append_status(f"오류: {term} 재분류 오류.")
            append_status("모든 재분류 완료.")
            root.after(0, lambda: progress_label_var.set("재분류 완료"))
            load_existing_directories()
        threading.Thread(target=worker, daemon=True).start()

    ttk.Button(existing_dirs_frame, text="분류된 이미지 재분류", command=lambda: reclassify_classified_images(global_stop_event), width=20).grid(row=3, column=2, padx=5, pady=2, sticky='ew')

    def start_crawling():
        append_status("크롤링 시작됨...")
        terms_raw = word_text.get("1.0", tk.END).strip()
        if not terms_raw:
            append_status("오류: 검색할 해시태그 또는 사용자 ID 입력 필요.")
            return
        
        # 검색어 목록 생성
        search_terms = [t.strip() for t in terms_raw.replace(',', '\n').split('\n') if t.strip()]
        if not search_terms:
            append_status("오류: 유효한 검색어 없음.")
            return
        
        # 존재하지 않는 프로필 제외
        non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
        if non_existent_profiles and config['LAST_SEARCH_TYPE'] == 'user':
            original_count = len(search_terms)
            search_terms = [term for term in search_terms if term not in non_existent_profiles]
            excluded_count = original_count - len(search_terms)
            if excluded_count > 0:
                excluded_terms = [term for term in terms_raw.replace(',', '\n').split('\n') if term.strip() in non_existent_profiles]
                append_status(f"존재하지 않는 프로필 {excluded_count}개 제외됨: {', '.join(excluded_terms)}")
        
        if not search_terms:
            append_status("오류: 제외 후 유효한 검색어가 없습니다.")
            return
        
        config['SEARCH_TERMS'] = search_terms
        try:
            target = int(post_count_entry.get().strip())
            if target < 0:
                append_status("오류: 게시글 수는 0 이상이어야 함.")
                return
        except ValueError:
            append_status("오류: 게시글 수는 정수여야 함.")
            return
        nonlocal main_search_terms, main_search_type
        main_search_terms.clear()
        main_search_terms.extend(config['SEARCH_TERMS'])
        config['LAST_SEARCH_TYPE'] = search_type_var.get()
        main_search_type = config['LAST_SEARCH_TYPE']
        config['INCLUDE_IMAGES'] = (include_images_var_hashtag.get() if config['LAST_SEARCH_TYPE'] == "hashtag" 
                                    else include_images_var_user.get() if include_images_var_user else False)
        config['INCLUDE_VIDEOS'] = (include_videos_var_hashtag.get() if config['LAST_SEARCH_TYPE'] == "hashtag" else False)
        config['INCLUDE_REELS'] = (include_reels_var_user.get() if config['LAST_SEARCH_TYPE'] == "user" else False)
        config['INCLUDE_HUMAN_CLASSIFY'] = (
            include_human_classify_var_hashtag.get() if config['LAST_SEARCH_TYPE'] == "hashtag"
            else include_human_classify_var_user.get() if config['LAST_SEARCH_TYPE'] == "user" else False
        )
        config['INCLUDE_UPSCALE'] = (
            upscale_var_hashtag.get() if config['LAST_SEARCH_TYPE'] == "hashtag"
            else upscale_var_user.get() if config['LAST_SEARCH_TYPE'] == "user" else False
        )
        allow_duplicate = allow_duplicate_var.get()
        d_path = download_directory_var.get().strip()
        if not os.path.isdir(d_path):
            create_dir_if_not_exists(d_path)
            append_status(f"다운로드 경로 생성됨: {d_path}")
        # Rate Limiting 설정 저장
        try:
            config['RATE_LIMIT_MIN_SLEEP'] = float(wait_time_var.get())
            config['RATE_LIMIT_MAX_SLEEP'] = float(max_wait_time_var.get())
        except ValueError:
            append_status("경고: Rate Limiting 설정이 잘못되었습니다. 기본값을 사용합니다.")
            config['RATE_LIMIT_MIN_SLEEP'] = 3.0
            config['RATE_LIMIT_MAX_SLEEP'] = 10.0
        
        # 마지막 다운로드 경로 업데이트
        config['LAST_DOWNLOAD_PATH'] = d_path
        save_config(config)
        append_status("설정 저장됨.")
        q = Queue()
        global_stop_event.clear()
        threading.Thread(
            target=crawl_and_download,
            args=(
                main_search_terms,
                target,
                loaded_accounts,
                config['LAST_SEARCH_TYPE'],
                config['INCLUDE_IMAGES'],
                config['INCLUDE_VIDEOS'],
                config['INCLUDE_REELS'],
                config['INCLUDE_HUMAN_CLASSIFY'],
                config['INCLUDE_UPSCALE'],
                q,
                on_complete,
                global_stop_event,
                d_path,
                append_status,
                root,
                download_directory_var,
                allow_duplicate
            ),
            daemon=True
        ).start()
        process_queue(q)

    def stop_crawling():
        global_stop_event.set()
        append_status("크롤링 및 분류 중지 요청됨.")

    button_frame = ttk.Frame(root)
    button_frame.grid(row=8, column=0, pady=5, padx=10, sticky='ew')
    for i in range(3):
        button_frame.columnconfigure(i, weight=1)
    ttk.Button(button_frame, text="크롤링 시작", command=start_crawling, width=15).grid(row=0, column=0, padx=5, pady=2, sticky='ew')
    ttk.Button(button_frame, text="중지", command=stop_crawling, width=15).grid(row=0, column=1, padx=5, pady=2, sticky='ew')
    ttk.Button(existing_dirs_frame, text="선택된 이미지 분류", command=lambda: process_images(global_stop_event), width=20).grid(row=2, column=2, padx=5, pady=2, sticky='ew')

    def on_complete(message):
        append_status(f"완료: {message}")
        progress_var.set(100)
        progress_label_var.set("100% 완료")
        load_existing_directories()

    if config['ACCOUNTS']:
        for account in config['ACCOUNTS']:
            accounts_listbox.insert(tk.END, account['INSTAGRAM_USERNAME'])
        append_status("저장된 계정 자동 입력됨.")
    if config['LAST_SEARCH_TYPE']:
        search_type_var.set(config['LAST_SEARCH_TYPE'])
    if config['LAST_SEARCH_TYPE'] == "hashtag":
        include_human_classify_var_hashtag.set(config['INCLUDE_HUMAN_CLASSIFY'])
    elif config['LAST_SEARCH_TYPE'] == "user":
        include_human_classify_var_user.set(config['INCLUDE_HUMAN_CLASSIFY'])
    if config['SEARCH_TERMS']:
        word_text.insert(tk.END, "\n".join(config['SEARCH_TERMS']))
        append_status("저장된 검색어 자동 입력됨.")
    
    def initial_toggle():
        if loaded_searchtype == 'hashtag':
            toggle_human_classify(hashtag_frame, include_images_var_hashtag, include_human_classify_var_hashtag)
        else:
            toggle_human_classify(user_id_frame, include_images_var_user, include_human_classify_var_user)
    initial_toggle()
    
    root.rowconfigure(7, weight=1)
    root.columnconfigure(0, weight=1)
    load_existing_directories()
    root.mainloop()
    print("GUI 종료")

if __name__ == '__main__':
    main_gui()