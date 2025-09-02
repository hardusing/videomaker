import azure.cognitiveservices.speech as speechsdk


def format_time(nanoseconds):
    """
    Format time for SRT subtitle from Azure's 100-nanosecond units
    audio_offset of Azure uses a unit of 100 nano seconds
    Need to be transformed to the form of HH:MM:SS,mmm
    """
    # transform to seconds
    total_seconds = nanoseconds / 10000000  # from 100ns to seconds

    # transform to hours/minutes/seconds/milliseconds
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    milliseconds = int((total_seconds * 1000) % 1000)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def create_srt(word_boundaries, output_path):
    """Generate SRT subtitle file"""
    with open(output_path, "w", encoding="utf-8") as srt_file:
        subtitle_index = 1
        current_line = []
        current_start = None

        for i, word in enumerate(word_boundaries):
            if current_start is None:
                current_start = word["audio_offset"]

            current_line.append(word["text"])

            # Convert duration from timedelta to microseconds
            duration_microseconds = int(
                word["duration"].total_seconds() * 10000000
            )  # Convert to 100-nanosecond units
            end_time = word["audio_offset"] + duration_microseconds

            srt_file.write(f"{subtitle_index}\n")
            srt_file.write(
                f"{format_time(current_start)} --> {format_time(end_time)}\n"
            )
            srt_file.write(f"{''.join(current_line)}\n\n")

            subtitle_index += 1
            current_line = []
            current_start = None


def text_to_speech_with_subtitle(
    speech_key, service_region, text, audio_path, srt_path
):
    """Convert text to speech and generate subtitle"""
    try:
        # Configure speech service
        speech_config = speechsdk.SpeechConfig(
            subscription=speech_key, region=service_region
        )
        speech_config.speech_synthesis_voice_name = "ja-JP-ShioriNeural"

        # Configure audio output
        audio_config = speechsdk.audio.AudioOutputConfig(filename=audio_path)

        # Create speech synthesizer
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )

        # Store word boundaries for subtitle generation
        word_boundaries = []

        def handle_word_boundary(evt):
            word_boundaries.append(
                {
                    "text": evt.text,
                    "audio_offset": evt.audio_offset,
                    "duration": evt.duration,  # This is a timedelta object
                }
            )

        # Subscribe to word boundary event
        speech_synthesizer.synthesis_word_boundary.connect(handle_word_boundary)

        # Perform synthesis
        result = speech_synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            #print(f"Speech synthesized for text [{text}]")
            # Generate subtitle file
            create_srt(word_boundaries, srt_path)
            print(f"Audio saved to: {audio_path}")
            print(f"Subtitle saved to: {srt_path}")
            return True
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"Speech synthesis canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"Error details: {cancellation_details.error_details}")
            return False

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback

        print(traceback.format_exc())
        return False


def controlable_text_to_speech_with_subtitle(
    speech_key,
    service_region,
    text,
    audio_path,
    srt_path,
    voice,
    rate="-20%",  # 语速控制
    punctuation_breaks={  # 标点符号的停顿时间
        "。": "800ms",
        "、": "200ms",
        "，": "200ms",
        "？": "500ms",
        "！": "500ms",
        "\n": "500ms",  # 换行符的停顿
    },
):
    """Convert text to speech and generate subtitle"""
    try:
        # Configure speech service
        speech_config = speechsdk.SpeechConfig(
            subscription=speech_key, region=service_region
        )
        speech_config.speech_synthesis_voice_name = voice

        # Configure audio output
        audio_config = speechsdk.audio.AudioOutputConfig(filename=audio_path)
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )

        # 处理标点停顿
        text_with_breaks = text
        for punct, break_time in punctuation_breaks.items():
            text_with_breaks = text_with_breaks.replace(
                punct, f'{punct}<break time="{break_time}"/>'
            )

        # 处理不同长度的停顿标记 - 完全替换，不保留原始标记
        text_with_all_breaks = text_with_breaks.replace(
            "[PAUSE5]", '<break time="5s"/>'
        )
        text_with_all_breaks = text_with_all_breaks.replace(
            "[PAUSE10]", '<break time="10s"/>'
        )
        text_with_all_breaks = text_with_all_breaks.replace(
            "[PAUSE15]", '<break time="15s"/>'
        )
        
        # 额外确保所有PAUSE标记都被处理
        import re
        text_with_all_breaks = re.sub(r'\[PAUSE\d+\]', '', text_with_all_breaks)

        # 根据voice判断语言
        lang = "zh-CN" if "zh-CN" in voice else "ja-JP"
        
        ssml = f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{lang}">
            <voice name="{voice}">
                <prosody rate="{rate}">
                    {text_with_all_breaks}
                </prosody>
            </voice>
        </speak>
        """

        word_boundaries = []

        def handle_word_boundary(evt):
            word_boundaries.append(
                {
                    "text": evt.text,
                    "audio_offset": evt.audio_offset,
                    "duration": evt.duration,
                }
            )

        speech_synthesizer.synthesis_word_boundary.connect(handle_word_boundary)
        result = speech_synthesizer.speak_ssml_async(ssml).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            #print(f"Speech synthesized for text [{text}]")
            create_srt(word_boundaries, srt_path)
            print(f"Audio saved to: {audio_path}")
            print(f"Subtitle saved to: {srt_path}")
            return True
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"Speech synthesis canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"Error details: {cancellation_details.error_details}")
            return False

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback

        print(traceback.format_exc())
        return False
