from stegano import lsb
import os
import cv2
import math
import shutil
from subprocess import call, STDOUT

# Temporary directory
TEMP_DIR = "tmp"
OUTPUT_VIDEO = "output_video.mov"


def split_string(s_str, count=10):
    """Split string into 'count' parts."""
    if len(s_str) == 0:
        return ['']
    per_c = math.ceil(len(s_str) / count)
    split_list = []
    for i in range(0, len(s_str), per_c):
        split_list.append(s_str[i:i+per_c])
    return split_list


def frame_extraction(video_path):
    """Extract frames from video and save to temp directory."""
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    vidcap = cv2.VideoCapture(video_path)
    if not vidcap.isOpened():
        raise IOError(f"Cannot open video file: {video_path}")

    count = 0
    while True:
        success, image = vidcap.read()
        if not success:
            break
        frame_path = os.path.join(TEMP_DIR, f"{count}.png")
        cv2.imwrite(frame_path, image)
        count += 1
    vidcap.release()
    print(f"[INFO] Extracted {count} frames to {TEMP_DIR}")


def encode_string(input_string, root=None):
    """Hide input_string across frames in temp directory."""
    if root is None:
        root = TEMP_DIR

    frames = [f for f in os.listdir(root) if f.endswith(".png")]
    frames.sort(key=lambda x: int(os.path.splitext(x)[0]))  # Sort by number
    num_frames = len(frames)

    if num_frames == 0:
        raise RuntimeError("No frames available for encoding.")

    split_strings = split_string(input_string, count=num_frames)

    for idx, chunk in enumerate(split_strings):
        frame_path = os.path.join(root, f"{idx}.png")
        if not os.path.exists(frame_path):
            print(f"[WARNING] Frame {frame_path} missing, skipping.")
            continue
        try:
            secret_enc = lsb.hide(frame_path, chunk)
            secret_enc.save(frame_path)
            print(f"[INFO] Encoded in frame {idx}: {chunk}")
        except Exception as e:
            print(f"[ERROR] Failed to encode in {frame_path}: {e}")


def decode_string(video_path):
    """Extract hidden message from video."""
    frame_extraction(video_path)
    secret = []
    root = TEMP_DIR

    idx = 0
    while True:
        frame_path = os.path.join(root, f"{idx}.png")
        if not os.path.exists(frame_path):
            break
        try:
            secret_dec = lsb.reveal(frame_path)
            if secret_dec is None:
                break
            secret.append(secret_dec)
        except Exception as e:
            print(f"[ERROR] Failed to decode {frame_path}: {e}")
            break
        idx += 1

    decoded = ''.join(secret)
    print("Decoded message:", decoded)
    clean_tmp()
    return decoded


def clean_tmp(path=TEMP_DIR):
    """Remove temporary directory."""
    if os.path.exists(path):
        shutil.rmtree(path)
        print(f"[INFO] Cleaned up {path}")


def main():
    input_string = input("Enter the message to hide: ").strip()
    if not input_string:
        print("[ERROR] Empty message.")
        return

    video_path = input("Enter the video filename (with extension): ").strip()
    if not os.path.isfile(video_path):
        print(f"[ERROR] Video file '{video_path}' not found.")
        return

    output_video = input(f"Enter output video name [default: {OUTPUT_VIDEO}]: ").strip()
    if not output_video:
        output_video = OUTPUT_VIDEO

    # Step 1: Extract frames
    print("[STEP] Extracting video frames...")
    frame_extraction(video_path)

    # Step 2: Extract audio (if exists)
    audio_path = os.path.join(TEMP_DIR, "audio.mp3")
    try:
        call([
            "ffmpeg", "-i", video_path,
            "-q:a", "0", "-map", "a",
            audio_path, "-y"
        ], stdout=open(os.devnull, "w"), stderr=STDOUT)
        has_audio = True
        print("[INFO] Audio extracted.")
    except Exception:
        has_audio = False
        print("[INFO] No audio stream found or ffmpeg error.")

    # Step 3: Encode message into frames
    print("[STEP] Hiding message in frames...")
    encode_string(input_string)

    # Step 4: Recreate video from frames
    print("[STEP] Recompressing video frames...")
    frames_pattern = os.path.join(TEMP_DIR, "%d.png")
    temp_video = os.path.join(TEMP_DIR, "temp_video.mov")
    call([
        "ffmpeg", "-r", "30", "-i", frames_pattern,
        "-vcodec", "png", temp_video, "-y"
    ], stdout=open(os.devnull, "w"), stderr=STDOUT)

    # Step 5: Combine with audio (if exists)
    print("[STEP] Merging audio and video...")
    if has_audio:
        call([
            "ffmpeg", "-i", temp_video,
            "-i", audio_path,
            "-codec", "copy", output_video, "-y"
        ], stdout=open(os.devnull, "w"), stderr=STDOUT)
    else:
        # Just copy video
        shutil.copyfile(temp_video, output_video)

    print(f"[SUCCESS] Steganography complete. Output saved as '{output_video}'")
    clean_tmp()


if __name__ == "__main__":
    while True:
        print("\n--- Video Steganography ---")
        print("1. Hide a message in video")
        print("2. Reveal a message from video")
        print("3. Exit")
        choice = input("Choose an option: ").strip()

        if choice == '1':
            try:
                main()
            except Exception as e:
                print(f"[ERROR] An error occurred: {e}")
        elif choice == '2':
            video_path = input("Enter the video filename to decode: ").strip()
            if os.path.isfile(video_path):
                try:
                    decode_string(video_path)
                except Exception as e:
                    print(f"[ERROR] Failed to decode: {e}")
            else:
                print(f"[ERROR] File '{video_path}' not found.")
        elif choice == '3':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Try again.")

