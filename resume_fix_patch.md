# Resume 기능 완료 시 파일 삭제 수정사항

## 문제
- 정상 다운로드 완료 시에도 `json.xz` resume 파일이 삭제되지 않는 문제 발생
- `nodeiterator.py`의 `resumable_iteration`에서 `resume_file_exists` 조건이 시작 시 상태만 체크하여 삭제되지 않음

## 해결 방법
`venv/insta_venv/Lib/site-packages/instaloader/instaloader.py`의 `posts_download_loop` 함수에 완료 시 삭제 로직 추가

### 수정 위치
약 1092-1095줄 이후에 추가:

```python
            # 다운로드 완료 시 resume 파일 삭제
            if self.resume_prefix and hasattr(posts, 'magic'):
                try:
                    resume_file_path = self.format_filename_within_target_path(
                        sanitized_target, owner_profile, self.resume_prefix or '', posts.magic, 'json.xz'
                    )
                    if os.path.isfile(resume_file_path):
                        os.unlink(resume_file_path)
                        self.context.log("Download complete, deleted resume file: {}".format(resume_file_path))
                except Exception:
                    pass  # 삭제 실패 시 무시
```

## 적용 방법
1. `venv/insta_venv/Lib/site-packages/instaloader/instaloader.py` 파일 열기
2. `posts_download_loop` 함수에서 for 루프가 끝나는 부분 찾기
3. 위 코드를 추가
4. 테스트: 다운로드 완료 후 resume 파일이 자동 삭제되는지 확인

## 테스트 결과
- [x] Resume 파일 생성: 매 포스트마다 생성됨
- [ ] Resume 파일 삭제: 다운로드 완료 시 삭제되어야 함 (테스트 필요)
