# src/core/downloader.py
import os
import instaloader
from instaloader import Profile, LatestStamps, RateController, exceptions
import time
from itertools import islice

# 커스텀 RateController 클래스 (단순화된 버전)
class CustomRateController(RateController):
    def __init__(self, context, additional_wait_time=0.0):
        super().__init__(context)
        self.additional_wait_time = additional_wait_time
        print(f"[REQUEST_WAIT_DEBUG] CustomRateController 초기화 - 추가 대기시간: {self.additional_wait_time}초")
    
    def wait_before_query(self, query_type: str) -> None:
        # Instaloader의 기본 대기시간 계산
        base_waittime = self.query_waittime(query_type, time.monotonic(), False)
        
        # 기본 동작만 수행 (프로필 간 대기는 다운로더 레벨에서 처리)
        if base_waittime > 0:
            print(f"[REQUEST_WAIT_DEBUG] 기본 대기 시작: {base_waittime}초")
            self.sleep(base_waittime)
        
        # Instaloader의 내부 상태 업데이트
        super().wait_before_query(query_type)
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

def instaloader_login(username, password, download_path, include_videos=False, include_reels=False, cookiefile=None, resume_prefix=None, request_wait_time=0.0):
    """
    Instaloader를 사용해 인스타그램에 로그인합니다.
    
    매개변수:
        username (str): 사용자 이름.
        password (str): 비밀번호.
        download_path (str): 다운로드 경로.
        include_videos (bool): 영상 다운로드 여부.
        include_reels (bool): 릴스 다운로드 여부.
        cookiefile (str): Firefox의 cookies.sqlite 파일 경로 (선택적).
        request_wait_time (float): 요청 간 추가 대기시간 (초).
        
    반환:
        Instaloader 객체 또는 None.
    """
    # Resume prefix 설정 - 기본적으로 이어받기 활성화 (프로필별로 나중에 설정)
    if resume_prefix is None:
        resume_prefix = "resume_default"  # 기본값, 프로필별로 덮어씀
    
    # 요청 간 대기시간 설정 적용
    print(f"[REQUEST_WAIT_DEBUG] 요청 간 대기시간 설정: {request_wait_time}초")
        
    L = instaloader.Instaloader(
        download_videos=include_videos or include_reels,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern='',
        dirname_pattern=download_path,
        max_connection_attempts=3,  # 재시도 횟수를 3회로 제한
        resume_prefix=resume_prefix,  # 기본 이어받기 활성화 (프로필별로 덮어씀)
        rate_controller=lambda context: CustomRateController(context, request_wait_time)
    )
    print(f"[REQUEST_WAIT_DEBUG] CustomRateController 적용됨 - 사용자: {username}, 추가 대기시간: {request_wait_time}초")
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

        # total_posts가 문자열인 경우 정수로 변환
        if isinstance(total_posts, str):
            try:
                total_posts = int(total_posts)
            except ValueError:
                print(f"경고: total_posts를 정수로 변환할 수 없습니다: {total_posts}")
                total_posts = 0

        if stop_event.is_set():
            print("중지 신호 감지. 다운로드 중지됨.")
            progress_queue.put(("term_error", search_term, "사용자 중지", username))
            return

        # 다운로드는 기본 디렉토리(unclassified) 내에 hashtag/[해시태그] 폴더에 저장
        target_folder = os.path.join(L.dirname_pattern, 'hashtag', search_term)
        create_dir_if_not_exists(target_folder)

        original_dirname = L.dirname_pattern
        L.dirname_pattern = target_folder
        
        # 해시태그별 resume prefix 설정
        hashtag_resume_prefix = f"resume_hashtag_{search_term}"
        L.resume_prefix = hashtag_resume_prefix
        print(f"📌 [RESUME HASHTAG] 해시태그: {search_term}, resume_prefix: {hashtag_resume_prefix}")
        
        # 해시태그 resume 파일 확인
        import glob as glob_module
        hashtag_resume_files = glob_module.glob(f"{hashtag_resume_prefix}_*.json.xz")
        if hashtag_resume_files:
            print(f"📌 [RESUME HASHTAG] 기존 resume 파일 발견: {hashtag_resume_files[0]}")
        else:
            print(f"📌 [RESUME HASHTAG] 기존 resume 파일 없음 - 새로 시작")

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
        # term_complete는 crawl_and_download에서 처리하므로 여기서는 전송하지 않음
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
    # target이 문자열인 경우 정수로 변환
    if isinstance(target, str):
        try:
            target = int(target)
        except ValueError:
            print(f"경고: target을 정수로 변환할 수 없습니다: {target}")
            target = 0
    
    def download_content():
        nonlocal search_user, base_path
        resume_prefix = None  # resume_prefix 변수를 함수 스코프에서 접근 가능하도록 선언
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

            # Resume prefix를 프로필 중심으로 설정 (로그인 계정과 무관)
            profile_resume_prefix = f"resume_profile_{profile.username}"
            L_content.resume_prefix = profile_resume_prefix 

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
                'max_count': int(target) if target != 0 else None,
            }

            # 다운로드 실행
            if stop_event.is_set():
                return
            L_content.download_profiles(**image_kwargs)
            
            # username이 변경된 경우 old_username을 전달하여 검색목록에서 제거
            completed_username = old_username if old_username != profile.username else profile.username
            # term_complete는 crawl_and_download에서 처리하므로 여기서는 전송하지 않음

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

