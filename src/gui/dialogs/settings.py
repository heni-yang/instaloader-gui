# crawling/gui_operations.py
"""
GUI의 주요 작업 함수들을 모아놓은 모듈
기존 gui.py의 UI는 그대로 두고 내부 로직만 분리
"""
import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import configparser
from crawling.config import load_config, save_config

def delete_selected_items(hashtag_listbox, user_id_listbox, download_directory_var, append_status_func):
    """
    선택된 해시태그와 사용자 ID와 관련된 모든 디렉토리를 삭제합니다.
    """
    # 해시태그 선택 확인
    hashtag_indices = hashtag_listbox.curselection()
    user_id_indices = user_id_listbox.curselection()
    
    if not hashtag_indices and not user_id_indices:
        append_status_func("오류: 삭제할 대상을 선택하세요.")
        return
    
    selected_hashtags = [hashtag_listbox.get(i) for i in hashtag_indices]
    selected_user_ids = [user_id_listbox.get(i) for i in user_id_indices]
    
    # 확인 대화상자 메시지 구성
    confirm_parts = []
    if selected_hashtags:
        confirm_parts.append(f"해시태그:\n" + "\n".join(selected_hashtags))
    if selected_user_ids:
        confirm_parts.append(f"사용자 ID:\n" + "\n".join(selected_user_ids))
    
    confirm_message = f"선택된 대상과 관련된 모든 디렉토리를 삭제하시겠습니까?\n\n" + "\n\n".join(confirm_parts)
    result = messagebox.askyesno("삭제 확인", confirm_message)
    
    if not result:
        append_status_func("삭제가 취소되었습니다.")
        return
    
    main_download_dir = download_directory_var.get()
    deleted_count = 0
    
    # 해시태그 삭제
    if selected_hashtags:
        sorted_hashtag_indices = sorted(hashtag_indices, reverse=True)
        for hashtag in selected_hashtags:
            try:
                # 해시태그 관련 디렉토리들 삭제
                dirs_to_delete = [
                    os.path.join(main_download_dir, "unclassified", "hashtag", hashtag),
                    os.path.join(main_download_dir, "Reels", "hashtag", hashtag),
                    os.path.join(main_download_dir, "인물", f"hashtag_{hashtag}"),
                    os.path.join(main_download_dir, "비인물", f"hashtag_{hashtag}")
                ]
                
                for dir_path in dirs_to_delete:
                    if os.path.exists(dir_path):
                        shutil.rmtree(dir_path)
                        append_status_func(f"삭제됨: {dir_path}")
                        deleted_count += 1
                
            except Exception as e:
                append_status_func(f"오류: {hashtag} 삭제 중 오류 발생 - {e}")
        
        # 해시태그 리스트박스에서 선택된 항목들 제거 (역순으로)
        for index in sorted_hashtag_indices:
            hashtag_listbox.delete(index)
    
    # 사용자 ID 삭제
    if selected_user_ids:
        sorted_user_id_indices = sorted(user_id_indices, reverse=True)
        for user_id in selected_user_ids:
            try:
                # 사용자 ID 관련 디렉토리들 삭제
                dirs_to_delete = [
                    os.path.join(main_download_dir, "unclassified", "ID", user_id),
                    os.path.join(main_download_dir, "Reels", "ID", user_id),
                    os.path.join(main_download_dir, "인물", f"user_{user_id}"),
                    os.path.join(main_download_dir, "비인물", f"user_{user_id}")
                ]
                
                for dir_path in dirs_to_delete:
                    if os.path.exists(dir_path):
                        shutil.rmtree(dir_path)
                        append_status_func(f"삭제됨: {dir_path}")
                        deleted_count += 1
                
            except Exception as e:
                append_status_func(f"오류: {user_id} 삭제 중 오류 발생 - {e}")
        
        # 사용자 ID 리스트박스에서 선택된 항목들 제거 (역순으로)
        for index in sorted_user_id_indices:
            user_id_listbox.delete(index)
    
    append_status_func(f"삭제 완료: {deleted_count}개의 디렉토리가 삭제되었습니다.")

