import os
import ffmpeg
from pathlib import Path
import time
import logging
import json
from datetime import datetime


# 设置日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('transcoding.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_video_info(file_path):
    """Get video information with detailed logging"""
    try:
        logger.info(f"获取视频信息: {file_path}")
        probe = ffmpeg.probe(file_path)
        video_info = next(s for s in probe["streams"] if s["codec_type"] == "video")
        audio_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
        
        # 获取文件大小
        file_size = Path(file_path).stat().st_size
        
        info = {
            "width": int(video_info["width"]),
            "height": int(video_info["height"]),
            "duration": float(probe["format"]["duration"]),
            "file_size": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "video_codec": video_info.get("codec_name", "unknown"),
            "video_bitrate": video_info.get("bit_rate", "unknown"),
            "audio_codec": audio_streams[0].get("codec_name", "unknown") if audio_streams else "none",
            "audio_bitrate": audio_streams[0].get("bit_rate", "unknown") if audio_streams else "none",
            "frame_rate": video_info.get("r_frame_rate", "unknown"),
            "format": probe["format"].get("format_name", "unknown"),
        }
        
        logger.info(f"视频信息获取成功: {info['width']}x{info['height']}, "
                   f"时长: {info['duration']:.2f}s, "
                   f"大小: {info['file_size_mb']}MB, "
                   f"编码: {info['video_codec']}")
        
        return info
    except ffmpeg.Error as e:
        error_msg = f"获取视频信息失败: {e.stderr.decode() if e.stderr else str(e)}"
        logger.error(error_msg)
        print(error_msg)
        return None


