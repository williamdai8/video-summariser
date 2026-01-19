import argparse
import multiprocessing
import logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from .processor import VideoProcessor, ConfigManager, setup_logging

def main():
    # Load Config
    cfg = ConfigManager()
    defaults = cfg.defaults
    dirs = cfg.dirs

    parser = argparse.ArgumentParser(description="CLI Video Summarizer")
    parser.add_argument("input_file", type=Path)
    
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--fixed", action="store_true", help="Fixed mode (default)")
    mode_group.add_argument("--random", action="store_true", help="Random mode")
    mode_group.add_argument("--coverage", type=float, help="Coverage mode (0.0-1.0)")

    parser.add_argument("--save-images", action="store_true", default=defaults["save_images"])
    parser.add_argument("--interval", type=int, default=defaults["interval"])
    parser.add_argument("--duration", type=float, default=defaults["duration"])
    parser.add_argument("--min-gap", type=float, default=defaults["min_gap"])
    parser.add_argument("--max-gap", type=float, default=defaults["max_gap"])
    parser.add_argument("--min-clip", type=float, default=defaults["min_clip"])
    parser.add_argument("--max-clip", type=float, default=defaults["max_clip"])
    parser.add_argument("--chunk-size", type=int, default=defaults["chunk_size"])
    parser.add_argument("--cores", type=int, default=max(1, multiprocessing.cpu_count() - 2))

    args = parser.parse_args()
    
    setup_logging(cfg, "cli_session.log")
    logging.info(f"CLI started for {args.input_file}")

    if not args.input_file.exists():
        logging.error("Input file not found.")
        return

    original_name = args.input_file.stem
    output_video = dirs["video_out"] / f"{original_name}_short.mp4"
    
    img_out_path = None
    if args.save_images:
        img_out_path = dirs["image_out"] / original_name
        img_out_path.mkdir(parents=True, exist_ok=True)

    # Build Config
    config = {}
    if args.coverage:
        config["mode"] = "coverage"
        config["coverage"] = args.coverage
        config["min_duration"] = args.min_clip
        config["max_duration"] = args.max_clip
    elif args.random:
        config["mode"] = "random"
        config["min_interval"] = args.min_gap
        config["max_interval"] = args.max_gap
        config["min_duration"] = args.min_clip
        config["max_duration"] = args.max_clip
    else:
        config["mode"] = "fixed"
        config["interval"] = args.interval
        config["duration"] = args.duration

    processor = VideoProcessor(dirs["temp_cli"])

    try:
        logging.info("Splitting video...")
        chunks = processor.split_video(args.input_file, args.chunk_size)
        
        logging.info("Processing chunks...")
        tasks = [(c, processor.proc_dir, args.chunk_size, config, args.save_images, img_out_path) for c in chunks]
        
        processed_files = []
        with ProcessPoolExecutor(max_workers=args.cores) as executor:
            futures = [executor.submit(VideoProcessor.process_chunk, t) for t in tasks]
            for future in as_completed(futures):
                success, path, msg = future.result()
                if success:
                    processed_files.append(path)
                    logging.info(msg)
                else:
                    logging.error(msg)

        if processed_files:
            processed_files.sort()
            processor.stitch_videos(processed_files, output_video)
            print(f"✅ Video saved to: {output_video}")
        else:
            logging.error("No chunks processed.")

    except Exception:
        logging.exception("Fatal error")
    finally:
        processor.cleanup()

if __name__ == "__main__":
    main()