def load_existing_directories(hashtag_listbox, user_id_listbox, download_directory_var, append_status_func):
    """
    다운로드 경로에 있는 기존 디렉토리들을 불러옵니다.
    """
    main_download_dir = download_directory_var.get()
    if not os.path.isdir(main_download_dir):
        append_status_func(f"오류: 다운로드 경로가 존재하지 않습니다: {main_download_dir}")
        return
    
    # '인물' 폴더는 해시태그와 사용자 디렉토리 모두 포함하는 상위 폴더입니다.
    people_dir = os.path.join(main_download_dir, '인물')
    os.makedirs(people_dir, exist_ok=True)
    
    # 해시태그 목록 새로고침: 'hashtag_'로 시작하는 디렉토리들만 추가
    hashtag_listbox.delete(0, tk.END)
    for d in os.listdir(people_dir):
        full_path = os.path.join(people_dir, d)
        if os.path.isdir(full_path) and d.startswith("hashtag_"):
            # 접두어 'hashtag_' 제거 후 남은 부분을 목록에 추가
            hashtag_listbox.insert(tk.END, d[len("hashtag_"):])
    
    # 사용자 ID 목록 새로고침: 'user_'로 시작하는 디렉토리들만 추가
    user_id_listbox.delete(0, tk.END)
    user_ids_cached = []
    for d in os.listdir(people_dir):
        full_path = os.path.join(people_dir, d)
        if os.path.isdir(full_path) and d.startswith("user_"):
            actual_uid = d[len("user_"):]
            try:
                ct = os.path.getctime(full_path)
                mt = os.path.getmtime(full_path)
                user_ids_cached.append((actual_uid, ct, mt))
            except Exception as e:
                append_status_func(f"경고: {d} 생성/수정일 오류: {e}")
    
    for uid, _, _ in sorted(user_ids_cached, key=lambda x: x[1], reverse=True):
        user_id_listbox.insert(tk.END, uid)

def sort_user_ids_by_creation_desc(user_id_listbox, append_status_func):
    """
    사용자 ID를 생성 시간 내림차순으로 정렬합니다.
    """
    ini_path = os.path.join(os.path.dirname(__file__), 'latest-stamps-images.ini')
    if not os.path.isfile(ini_path):
        append_status_func("오류: latest-stamps-images.ini 없음.")
        return
    
    parser = configparser.ConfigParser()
    parser.read(ini_path, encoding='utf-8')
    
    # 사용자 ID와 생성 시간을 추출
    user_times = []
    for section in parser.sections():
        if parser[section].get('post-timestamp'):
            try:
                timestamp = parser[section]['post-timestamp'].strip()
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                user_times.append((section, dt))
            except:
                continue
    
    # 생성 시간 내림차순으로 정렬
    user_times.sort(key=lambda x: x[1], reverse=True)
    
    # 정렬된 사용자 ID를 리스트박스에 반영
    user_id_listbox.delete(0, tk.END)
    for user, _ in user_times:
        user_id_listbox.insert(tk.END, user)
    
    append_status_func("사용자 ID가 생성일 내림차순 정렬됨.")

def sort_user_ids_by_creation_asc(user_id_listbox, append_status_func):
    """
    사용자 ID를 생성 시간 오름차순으로 정렬합니다.
    """
    ini_path = os.path.join(os.path.dirname(__file__), 'latest-stamps-images.ini')
    if not os.path.isfile(ini_path):
        append_status_func("오류: latest-stamps-images.ini 없음.")
        return
    
    parser = configparser.ConfigParser()
    parser.read(ini_path, encoding='utf-8')
    
    # 사용자 ID와 생성 시간을 추출
    user_times = []
    for section in parser.sections():
        if parser[section].get('post-timestamp'):
            try:
                timestamp = parser[section]['post-timestamp'].strip()
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                user_times.append((section, dt))
            except:
                continue
    
    # 생성 시간 오름차순으로 정렬
    user_times.sort(key=lambda x: x[1])
    
    # 정렬된 사용자 ID를 리스트박스에 반영
    user_id_listbox.delete(0, tk.END)
    for user, _ in user_times:
        user_id_listbox.insert(tk.END, user)
    
    append_status_func("사용자 ID가 생성일 오름차순 정렬됨.")

def sort_user_ids_by_modified_asc(user_id_listbox, append_status_func):
    """
    사용자 ID를 수정 시간 오름차순으로 정렬합니다.
    """
    ini_path = os.path.join(os.path.dirname(__file__), 'latest-stamps-images.ini')
    if not os.path.isfile(ini_path):
        append_status_func("오류: latest-stamps-images.ini 없음.")
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
    
    # 수정 시간 오름차순으로 정렬
    sorted_users = sorted(ini_ts.items(), key=lambda x: x[1])
    
    # 정렬된 사용자 ID를 리스트박스에 반영
    user_id_listbox.delete(0, tk.END)
    for user, _ in sorted_users:
        user_id_listbox.insert(tk.END, user)
    
    append_status_func("INI 기준 오름차순 정렬 완료.")
