import os
import instaloader
from instaloader import Profile, LatestStamps, RateController, exceptions
from queue import Empty
from itertools import islice
import threading
import time
import textwrap
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union
import inspect
import shutil  # 동영상 파일 이동을 위해 추가

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')
os.makedirs(SESSION_DIR, exist_ok=True)

# 사용자별로 분리된 latest-stamps 파일 경로 설정
STAMPS_FILE_IMAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"latest-stamps-images.ini")
STAMPS_FILE_REELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"latest-stamps-reels.ini")

def instaloader_login(username, password, download_path, include_videos=False, include_reels=False):
    L = instaloader.Instaloader(
        download_videos=include_videos or include_reels,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern='',
        dirname_pattern=download_path,
        rate_controller=lambda context: RateController(context)  
    )
    
    try:
        session_file = os.path.join(SESSION_DIR, f"{username}.session")
        if os.path.isfile(session_file):
            L.load_session_from_file(username, filename=session_file)
            print(f"세션 로드 성공: {username}")
        else:
            L.login(username, password)
            print(f"Instaloader 로그인 성공: {username}")
            L.save_session_to_file(filename=session_file)
    except instaloader.exceptions.BadCredentialsException:
        print(f"잘못된 아이디 또는 비밀번호입니다: {username}")
        return None
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        print(f"이중 인증이 필요합니다: {username}")
        return None
    except Exception as e:
        print(f"로그인 중 에러 발생 ({username}): {e}")
        return None

    return L

def download_posts(L, username, search_term, search_type, target, include_images, include_videos, include_reels, progress_queue, stop_event, resume_from=0):
    print(f"게시물 다운로드 시작: {search_term} (검색 유형: {search_type})")
    count = 0
    progress_queue.put(("term_start", search_term, username))

    try:
        if search_type == 'hashtag':
            hashtag = instaloader.Hashtag.from_name(L.context, search_term)
            total_posts = hashtag.mediacount
            posts = hashtag.get_all_posts()
        else:
            print("지원되지 않는 검색 유형입니다.")
            progress_queue.put(("term_error", search_term, "지원되지 않는 검색 유형", username))
            return

        if target != 0 and target < total_posts:
            total_posts = target

        if resume_from > 0 or target != 0:
            start = resume_from
            stop = None if target == 0 else resume_from + target
            posts = islice(posts, start, stop)

        for post in posts:
            if stop_event.is_set():
                print("중지 신호 감지. 다운로드 중단.")
                progress_queue.put(("term_error", search_term, "사용자에 의해 중지됨", username))
                return

            target_folder = os.path.join(L.dirname_pattern, 'hashtag' if search_type == 'hashtag' else 'ID', search_term, 'Reels' if include_reels else 'Image')
            os.makedirs(target_folder, exist_ok=True)
            original_dirname_pattern = L.dirname_pattern
            L.dirname_pattern = target_folder

            try:
                L.download_post(post, target=search_term)
            except Exception as e:
                print(f"게시물 다운로드 중 에러 발생: {e}")
                progress_queue.put(("term_error", search_term, f"게시물 다운로드 중 에러 발생: {e}", username))
                L.dirname_pattern = original_dirname_pattern
                continue

            L.dirname_pattern = original_dirname_pattern
            count += 1
            progress_queue.put(("term_progress", search_term, count, username))

        print(f"{search_term} 다운로드 완료: {count}개 게시물 수집.")
        progress_queue.put(("term_complete", search_term, username))
        return

    except instaloader.exceptions.LoginRequiredException as e:
        print(f"{search_term} 다운로드 중 로그인 필요 에러 발생: {e}")
        progress_queue.put(("term_error", search_term, "로그인 필요", username))
    except instaloader.exceptions.ConnectionException as e:
        print(f"{search_term} 다운로드 중 연결 에러 발생: {e}")
        progress_queue.put(("term_error", search_term, f"연결 에러: {e}", username))
    except Exception as e:
        print(f"{search_term} 다운로드 중 에러 발생: {e}")
        progress_queue.put(("account_switch_needed", username))