def encode_video(input_path, output_path, progress_callback=None):
    """Encode a single video file with detailed logging and progress tracking"""
    try:
        logger.info(f"开始转码: {input_path} -> {output_path}")
        
        # 获取转码前的视频信息
        input_info = get_video_info(input_path)
        if not input_info:
            logger.error(f"无法获取输入视频信息: {input_path}")
            return False, None
        
        logger.info("转码参数:")
        logger.info("  - 视频编码器: libx264")
        logger.info("  - 音频编码器: aac")
        logger.info("  - 视频配置: main profile, level 4.0")
        logger.info("  - 编码预设: slow")
        logger.info("  - CRF值: 23")
        logger.info("  - 音频比特率: 128k")
        logger.info("  - 快速启动: 启用")
        
        # 记录开始时间
        start_time = time.time()
        start_datetime = datetime.now()
        
        logger.info(f"转码开始时间: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 构建ffmpeg命令
        stream = (
            ffmpeg.input(input_path)
            .output(
                output_path,
                vcodec="libx264",  # Explicitly specify video codec
                acodec="aac",  # Explicitly specify audio codec
                **{
                    "profile:v": "main",  # Video profile
                    "level:v": "4.0",  # Video level
                    "preset": "slow",  # Encoding preset
                    "crf": 23,  # Constant Rate Factor
                    "b:a": "128k",  # Audio bitrate
                    "movflags": "+faststart",  # Enable fast start
                },
            )
            .overwrite_output()
        )

        # 执行转码过程并捕获输出
        logger.info("执行转码命令...")
        process = stream.run(capture_stdout=True, capture_stderr=True, input=None)
        
        # 计算转码时间
        end_time = time.time()
        encoding_duration = end_time - start_time
        end_datetime = datetime.now()
        
        logger.info(f"转码结束时间: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"转码耗时: {encoding_duration:.2f} 秒")
        
        # 获取转码后的视频信息
        output_info = get_video_info(output_path)
        if not output_info:
            logger.error(f"无法获取输出视频信息: {output_path}")
            return False, None
        
        # 计算转码前后的变化
        size_change = output_info['file_size'] - input_info['file_size']
        size_change_mb = round(size_change / (1024 * 1024), 2)
        size_change_percent = round((size_change / input_info['file_size']) * 100, 2)
        
        # 计算压缩比
        compression_ratio = round(output_info['file_size'] / input_info['file_size'], 3)
        
        # 记录转码结果
        transcode_result = {
            "status": "success",
            "input_file": str(input_path),
            "output_file": str(output_path),
            "start_time": start_datetime.isoformat(),
            "end_time": end_datetime.isoformat(),
            "encoding_duration": round(encoding_duration, 2),
            "input_info": input_info,
            "output_info": output_info,
            "changes": {
                "size_change_bytes": size_change,
                "size_change_mb": size_change_mb,
                "size_change_percent": size_change_percent,
                "compression_ratio": compression_ratio,
                "quality_maintained": True if abs(size_change_percent) < 50 else False
            },
            "encoding_settings": {
                "video_codec": "libx264",
                "audio_codec": "aac",
                "video_profile": "main",
                "video_level": "4.0",
                "preset": "slow",
                "crf": 23,
                "audio_bitrate": "128k"
            }
        }
        
        # 输出详细的转码结果
        logger.info("=" * 60)
        logger.info("转码完成 - 结果统计")
        logger.info("=" * 60)
        logger.info(f"输入文件: {Path(input_path).name}")
        logger.info(f"输出文件: {Path(output_path).name}")
        logger.info(f"转码时长: {encoding_duration:.2f} 秒")
        logger.info("")
        logger.info("转码前后对比:")
        logger.info(f"  分辨率: {input_info['width']}x{input_info['height']} -> {output_info['width']}x{output_info['height']}")
        logger.info(f"  文件大小: {input_info['file_size_mb']} MB -> {output_info['file_size_mb']} MB")
        logger.info(f"  大小变化: {size_change_mb:+.2f} MB ({size_change_percent:+.2f}%)")
        logger.info(f"  压缩比: {compression_ratio:.3f}")
        logger.info(f"  视频编码: {input_info['video_codec']} -> {output_info['video_codec']}")
        logger.info(f"  音频编码: {input_info['audio_codec']} -> {output_info['audio_codec']}")
        logger.info(f"  视频时长: {input_info['duration']:.2f}s -> {output_info['duration']:.2f}s")
        
        # 性能评估
        if encoding_duration > 0:
            speed_factor = input_info['duration'] / encoding_duration
            logger.info(f"  转码速度: {speed_factor:.2f}x (相对于实时播放)")
        
        logger.info("=" * 60)
        
        # 保存转码结果到JSON文件 
        result_file = Path(output_path).parent / f"{Path(output_path).stem}_transcode_result.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(transcode_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"转码结果已保存到: {result_file}")
        
        return True, transcode_result
        
    except ffmpeg.Error as e:
        error_msg = f"转码错误: {e.stderr.decode() if e.stderr else str(e)}"
        logger.error(error_msg)
        print(error_msg)
        
        # 记录失败的转码尝试
        failed_result = {
            "status": "failed",
            "input_file": str(input_path),
            "output_file": str(output_path),
            "error": error_msg,
            "timestamp": datetime.now().isoformat()
        }
        
        # 保存失败结果
        result_file = Path(output_path).parent / f"{Path(input_path).stem}_transcode_failed.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(failed_result, f, ensure_ascii=False, indent=2)
        
        return False, failed_result
    except Exception as e:
        error_msg = f"转码过程中发生未知错误: {str(e)}"
        logger.error(error_msg)
        print(error_msg)
        return False, None


def create_directory(directory_path):
    """Create directory if it doesn't exist"""
    try:
        os.makedirs(directory_path, exist_ok=True)
        logger.info(f"创建目录: {directory_path}")
        return True
    except Exception as e:
        error_msg = f"创建目录错误: {e}"
        logger.error(error_msg)
        print(error_msg)
        return False


def process_directory(input_directory, output_directory, progress_callback=None):
    """Process all MP4 files in the directory and its subdirectories with enhanced logging"""
    input_dir = Path(input_directory)
    output_dir = Path(output_directory)

    logger.info("=" * 80)
    logger.info("开始批量转码处理")
    logger.info("=" * 80)
    
    # Ensure input directory exists
    if not input_dir.exists() or not input_dir.is_dir():
        error_msg = f"输入目录不存在或无效: {input_dir}"
        logger.error(error_msg)
        print(error_msg)
        return

    # Get all MP4 files recursively
    mp4_files = list(input_dir.rglob("*.mp4"))
    total_files = len(mp4_files)

    if total_files == 0:
        logger.warning("未找到MP4文件")
        print("No MP4 files found")
        return

    logger.info(f"找到 {total_files} 个MP4文件")
    logger.info(f"输入目录: {input_dir}")
    logger.info(f"输出目录: {output_dir}")

    # 统计信息
    total_start_time = time.time()
    successful_transcodes = 0
    failed_transcodes = 0
    total_input_size = 0
    total_output_size = 0
    transcode_results = []

    # Process each file
    for index, input_file in enumerate(mp4_files, 1):
        logger.info(f"\n[{index}/{total_files}] 处理文件: {input_file}")
        
        # Calculate relative path from input directory
        relative_path = input_file.relative_to(input_dir)

        # Create corresponding output path
        output_file = output_dir / relative_path.parent / f"encoded_{input_file.name}"

        # Create output directory if it doesn't exist
        if not create_directory(output_file.parent):
            logger.error(f"创建输出目录失败: {output_file.parent}")
            failed_transcodes += 1
            continue

        # Skip if output file already exists
        if output_file.exists():
            logger.info(f"文件已存在，跳过: {output_file.name}")
            continue

        # Get video information
        info = get_video_info(str(input_file))
        if info:
            total_input_size += info['file_size']
            logger.info(f"输入视频信息: {info['width']}x{info['height']}, "
                       f"时长: {info['duration']:.2f}秒, "
                       f"大小: {info['file_size_mb']} MB")

        # Execute encoding
        success, result = encode_video(str(input_file), str(output_file), progress_callback)
        
        if success and result:
            successful_transcodes += 1
            total_output_size += result['output_info']['file_size']
            transcode_results.append(result)
            logger.info(f"✅ 转码成功: {output_file}")
        else:
            failed_transcodes += 1
            logger.error(f"❌ 转码失败: {input_file}")

    # 总结统计
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    
    logger.info("\n" + "=" * 80)
    logger.info("批量转码完成 - 总结报告")
    logger.info("=" * 80)
    logger.info(f"总文件数: {total_files}")
    logger.info(f"成功转码: {successful_transcodes}")
    logger.info(f"失败转码: {failed_transcodes}")
    logger.info(f"成功率: {(successful_transcodes/total_files*100):.1f}%")
    logger.info(f"总处理时间: {total_duration:.2f} 秒")
    
    if total_input_size > 0 and total_output_size > 0:
        total_size_change = total_output_size - total_input_size
        total_size_change_mb = round(total_size_change / (1024 * 1024), 2)
        total_compression_ratio = round(total_output_size / total_input_size, 3)
        
        logger.info(f"总输入大小: {round(total_input_size / (1024 * 1024), 2)} MB")
        logger.info(f"总输出大小: {round(total_output_size / (1024 * 1024), 2)} MB")
        logger.info(f"总大小变化: {total_size_change_mb:+.2f} MB")
        logger.info(f"整体压缩比: {total_compression_ratio:.3f}")
    
    logger.info("=" * 80)
    
    # 保存批量处理结果
    batch_result = {
        "batch_summary": {
            "total_files": total_files,
            "successful_transcodes": successful_transcodes,
            "failed_transcodes": failed_transcodes,
            "success_rate": round(successful_transcodes/total_files*100, 1) if total_files > 0 else 0,
            "total_duration": round(total_duration, 2),
            "total_input_size": total_input_size,
            "total_output_size": total_output_size,
            "total_size_change": total_output_size - total_input_size if total_input_size > 0 else 0,
            "overall_compression_ratio": round(total_output_size / total_input_size, 3) if total_input_size > 0 else 0,
            "timestamp": datetime.now().isoformat()
        },
        "individual_results": transcode_results
    }
    
    batch_result_file = output_dir / f"batch_transcode_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(batch_result_file, 'w', encoding='utf-8') as f:
        json.dump(batch_result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"批量处理结果已保存到: {batch_result_file}")


if __name__ == "__main__":
    # Get current directory
    current_directory = "./videos/"
    output_directory = "./encoded_videos/"

    # Start processing
    process_directory(current_directory, output_directory)