def setup_download_environment(download_path):
    """
    다운로드 환경을 설정합니다.
    
    매개변수:
        download_path (str): 기본 다운로드 경로
        
    반환:
        str: 설정된 다운로드 경로
    """
    base_download_path = download_path
    create_dir_if_not_exists(base_download_path)
    
    # 필수 하위 디렉토리 생성
    required_subdirs = ["unclassified", "Reels", "인물", "비인물"]
    for sub in required_subdirs:
        create_dir_if_not_exists(os.path.join(base_download_path, sub))
    
    return base_download_path

def create_anonymous_loader(base_download_path, include_videos, request_wait_time):
    """
    익명 사용자를 위한 Instaloader를 생성합니다.
    
    매개변수:
        base_download_path (str): 기본 다운로드 경로
        include_videos (bool): 비디오 다운로드 여부
        request_wait_time (float): 요청 간 대기시간
        
    반환:
        dict: 로더 정보
    """
    print(f"[REQUEST_WAIT_DEBUG] 익명 크롤링 시작 - 요청 간 대기시간: {request_wait_time}초")
    
    loader = instaloader.Instaloader(
        download_videos=include_videos,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern='',
        dirname_pattern=os.path.join(base_download_path, "unclassified"),
        max_connection_attempts=3,
        resume_prefix="resume_anonymous",
        rate_controller=lambda context: CustomRateController(context, request_wait_time)
    )
    
    print(f"[REQUEST_WAIT_DEBUG] CustomRateController 적용됨 - 익명 사용자, 추가 대기시간: {request_wait_time}초")
    return {'loader': loader, 'username': 'anonymous', 'password': None, 'active': True}

def create_account_loaders(accounts, base_download_path, include_videos, include_reels, request_wait_time):
    """
    계정 목록을 기반으로 Instaloader들을 생성합니다.
    
    매개변수:
        accounts (list): 계정 정보 목록
        base_download_path (str): 기본 다운로드 경로
        include_videos (bool): 비디오 다운로드 여부
        include_reels (bool): 릴스 다운로드 여부
        request_wait_time (float): 요청 간 대기시간
        
    반환:
        list: 로더 정보 목록
    """
    print(f"[REQUEST_WAIT_DEBUG] 계정 크롤링 시작 - 요청 간 대기시간: {request_wait_time}초")
    
    loaded_loaders = []
    for account in accounts:
        loader = instaloader_login(
            account['INSTAGRAM_USERNAME'],
            account['INSTAGRAM_PASSWORD'],
            os.path.join(base_download_path, "unclassified"),
            include_videos,
            include_reels,
            get_cookiefile(),
            request_wait_time=request_wait_time
        )
        
        if loader:
            loaded_loaders.append({
                'loader': loader,
                'username': account['INSTAGRAM_USERNAME'],
                'password': account['INSTAGRAM_PASSWORD'],
                'active': True
            })
            
            # 로그인 성공 시 설정 업데이트
            update_login_history(account)
        else:
            print(f"로그인 실패: {account['INSTAGRAM_USERNAME']}")
    
    return loaded_loaders

def update_login_history(account):
    """
    로그인 히스토리를 업데이트합니다.
    
    매개변수:
        account (dict): 계정 정보
    """
    config = load_config()
    config['LAST_ACCOUNT_USED'] = account['INSTAGRAM_USERNAME']
    
    # LOGIN_HISTORY 업데이트 (최근 사용한 계정을 맨 앞으로)
    login_history = config.get('LOGIN_HISTORY', [])
    # 기존 항목 제거 (중복 방지)
    login_history = [hist for hist in login_history if hist['username'] != account['INSTAGRAM_USERNAME']]
    # 새 항목을 맨 앞에 추가
    login_history.insert(0, {
        'username': account['INSTAGRAM_USERNAME'],
        'password': account['INSTAGRAM_PASSWORD'],
        'download_path': account['DOWNLOAD_PATH']
    })
    # 최대 10개까지만 유지
    config['LOGIN_HISTORY'] = login_history[:10]
    
    save_config(config)

