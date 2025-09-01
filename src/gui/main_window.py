# src/gui/main_window.py
"""
모듈화된 메인 윈도우 클래스
"""
import os
import tkinter as tk
from tkinter import ttk

from .components.account_panel import AccountPanel
from .components.search_panel import SearchPanel
from .components.progress_panel import ProgressPanel
from .components.status_panel import StatusPanel
from .controllers.gui_controller import GUIController
from ..utils.config import load_config, save_config
from ..utils.environment import Environment


class MainWindow:
    """메인 윈도우 클래스"""
    
    def __init__(self):
        self.root = None
        self.config = None
        self.account_panel = None
        self.search_panel = None
        self.progress_panel = None
        self.status_panel = None
        self.gui_controller = None
        
        # 프로젝트 루트 및 기본 다운로드 경로 설정
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
        self.default_download_path = os.path.join(self.project_root, 'data', 'downloads')
        
    def create_window(self):
        """메인 윈도우 생성"""
        print("GUI 시작...")
        
        # 설정 로드
        self.config = load_config()
        loaded_accounts = self.config['ACCOUNTS'][:]
        loaded_searchtype = self.config['LAST_SEARCH_TYPE'] if isinstance(self.config['LAST_SEARCH_TYPE'], str) else "hashtag"
        last_download_path = self.config.get('LAST_DOWNLOAD_PATH', self.default_download_path)
        
        # 메인 윈도우 생성
        self.root = tk.Tk()
        self.root.title("인스타그램 이미지 크롤링 프로그램 (Instaloader 기반)")
        self.root.geometry("900x1200")
        self.root.minsize(900, 1200)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(7, weight=1)  # 상태창이 있는 행에 가중치 부여
        
        # 스타일 설정
        self._setup_styles()
        
        # 헤더 생성
        self._create_header()
        
        # 상단 프레임 생성
        top_frame = self._create_top_frame()
        
        # 컴포넌트들 생성
        self._create_components(top_frame, loaded_accounts, loaded_searchtype, last_download_path)
        
        # 컨트롤러 생성
        self._create_controller()
        
        # 윈도우 종료 이벤트 설정
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        return self.root
    
    def _setup_styles(self):
        """스타일 설정"""
        style = ttk.Style(self.root)
        style.configure('TButton', font=('Arial', 10))
        style.configure('TLabel', font=('Arial', 10))
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Accent.TButton', font=('Arial', 10, 'bold'))
    
    def _create_header(self):
        """헤더 생성"""
        header = ttk.Label(self.root, text="인스타그램 이미지 크롤링 프로그램", style='Header.TLabel')
        header.grid(row=0, column=0, pady=10, padx=10, sticky='ew')
    
    def _create_top_frame(self):
        """상단 프레임 생성"""
        top_frame = ttk.Frame(self.root)
        top_frame.grid(row=1, column=0, padx=10, pady=5, sticky='ew')
        top_frame.columnconfigure(0, weight=1)
        top_frame.columnconfigure(1, weight=1)
        return top_frame
    
    def _create_components(self, top_frame, loaded_accounts, loaded_searchtype, last_download_path):
        """컴포넌트들 생성"""
        # 계정 패널 생성
        self.account_panel = AccountPanel(self.root, self.config, loaded_accounts)
        self.account_panel.create_account_frame(top_frame)
        
        # 검색 패널 생성 - 설정에서 하위 체크박스 상태도 로드
        self.search_panel = SearchPanel(self.root, self.config, loaded_searchtype, last_download_path)
        self.search_panel.create_search_type_frame(top_frame)
        self.search_panel.create_search_frame(self.root)
        self.search_panel.create_download_frame(self.root)
        self.search_panel.create_existing_dirs_frame(self.root)
        
        # 진행률 패널 생성
        self.progress_panel = ProgressPanel(self.root)
        self.progress_panel.create_progress_frame(self.root)
        
        # 상태 패널 생성
        self.status_panel = StatusPanel(self.root)
        self.status_panel.create_status_frame(self.root)
    
    def _create_controller(self):
        """컨트롤러 생성"""
        self.gui_controller = GUIController(
            self.root, self.account_panel, self.search_panel, 
            self.progress_panel, self.status_panel, self.config
        )
        self.gui_controller.create_control_buttons(self.root)
    
    def _on_closing(self):
        """윈도우 종료 이벤트"""
        # 설정 저장
        self._save_config()
        
        # 윈도우 종료
        self.root.destroy()
        print("GUI 종료")
    
    def _save_config(self):
        """설정 저장"""
        try:
            # 마지막 검색 유형 저장 (문자열로 저장)
            self.config['LAST_SEARCH_TYPE'] = self.search_panel.search_type_var.get()
            
            # 마지막 다운로드 경로 저장
            self.config['LAST_DOWNLOAD_PATH'] = self.search_panel.download_directory_var.get()
            
            # 계정 목록 저장
            accounts = self.account_panel.get_accounts()
            self.config['ACCOUNTS'] = accounts
            
            # 요청 대기시간 저장
            self.config['REQUEST_WAIT_TIME'] = float(self.search_panel.wait_time_var.get())
            
            # 해시태그 옵션 저장
            self.config['HASHTAG_OPTIONS'] = {
                'include_images': self.search_panel.include_images_var_hashtag.get(),
                'include_videos': self.search_panel.include_videos_var_hashtag.get(),
                'include_human_classify': self.search_panel.include_human_classify_var_hashtag.get(),
                'include_upscale': self.search_panel.include_upscale_var_hashtag.get()
            }
            
            # 사용자 ID 옵션 저장
            self.config['USER_ID_OPTIONS'] = {
                'include_images': self.search_panel.include_images_var_user.get(),
                'include_reels': self.search_panel.include_reels_var_user.get(),
                'include_human_classify': self.search_panel.include_human_classify_var_user.get(),
                'include_upscale': self.search_panel.include_upscale_var_user.get()
            }
            
            # 중복 다운로드 허용 설정 저장
            self.config['ALLOW_DUPLICATE'] = self.search_panel.allow_duplicate_var.get()
            
            # 설정 파일 저장
            save_config(self.config)
            print("설정이 저장되었습니다.")
            
        except Exception as e:
            print(f"설정 저장 오류: {e}")
    
    def run(self):
        """GUI 실행"""
        self.root.mainloop()


def main_gui():
    """메인 GUI 함수 (기존 호환성 유지)"""
    window = MainWindow()
    root = window.create_window()
    window.run()
    return root

