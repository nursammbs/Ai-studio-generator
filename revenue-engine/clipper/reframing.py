from __future__ import annotations

from pathlib import Path


def detect_subject_center(
    video_path: str | Path, start: float, end: float, sample_every_seconds: float = 1.0,
) -> tuple[float, float] | None:
    """Estimate the dominant face center for a clip; coordinates are normalized to 0..1."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Install requirements-ai.txt to enable face-focused framing") from exc

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("OpenCV could not read the uploaded video for face framing")
    classifier = cv2.CascadeClassifier(
        str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    )
    centers: list[tuple[float, float, float]] = []
    timestamp = max(0.0, start)
    try:
        while timestamp < end and len(centers) < 120:
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ok, frame = capture.read()
            if ok:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = classifier.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(36, 36),
                )
                if len(faces):
                    x, y, width, height = max(faces, key=lambda box: box[2] * box[3])
                    frame_height, frame_width = gray.shape[:2]
                    centers.append(((x + width / 2) / frame_width, (y + height / 2) / frame_height, width * height))
            timestamp += max(0.25, sample_every_seconds)
    finally:
        capture.release()

    if not centers:
        return None
    centers.sort(key=lambda item: item[2], reverse=True)
    dominant = centers[: max(1, len(centers) // 2)]
    return (
        sorted(item[0] for item in dominant)[len(dominant) // 2],
        sorted(item[1] for item in dominant)[len(dominant) // 2],
    )
