import base64
import mimetypes
from pathlib import Path


class ImageService:
    ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
    ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    MIME_TO_SUFFIX = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
    }

    @staticmethod
    def file_to_data_url(path: str | Path) -> str:
        image_path = Path(path)
        content_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        if content_type.lower() not in ImageService.ALLOWED_IMAGE_MIME_TYPES:
            raise ValueError("不支持的图片类型。")
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:{content_type};base64,{encoded}"

    @staticmethod
    def is_allowed_image_upload(filename: str, content_type: str | None) -> bool:
        suffix = Path(filename).suffix.lower()
        mime = (content_type or "").split(";", 1)[0].strip().lower()
        if suffix and suffix not in ImageService.ALLOWED_IMAGE_SUFFIXES:
            return False
        if mime and mime not in ImageService.ALLOWED_IMAGE_MIME_TYPES:
            return False
        return suffix in ImageService.ALLOWED_IMAGE_SUFFIXES or mime in ImageService.ALLOWED_IMAGE_MIME_TYPES

    @staticmethod
    def suffix_for_content_type(content_type: str | None) -> str | None:
        mime = (content_type or "").split(";", 1)[0].strip().lower()
        return ImageService.MIME_TO_SUFFIX.get(mime)

    @staticmethod
    def resolve_upload_image_path(path: str, upload_dir: str | Path) -> Path | None:
        upload_root = Path(upload_dir).resolve()
        image_path = Path(path).resolve()
        try:
            if not image_path.is_relative_to(upload_root):
                return None
        except ValueError:
            return None
        if not image_path.is_file():
            return None
        if image_path.suffix.lower() not in ImageService.ALLOWED_IMAGE_SUFFIXES:
            return None
        return image_path
