import os

from .azure_toolkit import controlable_text_to_speech_with_subtitle
from .merge_subtitle import merge_subtitles
from .srt_processer import process_srt
from app.utils.mysql_config_helper import get_config_value


speech_key = get_config_value("speech_key")
service_region = get_config_value("service_region")

custom_breaks = {
    "。": "800ms",
    "、": "200ms",
    "，": "200ms",
    "？": "500ms",
    "！": "500ms",
    "\n": "500ms",
}


def tts(filename, output_dir="./srt_and_wav", voice=None):
    # 从配置中获取声音设置，如果没有传入voice参数的话
    if voice is None:
        voice = get_config_value("voice", "ja-JP-DaichiNeural")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(filename, "r", encoding="utf-8") as file:
        content = file.read().replace("\n", "")

    fn_prefix = os.path.splitext(os.path.basename(filename))[0]
    audio_path = os.path.join(output_dir, fn_prefix + ".wav")
    srt_path = os.path.join(output_dir, fn_prefix + "_pre.srt")
    merged_srt_path = os.path.join(output_dir, fn_prefix + "_merged.srt")

    try:
        print(f"🔄 开始处理 {filename}")
        controlable_text_to_speech_with_subtitle(
            speech_key=speech_key,
            service_region=service_region,
            text=content,
            audio_path=audio_path,
            srt_path=srt_path,
            voice=voice,
            rate="-10%",
            punctuation_breaks=custom_breaks,
        )
        #print("✅ 合成完成，检查 SRT：", srt_path)

        if os.path.exists(srt_path):
            process_srt(srt_path, merged_srt_path)
            #print(f"✅ 成功生成：{merged_srt_path}")
        else:
            print(f"❌ 错误：SRT 文件未生成：{srt_path}")

    except Exception as e:
        print(f"[TTS错误] 文件 {filename} 处理失败: {e}")


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
