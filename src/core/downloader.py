# src/core/downloader.py
import os
import instaloader
from instaloader import Profile, LatestStamps, RateController, exceptions
from itertools import islice
import time
import shutil
import random
from datetime import datetime
from ..utils.file_utils import create_dir_if_not_exists, logging
from ..utils.config import load_config, save_config
from .profile_manager import add_non_existent_profile_id, is_profile_id_non_existent, get_profile_id_for_username, add_private_not_followed_profile_id, is_private_not_followed_profile_id
from sqlite3 import OperationalError, connect
from platform import system
from glob import glob
from os.path import expanduser
from ..utils.environment import Environment

# 세션 파일 저장 디렉토리 설정
SESSION_DIR = Environment.SESSIONS_DIR
create_dir_if_not_exists(SESSION_DIR)

# 최신 스탬프 파일 경로
STAMPS_FILE_IMAGES = Environment.STAMPS_FILE
STAMPS_FILE_REELS = Environment.CONFIG_DIR / "latest-stamps-reels.ini"

def instaloader_login(username, password, download_path, include_videos=False, include_reels=False, cookiefile=None, resume_prefix=None, rate_limit_config=None):
    """
    Instaloader를 사용해 인스타그램에 로그인합니다.
    
    매개변수:
        username (str): 사용자 이름.
        password (str): 비밀번호.
        download_path (str): 다운로드 경로.
        include_videos (bool): 영상 다운로드 여부.
        include_reels (bool): 릴스 다운로드 여부.
        cookiefile (str): Firefox의 cookies.sqlite 파일 경로 (선택적).
        
    반환:
        Instaloader 객체 또는 None.
    """
    if resume_prefix is None:
        resume_prefix = os.path.join(os.path.dirname(STAMPS_FILE_IMAGES), f"resume_{username}")
    
    # Rate Limiting 설정 적용
    if rate_limit_config:
        min_sleep = rate_limit_config.get('min_sleep', 3.0)
        max_sleep = rate_limit_config.get('max_sleep', 10.0)
        multiplier = rate_limit_config.get('multiplier', 1.5)
    else:
        min_sleep = 3.0
        max_sleep = 10.0
        multiplier = 1.5
        
    L = instaloader.Instaloader(
        download_videos=include_videos or include_reels,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern='',
        dirname_pattern=download_path,
        max_connection_attempts=3,  # 재시도 횟수를 3회로 제한
        resume_prefix=resume_prefix,
        rate_controller=lambda context: RateController(context)
    )
    session_file = os.path.join(SESSION_DIR, f"{username}.session")
    
    try:
        # 세션 파일이 존재하면 이를 우선 로드
        if os.path.isfile(session_file):
            L.load_session_from_file(username, filename=session_file)
            print(f"세션 로드 성공: {username}")
        # 세션 파일이 없고 cookiefile이 제공되면 쿠키를 이용해 로그인 및 세션 저장
        elif cookiefile:
            print("Using cookies from {}.".format(cookiefile))
            conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
            try:
                cookie_data = conn.execute(
                    "SELECT name, value FROM moz_cookies WHERE baseDomain='instagram.com'"
                )
            except OperationalError:
                cookie_data = conn.execute(
                    "SELECT name, value FROM moz_cookies WHERE host LIKE '%instagram.com'"
                )
            L.context._session.cookies.update(cookie_data)
            logged_in_username = L.test_login()
            if not logged_in_username:
                print("Firefox 쿠키를 통해 로그인하지 못했습니다.")
                return None
            print("Imported session cookie for {}.".format(logged_in_username))
            L.context.username = logged_in_username
            L.save_session_to_file(session_file)
        else:
            # 세션 파일이 없고 cookiefile도 제공되지 않으면, 사용자명과 비밀번호로 로그인
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

def get_cookiefile():
    default_cookiefile = {
        "Windows": "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite",
        "Darwin": "~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite",
    }.get(system(), "~/.mozilla/firefox/*/cookies.sqlite")
    cookiefiles = glob(expanduser(default_cookiefile))
    if not cookiefiles:
        raise SystemExit("No Firefox cookies.sqlite file found. Use -c COOKIEFILE.")
    return cookiefiles[0]

