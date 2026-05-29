import sys
import time
import math

import cv2
import mediapipe as mp


CAMERA_INDEX = 0

WINDOW_NAME = "LOCAL Hand Tracker"

MAX_HANDS = 2

# Чувствительность движения.
# Меньше число = сильнее реагирует на мелкие движения.
MOVEMENT_THRESHOLD = 7.0

# Через сколько секунд без движения писать "рука на месте".
STILL_AFTER_SECONDS = 0.35


FINGER_TIPS = {
    4: "Большой",
    8: "Указательный",
    12: "Средний",
    16: "Безымянный",
    20: "Мизинец",
}


# OpenCV использует BGR, не RGB.
# Потому что зачем делать нормально.
FINGER_COLORS = {
    4: (0, 140, 255),      # большой
    8: (0, 255, 255),      # указательный
    12: (0, 255, 0),       # средний
    16: (255, 120, 60),    # безымянный
    20: (255, 0, 255),     # мизинец
}


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

    for landmark in hand_landmarks.landmark:
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


def draw_finger_tips(frame, hand_landmarks, width: int, height: int):
    for tip_id, finger_name in FINGER_TIPS.items():
        landmark = hand_landmarks.landmark[tip_id]
        x, y = landmark_to_pixel(landmark, width, height)

        color = FINGER_COLORS.get(tip_id, (255, 255, 255))

        # Основной круг на кончике пальца.
        cv2.circle(frame, (x, y), 13, color, -1)

        # Белая обводка.
        cv2.circle(frame, (x, y), 17, (255, 255, 255), 2)

        # Подпись.
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


def run_hand_tracker(camera_index: int = 0):
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    mp_styles = mp.solutions.drawing_styles

    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print(f"Не удалось открыть камеру с индексом {camera_index}.")
        print("Попробуй другой индекс:")
        print("py -3.11 hand_tracker.py 1")
        print("py -3.11 hand_tracker.py 2")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    previous_centers = {}
    last_motion_time = 0.0

    previous_frame_time = time.time()

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=MAX_HANDS,
        model_complexity=1,
        min_detection_confidence=0.65,
        min_tracking_confidence=0.65,
    ) as hands:

        while True:
            ok, frame = cap.read()

            if not ok:
                print("Не удалось получить кадр с камеры.")
                break

            # Зеркалим, чтобы рука двигалась как в зеркале.
            frame = cv2.flip(frame, 1)

            height, width = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            now = time.time()
            fps = int(1.0 / max(now - previous_frame_time, 0.001))
            previous_frame_time = now

            status = "Рук не видно"
            hands_count = 0
            current_centers = {}

            if result.multi_hand_landmarks:
                hands_count = len(result.multi_hand_landmarks)
                total_movement = 0.0

                for hand_index, hand_landmarks in enumerate(result.multi_hand_landmarks):
                    points = get_hand_points(hand_landmarks, width, height)
                    center = get_hand_center(points)

                    current_centers[hand_index] = center

                    previous_center = previous_centers.get(hand_index)
                    total_movement += distance(center, previous_center)

                    # Скелет руки.
                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                        mp_styles.get_default_hand_landmarks_style(),
                        mp_styles.get_default_hand_connections_style(),
                    )

                    # Круги на кончиках пальцев.
                    draw_finger_tips(frame, hand_landmarks, width, height)

                    # Центр ладони.
                    draw_hand_center(frame, center, hand_index)

                if total_movement > MOVEMENT_THRESHOLD:
                    last_motion_time = now
                    status = "Рука движется"
                else:
                    if now - last_motion_time > STILL_AFTER_SECONDS:
                        status = "Рука на месте"
                    else:
                        status = "Рука движется"

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