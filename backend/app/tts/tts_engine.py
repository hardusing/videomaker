import os

from .azure_toolkit import controlable_text_to_speech_with_subtitle
from .merge_subtitle import merge_subtitles
from .srt_processer import process_srt

# Azure credentials
speech_key = "7jd2VgRY1wvbFk8HPLAwzXTP3MYQPPD6ceojmpTsHElPeZnmZSROJQQJ99ALACi0881XJ3w3AAAYACOGWNMn"
service_region = "japaneast"

custom_breaks = {
    "。": "800ms",
    "、": "200ms",
    "，": "200ms",
    "？": "500ms",
    "！": "500ms",
    "\n": "500ms",
}


def tts(filename, output_dir="./srt_and_mav"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(filename, "r", encoding="utf-8") as file:
        content = file.read().replace("\n", "")

    fn_prefix = os.path.splitext(os.path.basename(filename))[0]
    audio_path = os.path.join(output_dir, fn_prefix + ".wav")
    srt_path = os.path.join(output_dir, fn_prefix + "_pre.srt")

    controlable_text_to_speech_with_subtitle(
        speech_key=speech_key,
        service_region=service_region,
        text=content,
        audio_path=audio_path,
        srt_path=srt_path,
        #voice="ja-JP-DaichiNeural",
        voice="ja-JP-MayuNeural", 
        rate="-10%",
        punctuation_breaks=custom_breaks,
    )

    process_srt(srt_path, os.path.join(output_dir, fn_prefix + "_merged.srt"))


def find_txt_files(directory):

    txt_files = []

    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(".txt"):
                    full_path = os.path.join(root, file)
                    txt_files.append(full_path)

    except Exception as e:
        print(f"Error: {str(e)}")
        return []

    return txt_files


if __name__ == "__main__":
    # tts("./notes_output/5.txt")

     raw_txt = find_txt_files("./notes_output/")

     raw_txt.sort()

     for dift in raw_txt:
         tts(dift)