def user_download_with_profiles(L, search_user, target, include_images, include_reels, progress_queue, stop_event, allow_duplicate, base_path):
    def download_content():
        nonlocal search_user, allow_duplicate, base_path
        try:
            def my_post_filter(post):
                try:
                    if include_images and include_reels:
                        return True
                    if include_images and not include_reels:
                        return not post.is_video
                    if include_reels and not include_images:
                        return post.is_video
                    return False
                except Exception as e:
                    print(f"Error in post_filter: {e}")
                    return False

            L_content = L
            content_folder = os.path.join(base_path, 'ID', search_user, 'Image')
            L_content.dirname_pattern = content_folder
            os.makedirs(content_folder, exist_ok=True)

            list_of_users = [search_user]
            profiles = [instaloader.Profile.from_username(L_content.context, user) for user in list_of_users]
            profile_usernames = {profile.username.lower() for profile in profiles}

            profile = Profile.from_username(L_content.context, search_user)
                
            if allow_duplicate:
                latest_stamps_images = None
            else:
                latest_stamps_images = LatestStamps(STAMPS_FILE_IMAGES)
                latest_stamps_reels = LatestStamps(STAMPS_FILE_REELS)
                
            image_kwargs = {
                'profiles': {profile},
                'profile_pic': False,
                'posts': include_images or include_reels,
                'tagged': False,
                'igtv': False,
                'highlights': False,
                'stories': False,
                'fast_update': False,
                'post_filter': my_post_filter,
                'raise_errors': True,
                'latest_stamps': latest_stamps_images,
                'max_count': target if target != 0 else None,
            }
            
            L_content.download_profiles(**image_kwargs)

            progress_queue.put(("term_progress", search_user, "콘텐츠 다운로드 완료", L.context.username))

            if include_reels:
                reels_folder = os.path.join(base_path, 'ID', search_user, 'Reels')
                os.makedirs(reels_folder, exist_ok=True)

                video_files = []
                for root_dir, dirs, files in os.walk(content_folder):
                    for file in files:
                        if file.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                            video_files.append(file)
                            source_path = os.path.join(root_dir, file)
                            destination_path = os.path.join(reels_folder, file)
                            try:
                                shutil.move(source_path, destination_path)
                                print(f"동영상 파일 이동: {file} -> Reels 폴더")
                            except Exception as e:
                                print(f"동영상 파일 이동 중 에러 발생: {e}")
                                progress_queue.put(("term_error", search_user, f"동영상 파일 이동 중 에러 발생: {e}", L.context.username))

                if video_files:
                    # 동영상 파일이 실제로 존재하여 이동을 수행한 경우에만 업데이트
                    progress_queue.put(("term_progress", search_user, "동영상 파일 이동 완료", L.context.username))
                # else: 아무것도 하지 않음 (print 및 progress_queue 업데이트 생략)

        except Exception as e:
            progress_queue.put(("term_error", search_user, f"콘텐츠 다운로드 중 에러 발생: {e}", L.context.username))
                
    download_content()

