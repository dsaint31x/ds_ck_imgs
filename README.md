# ds_ck_imgs
CLI tool to analyze image resolution and DPI statistics in a directory or ZIP archive (without extraction), with `tqdm` progress bar.

# desc.

디렉터리(하위 디렉터리 포함) 또는 ZIP 파일 내부의 이미지들을 스캔하여 해상도 및 DPI 통계를 계산하는 CLI 도구.

* ZIP 파일은 압축을 해제하지 않고 메모리에서 직접 분석하며,
* tqdm이 설치되어 있으면 progressbar를 표시하고 없으면 progressbar 없이 동작.

## 주요 기능

- **해상도 통계**: 평균 / 중앙값 / 최빈 해상도, 너비·높이·픽셀 수 범위, 상위 10개 해상도 분포
- **DPI 통계**: `image.info["dpi"]` 및 EXIF(XResolution, YResolution, ResolutionUnit) 기반 추출,
  cm 단위(ResolutionUnit=3)는 inch로 자동 환산
- **ZIP 직접 분석**: 압축 해제 없이 분석, 암호화된 ZIP 지원 (`--password`)
- **견고한 처리**: 읽기 실패 파일은 건너뛰고 파일명 및 오류 메시지를 리포트에 포함
- 지원 포맷: jpg, jpeg, png, bmp, gif, tif, tiff, webp

## 사용법

```bash
# 디렉터리 분석 (하위 디렉터리 포함)
python ds_ck_imgs_with_tqdm.py ./images

# ZIP 파일 분석 (압축 해제 없이)
python ds_ck_imgs_with_tqdm.py dataset.zip --password mypw
```

## 요구 사항

- Python 3.10+ (`X | Y` Type Hint 사용)
- Pillow (필수), tqdm (선택 — 진행률 표시용)
