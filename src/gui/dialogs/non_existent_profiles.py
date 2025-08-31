# crawling/gui_non_existent_profiles.py
"""
존재하지 않는 프로필 관리 함수들을 모아놓은 모듈
기존 gui.py의 UI는 그대로 두고 내부 로직만 분리
"""
import tkinter as tk
from tkinter import ttk, messagebox
from crawling.config import load_config, save_config
from crawling.profile_manager import (
    get_non_existent_profile_ids, add_non_existent_profile_id, 
    remove_non_existent_profile_id, clear_non_existent_profile_ids,
    get_username_by_profile_id, load_profile_ids_from_stamps
)

def manage_non_existent_profiles(append_status_func):
    """
    존재하지 않는 프로필 관리 창을 엽니다.
    """
    
    dialog = tk.Toplevel()
    dialog.title("존재하지 않는 프로필 관리")
    dialog.geometry("500x400")
    dialog.transient()
    dialog.grab_set()
    
    # 중앙 정렬
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(0, weight=1)
    
    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    main_frame.columnconfigure(0, weight=1)
    main_frame.rowconfigure(1, weight=1)
    
    # 제목
    ttk.Label(main_frame, text="존재하지 않는 프로필 목록", font=('Arial', 12, 'bold')).grid(row=0, column=0, pady=(0, 10))
    
    # 리스트박스
    listbox_frame = ttk.Frame(main_frame)
    listbox_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
    listbox_frame.columnconfigure(0, weight=1)
    listbox_frame.rowconfigure(0, weight=1)
    
    listbox = tk.Listbox(listbox_frame, selectmode=tk.EXTENDED)
    listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
    scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    listbox.config(yscrollcommand=scrollbar.set)
    
    # 프로필 목록은 refresh_list()에서 로드됨
    
    # 버튼 프레임
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=2, column=0, pady=(0, 10))
    button_frame.columnconfigure(0, weight=1)
    button_frame.columnconfigure(1, weight=1)
    button_frame.columnconfigure(2, weight=1)
    
    def refresh_list():
        """리스트를 새로고침합니다."""
        listbox.delete(0, tk.END)
        
        # config를 한 번만 로드해서 재사용
        config = load_config()
        
        # profile-id 기반 목록 로드
        non_existent_profile_ids = config.get('NON_EXISTENT_PROFILE_IDS', [])
        if non_existent_profile_ids:
            # profile_ids_map을 한 번만 로드해서 재사용
            profile_ids_map = load_profile_ids_from_stamps()
            username_to_profile_id = {v: k for k, v in profile_ids_map.items()}  # 역방향 매핑
            
            for profile_id in non_existent_profile_ids:
                # 역방향 매핑에서 username 찾기
                username = username_to_profile_id.get(profile_id)
                if username:
                    listbox.insert(tk.END, f"{username} (ID: {profile_id})")
                else:
                    listbox.insert(tk.END, f"Unknown (ID: {profile_id})")
        
        # 하위 호환성을 위한 username 기반 목록도 로드
        non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
        for profile in non_existent_profiles:
            listbox.insert(tk.END, profile)
        
        total_count = len(non_existent_profile_ids) + len(non_existent_profiles)
        append_status_func(f"존재하지 않는 프로필 목록 새로고침됨 ({total_count}개)")
    
    def remove_selected():
        """선택된 프로필을 제거합니다."""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("경고", "제거할 프로필을 선택하세요.")
            return
        
        selected_items = [listbox.get(i) for i in selection]
        result = messagebox.askyesno("확인", f"선택된 {len(selected_items)}개의 프로필을 제거하시겠습니까?")
        
        if result:
            # 선택된 항목에서 profile-id 추출
            for item in selected_items:
                if "(ID: " in item:
                    # "username (ID: 123456)" 형태에서 profile-id 추출
                    profile_id = item.split("(ID: ")[1].split(")")[0]
                    remove_non_existent_profile_id(profile_id)
                else:
                    # 하위 호환성을 위한 username 기반 제거
                    config = load_config()
                    non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
                    if item in non_existent_profiles:
                        non_existent_profiles.remove(item)
                        config['NON_EXISTENT_PROFILES'] = non_existent_profiles
                        save_config(config)
            
            refresh_list()
            append_status_func(f"{len(selected_items)}개의 프로필이 제거되었습니다.")
    
    def clear_all():
        """모든 프로필을 제거합니다."""
        # config를 한 번만 로드해서 재사용
        config = load_config()
        non_existent_profile_ids = config.get('NON_EXISTENT_PROFILE_IDS', [])
        non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
        
        total_count = len(non_existent_profile_ids) + len(non_existent_profiles)
        
        if total_count == 0:
            messagebox.showinfo("정보", "제거할 프로필이 없습니다.")
            return
        
        result = messagebox.askyesno("확인", f"모든 {total_count}개의 프로필을 제거하시겠습니까?")
        
        if result:
            # 두 목록 모두 제거
            config['NON_EXISTENT_PROFILE_IDS'] = []
            config['NON_EXISTENT_PROFILES'] = []
            save_config(config)
            
            refresh_list()
            append_status_func("모든 존재하지 않는 프로필이 제거되었습니다.")
    
    def add_manual():
        """수동으로 프로필을 추가합니다."""
        add_dialog = tk.Toplevel(dialog)
        add_dialog.title("프로필 추가")
        add_dialog.geometry("300x150")
        add_dialog.transient(dialog)
        add_dialog.grab_set()
        
        add_dialog.columnconfigure(0, weight=1)
        add_dialog.rowconfigure(0, weight=1)
        
        add_frame = ttk.Frame(add_dialog, padding="10")
        add_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        add_frame.columnconfigure(1, weight=1)
        
        ttk.Label(add_frame, text="프로필명:").grid(row=0, column=0, sticky=tk.W, pady=5)
        profile_var = tk.StringVar()
        profile_entry = ttk.Entry(add_frame, textvariable=profile_var)
        profile_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        
        def save_profile():
            profile = profile_var.get().strip()
            if not profile:
                messagebox.showerror("오류", "프로필명을 입력하세요.")
                return
            
            config = load_config()
            non_existent_profiles = config.get('NON_EXISTENT_PROFILES', [])
            
            if profile in non_existent_profiles:
                messagebox.showwarning("경고", "이미 존재하는 프로필입니다.")
                return
            
            non_existent_profiles.append(profile)
            config['NON_EXISTENT_PROFILES'] = non_existent_profiles
            save_config(config)
            
            refresh_list()
            append_status_func(f"프로필 추가됨: {profile}")
            add_dialog.destroy()
        
        ttk.Button(add_frame, text="추가", command=save_profile).grid(row=1, column=0, columnspan=2, pady=20)
        profile_entry.focus()
    
    def add_profile():
        """현재 검색 텍스트에서 프로필을 추가합니다."""
        # 이 함수는 gui.py에서 호출될 때 검색 텍스트를 전달받아야 합니다.
        # 여기서는 기본 구현만 제공합니다.
        messagebox.showinfo("정보", "이 기능은 검색 텍스트에서 프로필을 추가하는 기능입니다.")
    
    # 버튼들
    ttk.Button(button_frame, text="새로고침", command=refresh_list).grid(row=0, column=0, padx=5)
    ttk.Button(button_frame, text="선택 제거", command=remove_selected).grid(row=0, column=1, padx=5)
    ttk.Button(button_frame, text="전체 제거", command=clear_all).grid(row=0, column=2, padx=5)
    
    # 하단 버튼들
    bottom_button_frame = ttk.Frame(main_frame)
    bottom_button_frame.grid(row=3, column=0)
    bottom_button_frame.columnconfigure(0, weight=1)
    bottom_button_frame.columnconfigure(1, weight=1)
    
    ttk.Button(bottom_button_frame, text="수동 추가", command=add_manual).grid(row=0, column=0, padx=5)
    ttk.Button(bottom_button_frame, text="닫기", command=dialog.destroy).grid(row=0, column=1, padx=5)
    
    # 초기 목록 로드
    refresh_list()
