# crawling/downloader.py
import os
import instaloader
from instaloader import Profile, LatestStamps, RateController, exceptions
from itertools import islice
import time
import shutil
import random
from datetime import datetime
from crawling.utils import create_dir_if_not_exists, logging

# 세션 파일 저장 디렉토리 설정
SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')
create_dir_if_not_exists(SESSION_DIR)

# 최신 스탬프 파일 경로
STAMPS_FILE_IMAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest-stamps-images.ini")
STAMPS_FILE_REELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest-stamps-reels.ini")

def instaloader_login(username, password, download_path, include_videos=False, include_reels=False):
    """
    Instaloader를 사용해 인스타그램에 로그인합니다.
    
    매개변수:
        username (str): 사용자 이름.
        password (str): 비밀번호.
        download_path (str): 다운로드 경로.
        include_videos (bool): 영상 다운로드 여부.
        include_reels (bool): 릴스 다운로드 여부.
        
    반환:
        Instaloader 객체 또는 None.
    """
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
    session_file = os.path.join(SESSION_DIR, f"{username}.session")
    try:
        if os.path.isfile(session_file):
            L.load_session_from_file(username, filename=session_file)
            print(f"세션 로드 성공: {username}")
        else:
            L.login(username, password)
            print(f"로그인 성공: {username}")
            L.save_session_to_file(filename=session_file)
    except instaloader.exceptions.BadCredentialsException:
        print(f"잘못된 아이디/비밀번호: {username}")
        return None
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        print(f"이중 인증 필요: {username}")
        return None
    except Exception as e:
        print(f"{username} 로그인 오류: {e}")
        return None

    return L

def download_posts(L, username, search_term, search_type, target, include_images, include_videos, include_reels, progress_queue, stop_event, resume_from=0):
    """
    해시태그 또는 사용자 ID를 기반으로 인스타그램 게시물을 다운로드합니다.
    
    매개변수:
        L (Instaloader): 로그인된 Instaloader 객체.
        username (str): 사용자 이름.
        search_term (str): 검색어.
        search_type (str): 'hashtag' 또는 'user'.
        target (int): 다운로드할 게시물 수 (0이면 전체).
        include_images (bool): 이미지 다운로드 여부.
        include_videos (bool): 영상 다운로드 여부.
        include_reels (bool): 릴스 다운로드 여부.
        progress_queue: 진행 상황 큐.
        stop_event: 중지 이벤트.
        resume_from (int): 재시작 인덱스.
    """
    print(f"{search_term} 다운로드 시작 (검색 유형: {search_type})")
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
            posts = islice(posts, resume_from, None if target == 0 else resume_from + target)

        for post in posts:
            if stop_event.is_set():
                print("중지 신호 감지. 다운로드 중지됨.")
                progress_queue.put(("term_error", search_term, "사용자 중지", username))
                return

            target_folder = os.path.join(
                L.dirname_pattern,
                'hashtag' if search_type == 'hashtag' else 'ID',
                search_term,
                'Reels' if include_reels else 'Image'
            )
            create_dir_if_not_exists(target_folder)
            original_dirname = L.dirname_pattern
            L.dirname_pattern = target_folder

            try:
                L.download_post(post, target=search_term)
            except Exception as e:
                print(f"게시물 다운로드 오류: {e}")
                progress_queue.put(("term_error", search_term, f"게시물 다운로드 오류: {e}", username))
                L.dirname_pattern = original_dirname
                continue

            L.dirname_pattern = original_dirname
            count += 1
            progress_queue.put(("term_progress", search_term, count, username))

        print(f"{search_term} 다운로드 완료: {count}개 게시물")
        progress_queue.put(("term_complete", search_term, username))
    except instaloader.exceptions.LoginRequiredException as e:
        print(f"로그인 필요 오류: {e}")
        progress_queue.put(("term_error", search_term, "로그인 필요", username))
    except instaloader.exceptions.ConnectionException as e:
        print(f"연결 오류: {e}")
        progress_queue.put(("term_error", search_term, f"연결 오류: {e}", username))
    except Exception as e:
        print(f"다운로드 오류: {e}")
        progress_queue.put(("account_switch_needed", username))