def handle_account_rotation(account_index, total_accounts, error_msg, current_username):
    """
    계정 순환을 처리합니다.
    
    매개변수:
        account_index (int): 현재 계정 인덱스
        total_accounts (int): 전체 계정 수
        error_msg (str): 오류 메시지
        current_username (str): 현재 사용자명
        
    반환:
        int: 새로운 계정 인덱스
    """
    # 429 오류인 경우: 계정을 순환 (라운드 로빈)
    if "429" in error_msg:
        print(f"429 오류 발생: {current_username}")
        return (account_index + 1) % total_accounts
    
    # 다른 오류인 경우: 다음 계정으로 이동
    return account_index + 1

def process_single_term(term, search_type, target, include_images, include_videos, include_reels,
                       include_human_classify, include_upscale, L, current_username, progress_queue,
                       stop_event, base_download_path, allow_duplicate, root, append_status,
                       download_directory_var, i, total_terms, update_overall_progress, update_eta, start_time):
    """
    단일 검색어를 처리합니다.
    
    매개변수:
        term (str): 검색어
        search_type (str): 검색 유형
        target (int): 다운로드 목표 수
        include_images (bool): 이미지 포함 여부
        include_videos (bool): 비디오 포함 여부
        include_reels (bool): 릴스 포함 여부
        include_human_classify (bool): 인물 분류 여부
        include_upscale (bool): 업스케일 여부
        L: Instaloader 객체
        current_username (str): 현재 사용자명
        progress_queue: 진행 상황 큐
        stop_event: 중지 이벤트
        base_download_path (str): 기본 다운로드 경로
        allow_duplicate (bool): 중복 허용 여부
        root: GUI 루트
        append_status: 상태 추가 함수
        download_directory_var: 다운로드 디렉토리 변수
        i (int): 현재 인덱스
        total_terms (int): 전체 검색어 수
        update_overall_progress: 전체 진행률 업데이트 함수
        update_eta: ETA 업데이트 함수
        start_time: 시작 시간
        
    반환:
        bool: 성공 여부
    """
    if stop_event.is_set():
        append_status("중지: 다운로드 중지 신호 감지됨.")
        return False
    
    # 다운로드 시작 시 프로그레스바를 0%로 표시
    progress_queue.put(("update_progress", 0, total_terms, term))
    progress_queue.put(("term_progress", term, "콘텐츠 다운로드 시작", L.context.username))
    
    # 다운로드 실행
    if search_type == 'hashtag':
        download_posts(L, current_username, term, search_type, target,
                       include_images, include_videos, progress_queue, stop_event, base_download_path)
    else:
        user_download_with_profiles(L, term, target, include_images, include_reels,
                                    progress_queue, stop_event, allow_duplicate, base_download_path, search_type)
    
    # 다운로드 완료 후 처리
    if include_human_classify and not stop_event.is_set():
        success = process_classification(term, search_type, base_download_path, root, append_status,
                                    download_directory_var, current_username, stop_event, include_upscale, progress_queue, L)
        if success:
            # 인물분류 완료 후 검색 목록에서 제거
            progress_queue.put(("remove_from_search", term, "인물분류 완료", L.context.username))
        return success
    else:
        # 인물 분류가 체크되어 있지 않으면 다운로드 완료 후 즉시 검색 목록에서 삭제
        progress_queue.put(("term_complete", term, "다운로드 완료", L.context.username))
        progress_queue.put(("remove_from_search", term, "다운로드 완료", L.context.username))
        return True

