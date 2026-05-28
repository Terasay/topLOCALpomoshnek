import speech_recognition as sr


def listen_ru(timeout: int = 5, phrase_time_limit: int = 6) -> str:
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.4)
        audio = recognizer.listen(
            source,
            timeout=timeout,
            phrase_time_limit=phrase_time_limit
        )

    try:
        text = recognizer.recognize_google(audio, language="ru-RU")
        return text.strip()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        return f"[Ошибка распознавания: {e}]"