def rename_directories(base_path, search_type, old_name, new_name):
    """
    기본 경로 내에서 여러 카테고리의 디렉토리 이름을 변경합니다.
    
    매개변수:
        base_path (str): 기본 다운로드 경로.
        search_type (str): 검색 유형 접두사.
        old_name (str): 기존 이름.
        new_name (str): 새 이름.
    """
    folders = [
        (os.path.join(base_path, "unclassified", "ID"), ""),
        (os.path.join(base_path, "Reels", "ID"), ""),
        (os.path.join(base_path, "인물"), f"{search_type}_"),
        (os.path.join(base_path, "비인물"), f"{search_type}_")
    ]
    for folder, prefix in folders:
        old_dir = os.path.join(folder, f"{prefix}{old_name}")
        new_dir = os.path.join(folder, f"{prefix}{new_name}")
        if os.path.exists(old_dir) and not os.path.exists(new_dir):
            os.rename(old_dir, new_dir)
            print(f"디렉토리 이름 변경: {old_dir} -> {new_dir}")
        else:
            print(f"디렉토리 없음 또는 이미 존재: {old_dir}")

def user_download_with_profiles(L, search_user, target, include_images, include_reels, progress_queue, stop_event, allow_duplicate, base_path, search_type):
    """
    특정 사용자의 프로필 및 게시물을 다운로드합니다.
    
    매개변수:
        L (Instaloader): 로그인된 Instaloader 객체.
        search_user (str): 대상 사용자.
        target (int): 다운로드할 게시물 수 (0이면 전체).
        include_images (bool): 이미지 다운로드 여부.
        include_reels (bool): 릴스 다운로드 여부.
        progress_queue: 진행 상황 큐.
        stop_event: 중지 이벤트.
        allow_duplicate (bool): 중복 다운로드 허용 여부.
        base_path (str): 기본 다운로드 경로.
        search_type (str): 검색 유형.
    """
    def download_content():
        nonlocal search_user, base_path
        try:
            def my_post_filter(post):
                if include_images and include_reels:
                    return True
                if include_images and not include_reels:
                    return not post.is_video
                if include_reels and not include_images:
                    return post.is_video
                return False

            L_content = L
            latest_stamps_images = LatestStamps(STAMPS_FILE_IMAGES)

            old_username = search_user
            stored_id = latest_stamps_images.get_profile_id(old_username)
            if stored_id:
                try:
                    temp_profile = Profile.from_id(L_content.context, stored_id)
                    if temp_profile.username != old_username:
                        latest_stamps_images.rename_profile(old_username, temp_profile.username)
                        print(f"사용자명 변경: {old_username} -> {temp_profile.username}")
                        rename_directories(base_path, search_type, old_username, temp_profile.username)
                        search_user = temp_profile.username
                        profile = temp_profile
                    else:
                        profile = Profile.from_id(L_content.context, stored_id)
                except Exception as e:
                    print(f"저장된 ID로 프로필 조회 실패: {e}")
                    profile = Profile.from_username(L_content.context, old_username)
            else:
                profile = Profile.from_username(L_content.context, search_user)

            content_folder = os.path.join(base_path, "unclassified", "ID", profile.username, "Image")
            L_content.dirname_pattern = content_folder
            create_dir_if_not_exists(content_folder)

            if latest_stamps_images.get_profile_id(profile.username) is None:
                latest_stamps_images.save_profile_id(profile.username, profile.userid)
                print(f"프로필 ID 저장: {profile.username} (ID: {profile.userid})")

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
            progress_queue.put(("term_progress", profile.username, "콘텐츠 다운로드 완료", L.context.username))

            if include_reels:
                reels_folder = os.path.join(base_path, 'Reels', 'ID', profile.username)
                create_dir_if_not_exists(reels_folder)
                video_files = []
                for root, dirs, files in os.walk(content_folder):
                    for file in files:
                        if file.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                            video_files.append(file)
                            source_path = os.path.join(root, file)
                            destination_path = os.path.join(reels_folder, file)
                            try:
                                shutil.move(source_path, destination_path)
                                print(f"동영상 이동: {file} -> Reels 폴더")
                            except Exception as e:
                                print(f"동영상 이동 오류: {e}")
                                progress_queue.put(("term_error", profile.username, f"동영상 이동 오류: {e}", L.context.username))
                if video_files:
                    progress_queue.put(("term_progress", profile.username, "동영상 이동 완료", L.context.username))
        except Exception as e:
            print(f"{search_user} 다운로드 오류: {e}")
            progress_queue.put(("term_error", search_user, f"콘텐츠 다운로드 오류: {e}", L.context.username))
    download_content()

