import sys
import time
import math
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp


CAMERA_INDEX = 0
WINDOW_NAME = "LOCAL Hand Tracker"

MAX_HANDS = 2
MOVEMENT_THRESHOLD = 7.0
STILL_AFTER_SECONDS = 0.35

MODEL_PATH = Path(__file__).resolve().parent / "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


FINGER_TIPS = {
    4: "Thumb",
    8: "Index",
    12: "Middle",
    16: "Ring",
    20: "Pinky",
}


FINGER_COLORS = {
    4: (0, 140, 255),
    8: (0, 255, 255),
    12: (0, 255, 0),
    16: (255, 120, 60),
    20: (255, 0, 255),
}


HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]


def ensure_model_exists():
    if MODEL_PATH.exists():
        return True

    print("Файл модели hand_landmarker.task не найден.")
    print("Пробую скачать модель...")

    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print(f"Модель скачана: {MODEL_PATH}")
        return True
    except Exception as e:
        print("Не удалось скачать модель автоматически.")
        print(f"Ошибка: {e}")
        print()
        print("Скачай файл вручную и положи рядом с hand_tracker.py:")
        print(MODEL_URL)
        print()
        print(f"Итоговый путь должен быть: {MODEL_PATH}")
        return False


def distance(p1, p2) -> float:
    if p1 is None or p2 is None:
        return 0.0

    return math.sqrt(
        (p1[0] - p2[0]) ** 2 +
        (p1[1] - p2[1]) ** 2
    )


def landmark_to_pixel(landmark, width: int, height: int):
    x = int(landmark.x * width)
    y = int(landmark.y * height)
    return x, y


def get_hand_points(hand_landmarks, width: int, height: int):
    points = []

    for landmark in hand_landmarks:
        points.append(landmark_to_pixel(landmark, width, height))

    return points


def get_hand_center(points):
    if not points:
        return None

    x = int(sum(point[0] for point in points) / len(points))
    y = int(sum(point[1] for point in points) / len(points))

    return x, y


def draw_panel(frame, status: str, fps: int, hands_count: int):
    height, width = frame.shape[:2]

    cv2.rectangle(frame, (15, 15), (520, 125), (20, 20, 20), -1)
    cv2.rectangle(frame, (15, 15), (520, 125), (90, 90, 90), 2)

    cv2.putText(
        frame,
        f"Status: {status}",
        (30, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        frame,
        f"Hands: {hands_count}",
        (30, 85),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (210, 230, 255),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        frame,
        f"FPS: {fps}",
        (190, 85),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (210, 230, 255),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        frame,
        "Q / ESC - close",
        (width - 230, height - 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (230, 230, 230),
        2,
        cv2.LINE_AA
    )


def draw_connections(frame, points):
    for start, end in HAND_CONNECTIONS:
        if start >= len(points) or end >= len(points):
            continue

        cv2.line(
            frame,
            points[start],
            points[end],
            (180, 180, 180),
            2,
            cv2.LINE_AA
        )


def draw_all_landmarks(frame, points):
    for point in points:
        cv2.circle(frame, point, 4, (230, 230, 230), -1)


def draw_finger_tips(frame, hand_landmarks, width: int, height: int):
    for tip_id, finger_name in FINGER_TIPS.items():
        if tip_id >= len(hand_landmarks):
            continue

        landmark = hand_landmarks[tip_id]
        x, y = landmark_to_pixel(landmark, width, height)

        color = FINGER_COLORS.get(tip_id, (255, 255, 255))

        cv2.circle(frame, (x, y), 13, color, -1)
        cv2.circle(frame, (x, y), 17, (255, 255, 255), 2)

        cv2.putText(
            frame,
            finger_name,
            (x + 18, y - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            color,
            2,
            cv2.LINE_AA
        )


def draw_hand_center(frame, center, hand_index: int):
    if center is None:
        return

    cv2.circle(frame, center, 8, (255, 255, 255), -1)

    cv2.putText(
        frame,
        f"Hand {hand_index + 1}",
        (center[0] + 12, center[1] + 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )


def create_landmarker():
    BaseOptions = mp.tasks.BaseOptions
    HandLandmarker = mp.tasks.vision.HandLandmarker
    HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=VisionRunningMode.VIDEO,
        num_hands=MAX_HANDS,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    return HandLandmarker.create_from_options(options)


def run_hand_tracker(camera_index: int = 0):
    if not ensure_model_exists():
        return

    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print(f"Не удалось открыть камеру с индексом {camera_index}.")
        print("Попробуй другой индекс:")
        print("py -3.11 hand_tracker.py 0")
        print("py -3.11 hand_tracker.py 1")
        print("py -3.11 hand_tracker.py 2")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    previous_centers = {}
    last_motion_time = 0.0
    previous_frame_time = time.time()
    start_time = time.time()

    try:
        landmarker = create_landmarker()
    except Exception as e:
        cap.release()
        print("Не удалось создать HandLandmarker.")
        print(f"Ошибка: {e}")
        print()
        print("Проверь, что рядом с hand_tracker.py есть файл:")
        print(MODEL_PATH)
        return

    with landmarker:
        while True:
            ok, frame = cap.read()

            if not ok:
                print("Не удалось получить кадр с камеры.")
                break

            frame = cv2.flip(frame, 1)

            height, width = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb
            )

            timestamp_ms = int((time.time() - start_time) * 1000)

            result = landmarker.detect_for_video(
                mp_image,
                timestamp_ms
            )

            now = time.time()
            fps = int(1.0 / max(now - previous_frame_time, 0.001))
            previous_frame_time = now

            status = "No hands"
            hands_count = 0
            current_centers = {}

            if result.hand_landmarks:
                hands_count = len(result.hand_landmarks)
                total_movement = 0.0

                for hand_index, hand_landmarks in enumerate(result.hand_landmarks):
                    points = get_hand_points(hand_landmarks, width, height)
                    center = get_hand_center(points)

                    current_centers[hand_index] = center

                    previous_center = previous_centers.get(hand_index)
                    total_movement += distance(center, previous_center)

                    draw_connections(frame, points)
                    draw_all_landmarks(frame, points)
                    draw_finger_tips(frame, hand_landmarks, width, height)
                    draw_hand_center(frame, center, hand_index)

                if total_movement > MOVEMENT_THRESHOLD:
                    last_motion_time = now
                    status = "Moving"
                else:
                    if now - last_motion_time > STILL_AFTER_SECONDS:
                        status = "Still"
                    else:
                        status = "Moving"

            previous_centers = current_centers

            draw_panel(frame, status, fps, hands_count)

            cv2.imshow(WINDOW_NAME, frame)

            key = cv2.waitKey(1) & 0xFF

            if key in (27, ord("q"), ord("Q")):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    camera = CAMERA_INDEX

    if len(sys.argv) >= 2:
        try:
            camera = int(sys.argv[1])
        except ValueError:
            camera = CAMERA_INDEX

    run_hand_tracker(camera)