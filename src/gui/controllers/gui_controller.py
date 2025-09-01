# src/gui/controllers/gui_controller.py
"""
GUI 이벤트 컨트롤러
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from queue import Queue
from datetime import datetime

from ..handlers.queue_handler import process_queue
from ..dialogs.profile_manager import manage_profiles
from ..dialogs.settings import load_existing_directories, delete_selected_items
from ...core.downloader import crawl_and_download
from ...processing.post_processing import process_images
from ...utils.config import save_config


class GUIController:
    """GUI 이벤트 컨트롤러 클래스"""
    
    def __init__(self, root, account_panel, search_panel, progress_panel, status_panel, config):
        self.root = root
        self.account_panel = account_panel
        self.search_panel = search_panel
        self.progress_panel = progress_panel
        self.status_panel = status_panel
        self.config = config
        
        # 크롤링 관련 변수들
        self.crawling_thread = None
        self.stop_event = threading.Event()
        self.progress_queue = Queue()
        self.start_time = None
        
        # 버튼들
        self.start_button = None
        self.stop_button = None
        
    def create_control_buttons(self, root):
        """제어 버튼들 생성"""
        control_frame = ttk.Frame(root)
        control_frame.grid(row=6, column=0, padx=10, pady=5, sticky='ew')
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        control_frame.columnconfigure(2, weight=1)
        control_frame.columnconfigure(3, weight=1)
        
        # 크롤링 시작 버튼
        self.start_button = ttk.Button(control_frame, text="크롤링 시작", 
                                      command=self.start_crawling, style='Accent.TButton')
        self.start_button.grid(row=0, column=0, padx=2, pady=2, sticky='ew')
        
        # 크롤링 중지 버튼
        self.stop_button = ttk.Button(control_frame, text="크롤링 중지", 
                                     command=self.stop_crawling, state='disabled')
        self.stop_button.grid(row=0, column=1, padx=2, pady=2, sticky='ew')
        
        # 프로필 관리 버튼
        manage_profiles_btn = ttk.Button(control_frame, text="프로필 관리", 
                                        command=self._manage_profiles_wrapper)
        manage_profiles_btn.grid(row=0, column=2, padx=2, pady=2, sticky='ew')
        
        return control_frame
    
    def start_crawling(self):
        """크롤링 시작"""
        # 검색어 검증
        search_terms = self._validate_search_terms()
        if not search_terms:
            return
        
        # 제외할 프로필 필터링
        filtered_terms = self._filter_excluded_profiles(search_terms)
        if not filtered_terms:
            messagebox.showwarning("경고", "모든 검색어가 제외 목록에 있습니다.")
            return
        
        # 크롤링 설정 준비
        crawling_config = self._prepare_crawling_config(filtered_terms)
        
        # 크롤링 실행
        self._execute_crawling(filtered_terms, crawling_config)
        
        # 시작 메시지
        self.status_panel.append_status("크롤링 시작")
    
    def stop_crawling(self):
        """크롤링 중지"""
        self.stop_event.set()
        self.status_panel.append_status("크롤링 중지 요청됨...")
        
        # 버튼 상태 변경
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
    
    def _validate_search_terms(self):
        """검색어 검증"""
        # 텍스트 위젯에서 검색어 가져오기
        search_text = self.search_panel.word_text.get(1.0, tk.END).strip()
        if not search_text:
            messagebox.showwarning("경고", "검색할 항목을 입력해주세요.")
            return []
        
        # 개행 또는 쉼표로 분리
        search_terms = []
        for line in search_text.split('\n'):
            for term in line.split(','):
                term = term.strip()
                if term:
                    search_terms.append(term)
        
        if not search_terms:
            messagebox.showwarning("경고", "검색할 항목을 입력해주세요.")
            return []
        
        return search_terms
    
    def _filter_excluded_profiles(self, search_terms):
        """제외된 프로필을 필터링합니다."""
        from ...core.profile_manager import (
            get_non_existent_profile_ids, get_private_not_followed_profile_ids,
            get_username_by_profile_id
        )
        
        non_existent_ids = get_non_existent_profile_ids()
        private_not_followed_ids = get_private_not_followed_profile_ids()
        
        excluded_usernames = set()
        
        for profile_id in non_existent_ids:
            username = get_username_by_profile_id(profile_id)
            if username:
                excluded_usernames.add(username)
            else:
                excluded_usernames.add(profile_id)
        
        for profile_id in private_not_followed_ids:
            username = get_username_by_profile_id(profile_id)
            if username:
                excluded_usernames.add(username)
            else:
                excluded_usernames.add(profile_id)
        
        config = self.config
        non_existent_usernames = config.get('NON_EXISTENT_PROFILES', [])
        private_usernames = config.get('PRIVATE_NOT_FOLLOWED_PROFILES', [])
        
        excluded_usernames.update(non_existent_usernames)
        excluded_usernames.update(private_usernames)
        
        filtered_terms = [term for term in search_terms if term not in excluded_usernames]
        
        self._update_search_text_with_filtered_terms(filtered_terms, len(search_terms))
        
        return filtered_terms
    
    def _update_search_text_with_filtered_terms(self, filtered_terms, original_count):
        """검색 텍스트 위젯을 필터링된 항목들로 업데이트"""
        if filtered_terms:
            # 필터링된 항목들을 텍스트로 변환
            filtered_text = '\n'.join(filtered_terms)
            
            # 검색 텍스트 위젯 업데이트
            self.search_panel.word_text.delete(1.0, tk.END)
            self.search_panel.word_text.insert(1.0, filtered_text)
            
            # 상태 메시지 표시
            filtered_count = len(filtered_terms)
            removed_count = original_count - filtered_count
            
            if removed_count > 0:
                self.status_panel.append_status(f"제외된 프로필 {removed_count}개가 검색 목록에서 제거되었습니다.")
        else:
            # 모든 항목이 제외된 경우
            self.search_panel.word_text.delete(1.0, tk.END)
            self.status_panel.append_status("모든 검색어가 제외 목록에 있어 검색 목록을 비웠습니다.")
    
    def _prepare_crawling_config(self, search_terms):
        """크롤링 설정 준비"""
        search_config = self.search_panel.get_search_config()
        accounts = self.account_panel.get_accounts()
        
        if not accounts:
            messagebox.showerror("오류", "계정을 추가해주세요.")
            return None
        
        # accounts가 문자열 리스트인 경우 딕셔너리 형태로 변환
        if isinstance(accounts, list) and len(accounts) > 0 and isinstance(accounts[0], str):
            converted_accounts = []
            login_history = self.config.get('LOGIN_HISTORY', [])
            
            for username in accounts:
                # LOGIN_HISTORY에서 비밀번호 찾기
                password = ''
                download_path = self.config.get('LAST_DOWNLOAD_PATH', '')
                
                for hist in login_history:
                    if hist.get('username') == username:
                        password = hist.get('password', '')
                        download_path = hist.get('download_path', download_path)
                        break
                
                converted_accounts.append({
                    'INSTAGRAM_USERNAME': username,
                    'INSTAGRAM_PASSWORD': password,
                    'DOWNLOAD_PATH': download_path
                })
            
            accounts = converted_accounts
        
        # 검색 유형에 따른 옵션 선택
        search_type = search_config.get('search_type', 'hashtag')
        if search_type == 'hashtag':
            options = search_config.get('hashtag_options', {})
        else:
            options = search_config.get('user_id_options', {})
        
        # options가 딕셔너리가 아닌 경우 기본값 사용
        if not isinstance(options, dict):
            options = {
                'include_images': True,
                'include_videos': False,
                'include_reels': False,
                'include_human_classify': False,
                'include_upscale': False
            }
        
        crawling_config = {
            'accounts': accounts,
            'search_type': search_type,
            'download_path': search_config.get('download_path', ''),
            'options': options,
            'allow_duplicate': search_config.get('allow_duplicate', False),
            'wait_time': search_config.get('wait_time', 0.0),
            'post_count': search_config.get('post_count', 0)
        }
        
        return crawling_config
    
    def _execute_crawling(self, search_terms, crawling_config):
        """크롤링 실행"""
        if not crawling_config:
            return
        
        # UI 상태 변경
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.progress_panel.reset_progress()
        
        # 시작 시간 설정
        self.start_time = datetime.now()
        self.progress_panel.set_start_time(self.start_time)
        
        # 크롤링 스레드 시작
        self.crawling_thread = threading.Thread(
            target=self._crawling_worker,
            args=(search_terms, crawling_config)
        )
        self.crawling_thread.daemon = True
        self.crawling_thread.start()
        
        # 진행률 업데이트 스레드 시작
        progress_thread = threading.Thread(target=self._progress_worker)
        progress_thread.daemon = True
        progress_thread.start()
    
    def _crawling_worker(self, search_terms, crawling_config):
        """크롤링 워커 스레드"""
        try:
            # options가 딕셔너리가 아닌 경우 기본값 사용
            options = crawling_config.get('options', {})
            if not isinstance(options, dict):
                options = {
                    'include_images': True,
                    'include_videos': False,
                    'include_reels': False,
                    'include_human_classify': False,
                    'include_upscale': False
                }
            
            crawl_and_download(
                search_terms=search_terms,
                target=crawling_config['post_count'],
                accounts=crawling_config['accounts'],
                search_type=crawling_config['search_type'],
                include_images=options.get('include_images', True),
                include_videos=options.get('include_videos', False),
                include_reels=options.get('include_reels', False),
                include_human_classify=options.get('include_human_classify', False),
                include_upscale=options.get('include_upscale', False),
                progress_queue=self.progress_queue,
                on_complete=self._on_crawling_complete,
                stop_event=self.stop_event,
                download_path=crawling_config['download_path'],
                append_status=self.status_panel.append_status,
                root=self.root,
                download_directory_var=self.search_panel.download_directory_var,
                update_overall_progress=self.progress_panel.update_progress,
                update_current_progress=self.progress_panel.update_progress,
                update_eta=self.progress_panel.update_eta,
                start_time=self.start_time,
                total_terms=len(search_terms),
                allow_duplicate=crawling_config['allow_duplicate']
            )
        except Exception as e:
            self.status_panel.append_status(f"크롤링 오류: {str(e)}")
            self._on_crawling_complete("크롤링 실패")
    
    def _progress_worker(self):
        """진행률 업데이트 워커 스레드"""
        while not self.stop_event.is_set():
            try:
                message = self.progress_queue.get(timeout=0.1)
                if message == "DONE":
                    break
                
                # 메시지 타입에 따른 처리
                if isinstance(message, tuple) and len(message) >= 3:
                    msg_type = message[0]
                    term = message[1]
                    status = message[2]
                    username = message[3] if len(message) > 3 else ""
                    
                    if msg_type == "remove_from_search":
                        # 검색 목록에서 항목 제거
                        self._remove_term_from_search(term)
                    elif msg_type == "term_progress":
                        # 진행 상황 메시지 (간단하게 표시)
                        if "다운로드 시작" in status:
                            self.status_panel.append_status(f"{term} 다운로드 시작")
                        elif "다운로드 완료" in status:
                            self.status_panel.append_status(f"{term} 다운로드 완료")
                        elif "분류 완료" in status:
                            self.status_panel.append_status(f"{term} 분류 완료")
                        elif "검색 목록에서 제거됨" in status:
                            self.status_panel.append_status(f"'{term}' 검색 목록에서 제거됨")
                        else:
                            self.status_panel.append_status(f"{term}: {status}")
                    elif msg_type == "term_complete":
                        self.status_panel.append_status(f"{term} 완료")
                    elif msg_type == "term_error":
                        self.status_panel.append_status(f"{term} 오류: {status}")
                    elif msg_type == "term_classify_complete":
                        self.status_panel.append_status(f"{term} 분류 완료")
                    elif msg_type == "account_relogin":
                        self.status_panel.append_status(f"계정 재로그인: {username}")
                    elif msg_type == "account_switch":
                        self.status_panel.append_status(f"계정 전환: {username}")
                    elif msg_type == "update_progress":
                        # 프로그레스바 업데이트
                        current = message[1]
                        total = message[2]
                        current_term = message[3] if len(message) > 3 else ""
                        self.progress_panel.update_progress(current, total, current_term)
                    elif msg_type == "update_eta":
                        # ETA 업데이트
                        start_time = message[1]
                        current = message[2]
                        total = message[3]
                        self.progress_panel.update_eta(start_time, current, total)
                        
            except:
                continue
    
    def _remove_term_from_search(self, term):
        """검색 목록에서 특정 항목을 제거합니다."""
        try:
            # 현재 검색 텍스트 가져오기
            current_text = self.search_panel.word_text.get(1.0, tk.END).strip()
            if not current_text:
                return
            
            # 항목들을 줄바꿈으로 분리
            terms = [t.strip() for t in current_text.split('\n') if t.strip()]
            
            # 해당 항목 제거
            if term in terms:
                terms.remove(term)
                
                # 업데이트된 텍스트로 교체
                updated_text = '\n'.join(terms)
                self.search_panel.word_text.delete(1.0, tk.END)
                self.search_panel.word_text.insert(1.0, updated_text)
                
                # 상태 메시지
                self.status_panel.append_status(f"🗑️ '{term}' 검색 목록에서 제거됨")
        except Exception as e:
            print(f"검색 목록에서 항목 제거 중 오류: {e}")
    
    def _on_crawling_complete(self, message):
        """크롤링 완료 콜백"""
        def complete():
            if "완료" in message:
                self.status_panel.append_status("크롤링 완료")
                # 프로그레스바를 100%로 업데이트 (실제 완료된 경우에만)
                if "완료됨" in message:
                    self.progress_panel.update_progress(1, 1, "완료")
            elif "실패" in message:
                self.status_panel.append_status("크롤링 실패")
            elif "중지" in message:
                self.status_panel.append_status("크롤링 중지됨")
            else:
                self.status_panel.append_status(message)
            self.start_button.config(state='normal')
            self.stop_button.config(state='disabled')
            self.stop_event.clear()
        
        self.root.after(0, complete)
    
    def _manage_profiles_wrapper(self):
        """프로필 관리 래퍼"""
        from ..dialogs.profile_manager import manage_profiles
        manage_profiles(self.status_panel.append_status)
    
    def _delete_selected_items_wrapper(self):
        """선택된 항목 삭제 래퍼"""
        delete_selected_items(self.search_panel.hashtag_listbox, 
                            self.search_panel.user_id_listbox, self.config)
