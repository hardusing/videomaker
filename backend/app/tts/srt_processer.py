import re
from datetime import timedelta


def parse_time(time_str):
    """将时间字符串转换为毫秒"""
    h, m, s = map(float, time_str.replace(",", ".").split(":"))
    return int((h * 3600 + m * 60 + s) * 1000)


def format_time(ms):
    """将毫秒转换为SRT格式的时间字符串"""
    time = str(timedelta(milliseconds=ms))[:-3]
    if len(time) < 11:
        time = "0" + time
    return time.replace(".", ",")


def process_srt(input_file, output_file, min_length=12):
    """处理SRT文件，合并文本并保持原始时间轴的连续性"""
    punctuation = r"[。？！…．，、｡?!､：；]"

    # 读取文件
    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read().strip()

    # 分割成字幕块
    raw_blocks = re.split(r"\n\n+", content)
    original_subs = []

    # 解析原始字幕
    for block in raw_blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            times = lines[1].split(" --> ")
            original_subs.append(
                {
                    "start_time": times[0].strip(),
                    "end_time": times[1].strip(),
                    "text": "".join(lines[2:]),
                }
            )

    # 初始化处理后的字幕
    processed_subs = []
    current_text = ""
    start_time = None

    for i, sub in enumerate(original_subs):
        if not sub["text"].strip():  # 如果是空字幕
            if current_text:  # 如果有累积的文本，先处理它
                if len(current_text) >= min_length:
                    processed_subs.append(
                        {
                            "start_time": start_time,
                            "end_time": original_subs[i - 1]["end_time"],
                            "text": current_text,
                        }
                    )
                    current_text = ""
                    start_time = None
            continue  # 跳过空字幕

        # 处理非空字幕
        if not start_time:
            start_time = sub["start_time"]

        current_text += sub["text"]

        # 检查是否需要分段
        if re.search(punctuation, sub["text"]):  # 当前字幕以标点结尾
            if len(current_text) >= min_length:
                processed_subs.append(
                    {
                        "start_time": start_time,
                        "end_time": sub["end_time"],
                        "text": current_text,
                    }
                )
                current_text = ""
                start_time = None

    # 处理最后剩余的文本
    if current_text and start_time:
        if processed_subs and len(current_text) < min_length:
            # 合并到前一个字幕
            last_sub = processed_subs[-1]
            processed_subs[-1] = {
                "start_time": last_sub["start_time"],
                "end_time": original_subs[-1]["end_time"],
                "text": last_sub["text"] + current_text,
            }
        else:
            # 作为新字幕
            processed_subs.append(
                {
                    "start_time": start_time,
                    "end_time": original_subs[-1]["end_time"],
                    "text": current_text,
                }
            )

    # 生成输出内容
    output_content = []
    for i, sub in enumerate(processed_subs, 1):
        output_content.extend(
            [str(i), f"{sub['start_time']} --> {sub['end_time']}", sub["text"], ""]
        )

    # 写入文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output_content))

    print(f"处理完成")
    print(f"原始字幕数: {len(original_subs)}")
    print(f"处理后字幕数: {len(processed_subs)}")


if __name__ == "__main__":
    process_srt("2_pre.srt", "output.srt")
