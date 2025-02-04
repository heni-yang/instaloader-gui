import os
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
from queue import Queue, Empty
from crawling.config import load_config, save_config
from crawling.downloader import crawl_and_download
from crawling.classifier import classify_images

# 프로젝트 기본 경로 및 다운로드 기본 경로
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
DEFAULT_DOWNLOAD_PATH = os.path.join(PROJECT_ROOT, 'download')


class InstaCrawlerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("인스타그램 이미지 크롤링 프로그램 (Instaloader 기반)")
        self.root.geometry("900x1000")
        self.root.minsize(900, 1000)
        self.root.columnconfigure(0, weight=1)

        self.setup_styles()

        # 설정 및 상태 변수 초기화
        self.loaded_accounts = []
        self.main_search_terms = []
        self.main_search_type = ""
        self.global_stop_event = threading.Event()

        # 설정 불러오기 (config.py 모듈 활용)
        (self.saved_accounts, self.saved_search_type,
         self.saved_search_terms, self.saved_include_images,
         self.saved_include_videos, self.saved_include_reels) = load_config()
        self.loaded_accounts.extend(self.saved_accounts)

        # 위젯 생성
        self.create_header()
        self.create_top_frame()
        self.create_search_settings_frame()
        self.create_download_dir_frame()
        self.create_existing_dirs_frame()
        self.create_progress_frame()
        self.create_button_frame()

        # 저장된 설정 적용
        self.load_saved_config()
        self.load_existing_directories()

    def setup_styles(self):
        style = ttk.Style(self.root)
        style.configure('TButton', font=('Arial', 10))
        style.configure('TLabel', font=('Arial', 10))
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

    def create_header(self):
        self.header = ttk.Label(self.root, text="인스타그램 이미지 크롤링 프로그램", style='Header.TLabel')
        self.header.grid(row=0, column=0, pady=10, padx=10, sticky='ew')

    def create_top_frame(self):
        # 상단 프레임: 계정 관리 영역과 검색 유형 선택 영역 포함
        self.top_frame = ttk.Frame(self.root)
        self.top_frame.grid(row=1, column=0, padx=10, pady=5, sticky='ew')
        self.top_frame.columnconfigure(0, weight=1)
        self.top_frame.columnconfigure(1, weight=1)

        self.create_account_frame(self.top_frame)
        self.create_search_type_frame(self.top_frame)

    def create_account_frame(self, parent):
        # 계정 관리 영역
        self.account_frame = ttk.LabelFrame(parent, text="계정 정보", padding=5)
        self.account_frame.grid(row=0, column=0, padx=(0, 10), pady=5, sticky='nsew')
        self.account_frame.columnconfigure(0, weight=1)
        self.account_frame.rowconfigure(0, weight=1)

        self.accounts_listbox = tk.Listbox(self.account_frame, height=3, font=('Arial', 10))
        self.accounts_listbox.grid(row=0, column=0, sticky='nsew', padx=(0, 5), pady=5)
        scrollbar = ttk.Scrollbar(self.account_frame, orient="vertical", command=self.accounts_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.accounts_listbox.config(yscrollcommand=scrollbar.set)

        self.account_buttons_frame = ttk.Frame(self.account_frame)
        self.account_buttons_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky='ew')
        self.account_buttons_frame.columnconfigure(0, weight=1)
        self.account_buttons_frame.columnconfigure(1, weight=1)

        add_btn = ttk.Button(self.account_buttons_frame, text="계정 추가", command=self.add_account, width=12)
        add_btn.grid(row=0, column=0, padx=5, pady=2, sticky='ew')
        remove_btn = ttk.Button(self.account_buttons_frame, text="계정 제거", command=self.remove_account, width=12)
        remove_btn.grid(row=0, column=1, padx=5, pady=2, sticky='ew')

    def create_search_type_frame(self, parent):
        # 검색 유형 선택 영역 (해시태그/사용자 ID)
        self.search_type_frame = ttk.LabelFrame(parent, text="검색 유형 선택", padding=5)
        self.search_type_frame.grid(row=0, column=1, padx=(10, 0), pady=5, sticky='nsew')
        self.search_type_frame.columnconfigure(0, weight=1)
        self.search_type_frame.columnconfigure(1, weight=1)

        self.search_type_var = tk.StringVar(value="hashtag")

        # 해시태그 프레임
        self.hashtag_frame = ttk.Frame(self.search_type_frame)
        self.hashtag_frame.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        self.hashtag_frame.columnconfigure(0, weight=1)
        self.hashtag_radio = ttk.Radiobutton(self.hashtag_frame, text="해시태그 검색",
                                             variable=self.search_type_var, value="hashtag")
        self.hashtag_radio.grid(row=0, column=0, sticky='w')

        hashtag_check_frame = ttk.Frame(self.hashtag_frame)
        hashtag_check_frame.grid(row=1, column=0, sticky='w', pady=2)
        self.include_images_var_hashtag = tk.BooleanVar(value=True)
        self.include_videos_var_hashtag = tk.BooleanVar(value=False)
        self.include_human_classify_var_hashtag = tk.BooleanVar(value=False)
        self.include_images_check_hashtag = ttk.Checkbutton(
            hashtag_check_frame, text="이미지", variable=self.include_images_var_hashtag)
        self.include_images_check_hashtag.pack(side='left', padx=(0, 5))
        self.include_videos_check_hashtag = ttk.Checkbutton(
            hashtag_check_frame, text="영상", variable=self.include_videos_var_hashtag)
        self.include_videos_check_hashtag.pack(side='left')
        self.include_human_classify_check_hashtag = ttk.Checkbutton(
            self.hashtag_frame, text="인물 분류", variable=self.include_human_classify_var_hashtag)
        self.include_human_classify_check_hashtag.grid(row=2, column=0, sticky='w', padx=20)
        self.include_human_classify_check_hashtag.configure(state='disabled')

        # 사용자 ID 프레임
        self.user_id_frame = ttk.Frame(self.search_type_frame)
        self.user_id_frame.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')
        self.user_id_frame.columnconfigure(0, weight=1)
        self.user_id_radio = ttk.Radiobutton(
            self.user_id_frame, text="사용자 ID 검색", variable=self.search_type_var, value="user")
        self.user_id_radio.grid(row=0, column=0, sticky='w')

        user_id_check_frame = ttk.Frame(self.user_id_frame)
        user_id_check_frame.grid(row=1, column=0, sticky='w', pady=2)
        self.include_images_var_user = tk.BooleanVar(value=True)
        self.include_reels_var_user = tk.BooleanVar(value=False)
        self.include_human_classify_var_user = tk.BooleanVar(value=False)
        self.include_images_check_user = ttk.Checkbutton(
            user_id_check_frame, text="이미지", variable=self.include_images_var_user)
        self.include_images_check_user.pack(side='left', padx=(0, 5))
        self.include_reels_check_user = ttk.Checkbutton(
            user_id_check_frame, text="릴스", variable=self.include_reels_var_user)
        self.include_reels_check_user.pack(side='left')
        self.include_human_classify_check_user = ttk.Checkbutton(
            self.user_id_frame, text="인물 분류", variable=self.include_human_classify_var_user)
        self.include_human_classify_check_user.grid(row=2, column=0, sticky='w', padx=20)
        self.include_human_classify_check_user.configure(state='disabled')

        # 중복 다운로드 허용 체크박스
        self.allow_duplicate_var = tk.BooleanVar(value=False)
        allow_duplicate_check = ttk.Checkbutton(
            self.search_type_frame, text="중복 다운로드 허용", variable=self.allow_duplicate_var)
        allow_duplicate_check.grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=5)

        # 검색 유형 변경에 따른 토글 처리
        self.search_type_var.trace_add('write', self.on_search_type_change)

    def create_search_settings_frame(self):
        # 검색어와 게시글 수 입력 영역
        self.search_frame = ttk.LabelFrame(self.root, text="검색 설정", padding=5)
        self.search_frame.grid(row=2, column=0, padx=10, pady=5, sticky='ew')
        self.search_frame.columnconfigure(1, weight=1)

        ttk.Label(self.search_frame,
                  text="검색할 해시태그 / 사용자 ID (여러 개는 개행 또는 쉼표로 구분):",
                  wraplength=300).grid(row=0, column=0, sticky='ne', pady=2, padx=10)
        self.word_text = scrolledtext.ScrolledText(self.search_frame, width=50, height=5, font=('Arial', 10))
        self.word_text.grid(row=0, column=1, pady=2, padx=10, sticky='ew')

        ttk.Label(self.search_frame, text="수집할 게시글 수 (0: 전체):").grid(row=1, column=0, sticky='e', pady=2, padx=10)
        self.post_count_entry = ttk.Entry(self.search_frame, width=20, font=('Arial', 10))
        self.post_count_entry.grid(row=1, column=1, sticky='w', pady=2, padx=10)
        self.post_count_entry.insert(0, "0")

    def create_download_dir_frame(self):
        # 다운로드 기본 경로 설정 영역
        self.download_dir_frame = ttk.LabelFrame(self.root, text="전체 다운로드 경로 설정", padding=5)
        self.download_dir_frame.grid(row=3, column=0, padx=10, pady=5, sticky='ew')
        self.download_dir_frame.columnconfigure(1, weight=1)
        self.download_dir_frame.columnconfigure(2, weight=0)

        ttk.Label(self.download_dir_frame, text="기본 저장 경로:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.download_directory_var = tk.StringVar(value=DEFAULT_DOWNLOAD_PATH)
        self.download_dir_entry = ttk.Entry(self.download_dir_frame, textvariable=self.download_directory_var,
                                            width=50, font=('Arial', 10))
        self.download_dir_entry.grid(row=0, column=1, sticky='ew', padx=10, pady=5)
        select_dir_button = ttk.Button(self.download_dir_frame, text="경로 선택",
                                       command=self.select_download_directory_main, width=12)
        select_dir_button.grid(row=0, column=2, padx=5, pady=5)

    def create_existing_dirs_frame(self):
        # 기존 다운로드 디렉토리 표시 영역
        self.existing_dirs_frame = ttk.LabelFrame(self.root, text="기존 다운로드 디렉토리", padding=5)
        self.existing_dirs_frame.grid(row=4, column=0, padx=10, pady=10, sticky='nsew')
        self.existing_dirs_frame.columnconfigure(0, weight=1)
        self.existing_dirs_frame.columnconfigure(1, weight=1)
        self.existing_dirs_frame.columnconfigure(2, weight=1)
        self.existing_dirs_frame.rowconfigure(0, weight=1)

        # 해시태그 목록
        self.hashtag_list_frame = ttk.Frame(self.existing_dirs_frame)
        self.hashtag_list_frame.grid(row=0, column=0, padx=10, pady=5, sticky='nsew')
        self.hashtag_list_frame.columnconfigure(0, weight=1)
        ttk.Label(self.hashtag_list_frame, text="해시태그 목록").pack(anchor='w')
        self.hashtag_listbox = tk.Listbox(self.hashtag_list_frame, height=5, font=('Arial', 10), selectmode=tk.MULTIPLE)
        self.hashtag_listbox.pack(side='left', fill='both', expand=True, padx=(0, 5), pady=5)
        hashtag_scroll = ttk.Scrollbar(self.hashtag_list_frame, orient="vertical", command=self.hashtag_listbox.yview)
        hashtag_scroll.pack(side='left', fill='y')
        self.hashtag_listbox.config(yscrollcommand=hashtag_scroll.set)

        # 사용자 ID 목록
        self.user_id_list_frame = ttk.Frame(self.existing_dirs_frame)
        self.user_id_list_frame.grid(row=0, column=1, padx=10, pady=5, sticky='nsew')
        self.user_id_list_frame.columnconfigure(0, weight=1)
        ttk.Label(self.user_id_list_frame, text="사용자 ID 목록").pack(anchor='w')
        self.user_id_listbox = tk.Listbox(self.user_id_list_frame, height=5, font=('Arial', 10), selectmode=tk.MULTIPLE)
        self.user_id_listbox.pack(side='left', fill='both', expand=True, padx=(0, 5), pady=5)
        user_scroll = ttk.Scrollbar(self.user_id_list_frame, orient="vertical", command=self.user_id_listbox.yview)
        user_scroll.pack(side='left', fill='y')
        self.user_id_listbox.config(yscrollcommand=user_scroll.set)

        # 선택 버튼 영역
        self.selection_buttons_frame = ttk.Frame(self.existing_dirs_frame)
        self.selection_buttons_frame.grid(row=0, column=2, padx=10, pady=5, sticky='nsew')
        self.selection_buttons_frame.columnconfigure(0, weight=1)
        self.selection_buttons_frame.columnconfigure(1, weight=1)
        btn_sel_hashtag = ttk.Button(self.selection_buttons_frame, text="선택된 해시태그 추가",
                                     command=self.add_selected_hashtags)
        btn_sel_hashtag.grid(row=0, column=0, padx=5, pady=2, sticky='ew')
        btn_all_hashtag = ttk.Button(self.selection_buttons_frame, text="모든 해시태그 추가",
                                     command=self.add_all_hashtags)
        btn_all_hashtag.grid(row=0, column=1, padx=5, pady=2, sticky='ew')
        btn_sel_user = ttk.Button(self.selection_buttons_frame, text="선택된 사용자 ID 추가",
                                  command=self.add_selected_user_ids)
        btn_sel_user.grid(row=1, column=0, padx=5, pady=2, sticky='ew')
        btn_all_user = ttk.Button(self.selection_buttons_frame, text="모든 사용자 ID 추가",
                                  command=self.add_all_user_ids)
        btn_all_user.grid(row=1, column=1, padx=5, pady=2, sticky='ew')
        refresh_btn = ttk.Button(self.existing_dirs_frame, text="새로 고침", command=self.load_existing_directories, width=15)
        refresh_btn.grid(row=1, column=0, columnspan=3, pady=5)

    def create_progress_frame(self):
        # 진행 상황 표시 영역 (진행률, 상태 메시지)
        self.progress_frame = ttk.Frame(self.root)
        self.progress_frame.grid(row=6, column=0, padx=10, pady=5, sticky='ew')
        self.progress_frame.columnconfigure(0, weight=1)
        self.progress_label_var = tk.StringVar()
        self.progress_label = ttk.Label(self.progress_frame, textvariable=self.progress_label_var)
        self.progress_label.grid(row=0, column=0, sticky='w', padx=10, pady=(0, 5))
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=1, column=0, sticky='ew', padx=10, pady=5)

    def create_button_frame(self):
        # 하단 버튼 영역: 크롤링 시작, 중지, 이미지 분류
        self.button_frame = ttk.Frame(self.root)
        self.button_frame.grid(row=8, column=0, pady=5, padx=10, sticky='ew')
        self.button_frame.columnconfigure(0, weight=1)
        self.button_frame.columnconfigure(1, weight=1)
        self.button_frame.columnconfigure(2, weight=1)
        start_btn = ttk.Button(self.button_frame, text="크롤링 시작", command=self.start_crawling, width=15)
        start_btn.grid(row=0, column=0, padx=5, pady=2, sticky='ew')
        stop_btn = ttk.Button(self.button_frame, text="중지", command=self.stop_crawling, width=15)
        stop_btn.grid(row=0, column=1, padx=5, pady=2, sticky='ew')
        classify_btn = ttk.Button(self.existing_dirs_frame, text="선택된 이미지 분류",
                                  command=lambda: self.classify_existing_images(self.global_stop_event), width=20)
        classify_btn.grid(row=2, column=2, padx=5, pady=2, sticky='ew')

    # ---------------- Event Handlers ----------------

    def add_account(self):
        add_window = tk.Toplevel(self.root)
        add_window.title("계정 추가")
        add_window.geometry("400x350")
        add_window.resizable(False, False)

        ttk.Label(add_window, text="아이디:").grid(row=0, column=0, sticky='w', pady=(10, 2), padx=10)
        new_username_entry = ttk.Entry(add_window, width=40, font=('Arial', 10))
        new_username_entry.grid(row=0, column=1, pady=(10, 10), padx=10)
        ttk.Label(add_window, text="비밀번호:").grid(row=1, column=0, sticky='w', pady=(5, 2), padx=10)
        new_password_entry = ttk.Entry(add_window, show="*", width=40, font=('Arial', 10))
        new_password_entry.grid(row=1, column=1, pady=(5, 10), padx=10)
        ttk.Label(add_window, text="다운로드 경로:").grid(row=2, column=0, sticky='w', pady=(5, 2), padx=10)
        download_dir_frame = ttk.Frame(add_window)
        download_dir_frame.grid(row=2, column=1, pady=(5, 10), padx=10, sticky='ew')
        download_directory_var_add = tk.StringVar(value=DEFAULT_DOWNLOAD_PATH)
        download_dir_entry = ttk.Entry(download_dir_frame, textvariable=download_directory_var_add, width=30, font=('Arial', 10))
        download_dir_entry.pack(side='left', padx=(0, 5), fill='x', expand=True)

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
                self.append_status("오류: 아이디와 비밀번호를 입력하세요.")
                return
            os.makedirs(download_path, exist_ok=True)
            os.makedirs(os.path.join(download_path, 'hashtag'), exist_ok=True)
            os.makedirs(os.path.join(download_path, 'ID'), exist_ok=True)
            self.accounts_listbox.insert(tk.END, username)
            self.loaded_accounts.append({
                'INSTAGRAM_USERNAME': username,
                'INSTAGRAM_PASSWORD': password,
                'DOWNLOAD_PATH': download_path
            })
            save_config(
                self.loaded_accounts,
                self.saved_search_type,
                self.saved_search_terms,
                self.saved_include_images,
                self.saved_include_videos,
                self.saved_include_reels
            )
            self.append_status(f"정보: 새로운 계정 '{username}'이 추가되었습니다.")
            add_window.destroy()
            self.load_existing_directories()

        save_button = ttk.Button(add_window, text="추가", command=save_new_account)
        save_button.grid(row=3, column=0, columnspan=2, pady=10)

    def remove_account(self):
        selected_indices = self.accounts_listbox.curselection()
        if not selected_indices:
            self.append_status("오류: 제거할 계정을 선택하세요.")
            return
        for index in reversed(selected_indices):
            username = self.accounts_listbox.get(index)
            self.accounts_listbox.delete(index)
            self.loaded_accounts[:] = [acc for acc in self.loaded_accounts if acc['INSTAGRAM_USERNAME'] != username]
            self.append_status(f"정보: 계정 '{username}'이 제거되었습니다.")
        save_config(
            self.loaded_accounts,
            self.saved_search_type,
            self.saved_search_terms,
            self.saved_include_images,
            self.saved_include_videos,
            self.saved_include_reels
        )
        self.load_existing_directories()

    def select_download_directory_main(self):
        directory = filedialog.askdirectory(initialdir=DEFAULT_DOWNLOAD_PATH)
        if directory:
            self.download_directory_var.set(directory)
            self.load_existing_directories()
            for acc in self.loaded_accounts:
                acc['DOWNLOAD_PATH'] = directory
            save_config(
                self.loaded_accounts,
                self.saved_search_type,
                self.saved_search_terms,
                self.saved_include_images,
                self.saved_include_videos,
                self.saved_include_reels
            )
            self.append_status("정보: 다운로드 경로가 변경되었습니다.")
            print("다운로드 경로 변경됨, 모든 계정의 DOWNLOAD_PATH 업데이트됨.")

    def add_selected_hashtags(self):
        selected_indices = self.hashtag_listbox.curselection()
        selected_hashtags = [self.hashtag_listbox.get(i) for i in selected_indices]
        if not selected_hashtags:
            self.append_status("정보: 추가할 해시태그를 선택하세요.")
            return
        current_text = self.word_text.get("1.0", tk.END).strip()
        new_terms = '\n'.join(selected_hashtags)
        updated_text = f"{current_text}\n{new_terms}" if current_text else new_terms
        self.word_text.delete("1.0", tk.END)
        self.word_text.insert(tk.END, updated_text)
        self.append_status(f"성공: {len(selected_hashtags)}개의 해시태그가 검색 목록에 추가되었습니다.")

    def add_selected_user_ids(self):
        selected_indices = self.user_id_listbox.curselection()
        selected_user_ids = [self.user_id_listbox.get(i) for i in selected_indices]
        if not selected_user_ids:
            self.append_status("정보: 추가할 사용자 ID를 선택하세요.")
            return
        new_terms = '\n'.join(selected_user_ids)
        self.word_text.delete("1.0", tk.END)
        self.word_text.insert(tk.END, new_terms)
        self.append_status(f"성공: {len(selected_user_ids)}개의 사용자 ID가 검색 목록에 추가되었습니다.")

    def add_all_hashtags(self):
        all_hashtags = self.hashtag_listbox.get(0, tk.END)
        if not all_hashtags:
            self.append_status("정보: 추가할 해시태그가 없습니다.")
            return
        new_terms = '\n'.join(all_hashtags)
        self.word_text.delete("1.0", tk.END)
        self.word_text.insert(tk.END, new_terms)
        self.append_status("성공: 모든 해시태그가 검색 목록에 추가되었습니다.")

    def add_all_user_ids(self):
        all_user_ids = self.user_id_listbox.get(0, tk.END)
        if not all_user_ids:
            self.append_status("정보: 추가할 사용자 ID가 없습니다.")
            return
        new_terms = '\n'.join(all_user_ids)
        self.word_text.delete("1.0", tk.END)
        self.word_text.insert(tk.END, new_terms)
        self.append_status("성공: 모든 사용자 ID가 검색 목록에 추가되었습니다.")

    def on_search_type_change(self, *args):
        selected_type = self.search_type_var.get()
        if selected_type == "hashtag":
            self.include_images_check_hashtag.configure(state='normal')
            self.include_videos_check_hashtag.configure(state='normal')
            self.toggle_human_classify(self.hashtag_frame, self.include_images_var_hashtag, self.include_human_classify_var_hashtag)
            self.include_images_check_user.configure(state='disabled')
            self.include_reels_check_user.configure(state='disabled')
            self.include_human_classify_var_user.set(False)
            self.include_human_classify_check_user.configure(state='disabled')
        elif selected_type == "user":
            self.include_images_check_user.configure(state='normal')
            self.include_reels_check_user.configure(state='normal')
            self.toggle_human_classify(self.user_id_frame, self.include_images_var_user, self.include_human_classify_var_user)
            self.include_images_check_hashtag.configure(state='disabled')
            self.include_videos_check_hashtag.configure(state='disabled')
            self.include_human_classify_var_hashtag.set(False)
            self.include_human_classify_check_hashtag.configure(state='disabled')

    def toggle_human_classify(self, parent_frame, include_images_var, include_human_classify_var):
        if include_images_var.get():
            if parent_frame == self.hashtag_frame:
                self.include_human_classify_check_hashtag.configure(state='normal')
            elif parent_frame == self.user_id_frame:
                self.include_human_classify_check_user.configure(state='normal')
        else:
            include_human_classify_var.set(False)
            if parent_frame == self.hashtag_frame:
                self.include_human_classify_check_hashtag.configure(state='disabled')
            elif parent_frame == self.user_id_frame:
                self.include_human_classify_check_user.configure(state='disabled')

    def process_queue(self, progress_queue):
        try:
            while True:
                message = progress_queue.get_nowait()
                if message[0] == "term_start":
                    self.append_status(f"시작: '{message[1]}' (계정: {message[2]})")
                elif message[0] == "term_progress":
                    self.append_status(f"진행: '{message[1]}' - {message[2]} (계정: {message[3]})")
                elif message[0] == "term_complete":
                    self.append_status(f"완료: '{message[1]}' (계정: {message[2]})")
                elif message[0] == "term_error":
                    self.append_status(f"오류: '{message[1]}' - {message[2]} (계정: {message[3]})")
                elif message[0] == "account_switch":
                    self.append_status(f"계정 전환: '{message[1]}'")
                elif message[0] == "account_relogin":
                    self.append_status(f"재로그인 시도: '{message[1]}'")
        except Empty:
            pass
        self.root.after(100, lambda: self.process_queue(progress_queue))

    def classify_existing_images(self, stop_event):
        self.append_status("정보: 선택된 이미지 분류를 시작합니다.")
        download_path = self.download_directory_var.get().strip()
        if not os.path.isdir(download_path):
            self.append_status(f"오류: 다운로드 경로가 존재하지 않습니다: {download_path}")
            return

        hashtag_dir = os.path.join(download_path, 'unclassified', 'hashtag')
        user_id_dir = os.path.join(download_path, 'unclassified', 'ID')
        if not os.path.isdir(hashtag_dir) and not os.path.isdir(user_id_dir):
            self.append_status(f"오류: 해시태그 또는 사용자 ID 디렉토리가 존재하지 않습니다: {download_path}")
            return

        directories_to_classify = []
        selected_hashtags = self.hashtag_listbox.curselection()
        for index in selected_hashtags:
            term = self.hashtag_listbox.get(index)
            term_image_dir = os.path.join(hashtag_dir, term, 'Image')
            if os.path.isdir(term_image_dir):
                directories_to_classify.append((term, 'hashtag'))

        selected_user_ids = self.user_id_listbox.curselection()
        for index in selected_user_ids:
            uid = self.user_id_listbox.get(index)
            uid_image_dir = os.path.join(user_id_dir, uid, 'Image')
            if os.path.isdir(uid_image_dir):
                directories_to_classify.append((uid, 'user'))

        if not directories_to_classify:
            self.append_status("정보: 선택된 해시태그 또는 사용자 ID에 대한 분류할 이미지가 없습니다.")
            return

        if not self.loaded_accounts:
            self.append_status("오류: 사용 가능한 계정이 없습니다.")
            return

        total_count = len(directories_to_classify)
        self.root.after(0, lambda: self.progress_var.set(0))
        self.append_status("정보: 분류 진행 중...")

        def worker():
            for i, (term, search_type) in enumerate(directories_to_classify, start=1):
                if stop_event.is_set():
                    self.append_status("중지: 분류 프로세스가 중지되었습니다.")
                    return
                success = classify_images(self.root, self.append_status, self.download_directory_var, term,
                                          self.loaded_accounts[0]['INSTAGRAM_USERNAME'], search_type, stop_event)
                progress_percentage = (i / total_count) * 100
                self.root.after(0, lambda p=progress_percentage: self.progress_var.set(p))
                if success:
                    self.append_status(f"완료: '{term}' 분류 완료.")
                else:
                    self.append_status(f"오류: '{term}' 분류 중 오류 발생.")
                if stop_event.is_set():
                    self.append_status("중지: 분류 중지됨.")
                    break
            self.append_status("완료: 모든 이미지 분류가 완료되었습니다.")
            self.root.after(0, lambda: self.progress_label_var.set("분류 완료"))
            self.load_existing_directories()

        threading.Thread(target=worker, daemon=True).start()

    def start_crawling(self):
        self.append_status("정보: 크롤링 시작됨...")
        search_terms_raw = self.word_text.get("1.0", tk.END).strip()
        if not search_terms_raw:
            self.append_status("오류: 검색할 해시태그 또는 사용자 ID를 입력하세요.")
            return
        search_terms = [term.strip() for term in search_terms_raw.replace(',', '\n').split('\n') if term.strip()]
        if not search_terms:
            self.append_status("오류: 유효한 검색어가 없습니다.")
            return
        try:
            target = int(self.post_count_entry.get().strip())
            if target < 0:
                self.append_status("오류: 게시글 수는 0 이상이어야 합니다.")
                return
        except ValueError:
            self.append_status("오류: 게시글 수는 정수여야 합니다.")
            return

        self.main_search_terms.clear()
        self.main_search_terms.extend(search_terms)
        search_type = self.search_type_var.get()
        self.main_search_type = search_type
        include_images = (self.include_images_var_hashtag.get() if search_type == "hashtag"
                          else self.include_images_var_user.get() if self.include_images_var_user else False)
        include_videos = self.include_videos_var_hashtag.get() if search_type == "hashtag" else False
        include_reels = self.include_reels_var_user.get() if search_type == "user" else False
        allow_duplicate = self.allow_duplicate_var.get()
        download_path = self.download_directory_var.get().strip()
        if not os.path.isdir(download_path):
            self.append_status(f"오류: 다운로드 경로가 존재하지 않습니다: {download_path}")
            return

        save_config(
            self.loaded_accounts,
            self.search_type_var.get(),
            search_terms,
            include_images,
            include_videos,
            include_reels
        )
        self.append_status("정보: 현재 설정이 저장되었습니다.")
        progress_queue = Queue()
        self.global_stop_event.clear()
        threading.Thread(
            target=crawl_and_download,
            args=(
                self.main_search_terms,
                target,
                self.loaded_accounts,
                search_type,
                include_images,
                include_videos,
                include_reels,
                progress_queue,
                lambda msg: self.on_complete(msg),
                self.global_stop_event,
                self.download_directory_var.get().strip(),
                self.append_status,
                self.root,
                self.download_directory_var,
                self.include_human_classify_var_hashtag,
                self.include_human_classify_var_user,
                allow_duplicate
            ),
            daemon=True
        ).start()
        self.process_queue(progress_queue)

    def on_complete(self, message):
        self.append_status(f"완료: {message}")
        self.progress_var.set(100)
        self.progress_label_var.set("100% 완료")
        self.load_existing_directories()

    def stop_crawling(self):
        self.global_stop_event.set()
        self.append_status("중지: 크롤링 및 분류 중지 요청됨.")

    def append_status(self, message):
        # GUI 상태 업데이트 (상태 창이 있으면 업데이트, 없으면 콘솔 출력)
        if hasattr(self, 'status_text'):
            def append():
                self.status_text.configure(state='normal')
                self.status_text.insert(tk.END, message + '\n')
                self.status_text.see(tk.END)
                self.status_text.configure(state='disabled')
            self.root.after(0, append)
        else:
            print(message)

    def load_existing_directories(self):
        main_download_dir = self.download_directory_var.get()
        if not os.path.isdir(main_download_dir):
            self.append_status(f"오류: 다운로드 경로가 존재하지 않습니다: {main_download_dir}")
            return

        hashtag_dir = os.path.join(main_download_dir, 'unclassified', 'hashtag')
        user_id_dir = os.path.join(main_download_dir, 'unclassified', 'ID')
        os.makedirs(hashtag_dir, exist_ok=True)
        os.makedirs(user_id_dir, exist_ok=True)

        self.hashtag_listbox.delete(0, tk.END)
        self.user_id_listbox.delete(0, tk.END)

        hashtags = [d for d in os.listdir(hashtag_dir) if os.path.isdir(os.path.join(hashtag_dir, d))]
        for tag in hashtags:
            self.hashtag_listbox.insert(tk.END, tag)

        user_ids = []
        user_ids_with_error = []
        for d in os.listdir(user_id_dir):
            dir_path = os.path.join(user_id_dir, d)
            if os.path.isdir(dir_path):
                try:
                    creation_time = os.path.getctime(dir_path)
                    user_ids.append((d, creation_time))
                except Exception as e:
                    self.append_status(f"경고: 디렉토리 '{d}'의 생성일 가져오는 중 오류: {e}")
                    user_ids_with_error.append((d, 0))
        user_ids_sorted = sorted(user_ids, key=lambda x: x[1], reverse=True)
        user_ids_sorted.extend(sorted(user_ids_with_error, key=lambda x: x[1], reverse=True))
        for uid, _ in user_ids_sorted:
            self.user_id_listbox.insert(tk.END, uid)

    def load_saved_config(self):
        if self.saved_accounts:
            for account in self.saved_accounts:
                self.accounts_listbox.insert(tk.END, account['INSTAGRAM_USERNAME'])
            self.append_status("정보: 저장된 계정을 자동으로 입력했습니다.")
        if self.saved_search_type:
            self.search_type_var.set(self.saved_search_type)
        if self.saved_search_terms:
            self.word_text.insert(tk.END, '\n'.join(self.saved_search_terms))
            self.append_status("정보: 저장된 검색어를 자동으로 입력했습니다.")
        self.initial_toggle()

    def initial_toggle(self):
        self.toggle_human_classify(self.hashtag_frame, self.include_images_var_hashtag, self.include_human_classify_var_hashtag)
        self.toggle_human_classify(self.user_id_frame, self.include_images_var_user, self.include_human_classify_var_user)

    def run(self):
        self.root.rowconfigure(7, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.mainloop()
        print("GUI 종료")


def main_gui():
    gui = InstaCrawlerGUI()
    gui.run()


if __name__ == "__main__":
    main_gui()