def process_classification(term, search_type, base_download_path, root, append_status,
                          download_directory_var, current_username, stop_event, include_upscale, progress_queue, L):
    """
    인물 분류를 처리합니다.
    
    매개변수:
        term (str): 검색어
        search_type (str): 검색 유형
        base_download_path (str): 기본 다운로드 경로
        root: GUI 루트
        append_status: 상태 추가 함수
        download_directory_var: 다운로드 디렉토리 변수
        current_username (str): 현재 사용자명
        stop_event: 중지 이벤트
        include_upscale (bool): 업스케일 여부
        progress_queue: 진행 상황 큐
        L: Instaloader 객체
        
    반환:
        bool: 성공 여부
    """
    from ..processing.post_processing import process_images
    
    # 인물 분류가 체크되어 있으면 분류 진행
    classify_dir = os.path.join(base_download_path, 'unclassified',
                                'hashtag' if search_type == 'hashtag' else 'ID',
                                term)
    
    if os.path.isdir(classify_dir):
        image_files = [fname for fname in os.listdir(classify_dir) if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
        
        if image_files:
            # append_status가 None인 경우 기본 함수 사용
            if append_status is None:
                append_status = lambda msg: print(f"[STATUS] {msg}")
            
            success = process_images(root, append_status, download_directory_var, term, current_username, search_type, stop_event, include_upscale, classified=False)
            
            if success:
                # 분류 완료 후 검색 목록에서 삭제
                progress_queue.put(("term_classify_complete", term, "다운로드 및 분류 완료", L.context.username))
                progress_queue.put(("remove_from_search", term, "인물분류 완료", L.context.username))
            
            return success
        else:
            # 이미지 파일이 없으면 다운로드 완료 후 검색 목록에서 삭제
            progress_queue.put(("term_complete", term, "다운로드 완료 (분류 스킵)", L.context.username))
            progress_queue.put(("remove_from_search", term, "다운로드 완료", L.context.username))
            return True
    else:
        # 디렉토리가 없으면 다운로드 완료 후 검색 목록에서 삭제
        progress_queue.put(("term_complete", term, "다운로드 완료 (분류 스킵)", L.context.username))
        progress_queue.put(("remove_from_search", term, "다운로드 완료", L.context.username))
        return True
    
    if stop_event.is_set():
        append_status("중지: 분류 중지됨.")
        return False
    
    return True

def crawl_and_download(search_terms, target, accounts, search_type, include_images, include_videos, include_reels,
                       include_human_classify, include_upscale, progress_queue, on_complete, stop_event, download_path='download', append_status=None,
                       root=None, download_directory_var=None, allow_duplicate=False, update_overall_progress=None, 
                       update_current_progress=None, update_eta=None, start_time=None, total_terms=None):
    """
    인스타그램 게시물을 크롤링 및 다운로드하는 메인 함수.
    """
    print("크롤링 및 다운로드 시작...")
    
    # append_status가 None인 경우 기본 함수 사용
    if append_status is None:
        append_status = lambda msg: print(f"[STATUS] {msg}")
    
    # 환경 설정
    base_download_path = setup_download_environment(download_path)
    config = load_config()
    request_wait_time = config.get('REQUEST_WAIT_TIME', 0.0)
    
    # 로더 생성
    loaded_loaders = create_loaders(accounts, base_download_path, include_videos, include_reels, request_wait_time)
    
    # 크롤링 실행
    execute_crawling_loop(search_terms, target, search_type, include_images, include_videos, include_reels,
                         include_human_classify, include_upscale, loaded_loaders, progress_queue, stop_event,
                         base_download_path, allow_duplicate, root, append_status, download_directory_var,
                         update_overall_progress, update_eta, start_time, total_terms, request_wait_time)
    
    # 완료 처리 - 모든 항목이 처리된 후에만 완료 메시지 전송
    if not stop_event.is_set():
        stop_event.clear()
        on_complete("크롤링 완료됨.")
    else:
        on_complete("크롤링 중지됨.")

def create_loaders(accounts, base_download_path, include_videos, include_reels, request_wait_time):
    """
    계정 정보에 따라 로더들을 생성합니다.
    """
    if not accounts:
        loader = create_anonymous_loader(base_download_path, include_videos, request_wait_time)
        return [loader]
    else:
        return create_account_loaders(accounts, base_download_path, include_videos, include_reels, request_wait_time)

def execute_crawling_loop(search_terms, target, search_type, include_images, include_videos, include_reels,
                         include_human_classify, include_upscale, loaded_loaders, progress_queue, stop_event,
                         base_download_path, allow_duplicate, root, append_status, download_directory_var,
                         update_overall_progress, update_eta, start_time, total_terms, request_wait_time):
    """
    크롤링 루프를 실행합니다.
    """
    account_index = 0
    total_accounts = len(loaded_loaders)
    last_processed_term = None
    
    try:
        while account_index < total_accounts:
            loader_dict = loaded_loaders[account_index]
            L = loader_dict['loader']
            current_username = loader_dict['username']
            
            try:
                process_all_terms(search_terms, target, search_type, include_images, include_videos, include_reels,
                                include_human_classify, include_upscale, L, current_username, progress_queue, stop_event,
                                base_download_path, allow_duplicate, root, append_status, download_directory_var,
                                update_overall_progress, update_eta, start_time, total_terms, request_wait_time, last_processed_term)
                break
            except Exception as e:
                account_index = handle_account_error(e, account_index, total_accounts, current_username, 
                                                   loaded_loaders, progress_queue, append_status, base_download_path,
                                                   include_videos, include_reels, request_wait_time)
    except Exception as e:
        handle_final_error(e, search_terms, progress_queue, current_username)

def process_all_terms(search_terms, target, search_type, include_images, include_videos, include_reels,
                     include_human_classify, include_upscale, L, current_username, progress_queue, stop_event,
                     base_download_path, allow_duplicate, root, append_status, download_directory_var,
                     update_overall_progress, update_eta, start_time, total_terms, request_wait_time, last_processed_term):
    """
    모든 검색어를 처리합니다.
    """
    for i, term in enumerate(search_terms):
        if stop_event.is_set():
            append_status("중지: 다운로드 중지 신호 감지됨.")
            return
        
        # 프로필 간 대기
        if request_wait_time > 0 and last_processed_term is not None:
            print(f"[REQUEST_WAIT_DEBUG] 프로필 간 대기 시작: {request_wait_time}초 (이전: {last_processed_term} -> 현재: {term})")
            time.sleep(request_wait_time)
            print(f"[REQUEST_WAIT_DEBUG] 프로필 간 대기 완료")
        
        # 단일 검색어 처리
        success = process_single_term(term, search_type, target, include_images, include_videos, include_reels,
                           include_human_classify, include_upscale, L, current_username, progress_queue,
                           stop_event, base_download_path, allow_duplicate, root, append_status,
                           download_directory_var, i, total_terms, update_overall_progress, update_eta, start_time)
        
        # 완료 후 진행률 업데이트
        if success:
            update_progress(i + 1, total_terms, term, progress_queue, start_time)
        
        last_processed_term = term

def update_progress(i, total_terms, term, progress_queue, start_time):
    """
    진행률을 업데이트합니다.
    """
    if progress_queue and total_terms:
        # 프로그레스바 업데이트 메시지 전송
        progress_queue.put(("update_progress", i, total_terms, term))
        
        # ETA 업데이트 메시지 전송
        if start_time:
            progress_queue.put(("update_eta", start_time, i, total_terms))

def handle_account_error(e, account_index, total_accounts, current_username, loaded_loaders, 
                        progress_queue, append_status, base_download_path, include_videos, include_reels, request_wait_time):
    """
    계정 오류를 처리합니다.
    """
    error_msg = str(e)
    print(f"계정 처리 오류: {error_msg}")
    append_status(f"{current_username} 계정 오류, 재로그인 시도 중...")
    progress_queue.put(("account_relogin", current_username, "재로그인 시도 중..."))

    # 계정 순환 처리
    new_account_index = handle_account_rotation(account_index, total_accounts, error_msg, current_username)
    new_username = loaded_loaders[new_account_index]['username']
    print(f"계정 전환: {new_username}")
    progress_queue.put(("account_switch", new_username, "계정 전환 중..."))
    
    # 계정 전환 시 설정 업데이트
    update_login_history(loaded_loaders[new_account_index])
    
    # 재로그인 시도
    if "429" not in error_msg:
        return try_relogin(loaded_loaders, new_account_index, base_download_path, include_videos, include_reels, request_wait_time)
    
    return new_account_index

def try_relogin(loaded_loaders, account_index, base_download_path, include_videos, include_reels, request_wait_time):
    """
    재로그인을 시도합니다.
    """
    loader_dict = loaded_loaders[account_index]
    new_loader = instaloader_login(
        loader_dict['username'],
        loader_dict['password'],
        os.path.join(base_download_path, "unclassified"),
        include_videos,
        include_reels,
        get_cookiefile(),
        request_wait_time=request_wait_time
    )
    
    if new_loader:
        loaded_loaders[account_index]['loader'] = new_loader
        print(f"재로그인 성공: {loader_dict['username']}")
        return account_index
    else:
        print(f"재로그인 실패: {loader_dict['username']}")
        return account_index + 1

def handle_final_error(e, search_terms, progress_queue, current_username):
    """
    최종 오류를 처리합니다.
    """
    for term in search_terms:
        progress_queue.put(("term_error", term, "모든 계정 차단됨", current_username))