def crawl_and_download(search_terms, target, accounts, search_type, include_images, include_videos, include_reels,
                       include_human_classify, progress_queue, on_complete, stop_event, download_path='download', append_status=None,
                       root=None, download_directory_var=None, allow_duplicate=False):
    """
    인스타그램 게시물을 크롤링 및 다운로드하는 메인 함수.
    
    매개변수:
        search_terms (list): 검색할 해시태그 또는 사용자 ID 목록.
        target (int): 각 검색어당 다운로드할 게시물 수 (0이면 전체).
        accounts (list): 로그인 정보가 담긴 계정 리스트.
        search_type (str): 'hashtag' 또는 'user'.
        include_images (bool): 이미지 다운로드 여부.
        include_videos (bool): 영상 다운로드 여부.
        include_reels (bool): 릴스 다운로드 여부.
        include_human_classify (bool): 다운로드 후 인물 분류 여부.
        progress_queue: 진행 상황 전달 큐.
        on_complete (callable): 크롤링 완료 후 호출 함수.
        stop_event: 중지 이벤트.
        download_path (str): 기본 다운로드 경로.
        append_status (callable): 상태 메시지 기록 함수.
        root: GUI용 Tkinter 루트 창.
        download_directory_var: 다운로드 경로 변수.
        allow_duplicate (bool): 중복 다운로드 허용 여부.
    """
    print("크롤링 및 다운로드 시작...")
    base_download_path = os.path.join(os.getcwd(), download_path)
    # 기본 다운로드 경로가 없으면 생성
    create_dir_if_not_exists(base_download_path)
    for sub in ["unclassified", "Reels", "인물", "비인물"]:
        create_dir_if_not_exists(os.path.join(base_download_path, sub))
    
    loaded_loaders = []
    if not accounts:
        loader = instaloader.Instaloader(
            download_videos=include_videos,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern='',
            dirname_pattern=base_download_path + "/unclassified",
            rate_controller=lambda context: RateController(context)
        )
        loaded_loaders.append({'loader': loader, 'username': 'anonymous', 'password': None, 'active': True})
    else:
        for account in accounts:
            loader = instaloader_login(
                account['INSTAGRAM_USERNAME'],
                account['INSTAGRAM_PASSWORD'],
                base_download_path + "/unclassified",
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
    
    account_index = 0
    total_accounts = len(loaded_loaders)
    
    from crawling.classifier import classify_images
    
    try:
        while account_index < total_accounts:
            loader_dict = loaded_loaders[account_index]
            L = loader_dict['loader']
            current_username = loader_dict['username']
            try:
                for term in search_terms:
                    if stop_event.is_set():
                        append_status("중지: 다운로드 중지 신호 감지됨.")
                        return
                    append_status(f"{current_username} 계정으로 {term} 다운로드 시작")
                    if search_type == 'hashtag':
                        download_posts(L, current_username, term, search_type, target,
                                       include_images, include_videos, include_reels, progress_queue, stop_event)
                    else:
                        user_download_with_profiles(L, term, target, include_images, include_reels,
                                                    progress_queue, stop_event, allow_duplicate, base_download_path, search_type)
                    if stop_event.is_set():
                        append_status("중지: 다운로드 중지됨.")
                        return
                    append_status(f"{current_username} 계정으로 {term} 다운로드 완료")
                    if include_human_classify and not stop_event.is_set():
                        classify_dir = os.path.join(base_download_path, 'unclassified',
                                                    'hashtag' if search_type == 'hashtag' else 'ID',
                                                    term, 'Image')
                        if os.path.isdir(classify_dir) and any(fname.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
                                                              for fname in os.listdir(classify_dir)):
                            classify_images(root, append_status, download_directory_var, term, current_username, search_type, stop_event)
                        if stop_event.is_set():
                            append_status("중지: 분류 중지됨.")
                            return
                    delay = random.uniform(60, 180)
                    print(f"다음 호출 전 {delay:.2f}초 대기...")
                    time.sleep(delay)
                break
            except Exception as e:
                print(f"계정 처리 오류: {e}")
                append_status(f"{current_username} 계정 오류, 재로그인 시도 중...")
                progress_queue.put(("account_relogin", current_username, "재로그인 시도 중..."))
                new_loader = instaloader_login(
                    loader_dict['username'],
                    loader_dict['password'],
                    base_download_path + "/unclassified",
                    include_videos,
                    include_reels
                )
                if new_loader:
                    loaded_loaders[account_index]['loader'] = new_loader
                    L = new_loader
                    print(f"재로그인 성공: {current_username}")
                    continue
                else:
                    print(f"재로그인 실패: {current_username}")
                    account_index += 1
                    if account_index < total_accounts:
                        print(f"계정 전환: {loaded_loaders[account_index]['username']}")
                        progress_queue.put(("account_switch", loaded_loaders[account_index]['username'], "계정 전환 중..."))
                        continue
                    else:
                        for term in search_terms:
                            progress_queue.put(("term_error", term, "모든 계정 차단됨", current_username))
                        break
    finally:
        stop_event.clear()
        on_complete("크롤링 완료됨.")

