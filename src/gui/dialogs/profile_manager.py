# src/gui/dialogs/profile_manager.py
"""
통합 프로필 관리 다이얼로그 (탭으로 구분)
"""
import tkinter as tk
from tkinter import ttk, messagebox
from ...utils.config import load_config, save_config
from ...core.profile_manager import (
    # 존재하지 않는 프로필 관리
    get_non_existent_profile_ids, 
    remove_non_existent_profile_id, 
    clear_non_existent_profile_ids,
    get_username_by_profile_id as get_username_by_profile_id_non_existent,
    load_profile_ids_from_stamps as load_profile_ids_from_stamps_non_existent,
    # 비공개 프로필 관리
    get_private_not_followed_profile_ids, 
    remove_private_not_followed_profile_id, 
    clear_private_not_followed_profile_ids,
    get_username_by_profile_id as get_username_by_profile_id_private,
    load_profile_ids_from_stamps as load_profile_ids_from_stamps_private
)

def manage_profiles(append_status_func):
    """
    통합 프로필 관리 다이얼로그를 표시합니다.
    """
    dialog = tk.Toplevel()
    dialog.title("프로필 관리")
    dialog.geometry("700x500")
    dialog.resizable(True, True)
    dialog.transient()
    dialog.grab_set()
    
    # 메인 프레임
    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(0, weight=1)
    main_frame.columnconfigure(0, weight=1)
    main_frame.rowconfigure(1, weight=1)
    
    # 제목
    title_label = ttk.Label(main_frame, text="프로필 관리", font=('Arial', 14, 'bold'))
    title_label.grid(row=0, column=0, pady=(0, 10), sticky='w')
    
    # 노트북 (탭) 생성
    notebook = ttk.Notebook(main_frame)
    notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
    
    # 탭 1: 존재하지 않는 프로필
    non_existent_frame = ttk.Frame(notebook, padding="10")
    notebook.add(non_existent_frame, text="존재하지 않는 프로필")
    non_existent_frame.columnconfigure(0, weight=1)
    non_existent_frame.rowconfigure(1, weight=1)
    
    # 탭 2: 비공개 프로필
    private_frame = ttk.Frame(notebook, padding="10")
    notebook.add(private_frame, text="비공개 프로필")
    private_frame.columnconfigure(0, weight=1)
    private_frame.rowconfigure(1, weight=1)
    
    # ===== 존재하지 않는 프로필 탭 =====
    non_existent_title = ttk.Label(non_existent_frame, text="존재하지 않는 프로필 목록", 
                                  font=('Arial', 12, 'bold'))
    non_existent_title.grid(row=0, column=0, pady=(0, 10), sticky='w')
    
    non_existent_desc = ttk.Label(non_existent_frame, 
                                 text="프로필이 다시 생성되면 해당 항목을 선택하고 '제거' 버튼을 클릭하세요.", 
                                 wraplength=650, font=('Arial', 9))
    non_existent_desc.grid(row=1, column=0, pady=(0, 10), sticky='w')
    
    # 존재하지 않는 프로필 리스트박스
    non_existent_list_frame = ttk.Frame(non_existent_frame)
    non_existent_list_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
    non_existent_list_frame.columnconfigure(0, weight=1)
    non_existent_list_frame.rowconfigure(0, weight=1)
    
    non_existent_listbox = tk.Listbox(non_existent_list_frame, selectmode=tk.EXTENDED, font=('Arial', 10))
    non_existent_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
    
    non_existent_scrollbar = ttk.Scrollbar(non_existent_list_frame, orient="vertical", command=non_existent_listbox.yview)
    non_existent_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    non_existent_listbox.config(yscrollcommand=non_existent_scrollbar.set)
    
    # 존재하지 않는 프로필 버튼 프레임
    non_existent_button_frame = ttk.Frame(non_existent_frame)
    non_existent_button_frame.grid(row=3, column=0, pady=(0, 10), sticky='ew')
    non_existent_button_frame.columnconfigure(0, weight=1)
    non_existent_button_frame.columnconfigure(1, weight=1)
    non_existent_button_frame.columnconfigure(2, weight=1)
    
    # 존재하지 않는 프로필 개수 라벨
    non_existent_count_label = ttk.Label(non_existent_frame, text="총 0개 항목", font=('Arial', 9))
    non_existent_count_label.grid(row=4, column=0, pady=(0, 10), sticky='w')
    
    # ===== 비공개 프로필 탭 =====
    private_title = ttk.Label(private_frame, text="비공개 프로필 목록", 
                             font=('Arial', 12, 'bold'))
    private_title.grid(row=0, column=0, pady=(0, 10), sticky='w')
    
    private_desc = ttk.Label(private_frame, 
                            text="팔로우 후 다시 시도하려면 해당 항목을 선택하고 '제거' 버튼을 클릭하세요.", 
                            wraplength=650, font=('Arial', 9))
    private_desc.grid(row=1, column=0, pady=(0, 10), sticky='w')
    
    # 비공개 프로필 리스트박스
    private_list_frame = ttk.Frame(private_frame)
    private_list_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
    private_list_frame.columnconfigure(0, weight=1)
    private_list_frame.rowconfigure(0, weight=1)
    
    private_listbox = tk.Listbox(private_list_frame, selectmode=tk.EXTENDED, font=('Arial', 10))
    private_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
    
    private_scrollbar = ttk.Scrollbar(private_list_frame, orient="vertical", command=private_listbox.yview)
    private_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    private_listbox.config(yscrollcommand=private_scrollbar.set)
    
    # 비공개 프로필 버튼 프레임
    private_button_frame = ttk.Frame(private_frame)
    private_button_frame.grid(row=3, column=0, pady=(0, 10), sticky='ew')
    private_button_frame.columnconfigure(0, weight=1)
    private_button_frame.columnconfigure(1, weight=1)
    private_button_frame.columnconfigure(2, weight=1)
    
    # 비공개 프로필 개수 라벨
    private_count_label = ttk.Label(private_frame, text="총 0개 항목", font=('Arial', 9))
    private_count_label.grid(row=4, column=0, pady=(0, 10), sticky='w')
    
    # ===== 존재하지 않는 프로필 함수들 =====
    def refresh_non_existent_list():
        """존재하지 않는 프로필 리스트를 새로고침합니다."""
        non_existent_listbox.delete(0, tk.END)
        config = load_config()
        
        # profile-id 기반 존재하지 않는 프로필 목록
        non_existent_profile_ids = config.get('NON_EXISTENT_PROFILE_IDS', [])
        profile_ids_map = load_profile_ids_from_stamps_non_existent()
        
        # profile-id를 username으로 변환하여 표시
        for profile_id in non_existent_profile_ids:
            username = get_username_by_profile_id_non_existent(profile_id)
            if username:
                non_existent_listbox.insert(tk.END, f"{username} (ID: {profile_id})")
            else:
                non_existent_listbox.insert(tk.END, f"Unknown (ID: {profile_id})")
        
        # username 기반 존재하지 않는 프로필 목록 (하위 호환성)
        non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
        for username in non_existent_profiles:
            if not any(f"{username} (ID:" in non_existent_listbox.get(i) for i in range(non_existent_listbox.size())):
                non_existent_listbox.insert(tk.END, username)
        
        count = non_existent_listbox.size()
        non_existent_count_label.config(text=f"총 {count}개 항목")
    
    def remove_selected_non_existent():
        """선택된 존재하지 않는 프로필을 제거합니다."""
        selected_indices = non_existent_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("경고", "제거할 항목을 선택하세요.")
            return
        
        if messagebox.askyesno("확인", "선택된 항목을 존재하지 않는 프로필 목록에서 제거하시겠습니까?"):
            config = load_config()
            removed_count = 0
            
            for index in reversed(selected_indices):
                item = non_existent_listbox.get(index)
                
                # "username (ID: profile_id)" 형태인지 확인
                if " (ID: " in item:
                    # profile-id 기반 항목
                    profile_id = item.split(" (ID: ")[1].rstrip(")")
                    remove_non_existent_profile_id(profile_id)
                    removed_count += 1
                else:
                    # username 기반 항목 (하위 호환성)
                    username = item.strip()
                    non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
                    if username in non_existent_profiles:
                        non_existent_profiles.remove(username)
                        config['NON_EXISTENT_PROFILES'] = non_existent_profiles
                        save_config(config)
                        removed_count += 1
            
            if removed_count > 0:
                append_status_func(f"존재하지 않는 프로필 목록에서 {removed_count}개 항목 제거됨")
                refresh_non_existent_list()
    
    def clear_all_non_existent():
        """모든 존재하지 않는 프로필을 제거합니다."""
        if messagebox.askyesno("확인", "모든 존재하지 않는 프로필을 목록에서 제거하시겠습니까?"):
            clear_non_existent_profile_ids()
            
            # username 기반 목록도 제거
            config = load_config()
            config['NON_EXISTENT_PROFILES'] = []
            save_config(config)
            
            append_status_func("모든 존재하지 않는 프로필 목록 제거됨")
            refresh_non_existent_list()
    
    # ===== 비공개 프로필 함수들 =====
    def refresh_private_list():
        """비공개 프로필 리스트를 새로고침합니다."""
        private_listbox.delete(0, tk.END)
        config = load_config()
        
        # profile-id 기반 비공개 프로필 목록
        private_profile_ids = config.get('PRIVATE_NOT_FOLLOWED_PROFILE_IDS', [])
        profile_ids_map = load_profile_ids_from_stamps_private()
        
        # profile-id를 username으로 변환하여 표시
        for profile_id in private_profile_ids:
            username = get_username_by_profile_id_private(profile_id)
            if username:
                private_listbox.insert(tk.END, f"{username} (ID: {profile_id})")
            else:
                private_listbox.insert(tk.END, f"Unknown (ID: {profile_id})")
        
        # username 기반 비공개 프로필 목록 (하위 호환성)
        private_profiles = config.get('PRIVATE_NOT_FOLLOWED_PROFILES', [])
        for username in private_profiles:
            if not any(f"{username} (ID:" in private_listbox.get(i) for i in range(private_listbox.size())):
                private_listbox.insert(tk.END, username)
        
        count = private_listbox.size()
        private_count_label.config(text=f"총 {count}개 항목")
    
    def remove_selected_private():
        """선택된 비공개 프로필을 제거합니다."""
        selected_indices = private_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("경고", "제거할 항목을 선택하세요.")
            return
        
        if messagebox.askyesno("확인", "선택된 항목을 비공개 프로필 목록에서 제거하시겠습니까?"):
            config = load_config()
            removed_count = 0
            
            for index in reversed(selected_indices):
                item = private_listbox.get(index)
                
                # "username (ID: profile_id)" 형태인지 확인
                if " (ID: " in item:
                    # profile-id 기반 항목
                    profile_id = item.split(" (ID: ")[1].rstrip(")")
                    remove_private_not_followed_profile_id(profile_id)
                    removed_count += 1
                else:
                    # username 기반 항목 (하위 호환성)
                    username = item.strip()
                    private_profiles = config.get('PRIVATE_NOT_FOLLOWED_PROFILES', [])
                    if username in private_profiles:
                        private_profiles.remove(username)
                        config['PRIVATE_NOT_FOLLOWED_PROFILES'] = private_profiles
                        save_config(config)
                        removed_count += 1
            
            if removed_count > 0:
                append_status_func(f"비공개 프로필 목록에서 {removed_count}개 항목 제거됨")
                refresh_private_list()
    
    def clear_all_private():
        """모든 비공개 프로필을 제거합니다."""
        if messagebox.askyesno("확인", "모든 비공개 프로필을 목록에서 제거하시겠습니까?"):
            clear_private_not_followed_profile_ids()
            
            # username 기반 목록도 제거
            config = load_config()
            config['PRIVATE_NOT_FOLLOWED_PROFILES'] = []
            save_config(config)
            
            append_status_func("모든 비공개 프로필 목록 제거됨")
            refresh_private_list()
    
    # ===== 버튼들 =====
    # 존재하지 않는 프로필 버튼들
    non_existent_remove_button = ttk.Button(non_existent_button_frame, text="선택된 항목 제거", 
                                           command=remove_selected_non_existent)
    non_existent_remove_button.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
    
    non_existent_clear_button = ttk.Button(non_existent_button_frame, text="모든 항목 제거", 
                                          command=clear_all_non_existent)
    non_existent_clear_button.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
    
    non_existent_refresh_button = ttk.Button(non_existent_button_frame, text="새로고침", 
                                            command=refresh_non_existent_list)
    non_existent_refresh_button.grid(row=0, column=2, padx=5, pady=5, sticky='ew')
    
    # 비공개 프로필 버튼들
    private_remove_button = ttk.Button(private_button_frame, text="선택된 항목 제거", 
                                      command=remove_selected_private)
    private_remove_button.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
    
    private_clear_button = ttk.Button(private_button_frame, text="모든 항목 제거", 
                                     command=clear_all_private)
    private_clear_button.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
    
    private_refresh_button = ttk.Button(private_button_frame, text="새로고침", 
                                       command=refresh_private_list)
    private_refresh_button.grid(row=0, column=2, padx=5, pady=5, sticky='ew')
    
    # 닫기 버튼
    close_button = ttk.Button(main_frame, text="닫기", command=dialog.destroy)
    close_button.grid(row=2, column=0, pady=(0, 10))
    
    # 초기 리스트 로드
    refresh_non_existent_list()
    refresh_private_list()
    
    # 다이얼로그가 닫힐 때까지 대기
    dialog.wait_window()
