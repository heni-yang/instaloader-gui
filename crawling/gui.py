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

def main_gui():
    print("GUI 시작...")
    root = tk.Tk()
    root.title("인스타그램 이미지 크롤링 프로그램 (Instaloader 기반)")
    root.geometry("900x1000")
    root.minsize(900, 1000)
    root.columnconfigure(0, weight=1)

    style = ttk.Style(root)
    style.configure('TButton', font=('Arial', 10))
    style.configure('TLabel', font=('Arial', 10))
    style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

    header = ttk.Label(root, text="인스타그램 이미지 크롤링 프로그램", style='Header.TLabel')
    header.grid(row=0, column=0, pady=10, padx=10, sticky='ew')

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

    loaded_accounts = []
    saved_accounts, saved_search_type, saved_search_terms, saved_include_images, saved_include_videos, saved_include_reels = load_config()
    loaded_accounts.extend(saved_accounts)

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

    def add_account():
        add_window = tk.Toplevel(root)
        add_window.title("계정 추가")
        add_window.geometry("400x350")
        add_window.resizable(False, False)

        ttk.Label(add_window, text="아이디:").grid(row=0, column=0, sticky='w', pady=(10,2), padx=10)
        new_username_entry = ttk.Entry(add_window, width=40, font=('Arial', 10))
        new_username_entry.grid(row=0, column=1, pady=(10,10), padx=10)

        ttk.Label(add_window, text="비밀번호:").grid(row=1, column=0, sticky='w', pady=(5,2), padx=10)
        new_password_entry = ttk.Entry(add_window, show="*", width=40, font=('Arial', 10))
        new_password_entry.grid(row=1, column=1, pady=(5,10), padx=10)

        ttk.Label(add_window, text="다운로드 경로:").grid(row=2, column=0, sticky='w', pady=(5,2), padx=10)
        download_dir_frame = ttk.Frame(add_window)
        download_dir_frame.grid(row=2, column=1, pady=(5,10), padx=10, sticky='ew')

        download_directory_var_add = tk.StringVar(value=DEFAULT_DOWNLOAD_PATH)
        download_dir_entry = ttk.Entry(download_dir_frame, textvariable=download_directory_var_add, width=30, font=('Arial', 10))
        download_dir_entry.pack(side='left', padx=(0,5), fill='x', expand=True)

        def select_download_directory_add():
            directory = filedialog.askdirectory(initialdir=DEFAULT_DOWNLOAD_PATH)
            if directory:
                download_directory_var_add.set(directory)

        select_dir_button = ttk.Button(download_dir_frame, text="경로 선택", command=select_download_directory_add, width=10)
        select_dir_button.pack(side='left')

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
            # 계정 추가 시, 계정 정보만 저장
            save_config(
                loaded_accounts,
                saved_search_type,
                saved_search_terms,
                saved_include_images,
                saved_include_videos,
                saved_include_reels
            )
            append_status(f"정보: 새로운 계정 '{username}'이 추가되었습니다.")
            add_window.destroy()
            load_existing_directories()

        save_button = ttk.Button(add_window, text="추가", command=save_new_account)
        save_button.grid(row=3, column=0, columnspan=2, pady=10)

    def remove_account():
        selected_indices = accounts_listbox.curselection()
        if not selected_indices:
            append_status("오류: 제거할 계정을 선택하세요.")
            return
        for index in reversed(selected_indices):
            username = accounts_listbox.get(index)
            accounts_listbox.delete(index)
            loaded_accounts[:] = [acc for acc in loaded_accounts if acc['INSTAGRAM_USERNAME'] != username]
            append_status(f"정보: 계정 '{username}'이 제거되었습니다.")
        # 계정 제거 시, 계정 정보만 저장
        save_config(
            loaded_accounts,
            saved_search_type,
            saved_search_terms,
            saved_include_images,
            saved_include_videos,
            saved_include_reels
        )
        load_existing_directories()

    add_account_button = ttk.Button(account_buttons_frame, text="계정 추가", command=add_account, width=12)
    add_account_button.grid(row=0, column=0, padx=5, pady=2, sticky='ew')

    remove_account_button = ttk.Button(account_buttons_frame, text="계정 제거", command=remove_account, width=12)
    remove_account_button.grid(row=0, column=1, padx=5, pady=2, sticky='ew')

    search_type_frame = ttk.LabelFrame(top_frame, text="검색 유형 선택", padding=5)
    search_type_frame.grid(row=0, column=1, padx=(10,0), pady=5, sticky='nsew')
    search_type_frame.columnconfigure(0, weight=1)
    search_type_frame.columnconfigure(1, weight=1)

    search_type_var = tk.StringVar(value="hashtag")

    hashtag_frame = ttk.Frame(search_type_frame)
    hashtag_frame.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
    hashtag_frame.columnconfigure(0, weight=1)

    hashtag_radio = ttk.Radiobutton(hashtag_frame, text="해시태그 검색", variable=search_type_var, value="hashtag")
    hashtag_radio.grid(row=0, column=0, sticky='w')

    hashtag_check_frame = ttk.Frame(hashtag_frame)
    hashtag_check_frame.grid(row=1, column=0, sticky='w', pady=2)

    include_images_var_hashtag = tk.BooleanVar(value=True)
    include_videos_var_hashtag = tk.BooleanVar(value=False)
    include_human_classify_var_hashtag = tk.BooleanVar(value=False)

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

    user_id_frame = ttk.Frame(search_type_frame)
    user_id_frame.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')
    user_id_frame.columnconfigure(0, weight=1)

    user_id_radio = ttk.Radiobutton(user_id_frame, text="사용자 ID 검색", variable=search_type_var, value="user")
    user_id_radio.grid(row=0, column=0, sticky='w')

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
    allow_duplicate_check = ttk.Checkbutton(
        search_type_frame,
        text="중복 다운로드 허용",
        variable=allow_duplicate_var
    )
    allow_duplicate_check.grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=5)

    def toggle_human_classify(parent_frame, include_images_var, include_human_classify_var):
        if include_images_var.get():
            if parent_frame == hashtag_frame:
                include_human_classify_check_hashtag.configure(state='normal')
            elif parent_frame == user_id_frame:
                include_human_classify_check_user.configure(state='normal')
        else:
            include_human_classify_var.set(False)
            if parent_frame == hashtag_frame:
                include_human_classify_check_hashtag.configure(state='disabled')
            elif parent_frame == user_id_frame:
                include_human_classify_check_user.configure(state='disabled')

    def on_search_type_change(*args):
        selected_type = search_type_var.get()
        if selected_type == "hashtag":
            include_images_check_hashtag.configure(state='normal')
            include_videos_check_hashtag.configure(state='normal')
            toggle_human_classify(hashtag_frame, include_images_var_hashtag, include_human_classify_var_hashtag)

            include_images_check_user.configure(state='disabled')
            include_reels_check_user.configure(state='disabled')
            include_human_classify_var_user.set(False)
            include_human_classify_check_user.configure(state='disabled')
        elif selected_type == "user":
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
    download_dir_frame.columnconfigure(2, weight=0)

    ttk.Label(download_dir_frame, text="기본 저장 경로:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
    download_directory_var = tk.StringVar(value=DEFAULT_DOWNLOAD_PATH)
    download_dir_entry = ttk.Entry(download_dir_frame, textvariable=download_directory_var, width=50, font=('Arial', 10))
    download_dir_entry.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

    def open_download_directory():
        directory = download_directory_var.get()
        if os.path.isdir(directory):
            if os.name == 'nt':  # Windows
                os.startfile(directory)
            else:
                subprocess.Popen(["open", directory])  # macOS는 open, 리눅스는 xdg-open 등으로 교체
        else:
            append_status("오류: 다운로드 디렉토리가 존재하지 않습니다.")

    def select_download_directory_main():
        directory = filedialog.askdirectory(initialdir=DEFAULT_DOWNLOAD_PATH)
        if directory:
            download_directory_var.set(directory)
            load_existing_directories()
            for acc in loaded_accounts:
                acc['DOWNLOAD_PATH'] = directory
            save_config(
                loaded_accounts,
                saved_search_type,
                saved_search_terms,
                saved_include_images,
                saved_include_videos,
                saved_include_reels
            )
            append_status("정보: 다운로드 경로가 변경되었습니다.")
            print("다운로드 경로가 변경되어 모든 계정의 DOWNLOAD_PATH가 업데이트되었습니다.")

    select_dir_button_main = ttk.Button(download_dir_frame, text="경로 선택", command=select_download_directory_main, width=12)
    select_dir_button_main.grid(row=0, column=2, padx=5, pady=5)

    open_dir_button_main = ttk.Button(download_dir_frame, text="폴더 열기", command=open_download_directory, width=12)
    open_dir_button_main.grid(row=0, column=3, padx=5, pady=5)

    existing_dirs_frame = ttk.LabelFrame(root, text="기존 다운로드 디렉토리", padding=5)
    existing_dirs_frame.grid(row=4, column=0, padx=10, pady=10, sticky='nsew')
    existing_dirs_frame.columnconfigure(0, weight=1)
    existing_dirs_frame.columnconfigure(1, weight=1)
    existing_dirs_frame.columnconfigure(2, weight=1)
    existing_dirs_frame.rowconfigure(0, weight=1)

    hashtag_list_frame = ttk.Frame(existing_dirs_frame)
    hashtag_list_frame.grid(row=0, column=0, padx=10, pady=5, sticky='nsew')
    hashtag_list_frame.columnconfigure(0, weight=1)

    ttk.Label(hashtag_list_frame, text="해시태그 목록").pack(anchor='w')

    hashtag_listbox = tk.Listbox(hashtag_list_frame, height=5, font=('Arial', 10), selectmode=tk.MULTIPLE)
    hashtag_listbox.pack(side='left', fill='both', expand=True, padx=(0,5), pady=5)

    hashtag_scrollbar = ttk.Scrollbar(hashtag_list_frame, orient="vertical", command=hashtag_listbox.yview)
    hashtag_scrollbar.pack(side='left', fill='y')
    hashtag_listbox.config(yscrollcommand=hashtag_scrollbar.set)

    user_id_list_frame = ttk.Frame(existing_dirs_frame)
    user_id_list_frame.grid(row=0, column=1, padx=10, pady=5, sticky='nsew')
    user_id_list_frame.columnconfigure(0, weight=1)

    ttk.Label(user_id_list_frame, text="사용자 ID 목록").pack(anchor='w')

    user_id_listbox = tk.Listbox(user_id_list_frame, height=5, font=('Arial', 10), selectmode=tk.MULTIPLE)
    user_id_listbox.pack(side='left', fill='both', expand=True, padx=(0,5), pady=5)

    user_id_scrollbar = ttk.Scrollbar(user_id_list_frame, orient="vertical", command=user_id_listbox.yview)
    user_id_scrollbar.pack(side='left', fill='y')
    user_id_listbox.config(yscrollcommand=user_id_scrollbar.set)

    selection_buttons_frame = ttk.Frame(existing_dirs_frame)
    selection_buttons_frame.grid(row=0, column=2, padx=10, pady=5, sticky='nsew')
    selection_buttons_frame.columnconfigure(0, weight=1)
    selection_buttons_frame.columnconfigure(1, weight=1)

    def add_selected_hashtags():
        selected_indices = hashtag_listbox.curselection()
        selected_hashtags = [hashtag_listbox.get(i) for i in selected_indices]
        if not selected_hashtags:
            append_status("정보: 추가할 해시태그를 선택하세요.")
            return
        current_text = word_text.get("1.0", tk.END).strip()
        new_terms = '\n'.join(selected_hashtags)
        if current_text:
            updated_text = current_text + '\n' + new_terms
        else:
            updated_text = new_terms
        word_text.delete("1.0", tk.END)
        word_text.insert(tk.END, updated_text)
        append_status(f"성공: {len(selected_hashtags)}개의 해시태그가 검색 목록에 추가되었습니다.")

    def add_selected_user_ids():
        selected_indices = user_id_listbox.curselection()
        selected_user_ids = [user_id_listbox.get(i) for i in selected_indices]
        if not selected_user_ids:
            append_status("정보: 추가할 사용자 ID를 선택하세요.")
            return
        current_text = word_text.get("1.0", tk.END).strip()
        new_terms = '\n'.join(selected_user_ids)
        if current_text:
            updated_text = current_text + '\n' + new_terms
        else:
            updated_text = new_terms
        word_text.delete("1.0", tk.END)
        word_text.insert(tk.END, updated_text)
        append_status(f"성공: {len(selected_user_ids)}개의 사용자 ID가 검색 목록에 추가되었습니다.")

    def add_all_hashtags():
        all_hashtags = hashtag_listbox.get(0, tk.END)
        if not all_hashtags:
            append_status("정보: 추가할 해시태그가 없습니다.")
            return
        current_text = word_text.get("1.0", tk.END).strip()
        new_terms = '\n'.join(all_hashtags)
        if current_text:
            updated_text = current_text + '\n' + new_terms
        else:
            updated_text = new_terms
        word_text.delete("1.0", tk.END)
        word_text.insert(tk.END, updated_text)
        append_status("성공: 모든 해시태그가 검색 목록에 추가되었습니다.")

    def add_all_user_ids():
        all_user_ids = user_id_listbox.get(0, tk.END)
        if not all_user_ids:
            append_status("정보: 추가할 사용자 ID가 없습니다.")
            return
        current_text = word_text.get("1.0", tk.END).strip()
        new_terms = '\n'.join(all_user_ids)
        if current_text:
            updated_text = current_text + '\n' + new_terms
        else:
            updated_text = new_terms
        word_text.delete("1.0", tk.END)
        word_text.insert(tk.END, updated_text)
        append_status("성공: 모든 사용자 ID가 검색 목록에 추가되었습니다.")

    add_selected_hashtags_button = ttk.Button(selection_buttons_frame, text="선택된 해시태그 추가", command=add_selected_hashtags)
    add_selected_hashtags_button.grid(row=0, column=0, padx=5, pady=2, sticky='ew')

    add_all_hashtags_button = ttk.Button(selection_buttons_frame, text="모든 해시태그 추가", command=add_all_hashtags)
    add_all_hashtags_button.grid(row=0, column=1, padx=5, pady=2, sticky='ew')

    add_selected_user_ids_button = ttk.Button(selection_buttons_frame, text="선택된 사용자 ID 추가", command=add_selected_user_ids)
    add_selected_user_ids_button.grid(row=1, column=0, padx=5, pady=2, sticky='ew')

    add_all_user_ids_button = ttk.Button(selection_buttons_frame, text="모든 사용자 ID 추가", command=add_all_user_ids)
    add_all_user_ids_button.grid(row=1, column=1, padx=5, pady=2, sticky='ew')

    ### 기존: (uid, ctime, mtime) 형태로 캐싱
    ### INI 정렬도 해야 하므로 기존 구조는 유지하되, "수정일 오름차순" 버튼에서만 ini로 정렬 로직을 수행
    user_ids_cached = []

    def sort_user_ids_by_creation_desc():
        """생성일(ctime) 기준 내림차순 정렬 (기존 방식)"""
        user_id_listbox.delete(0, tk.END)
        sorted_ids = sorted(user_ids_cached, key=lambda x: x[1], reverse=True)  # ctime desc
        for uid, ctime_val, mtime_val in sorted_ids:
            user_id_listbox.insert(tk.END, uid)
        append_status("정보: 사용자 ID가 '생성일' 기준 내림차순으로 정렬되었습니다.")

    ### 변경점 시작: INI 파일의 post-timestamp 에 따라 오름차순 정렬
    def sort_user_ids_by_modified_asc():
        """
        latest-stamps-images.ini 파일에서 [uid] 섹션의 post-timestamp를 읽어,
        오래된 순(오름차순)으로 정렬한다.
        디렉토리가 없더라도 ini에 타임스탬프가 있는 uid는 포함됩니다.
        """
        ini_path = os.path.join(os.path.dirname(__file__), 'latest-stamps-images.ini')
        if not os.path.isfile(ini_path):
            append_status("오류: latest-stamps-images.ini 파일을 찾을 수 없습니다.")
            return

        config = configparser.ConfigParser()
        config.read(ini_path, encoding='utf-8')

        # INI 파일로부터 uid별 타임스탬프 읽기
        ini_timestamps = {}
        for section in config.sections():
            if config[section].get('post-timestamp'):
                raw_ts = config[section]['post-timestamp'].strip()
                dt_obj = None
                try:
                    dt_obj = datetime.strptime(raw_ts, "%Y-%m-%dT%H:%M:%S.%f%z")
                except ValueError:
                    try:
                        dt_obj = datetime.fromisoformat(raw_ts)
                    except Exception as e:
                        pass
                if dt_obj:
                    ini_timestamps[section] = dt_obj

        # 기존 디렉토리에서 캐싱된 uid 목록 (실제 디렉토리가 있는 경우)
        uids_from_dirs = {uid for uid, _, _ in user_ids_cached}
        # INI 파일에 기록된 uid 목록
        uids_from_ini = set(ini_timestamps.keys())
        # 두 집합의 합집합: 실제 디렉토가 있거나 INI에 기록된 uid 모두 포함
        combined_uids = uids_from_dirs.union(uids_from_ini)

        # 각 uid에 대해 ini 타임스탬프가 있으면 사용, 없으면 None 처리
        user_list = [(uid, ini_timestamps.get(uid)) for uid in combined_uids]

        # 타임스탬프가 있는 것과 없는 것으로 분리
        user_list_with_ts = [item for item in user_list if item[1] is not None]
        user_list_without_ts = [item for item in user_list if item[1] is None]

        # 타임스탬프가 있는 항목만 오래된 순(오름차순) 정렬
        user_list_with_ts.sort(key=lambda x: x[1])
        final_sorted = user_list_with_ts + user_list_without_ts

        user_id_listbox.delete(0, tk.END)
        for uid, _ in final_sorted:
            user_id_listbox.insert(tk.END, uid)

        append_status("정보: INI의 post-timestamp 기준으로 오래된 순 정렬 완료.")
    ### 변경점 끝

    sort_buttons_frame = ttk.Frame(existing_dirs_frame)
    sort_buttons_frame.grid(row=1, column=1, padx=5, pady=2, sticky='nsew')
    sort_buttons_frame.columnconfigure(0, weight=1)
    sort_buttons_frame.columnconfigure(1, weight=1)

    # 기존 (생성일 내림차순) 버튼
    sort_ctime_desc_button = ttk.Button(sort_buttons_frame, text="생성일 내림차순", command=sort_user_ids_by_creation_desc)
    sort_ctime_desc_button.grid(row=0, column=0, padx=5, pady=2, sticky='ew')

    # 수정: ini post-timestamp 기반 오래된 순
    sort_mtime_asc_button = ttk.Button(sort_buttons_frame, text="(INI) 오름차순", command=sort_user_ids_by_modified_asc)
    sort_mtime_asc_button.grid(row=0, column=1, padx=5, pady=2, sticky='ew')

    refresh_button = ttk.Button(existing_dirs_frame, text="새로 고침", command=lambda: load_existing_directories(), width=15)
    refresh_button.grid(row=1, column=0, pady=5)

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

    def load_existing_directories():
        main_download_dir = download_directory_var.get()
        if not os.path.isdir(main_download_dir):
            append_status(f"오류: 다운로드 경로가 존재하지 않습니다: {main_download_dir}")
            return

        hashtag_dir = os.path.join(main_download_dir, 'unclassified', 'hashtag')
        user_id_dir = os.path.join(main_download_dir, 'unclassified', 'ID')
        os.makedirs(hashtag_dir, exist_ok=True)
        os.makedirs(user_id_dir, exist_ok=True)

        hashtag_listbox.delete(0, tk.END)
        user_id_listbox.delete(0, tk.END)

        hashtags = [d for d in os.listdir(hashtag_dir) if os.path.isdir(os.path.join(hashtag_dir, d))]
        for tag in hashtags:
            hashtag_listbox.insert(tk.END, tag)

        nonlocal user_ids_cached
        user_ids_cached = []
        for d in os.listdir(user_id_dir):
            dir_path = os.path.join(user_id_dir, d)
            if os.path.isdir(dir_path):
                try:
                    creation_time = os.path.getctime(dir_path)
                    modified_time = os.path.getmtime(dir_path)
                    user_ids_cached.append((d, creation_time, modified_time))
                except Exception as e:
                    append_status(f"경고: 디렉토리 '{d}'의 생성/수정일을 가져오는 중 오류: {e}")

        # 기본은 '생성일 내림차순' 정렬로 보여주기
        user_ids_sorted = sorted(user_ids_cached, key=lambda x: x[1], reverse=True)
        for uid, ctime_val, mtime_val in user_ids_sorted:
            user_id_listbox.insert(tk.END, uid)

    def process_queue(progress_queue):
        try:
            while True:
                message = progress_queue.get_nowait()
                if message[0] == "term_start":
                    append_status(f"시작: '{message[1]}' (계정: {message[2]})")
                elif message[0] == "term_progress":
                    append_status(f"진행: '{message[1]}' - {message[2]} (계정: {message[3]})")
                elif message[0] == "term_complete":
                    append_status(f"완료: '{message[1]}' (계정: {message[2]})")
                elif message[0] == "term_error":
                    append_status(f"오류: '{message[1]}' - {message[2]} (계정: {message[3]})")
                elif message[0] == "account_switch":
                    append_status(f"계정 전환: '{message[1]}'")
                elif message[0] == "account_relogin":
                    append_status(f"재로그인 시도: '{message[1]}'")
        except Empty:
            pass
        root.after(100, lambda: process_queue(progress_queue))

    def classify_existing_images(stop_event):
        append_status("정보: 선택된 이미지 분류를 시작합니다.")
        download_path = download_directory_var.get().strip()
        if not os.path.isdir(download_path):
            append_status(f"오류: 다운로드 경로가 존재하지 않습니다: {download_path}")
            return

        hashtag_dir = os.path.join(download_path, 'unclassified', 'hashtag')
        user_id_dir = os.path.join(download_path, 'unclassified', 'ID')

        if not os.path.isdir(hashtag_dir) and not os.path.isdir(user_id_dir):
            append_status(f"오류: 해시태그 또는 사용자 ID 디렉토리가 존재하지 않습니다: {download_path}")
            return

        directories_to_classify = []

        selected_hashtags = hashtag_listbox.curselection()
        for index in selected_hashtags:
            term = hashtag_listbox.get(index)
            term_image_dir = os.path.join(hashtag_dir, term, 'Image')
            if os.path.isdir(term_image_dir):
                directories_to_classify.append((term, 'hashtag'))

        selected_user_ids = user_id_listbox.curselection()
        for index in selected_user_ids:
            uid = user_id_listbox.get(index)
            uid_image_dir = os.path.join(user_id_dir, uid, 'Image')
            if os.path.isdir(uid_image_dir):
                directories_to_classify.append((uid, 'user'))

        if not directories_to_classify:
            append_status("정보: 선택된 해시태그 또는 사용자 ID에 대한 분류할 이미지가 없습니다.")
            return

        if not loaded_accounts:
            append_status("오류: 사용 가능한 계정이 없습니다.")
            return

        total_count = len(directories_to_classify)
        root.after(0, lambda: progress_var.set(0))
        append_status("정보: 분류 진행 중...")

        def worker():
            for i, (term, search_type) in enumerate(directories_to_classify, start=1):
                if stop_event.is_set():
                    append_status("중지: 분류 프로세스가 중지되었습니다.")
                    return
                success = classify_images(root, append_status, download_directory_var, term, loaded_accounts[0]['INSTAGRAM_USERNAME'], search_type, stop_event)

                progress_percentage = (i / total_count) * 100
                root.after(0, lambda p=progress_percentage: progress_var.set(p))
                if success:
                    append_status(f"완료: '{term}' 분류 완료.")
                else:
                    append_status(f"오류: '{term}' 분류 중 오류 발생.")

            append_status("완료: 모든 이미지 분류가 완료되었습니다.")
            root.after(0, lambda: progress_label_var.set("분류 완료"))
            load_existing_directories()

        threading.Thread(target=worker, daemon=True).start()

    def on_complete(message):
        append_status(f"완료: {message}")
        progress_var.set(100)
        progress_label_var.set(f"100% 완료")
        load_existing_directories()

    def start_crawling():
        append_status("정보: 크롤링 시작됨...")
        search_terms_raw = word_text.get("1.0", tk.END).strip()
        if not search_terms_raw:
            append_status("오류: 검색할 해시태그 또는 사용자 ID를 입력하세요.")
            return
        search_terms = [term.strip() for term in search_terms_raw.replace(',', '\n').split('\n') if term.strip()]
        if not search_terms:
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
        main_search_terms.extend(search_terms)
        search_type = search_type_var.get()
        main_search_type = search_type

        include_images = include_images_var_hashtag.get() if search_type == "hashtag" else include_images_var_user.get() if include_images_var_user else False
        include_videos = include_videos_var_hashtag.get() if search_type == "hashtag" else False
        include_reels = include_reels_var_user.get() if search_type == "user" else False

        allow_duplicate = allow_duplicate_var.get()

        download_path = download_directory_var.get().strip()
        if not os.path.isdir(download_path):
            append_status(f"오류: 다운로드 경로가 존재하지 않습니다: {download_path}")
            return

        save_config(
            loaded_accounts,
            search_type,
            search_terms,
            include_images,
            include_videos,
            include_reels
        )
        append_status("정보: 현재 설정이 저장되었습니다.")

        progress_queue = Queue()
        global_stop_event.clear()

        threading.Thread(
            target=crawl_and_download,
            args=(
                main_search_terms,
                target,
                loaded_accounts,
                search_type,
                include_images,
                include_videos,
                include_reels,
                progress_queue,
                on_complete,
                global_stop_event,
                download_path,
                append_status,
                root,
                download_directory_var,
                include_human_classify_var_hashtag,
                include_human_classify_var_user,
                allow_duplicate
            ),
            daemon=True
        ).start()

        process_queue(progress_queue)

    def stop_crawling():
        global_stop_event.set()
        append_status("중지: 크롤링 및 분류 중지 요청됨.")

    button_frame = ttk.Frame(root)
    button_frame.grid(row=8, column=0, pady=5, padx=10, sticky='ew')
    button_frame.columnconfigure(0, weight=1)
    button_frame.columnconfigure(1, weight=1)
    button_frame.columnconfigure(2, weight=1)

    start_button = ttk.Button(button_frame, text="크롤링 시작", command=start_crawling, width=15)
    start_button.grid(row=0, column=0, padx=5, pady=2, sticky='ew')

    stop_button = ttk.Button(button_frame, text="중지", command=stop_crawling, width=15)
    stop_button.grid(row=0, column=1, padx=5, pady=2, sticky='ew')

    classify_existing_button = ttk.Button(existing_dirs_frame, text="선택된 이미지 분류", command=lambda: classify_existing_images(global_stop_event), width=20)
    classify_existing_button.grid(row=2, column=2, padx=5, pady=2, sticky='ew')

    if saved_accounts:
        for account in saved_accounts:
            accounts_listbox.insert(tk.END, account['INSTAGRAM_USERNAME'])
        append_status("정보: 저장된 계정을 자동으로 입력했습니다.")
    if saved_search_type:
        search_type_var.set(saved_search_type)
    if saved_search_terms:
        word_text.insert(tk.END, '\n'.join(saved_search_terms))
        append_status("정보: 저장된 검색어를 자동으로 입력했습니다.")

    def initial_toggle():
        toggle_human_classify(hashtag_frame, include_images_var_hashtag, include_human_classify_var_hashtag)
        toggle_human_classify(user_id_frame, include_images_var_user, include_human_classify_var_user)

    initial_toggle()

    root.rowconfigure(7, weight=1)
    root.columnconfigure(0, weight=1)

    load_existing_directories()
    root.mainloop()
    print("GUI 종료")
