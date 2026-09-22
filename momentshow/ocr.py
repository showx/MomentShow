from __future__ import annotations

from dataclasses import dataclass

from Quartz import CGImageGetHeight, CGImageGetWidth
from Vision import VNImageRequestHandler, VNRecognizeTextRequest


@dataclass(frozen=True)
class OcrLine:
    text: str
    x: float
    y: float
    w: float
    h: float


def recognize_lines(cg_image) -> list[OcrLine]:
    if cg_image is None:
        return []
    width = CGImageGetWidth(cg_image)
    height = CGImageGetHeight(cg_image)
    if not width or not height:
        return []

    request = VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(0)
    request.setUsesLanguageCorrection_(True)
    try:
        request.setAutomaticallyDetectsLanguage_(True)
    except Exception:
        pass
    try:
        request.setRecognitionLanguages_(["zh-Hans", "zh-Hant", "en-US"])
    except Exception:
        pass

    handler = VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
    result = handler.performRequests_error_([request], None)
    ok, error = _unpack_perform(result)
    if not ok:
        message = str(error) if error else "Vision OCR failed"
        raise RuntimeError(message)

    lines: list[OcrLine] = []
    observations = request.results() or []
    for obs in observations:
        candidates = obs.topCandidates_(1)
        if not candidates:
            continue
        text = str(candidates[0].string() or "").strip()
        if not text:
            continue
        box = obs.boundingBox()
        origin = box.origin
        size = box.size
        lines.append(
            OcrLine(
                text=text,
                x=float(origin.x),
                y=1.0 - float(origin.y) - float(size.height),
                w=float(size.width),
                h=float(size.height),
            )
        )
    lines.sort(key=lambda item: (round(item.y, 3), round(item.x, 3)))
    return lines


def remap_lines(lines: list[OcrLine], nx: float, ny: float, nw: float, nh: float) -> list[OcrLine]:
    return [
        OcrLine(text=item.text, x=nx + item.x * nw, y=ny + item.y * nh, w=item.w * nw, h=item.h * nh)
        for item in lines
    ]


def _unpack_perform(result) -> tuple[bool, object | None]:
    if isinstance(result, tuple):
        ok = result[0]
        err = result[1] if len(result) > 1 else None
        return bool(ok), err
    return bool(result), None
