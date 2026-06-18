from app.services.image_service import ImageService


def test_image_upload_type_allowlist() -> None:
    assert ImageService.is_allowed_image_upload("screenshot.png", "image/png")
    assert ImageService.is_allowed_image_upload("blob", "image/webp")
    assert not ImageService.is_allowed_image_upload("notes.txt", "image/png")
    assert not ImageService.is_allowed_image_upload("screenshot.png", "text/plain")
