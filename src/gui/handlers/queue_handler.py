# src/gui/handlers/queue_handler.py
"""
GUI 이벤트 핸들러 함수들을 모아놓은 모듈
기존 gui.py의 UI는 그대로 두고 내부 로직만 분리
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ...utils.config import load_config, save_config

def add_items_from_listbox(listbox, text_widget, item_label):
    """
    리스트박스에서 선택된 항목들을 텍스트 위젯에 추가합니다.
    """
    indices = listbox.curselection()
    items = [listbox.get(i) for i in indices]
    if not items:
        print(f"정보: 추가할 {item_label}를 선택하세요.")
        return
    
    current_text = text_widget.get("1.0", tk.END).strip()
    new_text = "\n".join(items)
    updated_text = current_text + "\n" + new_text if current_text else new_text
    text_widget.delete("1.0", tk.END)
    text_widget.insert(tk.END, updated_text)
    print(f"성공: {len(items)}개의 {item_label} 추가됨.")

def add_all_items_from_listbox(listbox, text_widget, item_label):
    """
    리스트박스의 모든 항목을 텍스트 위젯에 추가합니다.
    """
    items = listbox.get(0, tk.END)
    if not items:
        print(f"정보: 추가할 {item_label}가 없습니다.")
        return
    
    current_text = text_widget.get("1.0", tk.END).strip()
    new_text = "\n".join(items)
    updated_text = current_text + "\n" + new_text if current_text else new_text
    text_widget.delete("1.0", tk.END)
    text_widget.insert(tk.END, updated_text)
    print(f"성공: 모든 {item_label} 추가됨.")

def toggle_upscale_hashtag(include_human_classify_var_hashtag, upscale_var_hashtag, upscale_checkbox_hashtag, *args):
    """
    해시태그 검색에서 인물 분류 체크박스 값에 따라 업스케일링 체크박스 활성/비활성 제어
    """
    if include_human_classify_var_hashtag.get():
        upscale_checkbox_hashtag.configure(state='normal')
    else:
        upscale_var_hashtag.set(False)
        upscale_checkbox_hashtag.configure(state='disabled')

def toggle_upscale_user(include_human_classify_var_user, upscale_var_user, upscale_checkbox_user, *args):
    """
    사용자 ID 검색에서 인물 분류 체크박스 값에 따라 업스케일링 체크박스 활성/비활성 제어
    """
    if include_human_classify_var_user.get():
        upscale_checkbox_user.configure(state='normal')
    else:
        upscale_var_user.set(False)
        upscale_checkbox_user.configure(state='disabled')

def toggle_human_classify(parent_frame, img_var, human_var, include_human_classify_check_hashtag=None, include_human_classify_check_user=None):
    """
    이미지 체크박스 값에 따라 인물 분류 체크박스 활성/비활성 제어
    """
    if img_var.get():
        if parent_frame == "hashtag_frame":
            if include_human_classify_check_hashtag:
                include_human_classify_check_hashtag.configure(state='normal')
        else:
            if include_human_classify_check_user:
                include_human_classify_check_user.configure(state='normal')
    else:
        human_var.set(False)
        if parent_frame == "hashtag_frame":
            if include_human_classify_check_hashtag:
                include_human_classify_check_hashtag.configure(state='disabled')
        else:
            if include_human_classify_check_user:
                include_human_classify_check_user.configure(state='disabled')

def on_search_type_change(search_type_var, include_images_check_hashtag, include_videos_check_hashtag, 
                         include_human_classify_check_hashtag, include_images_var_hashtag, include_human_classify_var_hashtag,
                         include_images_check_user, include_reels_check_user, include_human_classify_check_user,
                         include_images_var_user, include_human_classify_var_user, hashtag_frame, user_id_frame,
                         append_status_func, upscale_checkbox_hashtag=None, upscale_checkbox_user=None, *args):
    """
    검색 유형이 변경될 때 호출됩니다.
    """
    stype = search_type_var.get()
    
    if stype == "hashtag":
        # 해시태그 선택시: 해시태그 체크박스들 활성화, 사용자 ID 체크박스들 비활성화
        include_images_check_hashtag.configure(state='normal')
        include_videos_check_hashtag.configure(state='normal')
        include_human_classify_check_hashtag.configure(state='normal')
        
        # 사용자 ID 체크박스들 비활성화 (값은 유지)
        include_images_check_user.configure(state='disabled')
        include_reels_check_user.configure(state='disabled')
        include_human_classify_check_user.configure(state='disabled')
        
        # 해시태그 이미지 체크 상태에 따른 인물 분류 활성화
        if include_images_var_hashtag.get():
            include_human_classify_check_hashtag.configure(state='normal')
        else:
            include_human_classify_check_hashtag.configure(state='disabled')
        
        # 해시태그 인물 분류 체크 상태에 따른 업스케일링 활성화
        if upscale_checkbox_hashtag:
            if include_human_classify_var_hashtag.get():
                upscale_checkbox_hashtag.configure(state='normal')
            else:
                upscale_checkbox_hashtag.configure(state='disabled')
        
        # 사용자 ID 업스케일링 체크박스 비활성화
        if upscale_checkbox_user:
            upscale_checkbox_user.configure(state='disabled')
            
    else:  # user
        # 사용자 ID 선택시: 사용자 ID 체크박스들 활성화, 해시태그 체크박스들 비활성화
        include_images_check_user.configure(state='normal')
        include_reels_check_user.configure(state='normal')
        include_human_classify_check_user.configure(state='normal')
        
        # 해시태그 체크박스들 비활성화 (값은 유지)
        include_images_check_hashtag.configure(state='disabled')
        include_videos_check_hashtag.configure(state='disabled')
        include_human_classify_check_hashtag.configure(state='disabled')
        
        # 사용자 ID 이미지 체크 상태에 따른 인물 분류 활성화
        if include_images_var_user.get():
            include_human_classify_check_user.configure(state='normal')
        else:
            include_human_classify_check_user.configure(state='disabled')
        
        # 사용자 ID 인물 분류 체크 상태에 따른 업스케일링 활성화
        if upscale_checkbox_user:
            if include_human_classify_var_user.get():
                upscale_checkbox_user.configure(state='normal')
            else:
                upscale_checkbox_user.configure(state='disabled')
        
        # 해시태그 업스케일링 체크박스 비활성화
        if upscale_checkbox_hashtag:
            upscale_checkbox_hashtag.configure(state='disabled')

def open_download_directory(download_directory_var, append_status_func):
    """
    다운로드 디렉토리를 엽니다.
    """
    d = download_directory_var.get()
    if not os.path.isdir(d):
        # 디렉토리가 없으면 생성
        os.makedirs(d, exist_ok=True)
        append_status_func(f"다운로드 경로 생성됨: {d}")
    if os.name == 'nt':
        os.startfile(d)
    else:
        import subprocess
        subprocess.Popen(["open", d])

def select_download_directory_main(download_directory_var, last_download_path, loaded_accounts, 
                                 load_existing_directories_func, append_status_func):
    """
    메인 다운로드 디렉토리를 선택합니다.
    """
    d = filedialog.askdirectory(initialdir=last_download_path)
    if d:
        download_directory_var.set(d)
        load_existing_directories_func()
        for acc in loaded_accounts:
            acc['DOWNLOAD_PATH'] = d
        # 마지막 다운로드 경로 업데이트
        config = load_config()
        config['LAST_DOWNLOAD_PATH'] = d
        save_config(config)
        append_status_func("다운로드 경로 변경됨.")
        print("다운로드 경로 업데이트됨.")

def select_download_directory_add(download_directory_var_add, last_download_path):
    """
    계정 추가 시 다운로드 디렉토리를 선택합니다.
    """
    directory = filedialog.askdirectory(initialdir=last_download_path)
    if directory:
        download_directory_var_add.set(directory)

def process_queue(q, append_status_func, word_text=None, config_update_pending=None):
    """
    진행 상황 큐를 처리합니다.
    """
    try:
        while True:
            msg = q.get_nowait()
            if msg[0] == "term_start":
                append_status_func(f"시작: {msg[1]} (계정: {msg[2]})")
            elif msg[0] == "term_progress":
                append_status_func(f"진행: {msg[1]} - {msg[2]} (계정: {msg[3]})")

            elif msg[0] == "term_complete":
                append_status_func(f"완료: {msg[1]} (계정: {msg[2]})")
                # 다운로드 완료 후 검색목록에서 해당 항목 삭제
                if word_text:
                    try:
                        current_text = word_text.get("1.0", tk.END).strip()
                        if current_text:
                            lines = current_text.split('\n')
                            # 완료된 검색어를 제거
                            filtered_lines = [line.strip() for line in lines if line.strip() and line.strip() != msg[1]]
                            # 새로운 텍스트로 업데이트
                            word_text.delete("1.0", tk.END)
                            if filtered_lines:
                                word_text.insert("1.0", '\n'.join(filtered_lines))
                            
                            append_status_func(f"검색목록에서 '{msg[1]}' 제거됨")
                            
                            # 설정 파일 업데이트 요청 추가 (배치 처리용)
                            if config_update_pending is not None:
                                config_update_pending.add(msg[1])
                    except Exception as e:
                        append_status_func(f"검색목록 업데이트 오류: {e}")
            elif msg[0] == "term_classify_complete":
                append_status_func(f"완료: {msg[1]} - {msg[2]} (계정: {msg[3]})")
                # 분류 완료 후 검색목록에서 해당 항목 삭제
                if word_text:
                    try:
                        current_text = word_text.get("1.0", tk.END).strip()
                        if current_text:
                            lines = current_text.split('\n')
                            # 완료된 검색어를 제거
                            filtered_lines = [line.strip() for line in lines if line.strip() and line.strip() != msg[1]]
                            # 새로운 텍스트로 업데이트
                            word_text.delete("1.0", tk.END)
                            if filtered_lines:
                                word_text.insert("1.0", '\n'.join(filtered_lines))
                            
                            append_status_func(f"검색목록에서 '{msg[1]}' 제거됨 (분류 완료)")
                            
                            # 설정 파일 업데이트 요청 추가 (배치 처리용)
                            if config_update_pending is not None:
                                config_update_pending.add(msg[1])
                    except Exception as e:
                        append_status_func(f"검색목록 업데이트 오류: {e}")
            elif msg[0] == "term_error":
                # 프로필이 존재하지 않는 경우 유사한 프로필 정보도 표시
                if "does not exist" in msg[2]:
                    append_status_func(f"프로필이 존재하지 않음: {msg[1]}")
                    if "The most similar profiles are:" in msg[2]:
                        # 유사한 프로필 정보 추출
                        similar_profiles = msg[2].split("The most similar profiles are:")[1].strip()
                        append_status_func(f"유사한 프로필: {similar_profiles}")
                    
                    # 존재하지 않는 프로필을 검색목록에서도 제거
                    if word_text:
                        try:
                            current_text = word_text.get("1.0", tk.END).strip()
                            if current_text:
                                lines = current_text.split('\n')
                                # 존재하지 않는 프로필을 제거
                                filtered_lines = [line.strip() for line in lines if line.strip() and line.strip() != msg[1]]
                                # 새로운 텍스트로 업데이트
                                word_text.delete("1.0", tk.END)
                                if filtered_lines:
                                    word_text.insert("1.0", '\n'.join(filtered_lines))
                                
                                append_status_func(f"검색목록에서 존재하지 않는 프로필 '{msg[1]}' 제거됨")
                                
                                # 설정 파일 업데이트 요청 추가 (배치 처리용)
                                if config_update_pending is not None:
                                    config_update_pending.add(msg[1])
                        except Exception as e:
                            append_status_func(f"검색목록 업데이트 오류: {e}")
                else:
                    append_status_func(f"오류: {msg[1]} - {msg[2]} (계정: {msg[3]})")
            elif msg[0] == "account_switch":
                append_status_func(f"계정 전환: {msg[1]}")
            elif msg[0] == "account_relogin":
                append_status_func(f"재로그인 시도: {msg[1]}")
    except:
        pass