def download_posts(
    L,
    username,
    search_term,
    search_type,
    target,
    include_images,
    include_videos,
    progress_queue,
    stop_event,
    resume_from=0
):
    """
    해시태그 또는 사용자 ID를 기반으로 인스타그램 게시물을 다운로드합니다.
    """
    def my_tag_filter(post):
        if include_images and include_videos:
            return True
        if include_images and not include_videos:
            return not post.is_video
        if include_videos and not include_images:
            return post.is_video
        return False

    print(f"{search_term} 다운로드 시작 (검색 유형: {search_type})")
    progress_queue.put(("term_start", search_term, username))

    try:
        if search_type == 'hashtag':
            hashtag = instaloader.Hashtag.from_name(L.context, search_term)
            total_posts = hashtag.mediacount
        else:
            print("지원되지 않는 검색 유형입니다.")
            progress_queue.put(("term_error", search_term, "지원되지 않는 검색 유형", username))
            return

        if target != 0 and target < total_posts:
            total_posts = target

        if stop_event.is_set():
            print("중지 신호 감지. 다운로드 중지됨.")
            progress_queue.put(("term_error", search_term, "사용자 중지", username))
            return

        # 다운로드는 기본 디렉토리(unclassified) 내에 hashtag/[해시태그] 폴더에 저장
        target_folder = os.path.join(L.dirname_pattern, 'hashtag', search_term)
        create_dir_if_not_exists(target_folder)

        original_dirname = L.dirname_pattern
        L.dirname_pattern = target_folder

        try:
            if include_images or include_videos:
                L.download_hashtag_top_serp(
                    search_term,
                    max_count=total_posts,
                    post_filter=my_tag_filter,
                    profile_pic=False
                )
                if include_videos:
                    # 기본 다운로드 경로의 상위 폴더를 기준으로 Reels/hashtag/[해시태그] 경로를 설정
                    base_path = os.path.dirname(original_dirname)
                    videos_folder = os.path.join(base_path, 'Reels', 'hashtag', search_term)
                    create_dir_if_not_exists(videos_folder)
                    video_files = []
                    for root, dirs, files in os.walk(target_folder):
                        for file in files:
                            if file.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                                video_files.append(file)
                                source_path = os.path.join(root, file)
                                destination_path = os.path.join(videos_folder, file)
                                try:
                                    shutil.move(source_path, destination_path)
                                    print(f"동영상 이동: {file} -> {videos_folder}")
                                except Exception as e:
                                    print(f"동영상 이동 오류: {e}")
                                    progress_queue.put(("term_error", search_term, f"동영상 이동 오류: {e}", username))
                    if video_files:
                        progress_queue.put(("term_progress", search_term, "동영상 이동 완료", username))
        except Exception as e:
            print(f"게시물 다운로드 오류: {e}")
            progress_queue.put(("term_error", search_term, f"게시물 다운로드 오류: {e}", username))
            L.dirname_pattern = original_dirname

        L.dirname_pattern = original_dirname
        progress_queue.put(("term_progress", search_term, 1, username))
        print(f"{search_term} 다운로드 완료")
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
            profile = None
            
            # 프로필 조회 시도 (재시도 횟수 제한)
            max_retries = 3
            retry_count = 0
            
            # Rate Limiting을 위한 대기 시간
            time.sleep(2)
            
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
                    # 저장된 ID로 실패한 경우 username으로 재시도
                    profile = None
                    try:
                        profile = Profile.from_username(L_content.context, old_username)
                    except Exception as e:
                        error_msg = str(e)
                        print(f"프로필 조회 실패: {old_username} - {error_msg}")
                        # "does not exist" 메시지가 포함된 경우 유사한 프로필 정보도 표시
                        if "does not exist" in error_msg:
                            # 저장된 profile-id가 있으면 해당 ID를 존재하지 않는 프로필로 저장
                            stored_profile_id = get_profile_id_for_username(old_username)
                            if stored_profile_id:
                                add_non_existent_profile_id(stored_profile_id, old_username)
                            else:
                                # profile-id가 없으면 username으로 저장 (하위 호환성)
                                config = load_config()
                                if old_username not in config.get('NON_EXISTENT_PROFILES', []):
                                    config.setdefault('NON_EXISTENT_PROFILES', []).append(old_username)
                                    save_config(config)
                                    print(f"존재하지 않는 프로필 '{old_username}'을 설정에 저장했습니다.")
                            progress_queue.put(("term_error", old_username, error_msg, L.context.username))
                        else:
                            progress_queue.put(("term_error", old_username, f"프로필 조회 실패: {error_msg}", L.context.username))
                        return
            else:
                # 저장된 ID가 없는 경우 username으로 조회
                profile = None
                try:
                    profile = Profile.from_username(L_content.context, search_user)
                except Exception as e:
                    error_msg = str(e)
                    print(f"프로필 조회 실패: {search_user} - {error_msg}")
                    # "does not exist" 메시지가 포함된 경우 유사한 프로필 정보도 표시
                    if "does not exist" in error_msg:
                        # 저장된 profile-id가 있으면 해당 ID를 존재하지 않는 프로필로 저장
                        stored_profile_id = get_profile_id_for_username(search_user)
                        if stored_profile_id:
                            add_non_existent_profile_id(stored_profile_id, search_user)
                        else:
                            # profile-id가 없으면 username으로 저장 (하위 호환성)
                            config = load_config()
                            if search_user not in config.get('NON_EXISTENT_PROFILES', []):
                                config.setdefault('NON_EXISTENT_PROFILES', []).append(search_user)
                                save_config(config)
                                print(f"존재하지 않는 프로필 '{search_user}'을 설정에 저장했습니다.")
                        progress_queue.put(("term_error", search_user, error_msg, L.context.username))
                    else:
                        progress_queue.put(("term_error", search_user, f"프로필 조회 실패: {error_msg}", L.context.username))
                    return

            content_folder = os.path.join(base_path, "unclassified", "ID", profile.username)
            L_content.dirname_pattern = content_folder
            create_dir_if_not_exists(content_folder)             

            resume_prefix = f"resume_{profile.username}"
            print("📌 [RESUME INFO]")
            print(f" - resume_prefix: {resume_prefix}")
            print(f" - dirname_pattern: {L_content.dirname_pattern}")
            print(f" - 예상 저장 위치: {os.path.join(L_content.dirname_pattern, f'{os.path.basename(resume_prefix)}_<magic>.json.xz')}")

            L_content.resume_prefix = resume_prefix 

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
                'latest_stamps': None if allow_duplicate else latest_stamps_images,
                'max_count': target if target != 0 else None,
            }

            L_content.download_profiles(**image_kwargs)
            # username이 변경된 경우 old_username을 전달하여 검색목록에서 제거
            completed_username = old_username if old_username != profile.username else profile.username
            progress_queue.put(("term_complete", completed_username, "콘텐츠 다운로드 완료", L.context.username))

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
            error_msg = str(e)
            print(f"{search_user} 다운로드 오류: {error_msg}")
            
            # "Private but not followed" 오류 감지 및 저장
            if "Private but not followed" in error_msg:
                # 저장된 profile-id가 있으면 해당 ID를 비공개 프로필로 저장
                stored_profile_id = get_profile_id_for_username(search_user)
                if stored_profile_id:
                    add_private_not_followed_profile_id(stored_profile_id, search_user)
                else:
                    # profile-id가 없으면 username으로 저장 (하위 호환성)
                    config = load_config()
                    if search_user not in config.get('PRIVATE_NOT_FOLLOWED_PROFILES', []):
                        config.setdefault('PRIVATE_NOT_FOLLOWED_PROFILES', []).append(search_user)
                        save_config(config)
                        print(f"비공개 프로필 '{search_user}'을 설정에 저장했습니다.")
                
                # 비공개 프로필로 저장된 경우 검색목록에서 제거
                progress_queue.put(("term_complete", search_user, f"비공개 프로필로 저장됨: {error_msg}", L.context.username))
            else:
                progress_queue.put(("term_error", search_user, f"콘텐츠 다운로드 오류: {error_msg}", L.context.username))
            #raise
    download_content()

