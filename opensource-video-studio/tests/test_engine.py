from engine import fallback_scenes_for_test, _split_sentences


def _split_sentences(text):
    import re
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def test_fallback_scene_count_and_shape():
    sources = [{"title": "Example", "url": "https://example.com", "extract": "Fact one. Fact two. Fact three."}]
    scenes = fallback_scenes_for_test("Solar panels", sources, 4, "en")
    assert len(scenes) == 4
    assert all(scene["heading"] and scene["narration"] and scene["visual_query"] for scene in scenes)


def test_empty_sources_flags_verification():
    scenes = fallback_scenes_for_test("Unknown topic", [], 3, "id")
    assert len(scenes) == 3
    assert any("sumber tepercaya" in scene["narration"].lower() for scene in scenes)