def crawl_and_download(
    search_terms, target, accounts, search_type, include_images, include_videos, include_reels,
    progress_queue, on_complete, stop_event, download_path='download', append_status=None,
    root=None, download_directory_var=None,
    include_human_classify_var_hashtag=None, include_human_classify_var_user=None,
    allow_duplicate=False
):
    print("크롤링 및 다운로드 시작...")

    base_download_path = os.path.join(os.getcwd(), download_path)
    os.makedirs(base_download_path, exist_ok=True)

    loaded_loaders = []
    if not accounts:
        loader = instaloader.Instaloader(
            download_videos=include_videos,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern='',
            dirname_pattern=base_download_path,
            rate_controller=lambda context: RateController(context)  
        )
        loaded_loaders.append({
            'loader': loader,
            'username': 'anonymous',
            'password': None,
            'active': True
        })
    else:
        for account in accounts:
            loader = instaloader_login(
                account['INSTAGRAM_USERNAME'], 
                account['INSTAGRAM_PASSWORD'], 
                base_download_path,
                include_videos,
                include_reels
            )
            if loader:
                loaded_loaders.append({
                    'loader': loader,
                    'username': account['INSTAGRAM_USERNAME'],
                    'password': account['INSTAGRAM_PASSWORD'],
                    'active': True
                })
            else:
                print(f"로그인 실패: {account['INSTAGRAM_USERNAME']}")

    if search_type == "hashtag":
        include_human_classify = include_human_classify_var_hashtag.get() if include_human_classify_var_hashtag else False
    else:
        include_human_classify = include_human_classify_var_user.get() if include_human_classify_var_user else False

    account_index = 0
    total_accounts = len(loaded_loaders)

    from crawling.classifier import classify_images

    while account_index < total_accounts:
        loader_dict = loaded_loaders[account_index]
        L = loader_dict['loader']
        current_username = loader_dict['username']

        try:
            for term in search_terms:
                if stop_event.is_set():
                    append_status("중지: 다운로드 중지 신호 감지.")
                    break

                append_status(f"정보: '{term}' 다운로드 시작 (계정: {current_username})")
                if search_type == 'hashtag':
                    download_posts(L, current_username, term, search_type, target, include_images, include_videos, include_reels, progress_queue, stop_event)
                else:
                    try:
                        user_download_with_profiles(L, term, target, include_images, include_reels, progress_queue, stop_event, allow_duplicate, base_download_path)
                    except Exception as e:
                        print(e)
                if stop_event.is_set():
                    append_status("중지: 다운로드 중지됨.")
                    break

                append_status(f"완료: '{term}' 다운로드 완료 (계정: {current_username})")

                # 인물 분류 수행 전에 파일 존재 여부 확인
                if include_human_classify and not stop_event.is_set():
                    if search_type == 'hashtag':
                        classify_dir = os.path.join(base_download_path, 'hashtag', term, 'Image')
                    else:
                        classify_dir = os.path.join(base_download_path, 'ID', term, 'Image')
                    
                    # 이미지 파일 존재 여부 확인
                    has_images = False
                    if os.path.isdir(classify_dir):
                        for fname in os.listdir(classify_dir):
                            if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                                has_images = True
                                break

                    if has_images:
                        classify_images(root, append_status, download_directory_var, term, current_username, search_type, stop_event)
                        # classify_images 함수 내부에서 필요한 로그 및 progress_queue 업데이트를 수행
                    # else: 아무것도 하지 않음 (print 및 progress_queue 업데이트 생략)

                if stop_event.is_set():
                    append_status("중지: 분류 중지됨.")
                    break

            # 모든 검색어 처리 완료 (현재 계정)
            break

        except Exception as e:
            print(f"계정 에러 발생: {e}")
            append_status(f"오류: 계정 '{current_username}' 처리 중 에러 발생. 재로그인 시도.")
            progress_queue.put(("account_relogin", loaded_loaders[account_index]['username'], "계정 재로그인 시도 중..."))
            new_loader = instaloader_login(
                loader_dict['username'],
                loader_dict['password'],
                base_download_path,
                include_videos,
                include_reels
            )
            if new_loader:
                loaded_loaders[account_index]['loader'] = new_loader
                L = new_loader
                print(f"계정 재로그인 성공: {loaded_loaders[account_index]['username']}")
                continue
            else:
                print(f"계정 재로그인 실패: {loaded_loaders[account_index]['username']}")
                account_index += 1
                if account_index < total_accounts:
                    print(f"계정을 전환합니다: {loaded_loaders[account_index]['username']}")
                    progress_queue.put(("account_switch", loaded_loaders[account_index]['username'], "계정 전환 중..."))
                    continue
                else:
                    for term in search_terms:
                        progress_queue.put(("term_error", term, "모든 계정이 차단되었습니다.", loader_dict['username']))
                    break

    on_complete("크롤링이 완료되었습니다.")
