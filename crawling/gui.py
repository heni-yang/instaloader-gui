import os
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
from queue import Queue, Empty
from crawling.config import load_config, save_config
from crawling.downloader import crawl_and_download
from crawling.classifier import classify_images
import subprocess
import configparser
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
DEFAULT_DOWNLOAD_PATH = os.path.join(PROJECT_ROOT, 'download')
SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')

def main_gui():
    print("GUI 시작...")
    root = tk.Tk()
    root.title("인스타그램 이미지 크롤링 프로그램 (Instaloader 기반)")
    root.geometry("900x1000")
    root.minsize(900, 1000)
    root.columnconfigure(0, weight=1)

    # 스타일 설정
    style = ttk.Style(root)
    style.configure('TButton', font=('Arial', 10))
    style.configure('TLabel', font=('Arial', 10))
    style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

    header = ttk.Label(root, text="인스타그램 이미지 크롤링 프로그램", style='Header.TLabel')
    header.grid(row=0, column=0, pady=10, padx=10, sticky='ew')

    # 상단 프레임 및 계정 정보 영역
    top_frame = ttk.Frame(root)
    top_frame.grid(row=1, column=0, padx=10, pady=5, sticky='ew')
    top_frame.columnconfigure(0, weight=1)
    top_frame.columnconfigure(1, weight=1)

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

    # 설정 불러오기
    config = load_config()
    loaded_accounts = config['ACCOUNTS'][:] 

    # 상태 출력 영역
    status_frame = ttk.LabelFrame(root, text="상태", padding=3)
    status_frame.grid(row=7, column=0, padx=10, pady=5, sticky='nsew')
    status_frame.columnconfigure(0, weight=1)
    status_frame.rowconfigure(0, weight=1)
    status_text = tk.Text(status_frame, height=10, font=('Arial', 10), state='disabled')
    status_text.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

    def append_status(message):
        def append():
            status_text.configure(state='normal')
            status_text.insert(tk.END, message + '\n')
            status_text.see(tk.END)
            status_text.configure(state='disabled')
        root.after(0, append)

    # ─── 공통 함수 ───────────────────────────────────────────────
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
        append_status(f"성공: {len(items)}개의 {item_label}가 검색 목록에 추가되었습니다.")

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
        append_status(f"성공: 모든 {item_label}가 검색 목록에 추가되었습니다.")
    # ─────────────────────────────────────────────────────────────

    # ─── 계정 추가/삭제 ───────────────────────────────────────────
    def add_account():
        add_window = tk.Toplevel(root)
        add_window.title("계정 추가")
        add_window.geometry("430x250")  # 기존보다 창 높이를 늘림
        add_window.resizable(False, False)

        # ── 1) 로그인 히스토리 영역 ─────────────────────────────
        ttk.Label(add_window, text="히스토리:").grid(row=0, column=0, sticky='w', pady=(10,2), padx=10)
        history_var = tk.StringVar()
        # config의 LOGIN_HISTORY가 없으면 빈 리스트, 있으면 리스트 반환
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
            # LOGIN_HISTORY에서 선택된 계정을 제거
            new_history = [item for item in config.get('LOGIN_HISTORY', []) if item['username'] != selected]
            config['LOGIN_HISTORY'] = new_history
            save_config(config)
            append_status(f"히스토리에서 {selected} 계정을 삭제했습니다.")
            # 콤보박스 값 업데이트
            history_combo['values'] = [item['username'] for item in new_history]
            history_var.set("")

        ttk.Button(add_window, text="히스토리 삭제", command=delete_history).grid(row=1, column=1, sticky='e', padx=10, pady=(0,10))
        # ─────────────────────────────────────────────────────────────

        # ── 2) 아이디/비밀번호 입력 영역 ────────────────────────────
        ttk.Label(add_window, text="아이디:").grid(row=2, column=0, sticky='w', pady=(10,2), padx=10)
        new_username_entry = ttk.Entry(add_window, width=40, font=('Arial', 10))
        new_username_entry.grid(row=2, column=1, pady=(10,10), padx=10)

        ttk.Label(add_window, text="비밀번호:").grid(row=3, column=0, sticky='w', pady=(5,2), padx=10)
        new_password_entry = ttk.Entry(add_window, show="*", width=40, font=('Arial', 10))
        new_password_entry.grid(row=3, column=1, pady=(5,10), padx=10)

        # ── 3) 다운로드 경로 영역 ─────────────────────────────────────
        ttk.Label(add_window, text="다운로드 경로:").grid(row=4, column=0, sticky='w', pady=(5,2), padx=10)
        download_dir_frame = ttk.Frame(add_window)
        download_dir_frame.grid(row=4, column=1, pady=(5,10), padx=10, sticky='ew')
        download_directory_var_add = tk.StringVar(value=DEFAULT_DOWNLOAD_PATH)
        download_dir_entry = ttk.Entry(download_dir_frame, textvariable=download_directory_var_add, width=30, font=('Arial', 10))
        download_dir_entry.pack(side='left', padx=(0,5), fill='x', expand=True)

        def select_download_directory_add():
            directory = filedialog.askdirectory(initialdir=DEFAULT_DOWNLOAD_PATH)
            if directory:
                download_directory_var_add.set(directory)

        ttk.Button(download_dir_frame, text="경로 선택", command=select_download_directory_add, width=10).pack(side='left')

        # ── 4) 계정 추가 버튼 ─────────────────────────────────────────
        def save_new_account():
            username = new_username_entry.get().strip()
            password = new_password_entry.get().strip()
            download_path = download_directory_var_add.get().strip()
            if not username or not password:
                append_status("오류: 아이디와 비밀번호를 입력하세요.")
                return
            os.makedirs(download_path, exist_ok=True)
            os.makedirs(os.path.join(download_path, 'hashtag'), exist_ok=True)
            os.makedirs(os.path.join(download_path, 'ID'), exist_ok=True)
            accounts_listbox.insert(tk.END, username)
            loaded_accounts.append({
                'INSTAGRAM_USERNAME': username,
                'INSTAGRAM_PASSWORD': password,
                'DOWNLOAD_PATH': download_path
            })
            config['ACCOUNTS'] = loaded_accounts

            # 로그인 히스토리에 추가 (중복이면 업데이트)
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

            save_config(config)
            append_status(f"정보: 새로운 계정 {username}이 추가되었습니다.")
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
            append_status(f"정보: 계정 {username}이 제거되었습니다.")
        load_existing_directories()
    # ─────────────────────────────────────────────────────────────
        # ───────── 세션 삭제 함수 ─────────
    def remove_session():
        selected_indices = accounts_listbox.curselection()
        if not selected_indices:
            append_status("오류: 세션 삭제할 계정을 선택하세요.")
            return

        for index in reversed(selected_indices):
            username = accounts_listbox.get(index)
            session_file = os.path.join(SESSION_DIR, f"{username}.session")
            if os.path.isfile(session_file):
                os.remove(session_file)
                append_status(f"정보: {username} 계정의 세션 파일을 삭제했습니다.")
            else:
                append_status(f"정보: {username} 계정의 세션 파일이 없습니다.")
                
    # 버튼 3개: "계정 추가", "계정 제거", "세션 삭제"
    add_account_button = ttk.Button(account_buttons_frame, text="계정 추가", command=add_account, width=8)
    add_account_button.grid(row=0, column=0, padx=5, pady=2, sticky='ew')

    remove_account_button = ttk.Button(account_buttons_frame, text="계정 제거", command=remove_account, width=8)
    remove_account_button.grid(row=0, column=1, padx=5, pady=2, sticky='ew')

    remove_session_button = ttk.Button(account_buttons_frame, text="세션 삭제", command=remove_session, width=8)
    remove_session_button.grid(row=0, column=2, padx=5, pady=2, sticky='ew')


    # ─── 검색 유형 및 옵션 영역 ──────────────────────────────────────
    search_type_frame = ttk.LabelFrame(top_frame, text="검색 유형 선택", padding=5)
    search_type_frame.grid(row=0, column=1, padx=(10,0), pady=5, sticky='nsew')
    search_type_frame.columnconfigure(0, weight=1)
    search_type_frame.columnconfigure(1, weight=1)

    search_type_var = tk.StringVar(value="hashtag")

    # 해시태그 검색 프레임
    hashtag_frame = ttk.Frame(search_type_frame)
    hashtag_frame.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
    hashtag_frame.columnconfigure(0, weight=1)

    ttk.Radiobutton(hashtag_frame, text="해시태그 검색", variable=search_type_var, value="hashtag").grid(row=0, column=0, sticky='w')

    hashtag_check_frame = ttk.Frame(hashtag_frame)
    hashtag_check_frame.grid(row=1, column=0, sticky='w', pady=2)

    include_images_var_hashtag = tk.BooleanVar(value=True)
    include_videos_var_hashtag = tk.BooleanVar(value=False)
    include_human_classify_var_hashtag = tk.BooleanVar(value=False)

    # 체크박스 위젯에 대한 참조를 저장 (NameError 방지)
    include_images_check_hashtag = ttk.Checkbutton(
        hashtag_check_frame,
        text="이미지",
        variable=include_images_var_hashtag
    )
    include_images_check_hashtag.pack(side='left', padx=(0,5))

    include_videos_check_hashtag = ttk.Checkbutton(
        hashtag_check_frame,
        text="영상",
        variable=include_videos_var_hashtag
    )
    include_videos_check_hashtag.pack(side='left')

    include_human_classify_check_hashtag = ttk.Checkbutton(
        hashtag_frame,
        text="인물 분류",
        variable=include_human_classify_var_hashtag
    )
    include_human_classify_check_hashtag.grid(row=2, column=0, sticky='w', padx=20)
    include_human_classify_check_hashtag.configure(state='disabled')

    # 사용자 ID 검색 프레임
    user_id_frame = ttk.Frame(search_type_frame)
    user_id_frame.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')
    user_id_frame.columnconfigure(0, weight=1)

    ttk.Radiobutton(user_id_frame, text="사용자 ID 검색", variable=search_type_var, value="user").grid(row=0, column=0, sticky='w')

    user_id_check_frame = ttk.Frame(user_id_frame)
    user_id_check_frame.grid(row=1, column=0, sticky='w', pady=2)

    include_images_var_user = tk.BooleanVar(value=True)
    include_reels_var_user = tk.BooleanVar(value=False)
    include_human_classify_var_user = tk.BooleanVar(value=False)

    include_images_check_user = ttk.Checkbutton(
        user_id_check_frame,
        text="이미지",
        variable=include_images_var_user
    )
    include_images_check_user.pack(side='left', padx=(0,5))

    include_reels_check_user = ttk.Checkbutton(
        user_id_check_frame,
        text="릴스",
        variable=include_reels_var_user
    )
    include_reels_check_user.pack(side='left')

    include_human_classify_check_user = ttk.Checkbutton(
        user_id_frame,
        text="인물 분류",
        variable=include_human_classify_var_user
    )
    include_human_classify_check_user.grid(row=2, column=0, sticky='w', padx=20)
    include_human_classify_check_user.configure(state='disabled')

    allow_duplicate_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        search_type_frame,
        text="중복 다운로드 허용",
        variable=allow_duplicate_var
    ).grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=5)

    def toggle_human_classify(parent_frame, img_var, human_var):
        """이미지 옵션이 체크돼 있어야 인물 분류를 활성화한다."""
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

    def on_search_type_change(*args):
        """해시태그 검색/사용자 ID 검색 라디오 버튼 변경 시, 반대쪽 옵션 비활성화."""
        stype = search_type_var.get()
        if stype == "hashtag":
            # 해시태그 쪽 활성화
            include_images_check_hashtag.configure(state='normal')
            include_videos_check_hashtag.configure(state='normal')
            toggle_human_classify(hashtag_frame, include_images_var_hashtag, include_human_classify_var_hashtag)

            # 사용자 ID 쪽 비활성화
            include_images_check_user.configure(state='disabled')
            include_reels_check_user.configure(state='disabled')
            include_human_classify_var_user.set(False)
            include_human_classify_check_user.configure(state='disabled')
        else:
            # 사용자 ID 쪽 활성화
            include_images_check_user.configure(state='normal')
            include_reels_check_user.configure(state='normal')
            toggle_human_classify(user_id_frame, include_images_var_user, include_human_classify_var_user)

            # 해시태그 쪽 비활성화
            include_images_check_hashtag.configure(state='disabled')
            include_videos_check_hashtag.configure(state='disabled')
            include_human_classify_var_hashtag.set(False)
            include_human_classify_check_hashtag.configure(state='disabled')

    search_type_var.trace_add('write', on_search_type_change)
    # ─────────────────────────────────────────────────────────────

    # ─── 검색 설정 영역 ─────────────────────────────────────────────
    search_frame = ttk.LabelFrame(root, text="검색 설정", padding=5)
    search_frame.grid(row=2, column=0, padx=10, pady=5, sticky='ew')
    search_frame.columnconfigure(1, weight=1)

    ttk.Label(
        search_frame,
        text="검색할 해시태그 / 사용자 ID (여러 개는 개행 또는 쉼표로 구분):",
        wraplength=300
    ).grid(row=0, column=0, sticky='ne', pady=2, padx=10)

    word_text = scrolledtext.ScrolledText(search_frame, width=50, height=5, font=('Arial', 10))
    word_text.grid(row=0, column=1, pady=2, padx=10, sticky='ew')

    ttk.Label(search_frame, text="수집할 게시글 수 (0: 전체):").grid(row=1, column=0, sticky='e', pady=2, padx=10)
    post_count_entry = ttk.Entry(search_frame, width=20, font=('Arial', 10))
    post_count_entry.grid(row=1, column=1, sticky='w', pady=2, padx=10)
    post_count_entry.insert(0, "0")
    # ─────────────────────────────────────────────────────────────

    # ─── 다운로드 경로 설정 영역 ────────────────────────────────────
    download_dir_frame = ttk.LabelFrame(root, text="전체 다운로드 경로 설정", padding=5)
    download_dir_frame.grid(row=3, column=0, padx=10, pady=5, sticky='ew')
    download_dir_frame.columnconfigure(1, weight=1)

    ttk.Label(download_dir_frame, text="기본 저장 경로:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
    download_directory_var = tk.StringVar(value=DEFAULT_DOWNLOAD_PATH)
    download_dir_entry = ttk.Entry(download_dir_frame, textvariable=download_directory_var, width=50, font=('Arial', 10))
    download_dir_entry.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

    def open_download_directory():
        d = download_directory_var.get()
        if os.path.isdir(d):
            if os.name == 'nt':
                os.startfile(d)
            else:
                subprocess.Popen(["open", d])
        else:
            append_status("오류: 다운로드 디렉토리가 존재하지 않습니다.")

    def select_download_directory_main():
        d = filedialog.askdirectory(initialdir=DEFAULT_DOWNLOAD_PATH)
        if d:
            download_directory_var.set(d)
            load_existing_directories()
            for acc in loaded_accounts:
                acc['DOWNLOAD_PATH'] = d
            save_config(config)
            append_status("정보: 다운로드 경로가 변경되었습니다.")
            print("다운로드 경로 업데이트됨.")

    ttk.Button(download_dir_frame, text="경로 선택", command=select_download_directory_main, width=12).grid(row=0, column=2, padx=5, pady=5)
    ttk.Button(download_dir_frame, text="폴더 열기", command=open_download_directory, width=12).grid(row=0, column=3, padx=5, pady=5)
    # ─────────────────────────────────────────────────────────────

    # ─── 기존 다운로드 디렉토리 영역 ─────────────────────────────────
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
    # ─────────────────────────────────────────────────────────────

    # ─── 정렬 및 진행 영역 ──────────────────────────────────────────
    user_ids_cached = []

    def load_existing_directories():
        main_download_dir = download_directory_var.get()
        if not os.path.isdir(main_download_dir):
            append_status(f"오류: 다운로드 경로가 존재하지 않습니다: {main_download_dir}")
            return
        hashtag_dir = os.path.join(main_download_dir, '인물')
        user_id_dir = os.path.join(main_download_dir, '인물')
        os.makedirs(hashtag_dir, exist_ok=True)
        os.makedirs(user_id_dir, exist_ok=True)
        hashtag_listbox.delete(0, tk.END)
        user_id_listbox.delete(0, tk.END)
        for tag in [d for d in os.listdir(hashtag_dir) if os.path.isdir(os.path.join(hashtag_dir, d))]:
            hashtag_listbox.insert(tk.END, tag)
        nonlocal user_ids_cached
        user_ids_cached = []
        for d in os.listdir(user_id_dir):
            full_path = os.path.join(user_id_dir, d)
            if os.path.isdir(full_path) and d.startswith("user_"):
                actual_uid = d[len("user_"):]
                try:
                    ct = os.path.getctime(full_path)
                    mt = os.path.getmtime(full_path)
                    user_ids_cached.append((actual_uid, ct, mt))
                except Exception as e:
                    append_status(f"경고: 디렉토리 {d}의 생성/수정일 가져오기 오류: {e}")
        for uid, _, _ in sorted(user_ids_cached, key=lambda x: x[1], reverse=True):
            user_id_listbox.insert(tk.END, uid)

    def sort_user_ids_by_creation_desc():
        user_id_listbox.delete(0, tk.END)
        for uid, ct, mt in sorted(user_ids_cached, key=lambda x: x[1], reverse=True):
            user_id_listbox.insert(tk.END, uid)
        append_status("정보: 사용자 ID가 '생성일' 기준 내림차순 정렬되었습니다.")

    def sort_user_ids_by_creation_asc():
        user_id_listbox.delete(0, tk.END)
        for uid, ct, mt in sorted(user_ids_cached, key=lambda x: x[1]):
            user_id_listbox.insert(tk.END, uid)
        append_status("정보: 사용자 ID가 '생성일' 기준 오름차순 정렬되었습니다.")

    def sort_user_ids_by_modified_asc():
        ini_path = os.path.join(os.path.dirname(__file__), 'latest-stamps-images.ini')
        if not os.path.isfile(ini_path):
            append_status("오류: latest-stamps-images.ini 파일을 찾을 수 없습니다.")
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
        append_status("정보: INI의 post-timestamp 기준 오름차순 정렬 완료.")

    sort_buttons_frame = ttk.Frame(existing_dirs_frame)
    sort_buttons_frame.grid(row=1, column=1, padx=5, pady=2, sticky='nsew')
    sort_buttons_frame.columnconfigure(0, weight=1)
    sort_buttons_frame.columnconfigure(1, weight=1)
    ttk.Button(sort_buttons_frame, text="생성일 내림차순", command=sort_user_ids_by_creation_desc).grid(row=0, column=0, padx=5, pady=2, sticky='ew')
    ttk.Button(sort_buttons_frame, text="(INI) 오름차순", command=sort_user_ids_by_modified_asc).grid(row=0, column=1, padx=5, pady=2, sticky='ew')
    ttk.Button(sort_buttons_frame, text="생성일 올림차순", command=sort_user_ids_by_creation_asc).grid(row=1, column=0, padx=5, pady=2, sticky='ew')
    ttk.Button(existing_dirs_frame, text="새로 고침", command=load_existing_directories, width=15).grid(row=1, column=0, pady=5)
    # ─────────────────────────────────────────────────────────────

    # ─── 진행 및 분류 영역 ───────────────────────────────────────────
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
        append_status("정보: 선택된 분류된 이미지 재분류를 시작합니다.")
        d_path = download_directory_var.get().strip()
        classified_dir = os.path.join(d_path, "인물")
        dirs_to_reclassify = []

        # 해시태그 선택
        for idx in hashtag_listbox.curselection():
            tag = hashtag_listbox.get(idx)
            dir_name = "hashtag_" + tag
            img_dir = os.path.join(classified_dir, dir_name)
            if os.path.isdir(img_dir):
                dirs_to_reclassify.append((tag, 'hashtag', img_dir))
            else:
                append_status(f"경고: {img_dir}가 존재하지 않습니다.")

        # 사용자 ID 선택
        for idx in user_id_listbox.curselection():
            uid = user_id_listbox.get(idx)
            dir_name = "user_" + uid
            img_dir = os.path.join(classified_dir, dir_name)
            if os.path.isdir(img_dir):
                dirs_to_reclassify.append((uid, 'user', img_dir))
            else:
                append_status(f"경고: {img_dir}가 존재하지 않습니다.")

        if not dirs_to_reclassify:
            append_status("정보: 선택된 분류된 이미지가 없습니다.")
            return

        total = len(dirs_to_reclassify)
        root.after(0, lambda: progress_var.set(0))
        append_status("정보: 재분류 진행 중...")

        def worker():
            for i, (term, stype, img_dir) in enumerate(dirs_to_reclassify, start=1):
                if stop_evt.is_set():
                    append_status("중지: 재분류 프로세스가 중지되었습니다.")
                    return
                success = classify_images(
                    root, append_status, download_directory_var,
                    term, "", config['LAST_SEARCH_TYPE'], stop_evt,
                    classified=True
                )
                root.after(0, lambda p=(i/total)*100: progress_var.set(p))
                if success:
                    append_status(f"완료: {term} 재분류 완료.")
                else:
                    append_status(f"오류: {term} 재분류 중 오류 발생.")
            append_status("완료: 모든 분류된 이미지 재분류 완료.")
            root.after(0, lambda: progress_label_var.set("재분류 완료"))
            load_existing_directories()

        threading.Thread(target=worker, daemon=True).start()

    ttk.Button(
        existing_dirs_frame,
        text="분류된 이미지 재분류",
        command=lambda: reclassify_classified_images(global_stop_event),
        width=20
    ).grid(row=3, column=2, padx=5, pady=2, sticky='ew')

    def start_crawling():
        append_status("정보: 크롤링 시작됨...")
        terms_raw = word_text.get("1.0", tk.END).strip()
        if not terms_raw:
            append_status("오류: 검색할 해시태그 또는 사용자 ID를 입력하세요.")
            return
        config['SEARCH_TERMS'] = [t.strip() for t in terms_raw.replace(',', '\n').split('\n') if t.strip()]
        if not config['SEARCH_TERMS']:
            append_status("오류: 유효한 검색어가 없습니다.")
            return

        try:
            target = int(post_count_entry.get().strip())
            if target < 0:
                append_status("오류: 게시글 수는 0 이상이어야 합니다.")
                return
        except ValueError:
            append_status("오류: 게시글 수는 정수여야 합니다.")
            return

        nonlocal main_search_terms, main_search_type
        main_search_terms.clear()
        main_search_terms.extend(config['SEARCH_TERMS'])
        config['LAST_SEARCH_TYPE'] = search_type_var.get()
        main_search_type = config['LAST_SEARCH_TYPE']
        
        config['INCLUDE_IMAGES'] = (include_images_var_hashtag.get()
                                    if config['LAST_SEARCH_TYPE'] == "hashtag"
                                    else include_images_var_user.get() if include_images_var_user else False)
        config['INCLUDE_VIDEOS'] = (include_videos_var_hashtag.get()
                                    if config['LAST_SEARCH_TYPE'] == "hashtag"
                                    else False)
        config['INCLUDE_REELS'] = (include_reels_var_user.get()
                                   if config['LAST_SEARCH_TYPE'] == "user"
                                   else False)
        config['INCLUDE_HUMAN_CLASSIFY'] = (
            include_human_classify_var_hashtag.get()
            if config['LAST_SEARCH_TYPE'] == "hashtag"
            else include_human_classify_var_user.get() if config['LAST_SEARCH_TYPE'] == "user"
            else False
        )

        allow_duplicate = allow_duplicate_var.get()
        d_path = download_directory_var.get().strip()
        if not os.path.isdir(d_path):
            append_status(f"오류: 다운로드 경로가 존재하지 않습니다: {d_path}")
            return

        save_config(config)
        append_status("정보: 현재 설정이 저장되었습니다.")

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
        append_status("중지: 크롤링 및 분류 중지 요청됨.")

    button_frame = ttk.Frame(root)
    button_frame.grid(row=8, column=0, pady=5, padx=10, sticky='ew')
    for i in range(3):
        button_frame.columnconfigure(i, weight=1)

    ttk.Button(button_frame, text="크롤링 시작", command=start_crawling, width=15).grid(row=0, column=0, padx=5, pady=2, sticky='ew')
    ttk.Button(button_frame, text="중지", command=stop_crawling, width=15).grid(row=0, column=1, padx=5, pady=2, sticky='ew')
    ttk.Button(existing_dirs_frame, text="선택된 이미지 분류", command=lambda: classify_existing_images(global_stop_event), width=20
    ).grid(row=2, column=2, padx=5, pady=2, sticky='ew')

    def on_complete(message):
        append_status(f"완료: {message}")
        progress_var.set(100)
        progress_label_var.set(f"100% 완료")
        load_existing_directories()

    # ─── 초기 값 설정 ───────────────────────────────────────────────
    if config['ACCOUNTS']:
        for account in config['ACCOUNTS']:
            accounts_listbox.insert(tk.END, account['INSTAGRAM_USERNAME'])
        append_status("정보: 저장된 계정을 자동으로 입력했습니다.")

    if config['LAST_SEARCH_TYPE']:
        search_type_var.set(config['LAST_SEARCH_TYPE'])

    if config['LAST_SEARCH_TYPE'] == "hashtag":
        include_human_classify_var_hashtag.set(config['INCLUDE_HUMAN_CLASSIFY'])
    elif config['LAST_SEARCH_TYPE'] == "user":
        include_human_classify_var_user.set(config['INCLUDE_HUMAN_CLASSIFY'])

    if config['SEARCH_TERMS']:
        word_text.insert(tk.END, "\n".join(config['SEARCH_TERMS']))
        append_status("정보: 저장된 검색어를 자동으로 입력했습니다.")

    def initial_toggle():
        """GUI 초기화 시 이미지 체크박스 상태에 따라 인물 분류 활성화 여부를 설정."""
        toggle_human_classify(hashtag_frame, include_images_var_hashtag, include_human_classify_var_hashtag)
        toggle_human_classify(user_id_frame, include_images_var_user, include_human_classify_var_user)

    initial_toggle()

    root.rowconfigure(7, weight=1)
    root.columnconfigure(0, weight=1)
    load_existing_directories()
    root.mainloop()
    print("GUI 종료")

if __name__ == '__main__':
    main_gui()