def crawl_and_download(search_terms, target, accounts, search_type, include_images, include_videos, include_reels,
                       include_human_classify, include_upscale, progress_queue, on_complete, stop_event, download_path='download', append_status=None,
                       root=None, download_directory_var=None, allow_duplicate=False, update_overall_progress=None, 
                       update_current_progress=None, update_eta=None, start_time=None, total_terms=None):
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
        include_upscale (bool): 인물 분류 후 업스케일 여부.
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
    base_download_path = download_path
    # 기본 다운로드 경로가 없으면 생성
    create_dir_if_not_exists(base_download_path)
    for sub in ["unclassified", "Reels", "인물", "비인물"]:
        create_dir_if_not_exists(os.path.join(base_download_path, sub))
    
    loaded_loaders = []
    if not accounts:
        # Rate Limiting 설정 로드
        config = load_config()
        rate_limit_config = {
            'min_sleep': config.get('RATE_LIMIT_MIN_SLEEP', 3.0),
            'max_sleep': config.get('RATE_LIMIT_MAX_SLEEP', 10.0),
            'multiplier': config.get('RATE_LIMIT_MULTIPLIER', 1.5)
        }
        
        loader = instaloader.Instaloader(
            download_videos=include_videos,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern='',
            dirname_pattern=os.path.join(base_download_path, "unclassified"),
            max_connection_attempts=3,  # 재시도 횟수를 3회로 제한
            rate_controller=lambda context: RateController(context)
        )
        loaded_loaders.append({'loader': loader, 'username': 'anonymous', 'password': None, 'active': True})
    else:
        # Rate Limiting 설정 로드
        config = load_config()
        rate_limit_config = {
            'min_sleep': config.get('RATE_LIMIT_MIN_SLEEP', 3.0),
            'max_sleep': config.get('RATE_LIMIT_MAX_SLEEP', 10.0),
            'multiplier': config.get('RATE_LIMIT_MULTIPLIER', 1.5)
        }
        
        for account in accounts:
            loader = instaloader_login(
                account['INSTAGRAM_USERNAME'],
                account['INSTAGRAM_PASSWORD'],
                os.path.join(base_download_path, "unclassified"),
                include_videos,
                include_reels,
                get_cookiefile(),
                rate_limit_config=rate_limit_config
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
    
    from ..processing.post_processing import process_images
    
    try:
        while account_index < total_accounts:
            loader_dict = loaded_loaders[account_index]
            L = loader_dict['loader']
            current_username = loader_dict['username']
            try:
                for i, term in enumerate(search_terms):
                    if stop_event.is_set():
                        append_status("중지: 다운로드 중지 신호 감지됨.")
                        return
                    
                    # 전체 진행률 업데이트
                    if update_overall_progress and total_terms:
                        update_overall_progress(i, total_terms, term)
                    
                    # 현재 프로필 진행률 초기화 (제거됨)
                    
                    # 예상 완료 시간 업데이트
                    if update_eta and start_time:
                        update_eta(start_time, i, total_terms)
                    
                    progress_queue.put(("term_progress", term, "콘텐츠 다운로드 시작", L.context.username))
                    if search_type == 'hashtag':
                        download_posts(L, current_username, term, search_type, target,
                                       include_images, include_videos, progress_queue, stop_event, base_download_path)
                    else:
                        user_download_with_profiles(L, term, target, include_images, include_reels,
                                                    progress_queue, stop_event, allow_duplicate, base_download_path, search_type)
                    if stop_event.is_set():
                        append_status("중지: 다운로드 중지됨.")
                        return
                    if include_human_classify and not stop_event.is_set():
                        classify_dir = os.path.join(base_download_path, 'unclassified',
                                                    'hashtag' if search_type == 'hashtag' else 'ID',
                                                    term)
                        print(f"인물분류 체크: {term} - 디렉토리: {classify_dir}")
                        if os.path.isdir(classify_dir):
                            image_files = [fname for fname in os.listdir(classify_dir) if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
                            print(f"인물분류 체크: {term} - 이미지 파일 수: {len(image_files)}")
                            if image_files:
                                print(f"인물분류 시작: {term}")
                                process_images(root, append_status, download_directory_var, term, current_username, search_type, stop_event, include_upscale, classified=False)
                            else:
                                print(f"인물분류 스킵: {term} - 이미지 파일 없음")
                        else:
                            print(f"인물분류 스킵: {term} - 디렉토리 없음")
                        if stop_event.is_set():
                            append_status("중지: 분류 중지됨.")
                            return
                break
            except Exception as e:
                error_msg = str(e)
                print(f"계정 처리 오류: {error_msg}")
                append_status(f"{current_username} 계정 오류, 재로그인 시도 중...")
                progress_queue.put(("account_relogin", current_username, "재로그인 시도 중..."))

                # 429 오류인 경우: 계정을 순환 (라운드 로빈)
                if "429" in error_msg:
                    print(f"429 오류 발생: {current_username}")
                    account_index = (account_index + 1) % total_accounts
                    print(f"계정 전환: {loaded_loaders[account_index]['username']}")
                    progress_queue.put(("account_switch", loaded_loaders[account_index]['username'], "계정 전환 중..."))
                    continue

                # 429 오류가 아닌 경우: 재로그인 시도 후 실패하면 마지막 계정이면 중단
                new_loader = instaloader_login(
                    loader_dict['username'],
                    loader_dict['password'],
                    os.path.join(base_download_path, "unclassified"),
                    include_videos,
                    include_reels,
                    get_cookiefile(),
                    rate_limit_config=rate_limit_config
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

