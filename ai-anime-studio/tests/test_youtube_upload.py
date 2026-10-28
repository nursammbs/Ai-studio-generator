from pathlib import Path
import pytest

from youtube_upload import build_video_resource, parse_tags, validate_metadata


def test_resource_defaults_private_and_keeps_kids_setting_unset():
    resource = build_video_resource("Pilot kartun", "Deskripsi", ["anime", "kartun"])
    assert resource["status"] == {"privacyStatus": "private"}
    assert resource["snippet"]["tags"] == ["anime", "kartun"]


def test_public_upload_resource_is_explicit():
    resource = build_video_resource("Pilot", "", [], privacy="public", made_for_kids=False)
    assert resource["status"]["privacyStatus"] == "public"
    assert resource["status"]["selfDeclaredMadeForKids"] is False


def test_title_limit_and_empty_title():
    with pytest.raises(ValueError, match="wajib"):
        validate_metadata("   ", "", [])
    with pytest.raises(ValueError, match="100"):
        validate_metadata("x" * 101, "", [])


def test_rejects_bad_privacy_and_category():
    with pytest.raises(ValueError, match="Privacy"):
        build_video_resource("ok", "", [], privacy="everyone")
    with pytest.raises(ValueError, match="category"):
        build_video_resource("ok", "", [], category_id="films")


def test_tags_parse_and_trim():
    assert parse_tags(" anime, kartun ,, ai video ") == ["anime", "kartun", "ai video"]


def test_upload_rejects_missing_file_before_api_call(tmp_path):
    from youtube_upload import upload_video
    class NeverUseApi:
        def videos(self):
            raise AssertionError("API must not be called for missing file")
    with pytest.raises(FileNotFoundError):
        upload_video(NeverUseApi(), tmp_path / "missing.mp4", build_video_resource("x", "", []))
