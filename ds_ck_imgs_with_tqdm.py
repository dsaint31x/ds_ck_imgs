from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from io import BytesIO
from numbers import Real
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable
from zipfile import BadZipFile, ZipFile

from PIL import Image, UnidentifiedImageError

try:
    import tqdm
except ImportError:
    tqdm = None


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".webp",
}


def _show_progress(
    items: Iterable[Any],
    *,
    total: int,
    description: str,
) -> Iterable[Any]:
    """
    tqdm이 설치되어 있으면 터미널 진행률 표시줄을 붙여 반환.

    stderr가 TTY가 아닌 환경에서도 disable=False로 표시를 강제함.
    tqdm이 설치되어 있지 않으면 경고 후 원래 iterable을 반환함.
    """
    if tqdm is None:
        print(
            "[알림] tqdm이 설치되어 있지 않아 진행률을 표시하지 않음. "
            "설치: python -m pip install tqdm",
            file=sys.stderr,
        )
        return items

    return tqdm.tqdm(
        items,
        total=total,
        desc=description,
        unit="image",
        dynamic_ncols=True, # 터미널창 크기가 바뀔 때마다 bar너비를 그에 맞춰 자동재조정할지 여부
        disable=False, # True시 진행률 표시줄 표시 안함. Flase시 표시함. None시 자동 판단.
        leave=True,
        mininterval=0.1,
        file=sys.stderr, # 출력 대상 stream임
    )


def _to_positive_float(value: Any) -> float | None:
    """
    DPI 관련 값을 유효한 양의 실수로 변환.

    int, float, Fraction, IFDRational 등 
    float 변환이 가능한 값을 처리하며, 
    0 이하 또는 무한대/NaN 값은 무효로 간주.
    """
    try:
        result = float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None

    if not math.isfinite(result) or result <= 0:
        return None

    return result


def extract_dpi(image: Image.Image) -> tuple[float, float] | None:
    """
    Pillow 이미지 객체에서 수평 및 수직 DPI를 추출.

    우선 image.info["dpi"]를 확인하고, 
    값이 없으면 EXIF/TIFF의 XResolution, YResolution, ResolutionUnit 태그를 확인.

    Returns
    -------
    tuple[float, float] | None
        (수평 DPI, 수직 DPI). 유효한 DPI 정보가 없으면 None.
    """
    dpi = image.info.get("dpi")

    if dpi is not None:
        if isinstance(dpi, Real):
            value = _to_positive_float(dpi)
            if value is not None:
                return value, value
        elif isinstance(dpi, (tuple, list)) and len(dpi) >= 2:
            x_dpi = _to_positive_float(dpi[0])
            y_dpi = _to_positive_float(dpi[1])

            if x_dpi is not None and y_dpi is not None:
                return x_dpi, y_dpi

    try:
        exif = image.getexif()

        x_resolution = exif.get(282)  # XResolution
        y_resolution = exif.get(283)  # YResolution
        resolution_unit = exif.get(296)  # ResolutionUnit

        x_dpi = _to_positive_float(x_resolution)
        y_dpi = _to_positive_float(y_resolution)

        if x_dpi is None or y_dpi is None:
            return None

        if resolution_unit == 2:
            # Pixels per inch
            return x_dpi, y_dpi

        if resolution_unit == 3:
            # Pixels per centimeter -> pixels per inch
            return x_dpi * 2.54, y_dpi * 2.54

    except (AttributeError, TypeError, ValueError, OSError):
        pass

    return None


