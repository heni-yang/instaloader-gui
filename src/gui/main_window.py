# src/gui/main_window.py
import os
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from queue import Queue, Empty
from datetime import datetime, timedelta
import configparser
import subprocess
import shutil
import time

from ..utils.config import load_config, save_config
from ..core.downloader import crawl_and_download
from ..processing.post_processing import process_images
from ..utils.file_utils import create_dir_if_not_exists
from ..core.profile_manager import get_non_existent_profile_ids, get_profile_id_for_username, is_profile_id_non_existent, get_private_not_followed_profile_ids, is_private_not_followed_profile_id

# 모듈화된 GUI 함수들 import
from .handlers.queue_handler import (
    add_items_from_listbox, add_all_items_from_listbox,
    toggle_upscale_hashtag, toggle_upscale_user, toggle_human_classify,
    on_search_type_change, open_download_directory, select_download_directory_main,
    select_download_directory_add, process_queue
)
from .dialogs.settings import (
    delete_selected_items, load_existing_directories,
    sort_user_ids_by_creation_desc, sort_user_ids_by_creation_asc, 
    sort_user_ids_by_ini_asc, sort_user_ids_by_ini_desc
)
from .dialogs.account_management import (
    add_account, remove_account, remove_session, save_new_account
)
from .dialogs.profile_manager import manage_profiles

