#!/usr/bin/env python3
"""
TTS性别控制功能演示脚本
"""

from app.tts.tts_engine import tts
from app.api.tts_api import VOICE_MAPPING
import os

def demo_gender_control():
    """演示性别控制功能"""
    print("🎵 TTS性别控制功能演示")
    print("=" * 50)
    
    # 显示支持的声音映射
    print("📋 支持的声音映射:")
    for gender, voice in VOICE_MAPPING.items():
        gender_name = "男声" if gender == "male" else "女声"
        print(f"   {gender} ({gender_name}): {voice}")
    
    # 创建测试目录和文件
    test_dir = "./demo_output"
    os.makedirs(test_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, "demo_text.txt")
    test_content = "こんにちは。これは音声合成のテストです。男性の声と女性の声を比較してください。"
    
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(test_content)
    
    print(f"\n📝 创建测试文件: {test_file}")
    print(f"📄 测试内容: {test_content}")
    
    # 测试男声
    print("\n🎤 生成男声音频...")
    try:
        male_voice = VOICE_MAPPING["male"]
        tts(test_file, output_dir=test_dir, voice=male_voice)
        print(f"   ✅ 男声音频生成完成 (使用: {male_voice})")
        
        # 重命名输出文件以区分
        old_wav = os.path.join(test_dir, "demo_text.wav")
        old_srt = os.path.join(test_dir, "demo_text_merged.srt")
        new_wav = os.path.join(test_dir, "demo_text_male.wav")
        new_srt = os.path.join(test_dir, "demo_text_male.srt")
        
        if os.path.exists(old_wav):
            os.rename(old_wav, new_wav)
            print(f"   📁 男声音频: {new_wav}")
        if os.path.exists(old_srt):
            os.rename(old_srt, new_srt)
            print(f"   📁 男声字幕: {new_srt}")
            
    except Exception as e:
        print(f"   ❌ 男声生成失败: {e}")
    
    # 测试女声
    print("\n🎤 生成女声音频...")
    try:
        female_voice = VOICE_MAPPING["female"]
        tts(test_file, output_dir=test_dir, voice=female_voice)
        print(f"   ✅ 女声音频生成完成 (使用: {female_voice})")
        
        # 重命名输出文件以区分
        old_wav = os.path.join(test_dir, "demo_text.wav")
        old_srt = os.path.join(test_dir, "demo_text_merged.srt")
        new_wav = os.path.join(test_dir, "demo_text_female.wav")
        new_srt = os.path.join(test_dir, "demo_text_female.srt")
        
        if os.path.exists(old_wav):
            os.rename(old_wav, new_wav)
            print(f"   📁 女声音频: {new_wav}")
        if os.path.exists(old_srt):
            os.rename(old_srt, new_srt)
            print(f"   📁 女声字幕: {new_srt}")
            
    except Exception as e:
        print(f"   ❌ 女声生成失败: {e}")
    
    # 显示生成的文件
    print(f"\n📂 生成的文件列表:")
    if os.path.exists(test_dir):
        for file in os.listdir(test_dir):
            file_path = os.path.join(test_dir, file)
            size = os.path.getsize(file_path)
            print(f"   📄 {file} ({size} bytes)")
    
    print("\n🎉 演示完成！")
    print("💡 提示：你可以播放生成的音频文件来比较男声和女声的效果")

if __name__ == "__main__":
    demo_gender_control() 