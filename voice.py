import audioop
import speech_recognition as sr


# Если None, используется микрофон по умолчанию.
# Если надо выбрать конкретный микрофон, поставь его номер:
# py -3.11 -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"
MIC_DEVICE_INDEX = None

# Сколько секунд ждать, пока ты начнёшь говорить.
MIC_TIMEOUT = 12

# Максимальная длина фразы.
PHRASE_TIME_LIMIT = 10

# Длительность настройки под шум.
AMBIENT_NOISE_DURATION = 0.8

# Чем меньше, тем чувствительнее.
# Для тихого микрофона 60-120 обычно норм.
ENERGY_THRESHOLD = 80

# Программное усиление записанного звука.
# Если всё ещё тихо, поставь 5.0 или 6.0.
AUDIO_GAIN = 4.0


def list_microphones():
    return sr.Microphone.list_microphone_names()


def amplify_audio(audio: sr.AudioData, gain: float) -> sr.AudioData:
    """
    Программно усиливает записанный звук перед распознаванием.
    Да, это костыль. Но рабочий костыль лучше красивой ошибки.
    """

    try:
        raw_data = audio.get_raw_data()
        amplified = audioop.mul(raw_data, audio.sample_width, gain)

        return sr.AudioData(
            amplified,
            audio.sample_rate,
            audio.sample_width
        )

    except Exception:
        return audio


def listen_ru():
    recognizer = sr.Recognizer()

    # Для тихого микрофона лучше вручную задать порог.
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold = ENERGY_THRESHOLD

    recognizer.pause_threshold = 0.9
    recognizer.non_speaking_duration = 0.45

    try:
        with sr.Microphone(device_index=MIC_DEVICE_INDEX) as source:
            print("Доступные микрофоны:")
            for index, name in enumerate(list_microphones()):
                print(f"{index}: {name}")

            print("Настраиваю шум...")
            recognizer.adjust_for_ambient_noise(
                source,
                duration=AMBIENT_NOISE_DURATION
            )

            # После автонастройки принудительно делаем порог ниже,
            # чтобы тихий микрофон не игнорировался.
            recognizer.energy_threshold = min(
                recognizer.energy_threshold,
                ENERGY_THRESHOLD
            )

            print(f"Energy threshold: {recognizer.energy_threshold}")
            print("Говори...")

            audio = recognizer.listen(
                source,
                timeout=MIC_TIMEOUT,
                phrase_time_limit=PHRASE_TIME_LIMIT
            )

        print("Усиливаю звук...")
        audio = amplify_audio(audio, AUDIO_GAIN)

        print("Распознаю...")

        text = recognizer.recognize_google(
            audio,
            language="ru-RU"
        )

        return text.strip()

    except sr.WaitTimeoutError:
        return (
            "[Ошибка голосового ввода: микрофон не услышал начало речи. "
            "Говори громче/ближе или увеличь усиление микрофона в Windows.]"
        )

    except sr.UnknownValueError:
        return (
            "[Ошибка голосового ввода: речь не распознана. "
            "Попробуй говорить ближе к микрофону или увеличь AUDIO_GAIN в voice.py.]"
        )

    except sr.RequestError as e:
        return f"[Ошибка распознавания Google Speech: {e}]"

    except Exception as e:
        return f"[Ошибка голосового ввода: {e}]"