# 프로젝트 루트 및 기본 다운로드 경로 설정
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
DEFAULT_DOWNLOAD_PATH = os.path.join(PROJECT_ROOT, 'data', 'downloads')
from ..utils.environment import Environment
SESSION_DIR = Environment.SESSIONS_DIR

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

    # 리스트박스 항목을 텍스트 위젯에 추가하는 함수들 (모듈에서 호출)


    # 계정 관리 함수들 (모듈에서 호출)
    account_dialog = None
    
    def add_account_wrapper():
        nonlocal account_dialog
        
        # 이미 열려있는 창이 있는지 확인
        try:
            if account_dialog and account_dialog.winfo_exists():
                # 기존 창을 앞으로 가져오기
                account_dialog.lift()
                account_dialog.focus()
                return
        except tk.TclError:
            # 창이 이미 닫혀있는 경우
            account_dialog = None
        
        # 새 창 생성
        account_dialog = add_account(accounts_listbox, loaded_accounts, append_status)
        return account_dialog

    def remove_account_wrapper():
        remove_account(accounts_listbox, loaded_accounts, append_status)

    def remove_session_wrapper():
        remove_session(append_status, accounts_listbox)

    add_account_button = ttk.Button(account_buttons_frame, text="계정 추가", command=add_account_wrapper, width=8)
    add_account_button.grid(row=0, column=0, padx=5, pady=2, sticky='ew')
    remove_account_button = ttk.Button(account_buttons_frame, text="계정 제거", command=remove_account_wrapper, width=8)
    remove_account_button.grid(row=0, column=1, padx=5, pady=2, sticky='ew')
    remove_session_button = ttk.Button(account_buttons_frame, text="세션 삭제", command=remove_session_wrapper, width=8)
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
    include_human_classify_var_hashtag.trace_add('write', 
        lambda *args: toggle_upscale_hashtag(include_human_classify_var_hashtag, upscale_var_hashtag, upscale_checkbox_hashtag, *args))


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
    include_human_classify_var_user.trace_add('write', 
        lambda *args: toggle_upscale_user(include_human_classify_var_user, upscale_var_user, upscale_checkbox_user, *args))


    allow_duplicate_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(search_type_frame, text="중복 다운로드 허용", variable=allow_duplicate_var).grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=5)

    # 요청 간 대기시간 설정
    rate_limit_frame = ttk.LabelFrame(search_type_frame, text="요청 간 대기시간", padding=5)
    rate_limit_frame.grid(row=4, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
    
    ttk.Label(rate_limit_frame, text="추가 대기시간 (초, 0=자동):").grid(row=0, column=0, sticky='w', padx=5, pady=2)
    wait_time_var = tk.StringVar(value=str(config.get('REQUEST_WAIT_TIME', 0.0)))
    wait_time_entry = ttk.Entry(rate_limit_frame, textvariable=wait_time_var, width=10)
    wait_time_entry.grid(row=0, column=1, sticky='w', padx=5, pady=2)
    
    ttk.Label(rate_limit_frame, text="(0초: Instaloader 자동 제어, 1초 이상: 추가 대기)").grid(row=1, column=0, columnspan=2, sticky='w', padx=5, pady=2)

    include_images_var_hashtag.trace_add('write',
        lambda *args: toggle_human_classify(hashtag_frame, include_images_var_hashtag, include_human_classify_var_hashtag, 
                                          include_human_classify_check_hashtag, include_human_classify_check_user)
)                              
    search_type_var.trace_add('write', 
        lambda *args: on_search_type_change(search_type_var, include_images_check_hashtag, include_videos_check_hashtag,
                                          include_human_classify_check_hashtag, include_images_var_hashtag, include_human_classify_var_hashtag,
                                          include_images_check_user, include_reels_check_user, include_human_classify_check_user,
                                          include_images_var_user, include_human_classify_var_user, hashtag_frame, user_id_frame,
                                          append_status, *args))

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
    
    # 다운로드 디렉토리 관련 함수들을 모듈에서 호출



    ttk.Button(download_dir_frame, text="경로 선택", 
               command=lambda: select_download_directory_main(download_directory_var, last_download_path, loaded_accounts, load_existing_directories, append_status), width=12).grid(row=0, column=2, padx=5, pady=5)
    ttk.Button(download_dir_frame, text="폴더 열기", 
               command=lambda: open_download_directory(download_directory_var, append_status), width=12).grid(row=0, column=3, padx=5, pady=5)

    existing_dirs_frame = ttk.LabelFrame(root, text="다운로드된 프로필 목록", padding=3)
    existing_dirs_frame.grid(row=4, column=0, padx=10, pady=5, sticky='nsew')
    for i in range(3):
        existing_dirs_frame.columnconfigure(i, weight=1)
    existing_dirs_frame.rowconfigure(0, weight=1)
    hashtag_list_frame = ttk.Frame(existing_dirs_frame)
    hashtag_list_frame.grid(row=0, column=0, padx=10, pady=5, sticky='nsew')
    hashtag_list_frame.columnconfigure(0, weight=1)
    hashtag_list_frame.rowconfigure(2, weight=1)
    
    # 해시태그 제목과 개수
    hashtag_header_frame = ttk.Frame(hashtag_list_frame)
    hashtag_header_frame.pack(fill='x', pady=(0, 2))
    hashtag_count_var = tk.StringVar(value="해시태그 목록 (0개)")
    ttk.Label(hashtag_header_frame, textvariable=hashtag_count_var, font=('Arial', 10, 'bold')).pack(side='left')
    
    # 해시태그 검색
    hashtag_search_var = tk.StringVar()
    hashtag_search_entry = ttk.Entry(hashtag_list_frame, textvariable=hashtag_search_var)
    hashtag_search_entry.pack(fill='x', pady=(0, 5))
    hashtag_search_entry.insert(0, "해시태그 검색...")
    
    def on_hashtag_search_focus_in(event):
        if hashtag_search_var.get() == "해시태그 검색...":
            hashtag_search_entry.delete(0, tk.END)
    
    def on_hashtag_search_focus_out(event):
        if not hashtag_search_var.get():
            hashtag_search_entry.insert(0, "해시태그 검색...")
    
    hashtag_search_entry.bind('<FocusIn>', on_hashtag_search_focus_in)
    hashtag_search_entry.bind('<FocusOut>', on_hashtag_search_focus_out)
    
    # 해시태그 리스트박스와 스크롤바
    hashtag_listbox_frame = ttk.Frame(hashtag_list_frame)
    hashtag_listbox_frame.pack(fill='both', expand=True)
    hashtag_listbox = tk.Listbox(hashtag_listbox_frame, height=5, font=('Arial', 10), selectmode=tk.EXTENDED)
    hashtag_listbox.pack(side='left', fill='both', expand=True, padx=(0,5))
    hashtag_scrollbar = ttk.Scrollbar(hashtag_listbox_frame, orient="vertical", command=hashtag_listbox.yview)
    hashtag_scrollbar.pack(side='left', fill='y')
    hashtag_listbox.config(yscrollcommand=hashtag_scrollbar.set)
    user_id_list_frame = ttk.Frame(existing_dirs_frame)
    user_id_list_frame.grid(row=0, column=1, padx=10, pady=5, sticky='nsew')
    user_id_list_frame.columnconfigure(0, weight=1)
    user_id_list_frame.rowconfigure(2, weight=1)
    
    # 사용자 ID 제목과 개수
    user_id_header_frame = ttk.Frame(user_id_list_frame)
    user_id_header_frame.pack(fill='x', pady=(0, 2))
    user_id_count_var = tk.StringVar(value="사용자 ID 목록 (0개)")
    ttk.Label(user_id_header_frame, textvariable=user_id_count_var, font=('Arial', 10, 'bold')).pack(side='left')
    
    # 사용자 ID 검색
    user_id_search_var = tk.StringVar()
    user_id_search_entry = ttk.Entry(user_id_list_frame, textvariable=user_id_search_var)
    user_id_search_entry.pack(fill='x', pady=(0, 5))
    user_id_search_entry.insert(0, "사용자 ID 검색...")
    
    def on_user_id_search_focus_in(event):
        if user_id_search_var.get() == "사용자 ID 검색...":
            user_id_search_entry.delete(0, tk.END)
    
    def on_user_id_search_focus_out(event):
        if not user_id_search_var.get():
            user_id_search_entry.insert(0, "사용자 ID 검색...")
    
    user_id_search_entry.bind('<FocusIn>', on_user_id_search_focus_in)
    user_id_search_entry.bind('<FocusOut>', on_user_id_search_focus_out)
    
    # 사용자 ID 리스트박스와 스크롤바
    user_id_listbox_frame = ttk.Frame(user_id_list_frame)
    user_id_listbox_frame.pack(fill='both', expand=True)
    user_id_listbox = tk.Listbox(user_id_listbox_frame, height=5, font=('Arial', 10), selectmode=tk.EXTENDED)
    user_id_listbox.pack(side='left', fill='both', expand=True, padx=(0,5))
    user_id_scrollbar = ttk.Scrollbar(user_id_listbox_frame, orient="vertical", command=user_id_listbox.yview)
    user_id_scrollbar.pack(side='left', fill='y')
    user_id_listbox.config(yscrollcommand=user_id_scrollbar.set)
    selection_buttons_frame = ttk.Frame(existing_dirs_frame)
    selection_buttons_frame.grid(row=0, column=2, padx=10, pady=5, sticky='nsew')
    selection_buttons_frame.columnconfigure(0, weight=1)
    selection_buttons_frame.columnconfigure(1, weight=1)
    # 추가 함수들을 모듈에서 호출

    
    # === 그룹 1: 검색 목록 관리 ===
    ttk.Button(selection_buttons_frame, text="선택된 해시태그 추가",
               command=lambda: [add_items_from_listbox(hashtag_listbox, word_text, "해시태그", append_status), append_status("선택된 해시태그가 검색 목록에 추가되었습니다.")]
    ).grid(row=0, column=0, padx=5, pady=1, sticky='ew')
    ttk.Button(selection_buttons_frame, text="모든 해시태그 추가",
               command=lambda: [add_all_items_from_listbox(hashtag_listbox, word_text, "해시태그", append_status), append_status("모든 해시태그가 검색 목록에 추가되었습니다.")]
    ).grid(row=0, column=1, padx=5, pady=1, sticky='ew')
    ttk.Button(selection_buttons_frame, text="선택된 사용자 ID 추가",
               command=lambda: [add_items_from_listbox(user_id_listbox, word_text, "사용자 ID", append_status), append_status("선택된 사용자 ID가 검색 목록에 추가되었습니다.")]
    ).grid(row=1, column=0, padx=5, pady=1, sticky='ew')
    ttk.Button(selection_buttons_frame, text="모든 사용자 ID 추가",
               command=lambda: [add_all_items_from_listbox(user_id_listbox, word_text, "사용자 ID", append_status), append_status("모든 사용자 ID가 검색 목록에 추가되었습니다.")]
    ).grid(row=1, column=1, padx=5, pady=1, sticky='ew')

    user_ids_cached = []
    
    # 전체 목록을 저장할 변수들 (검색 필터링용)
    all_hashtags = []
    all_user_ids = []
    
    # 검색 기능 구현
    def filter_hashtags(*args):
        """해시태그 검색 필터링"""
        search_term = hashtag_search_var.get()
        
        # placeholder 텍스트인 경우 전체 표시
        if search_term == "해시태그 검색..." or not search_term:
            hashtag_listbox.delete(0, tk.END)
            for hashtag in all_hashtags:
                hashtag_listbox.insert(tk.END, hashtag)
            hashtag_count_var.set(f"해시태그 목록 ({len(all_hashtags)}개)")
            return
        
        search_term = search_term.lower()
        hashtag_listbox.delete(0, tk.END)
        
        filtered_hashtags = []
        for hashtag in all_hashtags:
            if search_term in hashtag.lower():
                filtered_hashtags.append(hashtag)
                hashtag_listbox.insert(tk.END, hashtag)
        
        # 개수 업데이트
        hashtag_count_var.set(f"해시태그 목록 ({len(filtered_hashtags)}개)")
    
    def filter_user_ids(*args):
        """사용자 ID 검색 필터링"""
        search_term = user_id_search_var.get()
        
        # placeholder 텍스트인 경우 전체 표시
        if search_term == "사용자 ID 검색..." or not search_term:
            user_id_listbox.delete(0, tk.END)
            for user_id in all_user_ids:
                user_id_listbox.insert(tk.END, user_id)
            user_id_count_var.set(f"사용자 ID 목록 ({len(all_user_ids)}개)")
            return
        
        search_term = search_term.lower()
        user_id_listbox.delete(0, tk.END)
        
        filtered_user_ids = []
        for user_id in all_user_ids:
            if search_term in user_id.lower():
                filtered_user_ids.append(user_id)
                user_id_listbox.insert(tk.END, user_id)
        
        # 개수 업데이트
        user_id_count_var.set(f"사용자 ID 목록 ({len(filtered_user_ids)}개)")
    
    # 검색 이벤트 바인딩
    hashtag_search_var.trace('w', filter_hashtags)
    user_id_search_var.trace('w', filter_user_ids)

    # === 그룹 2: 데이터 관리 ===


    ttk.Button(selection_buttons_frame, text="선택된 대상 삭제",
               command=lambda: delete_selected_items(hashtag_listbox, user_id_listbox, download_directory_var, append_status), width=15
    ).grid(row=2, column=0, columnspan=2, padx=5, pady=(5, 1), sticky='ew')

    # 디렉토리 로드 함수를 모듈에서 호출
    def load_existing_directories_wrapper():
        nonlocal all_hashtags, all_user_ids
        
        # 기존 로드 함수 호출
        load_existing_directories(hashtag_listbox, user_id_listbox, download_directory_var, append_status)
        
        # 전체 목록 업데이트
        all_hashtags = [hashtag_listbox.get(i) for i in range(hashtag_listbox.size())]
        all_user_ids = [user_id_listbox.get(i) for i in range(user_id_listbox.size())]
        
        # 개수 업데이트
        hashtag_count_var.set(f"해시태그 목록 ({len(all_hashtags)}개)")
        user_id_count_var.set(f"사용자 ID 목록 ({len(all_user_ids)}개)")
        
        # 검색 필터 재적용 (검색어가 있는 경우)
        if hashtag_search_var.get():
            filter_hashtags()
        if user_id_search_var.get():
            filter_user_ids()

    # 정렬 함수들 (통합)
    def create_sort_function(sort_func, *args):
        def sort_wrapper():
            nonlocal all_user_ids
            sort_func(user_id_listbox, append_status, *args)
            # 전체 목록 업데이트
            all_user_ids = [user_id_listbox.get(i) for i in range(user_id_listbox.size())]
            user_id_count_var.set(f"사용자 ID 목록 ({len(all_user_ids)}개)")
            # 검색 필터 재적용
            if user_id_search_var.get():
                filter_user_ids()
        return sort_wrapper
    
    sort_creation_desc = create_sort_function(sort_user_ids_by_creation_desc, download_directory_var)
    sort_creation_asc = create_sort_function(sort_user_ids_by_creation_asc, download_directory_var)
    sort_ini_asc = create_sort_function(sort_user_ids_by_ini_asc)
    sort_ini_desc = create_sort_function(sort_user_ids_by_ini_desc)
    
    # 다이얼로그 창 상태 관리
    profile_dialog = None
    
    # 존재하지 않는 프로필 관리 함수를 모듈에서 호출
    def manage_profiles_wrapper():
        """통합 프로필 관리 다이얼로그를 표시합니다."""
        nonlocal profile_dialog
        
        # 이미 열려있는 창이 있는지 확인
        try:
            if profile_dialog and profile_dialog.winfo_exists():
                # 기존 창을 앞으로 가져오기
                profile_dialog.lift()
                profile_dialog.focus()
                return
        except tk.TclError:
            # 창이 이미 닫혀있는 경우
            profile_dialog = None
        
        # 새 창 생성
        profile_dialog = manage_profiles(append_status)
        return profile_dialog
    
    sort_buttons_frame = ttk.Frame(existing_dirs_frame)
    sort_buttons_frame.grid(row=1, column=1, padx=5, pady=1, sticky='nsew')
    sort_buttons_frame.columnconfigure(0, weight=1)
    sort_buttons_frame.columnconfigure(1, weight=1)
    ttk.Button(sort_buttons_frame, text="생성일 내림차순", command=sort_creation_desc).grid(row=0, column=0, padx=5, pady=1, sticky='ew')
    ttk.Button(sort_buttons_frame, text="INI 내림차순", command=sort_ini_desc).grid(row=0, column=1, padx=5, pady=1, sticky='ew')
    ttk.Button(sort_buttons_frame, text="생성일 오름차순", command=sort_creation_asc).grid(row=1, column=0, padx=5, pady=1, sticky='ew')
    ttk.Button(sort_buttons_frame, text="INI 오름차순", command=sort_ini_asc).grid(row=1, column=1, padx=5, pady=1, sticky='ew')
    ttk.Button(existing_dirs_frame, text="새로 고침", command=load_existing_directories_wrapper, width=15).grid(row=1, column=0, pady=3)

    progress_frame = ttk.Frame(root)
    progress_frame.grid(row=6, column=0, padx=10, pady=5, sticky='ew')
    progress_frame.columnconfigure(0, weight=1)
    
    # 진행률
    overall_progress_label_var = tk.StringVar(value="진행률: 0% (0/0)")
    overall_progress_label = ttk.Label(progress_frame, textvariable=overall_progress_label_var, font=('Arial', 10, 'bold'))
    overall_progress_label.grid(row=0, column=0, sticky='w', padx=10, pady=(0,2))
    overall_progress_var = tk.DoubleVar()
    overall_progress_bar = ttk.Progressbar(progress_frame, variable=overall_progress_var, maximum=100, length=400)
    overall_progress_bar.grid(row=1, column=0, sticky='ew', padx=10, pady=2)
    
    # 예상 완료 시간
    eta_label_var = tk.StringVar(value="예상 완료 시간: 계산 중...")
    eta_label = ttk.Label(progress_frame, textvariable=eta_label_var, font=('Arial', 8))
    eta_label.grid(row=2, column=0, sticky='w', padx=10, pady=(2,5))
    global_stop_event = threading.Event()

    # 설정 업데이트를 위한 전역 변수
    config_update_pending = set()  # 제거할 검색어들을 저장
    last_config_update_time = 0

    main_search_terms = []
    main_search_type = ""

    # 프로그레스바 업데이트 함수들
    def update_overall_progress(current, total, current_term=""):
        """진행률 업데이트"""
        if total > 0:
            percentage = (current / total) * 100
            overall_progress_var.set(percentage)
            overall_progress_label_var.set(f"진행률: {percentage:.1f}% ({current}/{total})")
            if current_term:
                overall_progress_label_var.set(f"진행률: {percentage:.1f}% ({current}/{total}) - {current_term}")
    
    def update_current_progress(current, total, term_name=""):
        """현재 프로필 진행률 업데이트 (사용하지 않음)"""
        pass
    
    def reset_progress():
        """프로그레스바 초기화"""
        overall_progress_var.set(0)
        overall_progress_label_var.set("진행률: 0% (0/0)")
        eta_label_var.set("예상 완료 시간: 계산 중...")
    
    def update_eta(start_time, current, total):
        """예상 완료 시간 업데이트"""
        if current > 0 and total > 0:
            elapsed_time = time.time() - start_time
            avg_time_per_item = elapsed_time / current
            remaining_items = total - current
            estimated_remaining_time = avg_time_per_item * remaining_items
            
            # 예상 완료 시간 계산
            estimated_completion_time = datetime.now() + timedelta(seconds=estimated_remaining_time)
            eta_str = estimated_completion_time.strftime("%H:%M:%S")
            
            # 남은 시간을 분:초 형태로 표시
            remaining_minutes = int(estimated_remaining_time // 60)
            remaining_seconds = int(estimated_remaining_time % 60)
            time_str = f"{remaining_minutes}분 {remaining_seconds}초"
            
            eta_label_var.set(f"예상 완료 시간: {eta_str} (약 {time_str} 남음)")

    # 설정 업데이트 함수 (배치 처리)
    def update_config_batch():
        nonlocal last_config_update_time
        import time
        current_time = time.time()
        
        # 1초 이상 지났고 업데이트할 항목이 있으면 처리
        if config_update_pending and (current_time - last_config_update_time) > 1.0:
            try:
                config = load_config()
                search_terms = config.get('SEARCH_TERMS', [])
                
                # 제거할 항목들을 일괄 제거
                for term_to_remove in config_update_pending:
                    if term_to_remove in search_terms:
                        search_terms.remove(term_to_remove)
                
                config['SEARCH_TERMS'] = search_terms
                save_config(config)
                
                removed_count = len(config_update_pending)
                config_update_pending.clear()
                last_config_update_time = current_time
                
                append_status(f"설정 파일 업데이트: {removed_count}개 항목 제거됨")
            except Exception as e:
                append_status(f"설정 파일 업데이트 오류: {e}")
                config_update_pending.clear()

    # process_queue 함수를 모듈에서 호출
    def process_queue_wrapper(q):
        process_queue(q, append_status, word_text, config_update_pending)
        update_config_batch()  # 설정 업데이트 확인
        root.after(100, lambda: process_queue_wrapper(q))

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
        reset_progress()
        update_overall_progress(0, total, "재분류 시작")
        append_status("재분류 진행 중...")
        def worker():
            for i, (term, stype, img_dir) in enumerate(dirs_to_reclassify, start=1):
                if stop_evt.is_set():
                    append_status("중지: 재분류 중지됨.")
                    return
                
                # 현재 프로필 진행률 업데이트 (제거됨)
                
                success = process_images(
                    root, append_status, download_directory_var,
                    term, "", config['LAST_SEARCH_TYPE'], stop_evt,
                    upscale=False,
                    classified=True
                )
                
                # 전체 진행률 업데이트
                update_overall_progress(i, total, f"재분류: {term}")
                
                if success:
                    append_status(f"완료: {term} 재분류 완료.")
                else:
                    append_status(f"오류: {term} 재분류 오류.")
            
            append_status("모든 재분류 완료.")
            update_overall_progress(total, total, "재분류 완료")
            eta_label_var.set("재분류 완료!")
            load_existing_directories_wrapper()
        threading.Thread(target=worker, daemon=True).start()



    # 크롤링 관련 헬퍼 함수들
    def validate_search_terms():
        """검색어 검증 및 파싱"""
        terms_raw = word_text.get("1.0", tk.END).strip()
        if not terms_raw:
            append_status("오류: 검색할 해시태그 또는 사용자 ID 입력 필요.")
            return None
        
        search_terms = [t.strip() for t in terms_raw.replace(',', '\n').split('\n') if t.strip()]
        if not search_terms:
            append_status("오류: 유효한 검색어 없음.")
            return None
        
        return search_terms
    
    def filter_excluded_profiles(search_terms):
        """존재하지 않는 프로필과 비공개 프로필 제외"""
        if config['LAST_SEARCH_TYPE'] != 'user':
            return search_terms
        
        from ..core.profile_manager import load_profile_ids_from_stamps
        
        non_existent_profile_ids = config.get('NON_EXISTENT_PROFILE_IDS', [])
        profile_ids_map = load_profile_ids_from_stamps()
        excluded_terms = []
        
        # profile-id 기반으로 제외할 프로필 찾기
        for term in search_terms[:]:
            profile_id = profile_ids_map.get(term)
            if profile_id and profile_id in non_existent_profile_ids:
                search_terms.remove(term)
                excluded_terms.append(term)
        
        # 하위 호환성을 위한 username 기반 제외
        non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
        for term in search_terms[:]:
            if term in non_existent_profiles:
                search_terms.remove(term)
                excluded_terms.append(term)
        
        # 비공개 프로필 제외 (profile-id 기반)
        private_not_followed_profile_ids = config.get('PRIVATE_NOT_FOLLOWED_PROFILE_IDS', [])
        for term in search_terms[:]:
            profile_id = profile_ids_map.get(term)
            if profile_id and profile_id in private_not_followed_profile_ids:
                search_terms.remove(term)
                excluded_terms.append(term)
        
        # 하위 호환성을 위한 username 기반 제외
        private_not_followed_profiles = config.get('PRIVATE_NOT_FOLLOWED_PROFILES', [])
        for term in search_terms[:]:
            if term in private_not_followed_profiles:
                search_terms.remove(term)
                excluded_terms.append(term)
        
        # 제외된 프로필 처리
        if excluded_terms:
            append_status(f"존재하지 않는 프로필 및 비공개 프로필 {len(excluded_terms)}개 제외됨: {', '.join(excluded_terms)}")
            
            # GUI 검색목록에서도 제외된 프로필들 제거
            current_text = word_text.get("1.0", tk.END).strip()
            if current_text:
                lines = current_text.split('\n')
                filtered_lines = [line.strip() for line in lines if line.strip() and line.strip() not in excluded_terms]
                word_text.delete("1.0", tk.END)
                if filtered_lines:
                    word_text.insert("1.0", '\n'.join(filtered_lines))
                append_status(f"검색목록에서 제외된 프로필 {len(excluded_terms)}개 제거됨")
        
        return search_terms
    
    def prepare_crawling_config(search_terms):
        """크롤링 설정 준비"""
        # 게시글 수 설정
        try:
            target = int(post_count_entry.get().strip())
            if target < 0:
                append_status("오류: 게시글 수는 0 이상이어야 함.")
                return None
        except ValueError:
            append_status("오류: 게시글 수는 정수여야 함.")
            return None
        
        # 다운로드 경로 설정
        d_path = download_directory_var.get().strip()
        if not os.path.isdir(d_path):
            create_dir_if_not_exists(d_path)
            append_status(f"다운로드 경로 생성됨: {d_path}")
        
        # 요청 간 대기시간 설정
        try:
            request_wait_time = float(wait_time_var.get())
            if request_wait_time < 0:
                append_status("경고: 대기시간은 0 이상이어야 합니다. 0초로 설정합니다.")
                request_wait_time = 0.0
            config['REQUEST_WAIT_TIME'] = request_wait_time
        except ValueError:
            append_status("경고: 대기시간 설정이 잘못되었습니다. 0초로 설정합니다.")
            config['REQUEST_WAIT_TIME'] = 0.0
        
        # 설정 업데이트
        config['SEARCH_TERMS'] = search_terms
        config['LAST_SEARCH_TYPE'] = search_type_var.get()
        config['INCLUDE_IMAGES'] = (include_images_var_hashtag.get() if config['LAST_SEARCH_TYPE'] == "hashtag" 
                                    else include_images_var_user.get())
        config['INCLUDE_VIDEOS'] = (include_videos_var_hashtag.get() if config['LAST_SEARCH_TYPE'] == "hashtag" else False)
        config['INCLUDE_REELS'] = (include_reels_var_user.get() if config['LAST_SEARCH_TYPE'] == "user" else False)
        config['INCLUDE_HUMAN_CLASSIFY'] = (
            include_human_classify_var_hashtag.get() if config['LAST_SEARCH_TYPE'] == "hashtag"
            else include_human_classify_var_user.get()
        )
        config['INCLUDE_UPSCALE'] = (
            upscale_var_hashtag.get() if config['LAST_SEARCH_TYPE'] == "hashtag"
            else upscale_var_user.get()
        )
        config['LAST_DOWNLOAD_PATH'] = d_path
        save_config(config)
        
        return {
            'target': target,
            'download_path': d_path,
            'allow_duplicate': allow_duplicate_var.get(),
            'config': config
        }
    
    def execute_crawling(search_terms, crawling_config):
        """크롤링 실행"""
        config = crawling_config['config']
        nonlocal main_search_terms, main_search_type
        main_search_terms.clear()
        main_search_terms.extend(search_terms)
        main_search_type = config['LAST_SEARCH_TYPE']
        
        # 전체 진행률 초기화
        global total_terms
        total_terms = len(search_terms)
        update_overall_progress(0, total_terms)
        
        q = Queue()
        global_stop_event.clear()
        start_time = time.time()
        
        threading.Thread(
            target=crawl_and_download,
            args=(
                main_search_terms,
                crawling_config['target'],
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
                crawling_config['download_path'],
                append_status,
                root,
                download_directory_var,
                crawling_config['allow_duplicate'],
                update_overall_progress,
                update_current_progress,
                update_eta,
                start_time,
                total_terms
            ),
            daemon=True
        ).start()
        process_queue_wrapper(q)

    def start_crawling():
        """크롤링 시작 - 리팩토링된 버전"""
        append_status("크롤링 시작됨...")
        reset_progress()
        
        # 1. 검색어 검증
        search_terms = validate_search_terms()
        if not search_terms:
            return
        
        # 2. 프로필 필터링
        search_terms = filter_excluded_profiles(search_terms)
        if not search_terms:
            append_status("오류: 제외 후 유효한 검색어가 없습니다.")
            return
        
        # 3. 설정 준비
        crawling_config = prepare_crawling_config(search_terms)
        if not crawling_config:
            return
        
        # 4. 크롤링 실행
        execute_crawling(search_terms, crawling_config)

    def stop_crawling():
        global_stop_event.set()
        append_status("크롤링 및 분류 중지 요청됨.")

    button_frame = ttk.Frame(root)
    button_frame.grid(row=8, column=0, pady=5, padx=10, sticky='ew')
    for i in range(3):
        button_frame.columnconfigure(i, weight=1)
    ttk.Button(button_frame, text="크롤링 시작", command=start_crawling, width=15).grid(row=0, column=0, padx=5, pady=2, sticky='ew')
    ttk.Button(button_frame, text="중지", command=stop_crawling, width=15).grid(row=0, column=1, padx=5, pady=2, sticky='ew')
    ttk.Button(selection_buttons_frame, text="프로필 관리", command=manage_profiles_wrapper, width=20).grid(row=3, column=0, columnspan=2, padx=5, pady=1, sticky='ew')
    
    # === 그룹 3: 이미지 처리 ===
    ttk.Button(selection_buttons_frame, text="선택된 이미지 분류", command=lambda: process_images(global_stop_event), width=20).grid(row=4, column=0, columnspan=2, padx=5, pady=(5, 1), sticky='ew')
    ttk.Button(selection_buttons_frame, text="분류된 이미지 재분류", command=lambda: reclassify_classified_images(global_stop_event), width=20).grid(row=5, column=0, columnspan=2, padx=5, pady=1, sticky='ew')

    def on_complete(message):
        append_status(f"완료: {message}")
        # 진행률을 100%로 설정
        if 'total_terms' in globals():
            update_overall_progress(total_terms, total_terms, "완료")
        else:
            update_overall_progress(1, 1, "완료")
        eta_label_var.set("완료!")
        
        # 마지막 배치 업데이트 처리
        if config_update_pending:
            update_config_batch()
        
        load_existing_directories_wrapper()

    if config['ACCOUNTS']:
        for account in config['ACCOUNTS']:
            accounts_listbox.insert(tk.END, account['INSTAGRAM_USERNAME'])
        append_status("저장된 계정 자동 입력됨.")
        
        # 마지막 사용된 계정 자동 선택
        last_account_used = config.get('LAST_ACCOUNT_USED')
        if last_account_used:
            for i in range(accounts_listbox.size()):
                if accounts_listbox.get(i) == last_account_used:
                    accounts_listbox.selection_set(i)
                    accounts_listbox.see(i)
                    append_status(f"마지막 사용 계정 자동 선택됨: {last_account_used}")
                    break
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
            toggle_human_classify(hashtag_frame, include_images_var_hashtag, include_human_classify_var_hashtag, 
                                include_human_classify_check_hashtag, include_human_classify_check_user)
        else:
            toggle_human_classify(user_id_frame, include_images_var_user, include_human_classify_var_user,
                                include_human_classify_check_hashtag, include_human_classify_check_user)
    initial_toggle()
    
    root.rowconfigure(7, weight=1)
    root.columnconfigure(0, weight=1)
    load_existing_directories_wrapper()
    root.mainloop()
    print("GUI 종료")

if __name__ == '__main__':
    main_gui()