def summarize_resolutions(
    resolutions: Iterable[tuple[int, int]],
    dpis: Iterable[tuple[float, float]] | None = None,
    dpi_missing_count: int = 0,
    failed_files: list[tuple[str, str]] | None = None,
    source: str | Path | None = None,
) -> dict[str, Any]:
    """
    (width, height) 목록과 DPI 목록으로부터 통계치를 계산.
    """
    resolutions = list(resolutions)
    dpis = list(dpis or [])
    failed_files = failed_files or []

    if not resolutions:
        raise ValueError(f"읽을 수 있는 이미지가 없음: {source}")

    widths = [width for width, _ in resolutions]
    heights = [height for _, height in resolutions]
    pixel_counts = [width * height for width, height in resolutions]

    resolution_counts = Counter(resolutions)
    max_frequency = max(resolution_counts.values())

    mode_resolutions = sorted(
        resolution
        for resolution, count in resolution_counts.items()
        if count == max_frequency
    )

    result: dict[str, Any] = {
        "source": source,
        "image_count": len(resolutions),
        "failed_count": len(failed_files),
        "mean_resolution": (
            mean(widths),
            mean(heights),
        ),
        "median_resolution": (
            median(widths),
            median(heights),
        ),
        "mode_resolutions": mode_resolutions,
        "mode_frequency": max_frequency,
        "width_range": (
            min(widths),
            max(widths),
        ),
        "height_range": (
            min(heights),
            max(heights),
        ),
        "pixel_count_range": (
            min(pixel_counts),
            max(pixel_counts),
        ),
        "resolution_counts": resolution_counts,
        "failed_files": failed_files,
        "dpi_count": len(dpis),
        "dpi_missing_count": dpi_missing_count,
    }

    if dpis:
        x_dpis = [x_dpi for x_dpi, _ in dpis]
        y_dpis = [y_dpi for _, y_dpi in dpis]

        rounded_dpis = [
            (round(x_dpi, 2), round(y_dpi, 2))
            for x_dpi, y_dpi in dpis
        ]

        dpi_counts = Counter(rounded_dpis)
        max_dpi_frequency = max(dpi_counts.values())

        mode_dpis = sorted(
            dpi
            for dpi, count in dpi_counts.items()
            if count == max_dpi_frequency
        )

        result.update(
            {
                "mean_dpi": (
                    mean(x_dpis),
                    mean(y_dpis),
                ),
                "median_dpi": (
                    median(x_dpis),
                    median(y_dpis),
                ),
                "mode_dpis": mode_dpis,
                "mode_dpi_frequency": max_dpi_frequency,
                "x_dpi_range": (
                    min(x_dpis),
                    max(x_dpis),
                ),
                "y_dpi_range": (
                    min(y_dpis),
                    max(y_dpis),
                ),
                "dpi_counts": dpi_counts,
            }
        )
    else:
        result.update(
            {
                "mean_dpi": None,
                "median_dpi": None,
                "mode_dpis": [],
                "mode_dpi_frequency": 0,
                "x_dpi_range": None,
                "y_dpi_range": None,
                "dpi_counts": Counter(),
            }
        )

    return result


