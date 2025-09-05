# src/gui/components/search_panel.py
"""
검색 설정 패널 컴포넌트
"""
import os
import tkinter as tk
from tkinter import ttk, scrolledtext
from ..handlers.queue_handler import (
    add_items_from_listbox, add_all_items_from_listbox, 
    toggle_upscale_hashtag, toggle_upscale_user, toggle_human_classify,
    on_search_type_change, open_download_directory, select_download_directory_main
)
from ..dialogs.settings import delete_selected_items, load_existing_directories
from ..dialogs.settings import (
    sort_user_ids_by_creation_desc, sort_user_ids_by_creation_asc,
    sort_user_ids_by_ini_desc, sort_user_ids_by_ini_asc
)


class SearchPanel:
    """검색 설정 패널 클래스"""
    
    def __init__(self, parent, config, loaded_searchtype, last_download_path):
        self.parent = parent
        self.config = config
        self.loaded_searchtype = loaded_searchtype
        self.last_download_path = last_download_path
        
        # 검색 유형 변수
        self.search_type_var = tk.StringVar(value=loaded_searchtype)
        
        # 해시태그 관련 변수들 - 설정에서 로드
        self.hashtag_listbox = None
        self.hashtag_search_var = tk.StringVar()
        self.hashtag_count_var = tk.StringVar(value="해시태그 목록 (0개)")
        hashtag_options = config.get('HASHTAG_OPTIONS', {})
        self.include_images_var_hashtag = tk.BooleanVar(value=hashtag_options.get('include_images', True))
        self.include_videos_var_hashtag = tk.BooleanVar(value=hashtag_options.get('include_videos', False))
        self.include_human_classify_var_hashtag = tk.BooleanVar(value=hashtag_options.get('include_human_classify', False))
        self.include_upscale_var_hashtag = tk.BooleanVar(value=hashtag_options.get('include_upscale', False))
        
        # 사용자 ID 관련 변수들 - 설정에서 로드
        self.user_id_listbox = None
        self.user_id_search_var = tk.StringVar()
        self.user_id_count_var = tk.StringVar(value="사용자 ID 목록 (0개)")
        user_id_options = config.get('USER_ID_OPTIONS', {})
        self.include_images_var_user = tk.BooleanVar(value=user_id_options.get('include_images', True))
        self.include_reels_var_user = tk.BooleanVar(value=user_id_options.get('include_reels', False))
        self.include_human_classify_var_user = tk.BooleanVar(value=user_id_options.get('include_human_classify', False))
        self.include_upscale_var_user = tk.BooleanVar(value=user_id_options.get('include_upscale', False))
        
        # 다운로드 경로 변수
        self.download_directory_var = tk.StringVar(value=last_download_path)
        
        # 기타 변수들 - 설정에서 로드
        from ...core.anti_detection import migrate_old_config, get_display_value_from_mode
        config = migrate_old_config(config)  # 기존 설정 마이그레이션
        
        self.allow_duplicate_var = tk.BooleanVar(value=config.get('ALLOW_DUPLICATE', False))
        self.wait_time_var = tk.StringVar(value=str(config.get('REQUEST_WAIT_TIME', 0.0)))
        self.anti_detection_mode_var = tk.StringVar(value=get_display_value_from_mode(config.get('ANTI_DETECTION_MODE', 'ON')))
        self.word_text = None
        self.post_count_entry = None
        
        # 필터링을 위한 원본 데이터 저장
        self.original_hashtags = []
        self.original_user_ids = []
        
        # 설정 저장을 위한 콜백 함수
        self.save_config_callback = None
        
        # 설정 저장 중 무한 루프 방지 플래그
        self._saving_config = False
        self._save_timer = None
        
        # 검색어 텍스트 변경 감지를 위한 변수
        self._last_search_text = ""
    
    def create_search_type_frame(self, top_frame):
        """검색 유형 선택 프레임 생성"""
        search_type_frame = ttk.LabelFrame(top_frame, text="검색 유형 선택", padding=5)
        search_type_frame.grid(row=0, column=1, padx=(10,0), pady=5, sticky='nsew')
        search_type_frame.columnconfigure(0, weight=1)
        search_type_frame.columnconfigure(1, weight=1)
        
        # 해시태그 검색 영역
        hashtag_frame = ttk.Frame(search_type_frame)
        hashtag_frame.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        hashtag_frame.columnconfigure(0, weight=1)
        hashtag_frame.columnconfigure(1, weight=1)
        
        ttk.Radiobutton(hashtag_frame, text="해시태그 검색", variable=self.search_type_var, value="hashtag")\
            .grid(row=0, column=0, columnspan=2, sticky='w')
        
        # 1행: 이미지, 영상 체크박스
        include_images_check_hashtag = ttk.Checkbutton(hashtag_frame, text="이미지", variable=self.include_images_var_hashtag)
        include_images_check_hashtag.grid(row=1, column=0, sticky='w', padx=5, pady=2)
        include_videos_check_hashtag = ttk.Checkbutton(hashtag_frame, text="영상", variable=self.include_videos_var_hashtag)
        include_videos_check_hashtag.grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        # 2행: 인물 분류, 업스케일링 체크박스
        include_human_classify_check_hashtag = ttk.Checkbutton(hashtag_frame, text="인물 분류", variable=self.include_human_classify_var_hashtag)
        include_human_classify_check_hashtag.grid(row=2, column=0, sticky='w', padx=5, pady=2)
        upscale_checkbox_hashtag = ttk.Checkbutton(hashtag_frame, text="업스케일링", variable=self.include_upscale_var_hashtag)
        upscale_checkbox_hashtag.grid(row=2, column=1, sticky='w', padx=5, pady=2)
        upscale_checkbox_hashtag.configure(state='disabled')
        
        # 사용자 ID 검색 영역
        user_id_frame = ttk.Frame(search_type_frame)
        user_id_frame.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')
        user_id_frame.columnconfigure(0, weight=1)
        user_id_frame.columnconfigure(1, weight=1)
        
        ttk.Radiobutton(user_id_frame, text="사용자 ID 검색", variable=self.search_type_var, value="user_id")\
            .grid(row=0, column=0, columnspan=2, sticky='w')
        
        # 1행: 이미지, 릴스 체크박스
        include_images_check_user = ttk.Checkbutton(user_id_frame, text="이미지", variable=self.include_images_var_user)
        include_images_check_user.grid(row=1, column=0, sticky='w', padx=5, pady=2)
        include_reels_check_user = ttk.Checkbutton(user_id_frame, text="릴스", variable=self.include_reels_var_user)
        include_reels_check_user.grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        # 2행: 인물 분류, 업스케일링 체크박스
        include_human_classify_check_user = ttk.Checkbutton(user_id_frame, text="인물 분류", variable=self.include_human_classify_var_user)
        include_human_classify_check_user.grid(row=2, column=0, sticky='w', padx=5, pady=2)
        upscale_checkbox_user = ttk.Checkbutton(user_id_frame, text="업스케일링", variable=self.include_upscale_var_user)
        upscale_checkbox_user.grid(row=2, column=1, sticky='w', padx=5, pady=2)
        upscale_checkbox_user.configure(state='disabled')
        
        # 중복 다운로드 허용
        ttk.Checkbutton(search_type_frame, text="중복 다운로드 허용", variable=self.allow_duplicate_var).grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=5)
        
        # Anti-Detection 모드 설정
        from ...core.anti_detection import get_mode_display_values
        
        anti_detection_frame = ttk.LabelFrame(search_type_frame, text="🛡️ Anti-Detection 모드", padding=5)
        anti_detection_frame.grid(row=4, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        
        ttk.Label(anti_detection_frame, text="크롤링 보안 모드:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
        
        mode_values = get_mode_display_values()
        self.anti_detection_combo = ttk.Combobox(
            anti_detection_frame, 
            textvariable=self.anti_detection_mode_var,
            values=mode_values,
            state="readonly",
            width=25
        )
        self.anti_detection_combo.grid(row=0, column=1, sticky='w', padx=5, pady=2)
        
        # 모드 설명 (동적 업데이트)
        self.mode_description_var = tk.StringVar()
        description_label = ttk.Label(
            anti_detection_frame, 
            textvariable=self.mode_description_var, 
            foreground="gray", 
            wraplength=400,
            font=('Arial', 9)
        )
        description_label.grid(row=1, column=0, columnspan=2, sticky='w', padx=5, pady=(2, 5))
        
        # 모드 변경 이벤트 바인딩
        self.anti_detection_combo.bind('<<ComboboxSelected>>', self._on_anti_detection_mode_change)
        
        # 초기 설명 설정
        self._update_mode_description()
        
        # 이벤트 바인딩
        self._bind_events(hashtag_frame, user_id_frame, include_images_check_hashtag, include_videos_check_hashtag,
                         include_human_classify_check_hashtag, include_images_check_user, include_reels_check_user,
                         include_human_classify_check_user, upscale_checkbox_hashtag, upscale_checkbox_user)
        
        return search_type_frame
    
    def create_search_frame(self, root):
        """검색 설정 프레임 생성"""
        search_frame = ttk.LabelFrame(root, text="검색 설정", padding=5)
        search_frame.grid(row=2, column=0, padx=10, pady=5, sticky='ew')
        search_frame.columnconfigure(1, weight=1)
        
        ttk.Label(search_frame, text="검색할 해시태그 / 사용자 ID (여러 개는 개행 또는 쉼표로 구분):", wraplength=300).grid(row=0, column=0, sticky='ne', pady=2, padx=10)
        self.word_text = scrolledtext.ScrolledText(search_frame, width=50, height=5, font=('Arial', 10))
        self.word_text.grid(row=0, column=1, pady=2, padx=10, sticky='ew')
        
        # 저장된 검색어 로드
        saved_search_terms = self.config.get('SEARCH_TERMS', [])
        if saved_search_terms:
            search_text = '\n'.join(saved_search_terms)
            self.word_text.insert(1.0, search_text)
            self._last_search_text = search_text
        
        # 검색어 텍스트 변경 이벤트 바인딩 제거 (크롤링 시작 시에만 저장)
        
        ttk.Label(search_frame, text="수집할 게시글 수 (0: 전체):").grid(row=1, column=0, sticky='e', pady=2, padx=10)
        self.post_count_entry = ttk.Entry(search_frame, width=20, font=('Arial', 10))
        self.post_count_entry.grid(row=1, column=1, sticky='w', pady=2, padx=10)
        self.post_count_entry.insert(0, "0")
        
        return search_frame
    
    def create_download_frame(self, root):
        """다운로드 설정 프레임 생성"""
        download_dir_frame = ttk.LabelFrame(root, text="전체 다운로드 경로 설정", padding=5)
        download_dir_frame.grid(row=3, column=0, padx=10, pady=5, sticky='ew')
        download_dir_frame.columnconfigure(1, weight=1)
        
        ttk.Label(download_dir_frame, text="기본 저장 경로:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        download_dir_entry = ttk.Entry(download_dir_frame, textvariable=self.download_directory_var, width=50, font=('Arial', 10))
        download_dir_entry.grid(row=0, column=1, sticky='ew', padx=10, pady=5)
        
        ttk.Button(download_dir_frame, text="경로 선택", 
                   command=lambda: select_download_directory_main(self.download_directory_var, self.last_download_path, [], load_existing_directories, lambda x: None), width=12).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(download_dir_frame, text="폴더 열기", 
                   command=lambda: open_download_directory(self.download_directory_var, lambda x: None), width=12).grid(row=0, column=3, padx=5, pady=5)
        
        return download_dir_frame
    
    def create_existing_dirs_frame(self, root):
        """다운로드된 프로필 목록 프레임 생성"""
        existing_dirs_frame = ttk.LabelFrame(root, text="다운로드된 프로필 목록", padding=3)
        existing_dirs_frame.grid(row=4, column=0, padx=10, pady=5, sticky='nsew')
        for i in range(3):
            existing_dirs_frame.columnconfigure(i, weight=1)
        existing_dirs_frame.rowconfigure(0, weight=1)
        
        # 해시태그 목록 프레임
        hashtag_frame = ttk.Frame(existing_dirs_frame)
        hashtag_frame.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        hashtag_frame.columnconfigure(0, weight=1)
        hashtag_frame.rowconfigure(2, weight=1)
        
        # 해시태그 제목
        ttk.Label(hashtag_frame, textvariable=self.hashtag_count_var, font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=(0, 3))
        
        # 해시태그 검색 프레임
        hashtag_search_frame = ttk.Frame(hashtag_frame)
        hashtag_search_frame.grid(row=1, column=0, sticky='ew', pady=(0, 3))
        hashtag_search_frame.columnconfigure(0, weight=1)
        
        hashtag_search_entry = ttk.Entry(hashtag_search_frame, textvariable=self.hashtag_search_var)
        hashtag_search_entry.grid(row=0, column=0, sticky='ew')
        hashtag_search_entry.insert(0, "해시태그 검색...")
        hashtag_search_entry.bind('<FocusIn>', self._on_hashtag_search_focus_in)
        hashtag_search_entry.bind('<FocusOut>', self._on_hashtag_search_focus_out)
        
        # 해시태그 리스트박스와 스크롤바 (같은 행에 배치)
        hashtag_list_frame = ttk.Frame(hashtag_frame)
        hashtag_list_frame.grid(row=2, column=0, sticky='nsew', pady=(0, 5))
        hashtag_list_frame.columnconfigure(0, weight=1)
        hashtag_list_frame.rowconfigure(0, weight=1)
        
        self.hashtag_listbox = tk.Listbox(hashtag_list_frame, selectmode=tk.EXTENDED, font=('Arial', 10), height=12)
        self.hashtag_listbox.grid(row=0, column=0, sticky='nsew', padx=(0, 2))
        
        hashtag_scrollbar = ttk.Scrollbar(hashtag_list_frame, orient="vertical", command=self.hashtag_listbox.yview)
        hashtag_scrollbar.grid(row=0, column=1, sticky='ns')
        self.hashtag_listbox.config(yscrollcommand=hashtag_scrollbar.set)
        
        # 사용자 ID 목록 프레임
        user_id_frame = ttk.Frame(existing_dirs_frame)
        user_id_frame.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')
        user_id_frame.columnconfigure(0, weight=1)
        user_id_frame.rowconfigure(2, weight=1)
        
        # 사용자 ID 제목
        ttk.Label(user_id_frame, textvariable=self.user_id_count_var, font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=(0, 3))
        
        # 사용자 ID 검색 프레임
        user_id_search_frame = ttk.Frame(user_id_frame)
        user_id_search_frame.grid(row=1, column=0, sticky='ew', pady=(0, 3))
        user_id_search_frame.columnconfigure(0, weight=1)
        
        user_id_search_entry = ttk.Entry(user_id_search_frame, textvariable=self.user_id_search_var)
        user_id_search_entry.grid(row=0, column=0, sticky='ew')
        user_id_search_entry.insert(0, "사용자 ID 검색...")
        user_id_search_entry.bind('<FocusIn>', self._on_user_id_search_focus_in)
        user_id_search_entry.bind('<FocusOut>', self._on_user_id_search_focus_out)
        
        # 사용자 ID 리스트박스와 스크롤바 (같은 행에 배치)
        user_id_list_frame = ttk.Frame(user_id_frame)
        user_id_list_frame.grid(row=2, column=0, sticky='nsew', pady=(0, 5))
        user_id_list_frame.columnconfigure(0, weight=1)
        user_id_list_frame.rowconfigure(0, weight=1)
        
        self.user_id_listbox = tk.Listbox(user_id_list_frame, selectmode=tk.EXTENDED, font=('Arial', 10), height=12)
        self.user_id_listbox.grid(row=0, column=0, sticky='nsew', padx=(0, 2))
        
        user_id_scrollbar = ttk.Scrollbar(user_id_list_frame, orient="vertical", command=self.user_id_listbox.yview)
        user_id_scrollbar.grid(row=0, column=1, sticky='ns')
        self.user_id_listbox.config(yscrollcommand=user_id_scrollbar.set)
        
        # 선택 버튼 프레임 - UX 개선
        selection_buttons_frame = ttk.Frame(existing_dirs_frame)
        selection_buttons_frame.grid(row=0, column=2, padx=10, pady=5, sticky='nsew')
        selection_buttons_frame.columnconfigure(0, weight=1)
        
        # 1. 목록 관리 그룹
        list_management_frame = ttk.LabelFrame(selection_buttons_frame, text="📋 목록 관리", padding=5)
        list_management_frame.grid(row=0, column=0, padx=2, pady=2, sticky='ew')
        list_management_frame.columnconfigure(0, weight=1)
        
        ttk.Button(list_management_frame, text="목록 새로고침", 
                   command=self._refresh_lists).grid(row=0, column=0, padx=2, pady=1, sticky='ew')
        ttk.Button(list_management_frame, text="선택된 대상 삭제", 
                   command=lambda: delete_selected_items(self.hashtag_listbox, self.user_id_listbox, self.config)).grid(row=1, column=0, padx=2, pady=1, sticky='ew')
        
        # 2. 정렬 기능 그룹
        sort_frame = ttk.LabelFrame(selection_buttons_frame, text="정렬", padding=5)
        sort_frame.grid(row=1, column=0, padx=2, pady=2, sticky='ew')
        sort_frame.columnconfigure(0, weight=1)
        sort_frame.columnconfigure(1, weight=1)
        
        # 정렬 기준 콤보박스
        self.sort_criteria_var = tk.StringVar(value="생성일 내림차순")
        sort_criteria_combo = ttk.Combobox(sort_frame, textvariable=self.sort_criteria_var, 
                                          values=["생성일 내림차순", "생성일 오름차순", 
                                                 "INI 내림차순", "INI 오름차순", "이름순"],
                                          state="readonly", width=12)
        sort_criteria_combo.grid(row=0, column=0, padx=2, pady=2, sticky='ew')
        
        # 정렬 실행 버튼
        ttk.Button(sort_frame, text="정렬", 
                   command=self._apply_sort).grid(row=0, column=1, padx=2, pady=2, sticky='ew')
        
        # 3. 데이터 추가 그룹
        add_data_frame = ttk.LabelFrame(selection_buttons_frame, text="➕ 데이터 추가", padding=5)
        add_data_frame.grid(row=2, column=0, padx=2, pady=2, sticky='ew')
        add_data_frame.columnconfigure(0, weight=1)
        
        # 해시태그 추가 서브그룹
        hashtag_add_subframe = ttk.LabelFrame(add_data_frame, text="🏷️ 해시태그", padding=3)
        hashtag_add_subframe.grid(row=0, column=0, padx=2, pady=2, sticky='ew')
        hashtag_add_subframe.columnconfigure(0, weight=1)
        hashtag_add_subframe.columnconfigure(1, weight=1)
        
        ttk.Button(hashtag_add_subframe, text="선택된 항목 추가", 
                   command=lambda: add_items_from_listbox(self.hashtag_listbox, self.word_text, "해시태그")).grid(row=0, column=0, padx=1, pady=1, sticky='ew')
        ttk.Button(hashtag_add_subframe, text="전체 항목 추가", 
                   command=lambda: add_all_items_from_listbox(self.hashtag_listbox, self.word_text, "해시태그")).grid(row=0, column=1, padx=1, pady=1, sticky='ew')
        
        # 사용자 ID 추가 서브그룹
        user_add_subframe = ttk.LabelFrame(add_data_frame, text="👤 사용자 ID", padding=3)
        user_add_subframe.grid(row=1, column=0, padx=2, pady=2, sticky='ew')
        user_add_subframe.columnconfigure(0, weight=1)
        user_add_subframe.columnconfigure(1, weight=1)
        
        ttk.Button(user_add_subframe, text="선택된 항목 추가", 
                   command=lambda: add_items_from_listbox(self.user_id_listbox, self.word_text, "사용자 ID")).grid(row=0, column=0, padx=1, pady=1, sticky='ew')
        ttk.Button(user_add_subframe, text="전체 항목 추가", 
                   command=lambda: add_all_items_from_listbox(self.user_id_listbox, self.word_text, "사용자 ID")).grid(row=0, column=1, padx=1, pady=1, sticky='ew')
        
        # 초기 목록 로드
        self._refresh_lists()
        
        # 검색 이벤트 바인딩
        self._bind_search_events()
        
        return existing_dirs_frame
    

    
    def _bind_search_events(self):
        """검색 이벤트 바인딩"""
        # 해시태그 검색 이벤트 (지연 검색으로 부드러운 UX)
        self.hashtag_search_var.trace_add('write', self._delayed_filter_hashtags)
        
        # 사용자 ID 검색 이벤트 (지연 검색으로 부드러운 UX)
        self.user_id_search_var.trace_add('write', self._delayed_filter_user_ids)
    
    def _delayed_filter_hashtags(self, *args):
        """지연된 해시태그 필터링"""
        # 기존 타이머 취소
        if hasattr(self, '_hashtag_filter_timer'):
            self.parent.after_cancel(self._hashtag_filter_timer)
        
        # 300ms 후에 필터링 실행
        self._hashtag_filter_timer = self.parent.after(300, self._filter_hashtags)
    
    def _delayed_filter_user_ids(self, *args):
        """지연된 사용자 ID 필터링"""
        # 기존 타이머 취소
        if hasattr(self, '_user_id_filter_timer'):
            self.parent.after_cancel(self._user_id_filter_timer)
        
        # 300ms 후에 필터링 실행
        self._user_id_filter_timer = self.parent.after(300, self._filter_user_ids)
    
    def _bind_events(self, hashtag_frame, user_id_frame, include_images_check_hashtag, include_videos_check_hashtag,
                    include_human_classify_check_hashtag, include_images_check_user, include_reels_check_user,
                    include_human_classify_check_user, upscale_checkbox_hashtag, upscale_checkbox_user):
        """이벤트 바인딩"""
        # 업스케일링 체크박스를 인스턴스 변수로 저장
        self.upscale_checkbox_hashtag = upscale_checkbox_hashtag
        self.upscale_checkbox_user = upscale_checkbox_user
        
        # 인물 분류 체크박스 값에 따라 업스케일링 체크박스 활성/비활성 제어
        self.include_human_classify_var_hashtag.trace_add('write', 
            lambda *args: toggle_upscale_hashtag(self.include_human_classify_var_hashtag, self.include_upscale_var_hashtag, upscale_checkbox_hashtag, *args))
        
        self.include_human_classify_var_user.trace_add('write', 
            lambda *args: toggle_upscale_user(self.include_human_classify_var_user, self.include_upscale_var_user, upscale_checkbox_user, *args))
        
        # 이미지 체크박스에 따른 인물 분류 제어 (올바른 매개변수 전달)
        self.include_images_var_hashtag.trace_add('write',
            lambda *args: self._on_hashtag_images_change(include_human_classify_check_hashtag, *args))
        
        self.include_images_var_user.trace_add('write',
            lambda *args: self._on_user_images_change(include_human_classify_check_user, *args))
        
        # 검색 유형 변경 이벤트 (설정 저장 포함)
        self.search_type_var.trace_add('write', 
            lambda *args: self._on_search_type_change(include_images_check_hashtag, include_videos_check_hashtag,
                                                    include_human_classify_check_hashtag, include_images_check_user, 
                                                    include_reels_check_user, include_human_classify_check_user, *args))
        
        # 초기 상태 설정
        self._set_initial_state(include_images_check_hashtag, include_videos_check_hashtag, include_human_classify_check_hashtag,
                               include_images_check_user, include_reels_check_user, include_human_classify_check_user)
        
        # 설정 저장을 위한 이벤트 바인딩 (검색 유형 제외)
        self._bind_save_events()
    
    def _on_hashtag_images_change(self, include_human_classify_check_hashtag, *args):
        """해시태그 이미지 체크박스 변경 처리"""
        if self.include_images_var_hashtag.get():
            include_human_classify_check_hashtag.configure(state='normal')
        else:
            self.include_human_classify_var_hashtag.set(False)
            include_human_classify_check_hashtag.configure(state='disabled')
            # 인물 분류가 해제되면 업스케일링도 비활성화
            if hasattr(self, 'upscale_checkbox_hashtag') and self.upscale_checkbox_hashtag:
                self.upscale_checkbox_hashtag.configure(state='disabled')
        
        # 설정 저장
        self._save_config()
    
    def _on_user_images_change(self, include_human_classify_check_user, *args):
        """사용자 ID 이미지 체크박스 변경 처리"""
        if self.include_images_var_user.get():
            include_human_classify_check_user.configure(state='normal')
        else:
            self.include_human_classify_var_user.set(False)
            include_human_classify_check_user.configure(state='disabled')
            # 인물 분류가 해제되면 업스케일링도 비활성화
            if hasattr(self, 'upscale_checkbox_user') and self.upscale_checkbox_user:
                self.upscale_checkbox_user.configure(state='disabled')
        
        # 설정 저장
        self._save_config()
    
    def _on_search_type_change(self, include_images_check_hashtag, include_videos_check_hashtag, include_human_classify_check_hashtag,
                              include_images_check_user, include_reels_check_user, include_human_classify_check_user, *args):
        """검색 유형 변경 처리"""
        # 기존 on_search_type_change 함수 호출
        from ..handlers.queue_handler import on_search_type_change
        on_search_type_change(self.search_type_var, include_images_check_hashtag, include_videos_check_hashtag,
                            include_human_classify_check_hashtag, self.include_images_var_hashtag, self.include_human_classify_var_hashtag,
                            include_images_check_user, include_reels_check_user, include_human_classify_check_user,
                            self.include_images_var_user, self.include_human_classify_var_user, None, None,
                            lambda x: None, self.upscale_checkbox_hashtag, self.upscale_checkbox_user, *args)
        
        # 검색 유형 변경은 즉시 저장
        self._save_config_actual()
    
    def _set_initial_state(self, include_images_check_hashtag, include_videos_check_hashtag, include_human_classify_check_hashtag,
                          include_images_check_user, include_reels_check_user, include_human_classify_check_user):
        """초기 상태 설정"""
        search_type = self.search_type_var.get()
        
        if search_type == "hashtag":
            # 해시태그 선택시: 해시태그 체크박스들 활성화, 사용자 ID 체크박스들 비활성화
            include_images_check_hashtag.configure(state='normal')
            include_videos_check_hashtag.configure(state='normal')
            include_human_classify_check_hashtag.configure(state='normal')
            
            include_images_check_user.configure(state='disabled')
            include_reels_check_user.configure(state='disabled')
            include_human_classify_check_user.configure(state='disabled')
            
            # 해시태그 이미지 체크 상태에 따른 인물 분류 활성화
            if self.include_images_var_hashtag.get():
                include_human_classify_check_hashtag.configure(state='normal')
            else:
                include_human_classify_check_hashtag.configure(state='disabled')
            
            # 해시태그 인물 분류 체크 상태에 따른 업스케일링 활성화
            if hasattr(self, 'upscale_checkbox_hashtag') and self.upscale_checkbox_hashtag:
                if self.include_human_classify_var_hashtag.get():
                    self.upscale_checkbox_hashtag.configure(state='normal')
                else:
                    self.upscale_checkbox_hashtag.configure(state='disabled')
            
            # 사용자 ID 업스케일링 체크박스 비활성화
            if hasattr(self, 'upscale_checkbox_user') and self.upscale_checkbox_user:
                self.upscale_checkbox_user.configure(state='disabled')
            
        else:  # user
            # 사용자 ID 선택시: 사용자 ID 체크박스들 활성화, 해시태그 체크박스들 비활성화
            include_images_check_user.configure(state='normal')
            include_reels_check_user.configure(state='normal')
            include_human_classify_check_user.configure(state='normal')
            
            include_images_check_hashtag.configure(state='disabled')
            include_videos_check_hashtag.configure(state='disabled')
            include_human_classify_check_hashtag.configure(state='disabled')
            
            # 사용자 ID 이미지 체크 상태에 따른 인물 분류 활성화
            if self.include_images_var_user.get():
                include_human_classify_check_user.configure(state='normal')
            else:
                include_human_classify_check_user.configure(state='disabled')
            
            # 사용자 ID 인물 분류 체크 상태에 따른 업스케일링 활성화
            if hasattr(self, 'upscale_checkbox_user') and self.upscale_checkbox_user:
                if self.include_human_classify_var_user.get():
                    self.upscale_checkbox_user.configure(state='normal')
                else:
                    self.upscale_checkbox_user.configure(state='disabled')
            
            # 해시태그 업스케일링 체크박스 비활성화
            if hasattr(self, 'upscale_checkbox_hashtag') and self.upscale_checkbox_hashtag:
                self.upscale_checkbox_hashtag.configure(state='disabled')
    
    def _bind_save_events(self):
        """설정 저장을 위한 이벤트 바인딩 (검색 유형과 이미지 체크박스 제외)"""
        # 해시태그 옵션 변경 시 저장 (이미지 제외)
        self.include_videos_var_hashtag.trace_add('write', lambda *args: self._save_config())
        self.include_human_classify_var_hashtag.trace_add('write', lambda *args: self._save_config())
        self.include_upscale_var_hashtag.trace_add('write', lambda *args: self._save_config())
        
        # 사용자 ID 옵션 변경 시 저장 (이미지 제외)
        self.include_reels_var_user.trace_add('write', lambda *args: self._save_config())
        self.include_human_classify_var_user.trace_add('write', lambda *args: self._save_config())
        self.include_upscale_var_user.trace_add('write', lambda *args: self._save_config())
        
        # 기타 설정 변경 시 저장
        self.allow_duplicate_var.trace_add('write', lambda *args: self._save_config())
        self.wait_time_var.trace_add('write', lambda *args: self._save_config())
    
    def _save_config(self):
        """현재 설정을 저장 (지연 저장으로 무한 루프 방지)"""
        # 기존 타이머 취소
        if self._save_timer:
            self.parent.after_cancel(self._save_timer)
        
        # 500ms 후에 저장 실행
        self._save_timer = self.parent.after(500, self._save_config_actual)
    
    def _save_config_actual(self):
        """실제 설정 저장 실행"""
        # 무한 루프 방지
        if self._saving_config:
            return
        
        self._saving_config = True
        try:
            from ...utils.config import load_config, save_config
            
            config = load_config()
            
            # 검색 유형 저장
            config['LAST_SEARCH_TYPE'] = self.search_type_var.get()
            
            # 해시태그 옵션 저장
            config['HASHTAG_OPTIONS'] = {
                'include_images': self.include_images_var_hashtag.get(),
                'include_videos': self.include_videos_var_hashtag.get(),
                'include_human_classify': self.include_human_classify_var_hashtag.get(),
                'include_upscale': self.include_upscale_var_hashtag.get()
            }
            
            # 사용자 ID 옵션 저장
            config['USER_ID_OPTIONS'] = {
                'include_images': self.include_images_var_user.get(),
                'include_reels': self.include_reels_var_user.get(),
                'include_human_classify': self.include_human_classify_var_user.get(),
                'include_upscale': self.include_upscale_var_user.get()
            }
            
            # 기타 설정 저장
            config['ALLOW_DUPLICATE'] = self.allow_duplicate_var.get()
            config['REQUEST_WAIT_TIME'] = float(self.wait_time_var.get())
            
            # Anti-Detection 모드 저장
            from ...core.anti_detection import get_mode_from_display_value, get_anti_detection_settings
            display_value = self.anti_detection_mode_var.get()
            mode_key = get_mode_from_display_value(display_value)
            config['ANTI_DETECTION_MODE'] = mode_key
            
            # 호환성을 위해 기존 REQUEST_WAIT_TIME도 업데이트
            settings = get_anti_detection_settings(mode_key)
            config['REQUEST_WAIT_TIME'] = settings['additional_wait_time']
            
            save_config(config)
            
        except Exception as e:
            print(f"설정 저장 오류: {e}")
        finally:
            self._saving_config = False
    
    def set_save_config_callback(self, callback):
        """설정 저장 콜백 함수 설정"""
        self.save_config_callback = callback
    
    def _on_hashtag_search_focus_in(self, event):
        """해시태그 검색 포커스 인"""
        if self.hashtag_search_var.get() == "해시태그 검색...":
            self.hashtag_search_var.set("")
    
    def _on_hashtag_search_focus_out(self, event):
        """해시태그 검색 포커스 아웃"""
        if not self.hashtag_search_var.get():
            self.hashtag_search_var.set("해시태그 검색...")
    
    def _on_user_id_search_focus_in(self, event):
        """사용자 ID 검색 포커스 인"""
        if self.user_id_search_var.get() == "사용자 ID 검색...":
            self.user_id_search_var.set("")
    
    def _on_user_id_search_focus_out(self, event):
        """사용자 ID 검색 포커스 아웃"""
        if not self.user_id_search_var.get():
            self.user_id_search_var.set("사용자 ID 검색...")
    
    def _filter_hashtags(self, *args):
        """해시태그 필터링"""
        search_term = self.hashtag_search_var.get().lower()
        
        # 원본 데이터가 없으면 현재 리스트박스 내용을 저장
        if not self.original_hashtags:
            self.original_hashtags = list(self.hashtag_listbox.get(0, tk.END))
        
        # 검색어가 기본값이면 모든 항목 표시
        if search_term in ["", "해시태그 검색..."]:
            self.hashtag_listbox.delete(0, tk.END)
            for item in self.original_hashtags:
                self.hashtag_listbox.insert(tk.END, item)
        else:
            # 필터링된 항목만 표시
            filtered_items = [item for item in self.original_hashtags if search_term in item.lower()]
            self.hashtag_listbox.delete(0, tk.END)
            for item in filtered_items:
                self.hashtag_listbox.insert(tk.END, item)
        
        self._update_count_labels()
    
    def _refresh_lists(self):
        """목록 새로고침"""
        try:
            # 다운로드 경로 확인
            download_path = self.download_directory_var.get()
            if not download_path or not os.path.exists(download_path):
                print(f"다운로드 경로가 존재하지 않습니다: {download_path}")
                return
            
            load_existing_directories(self.hashtag_listbox, self.user_id_listbox, 
                                    self.download_directory_var, lambda x: print(f"상태: {x}"))
            self._update_count_labels()
            
            # 원본 데이터 초기화 (필터링을 위해)
            self.original_hashtags = list(self.hashtag_listbox.get(0, tk.END))
            self.original_user_ids = list(self.user_id_listbox.get(0, tk.END))
            
            print(f"목록 새로고침 완료: 해시태그 {len(self.original_hashtags)}개, 사용자 ID {len(self.original_user_ids)}개")
            
        except Exception as e:
            print(f"목록 새로고침 오류: {e}")
    
    def _update_count_labels(self):
        """개수 라벨 업데이트"""
        hashtag_count = self.hashtag_listbox.size()
        user_id_count = self.user_id_listbox.size()
        self.hashtag_count_var.set(f"해시태그 목록 ({hashtag_count}개)")
        self.user_id_count_var.set(f"사용자 ID 목록 ({user_id_count}개)")
    
    def _filter_user_ids(self, *args):
        """사용자 ID 필터링"""
        search_term = self.user_id_search_var.get().lower()
        
        # 원본 데이터가 없으면 현재 리스트박스 내용을 저장
        if not self.original_user_ids:
            self.original_user_ids = list(self.user_id_listbox.get(0, tk.END))
        
        # 검색어가 기본값이면 모든 항목 표시
        if search_term in ["", "사용자 id 검색..."]:
            self.user_id_listbox.delete(0, tk.END)
            for item in self.original_user_ids:
                self.user_id_listbox.insert(tk.END, item)
        else:
            # 필터링된 항목만 표시
            filtered_items = [item for item in self.original_user_ids if search_term in item.lower()]
            self.user_id_listbox.delete(0, tk.END)
            for item in filtered_items:
                self.user_id_listbox.insert(tk.END, item)
        
        self._update_count_labels()
    
    def _apply_sort(self):
        """선택된 정렬 기준에 따라 목록 정렬"""
        criteria = self.sort_criteria_var.get()
        
        try:
            if criteria == "생성일 내림차순":
                sort_user_ids_by_creation_desc(self.user_id_listbox, lambda x: print(f"상태: {x}"), self.download_directory_var)
            elif criteria == "생성일 오름차순":
                sort_user_ids_by_creation_asc(self.user_id_listbox, lambda x: print(f"상태: {x}"), self.download_directory_var)
            elif criteria == "INI 내림차순":
                sort_user_ids_by_ini_desc(self.user_id_listbox, lambda x: print(f"상태: {x}"))
            elif criteria == "INI 오름차순":
                sort_user_ids_by_ini_asc(self.user_id_listbox, lambda x: print(f"상태: {x}"))
            elif criteria == "이름순":
                # 이름순 정렬 - 현재 목록을 알파벳 순으로 정렬
                current_items = list(self.user_id_listbox.get(0, tk.END))
                current_items.sort()
                self.user_id_listbox.delete(0, tk.END)
                for item in current_items:
                    self.user_id_listbox.insert(tk.END, item)
            
            self._update_count_labels()
            print(f"정렬 완료: {criteria}")
            
        except Exception as e:
            print(f"정렬 오류: {e}")
    
    def get_search_config(self):
        """검색 설정 반환"""
        return {
            'search_type': self.search_type_var.get(),
            'hashtag_options': {
                'include_images': self.include_images_var_hashtag.get(),
                'include_videos': self.include_videos_var_hashtag.get(),
                'include_human_classify': self.include_human_classify_var_hashtag.get(),
                'include_upscale': self.include_upscale_var_hashtag.get()
            },
            'user_id_options': {
                'include_images': self.include_images_var_user.get(),
                'include_reels': self.include_reels_var_user.get(),
                'include_human_classify': self.include_human_classify_var_user.get(),
                'include_upscale': self.include_upscale_var_user.get()
            },
            'download_path': self.download_directory_var.get(),
            'allow_duplicate': self.allow_duplicate_var.get(),
            'wait_time': float(self.wait_time_var.get()),
            'post_count': int(self.post_count_entry.get()) if self.post_count_entry.get() else 0
        }

    def _on_search_text_change(self, event=None):
        """검색어 텍스트 변경 이벤트"""
        current_text = self.word_text.get(1.0, tk.END).strip()
        
        # 텍스트가 실제로 변경된 경우에만 저장
        if current_text != self._last_search_text:
            self._last_search_text = current_text
            self._save_search_terms()
    
    def _save_search_terms(self):
        """검색어를 config에 저장"""
        try:
            from ...utils.config import load_config, save_config
            
            config = load_config()
            
            # 텍스트에서 검색어 추출
            search_text = self.word_text.get(1.0, tk.END).strip()
            search_terms = []
            
            if search_text:
                for line in search_text.split('\n'):
                    for term in line.split(','):
                        term = term.strip()
                        if term:
                            search_terms.append(term)
            
            # config에 저장
            config['SEARCH_TERMS'] = search_terms
            save_config(config)
            
        except Exception as e:
            print(f"검색어 저장 오류: {e}")
    
    def _on_anti_detection_mode_change(self, event=None):
        """Anti-Detection 모드 변경 시 호출"""
        self._update_mode_description()
        self._save_config()

    def _update_mode_description(self):
        """모드 설명 업데이트"""
        from ...core.anti_detection import get_anti_detection_settings, get_mode_from_display_value
        
        display_value = self.anti_detection_mode_var.get()
        mode_key = get_mode_from_display_value(display_value)
        
        settings = get_anti_detection_settings(mode_key)
        description = f"{settings['description']} - {settings['use_case']}"
        self.mode_description_var.set(description)