def analyze_image_directory(
    root_dir: str | Path,
    recursive: bool = True,
) -> dict[str, Any]:
    """
    디렉터리와 하위 디렉터리의 이미지 해상도 및 DPI를 분석.
    """
    root = Path(root_dir).expanduser().resolve()

    if not root.exists():
        raise FileNotFoundError(f"경로가 존재하지 않음: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"디렉터리가 아님: {root}")

    iterator = root.rglob("*") if recursive else root.glob("*")

    image_paths = sorted(
        (
            path
            for path in iterator
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
        ),
        key=lambda path: str(path).lower(),
    )

    resolutions: list[tuple[int, int]] = []
    dpis: list[tuple[float, float]] = []
    dpi_missing_count = 0
    failed_files: list[tuple[str, str]] = []

    for path in _show_progress(
        image_paths,
        total=len(image_paths),
        description="이미지 분석",
    ):
        try:
            with Image.open(path) as image:
                resolutions.append(image.size)

                dpi = extract_dpi(image)
                if dpi is None:
                    dpi_missing_count += 1
                else:
                    dpis.append(dpi)

        except (UnidentifiedImageError, OSError, ValueError) as error:
            failed_files.append((str(path), str(error)))

    return summarize_resolutions(
        resolutions=resolutions,
        dpis=dpis,
        dpi_missing_count=dpi_missing_count,
        failed_files=failed_files,
        source=root,
    )


def analyze_image_zip(
    zip_path: str | Path,
    password: str | bytes | None = None,
) -> dict[str, Any]:
    """
    ZIP 파일을 압축 해제하지 않고 내부 이미지의 해상도 및 DPI를 분석.
    """
    archive_path = Path(zip_path).expanduser().resolve()

    if not archive_path.exists():
        raise FileNotFoundError(
            f"ZIP 파일이 존재하지 않음: {archive_path}"
        )

    if not archive_path.is_file():
        raise ValueError(f"파일이 아님: {archive_path}")

    if isinstance(password, str):
        password = password.encode("utf-8")

    resolutions: list[tuple[int, int]] = []
    dpis: list[tuple[float, float]] = []
    dpi_missing_count = 0
    failed_files: list[tuple[str, str]] = []

    try:
        with ZipFile(archive_path, "r") as archive:
            image_members = [
                info
                for info in archive.infolist()
                if (
                    not info.is_dir()
                    and Path(info.filename).suffix.lower()
                    in IMAGE_EXTENSIONS
                )
            ]

            image_members.sort(
                key=lambda info: info.filename.lower()
            )

            for info in _show_progress(
                image_members,
                total=len(image_members),
                description="ZIP 이미지 분석",
            ):
                try:
                    image_data = archive.read(
                        info,
                        pwd=password,
                    )

                    with Image.open(BytesIO(image_data)) as image:
                        resolutions.append(image.size)

                        dpi = extract_dpi(image)
                        if dpi is None:
                            dpi_missing_count += 1
                        else:
                            dpis.append(dpi)

                except (
                    RuntimeError,
                    UnidentifiedImageError,
                    OSError,
                    ValueError,
                ) as error:
                    failed_files.append(
                        (info.filename, str(error))
                    )

    except BadZipFile as error:
        raise ValueError(
            f"유효한 ZIP 파일이 아님: {archive_path}"
        ) from error

    return summarize_resolutions(
        resolutions=resolutions,
        dpis=dpis,
        dpi_missing_count=dpi_missing_count,
        failed_files=failed_files,
        source=archive_path,
    )


def print_resolution_report(result: dict[str, Any]) -> None:
    """
    해상도와 DPI 분석 결과를 읽기 쉬운 형식으로 출력.
    """
    mean_width, mean_height = result["mean_resolution"]
    median_width, median_height = result["median_resolution"]
    min_width, max_width = result["width_range"]
    min_height, max_height = result["height_range"]
    min_pixels, max_pixels = result["pixel_count_range"]

    print(f"분석 대상: {result['source']}")
    print(f"읽은 이미지 수: {result['image_count']:,}")
    print(f"읽기 실패 수: {result['failed_count']:,}")
    print()

    print(
        "평균 해상도: "
        f"{mean_width:.2f} x {mean_height:.2f}"
    )
    print(
        "중앙값 해상도: "
        f"{median_width:g} x {median_height:g}"
    )

    modes = ", ".join(
        f"{width} x {height}"
        for width, height in result["mode_resolutions"]
    )
    print(f"최빈 해상도: {modes}")
    print(f"최빈 해상도 빈도: {result['mode_frequency']:,}개")
    print()

    print(f"너비 범위: {min_width:,} ~ {max_width:,} px")
    print(f"높이 범위: {min_height:,} ~ {max_height:,} px")
    print(
        "픽셀 수 범위: "
        f"{min_pixels:,} ~ {max_pixels:,} pixels"
    )

    print("\n가장 흔한 해상도 10개:")

    for (width, height), count in (
        result["resolution_counts"].most_common(10)
    ):
        percentage = count / result["image_count"] * 100

        print(
            f"  {width:>5} x {height:<5}: "
            f"{count:>6,}개 ({percentage:6.2f}%)"
        )

    print("\nDPI 정보:")
    print(f"DPI 메타데이터 있음: {result['dpi_count']:,}개")
    print(
        "DPI 메타데이터 없음: "
        f"{result['dpi_missing_count']:,}개"
    )

    if result["dpi_count"] > 0:
        mean_x_dpi, mean_y_dpi = result["mean_dpi"]
        median_x_dpi, median_y_dpi = result["median_dpi"]
        min_x_dpi, max_x_dpi = result["x_dpi_range"]
        min_y_dpi, max_y_dpi = result["y_dpi_range"]

        print(
            "평균 DPI: "
            f"{mean_x_dpi:.2f} x {mean_y_dpi:.2f}"
        )
        print(
            "중앙값 DPI: "
            f"{median_x_dpi:.2f} x {median_y_dpi:.2f}"
        )

        mode_text = ", ".join(
            f"{x_dpi:g} x {y_dpi:g}"
            for x_dpi, y_dpi in result["mode_dpis"]
        )

        print(f"최빈 DPI: {mode_text}")
        print(
            "최빈 DPI 빈도: "
            f"{result['mode_dpi_frequency']:,}개"
        )
        print(
            "수평 DPI 범위: "
            f"{min_x_dpi:.2f} ~ {max_x_dpi:.2f}"
        )
        print(
            "수직 DPI 범위: "
            f"{min_y_dpi:.2f} ~ {max_y_dpi:.2f}"
        )

        print("\n가장 흔한 DPI 10개:")

        for (x_dpi, y_dpi), count in (
            result["dpi_counts"].most_common(10)
        ):
            percentage = count / result["dpi_count"] * 100

            print(
                f"  {x_dpi:>8g} x {y_dpi:<8g}: "
                f"{count:>6,}개 ({percentage:6.2f}%)"
            )
    else:
        print("유효한 DPI 메타데이터가 없음.")

    if result["failed_files"]:
        print("\n읽지 못한 이미지:")

        for filename, error in result["failed_files"]:
            print(f"  {filename}: {error}")


def main(
    path: str,
    password: str | None = None,
) -> None:
    """
    경로를 받아 디렉터리 또는 ZIP 파일을 자동으로 분석.
    """
    target = Path(path).expanduser().resolve()

    if not target.exists():
        raise FileNotFoundError(
            f"경로가 존재하지 않음: {target}"
        )

    if target.is_dir():
        result = analyze_image_directory(
            target,
            recursive=True,
        )
    elif target.is_file() and target.suffix.lower() == ".zip":
        result = analyze_image_zip(
            target,
            password=password,
        )
    else:
        raise ValueError(
            "이미지 디렉터리 또는 ZIP 파일을 지정할 것: "
            f"{target}"
        )

    print_resolution_report(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "디렉터리 또는 ZIP 파일 내부 이미지의 "
            "해상도 및 DPI 통계치를 계산."
        )
    )

    parser.add_argument(
        "path",
        help="이미지 디렉터리 또는 ZIP 파일 경로",
    )

    parser.add_argument(
        "--password",
        default=None,
        help="암호화된 ZIP 파일의 비밀번호",
    )

    args = parser.parse_args()

    main(
        path=args.path,
        password=args.password,
    )
