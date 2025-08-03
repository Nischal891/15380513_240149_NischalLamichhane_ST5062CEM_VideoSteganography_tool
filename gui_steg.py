import os
import cv2
import math
import shutil
from subprocess import call, STDOUT
from stegano import lsb
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Configuration
TEMP_DIR = "tmp"
OUTPUT_VIDEO = "output_video.mov"

def split_string(s_str, count=10):
    if len(s_str) == 0:
        return ['']
    per_c = math.ceil(len(s_str) / count)
    return [s_str[i:i+per_c] for i in range(0, len(s_str), per_c)]

def frame_extraction(video_path):
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
        cv2.imwrite(os.path.join(TEMP_DIR, f"{count}.png"), image)
        count += 1
    vidcap.release()

def encode_string(input_string, root=None):
    if root is None:
        root = TEMP_DIR
    frames = [f for f in os.listdir(root) if f.endswith(".png")]
    frames.sort(key=lambda x: int(os.path.splitext(x)[0]))
    num_frames = len(frames)
    if num_frames == 0:
        raise RuntimeError("No frames available for encoding.")
    split_strings = split_string(input_string, count=num_frames)
    for idx, chunk in enumerate(split_strings):
        frame_path = os.path.join(root, f"{idx}.png")
        if not os.path.exists(frame_path):
            continue
        try:
            secret_enc = lsb.hide(frame_path, chunk)
            secret_enc.save(frame_path)
        except Exception as e:
            print(f"Error encoding {frame_path}: {e}")

def decode_string(video_path):
    frame_extraction(video_path)
    secret = []
    idx = 0
    while True:
        frame_path = os.path.join(TEMP_DIR, f"{idx}.png")
        if not os.path.exists(frame_path):
            break
        try:
            secret_dec = lsb.reveal(frame_path)
            if secret_dec is None:
                break
            secret.append(secret_dec)
        except Exception:
            break
        idx += 1
    clean_tmp()
    return ''.join(secret)

def clean_tmp(path=TEMP_DIR):
    if os.path.exists(path):
        shutil.rmtree(path)

# --- Simplified GUI Application ---
class StegApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Steganography")
        self.root.geometry("400x200")
        self.root.resizable(False, False)

        # Main buttons
        self.hide_btn = tk.Button(root, text="Hide Message", command=self.hide_mode, width=20, height=2)
        self.hide_btn.pack(pady=20)

        self.reveal_btn = tk.Button(root, text="Reveal Message", command=self.reveal_mode, width=20, height=2)
        self.reveal_btn.pack(pady=10)

        # Status label
        self.status_label = tk.Label(root, text="", fg="green")
        self.status_label.pack(pady=10)

    def update_status(self, message, color="green"):
        self.status_label.config(text=message, fg=color)

    def hide_mode(self):
        self.update_status("")
        # Select video
        video_path = filedialog.askopenfilename(
            title="Select Video to Hide Message In",
            filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv *.webm")]
        )
        if not video_path:
            self.update_status("No video selected.", "red")
            return

        # Get message
        message = tk.simpledialog.askstring("Input", "Enter message to hide:")
        if not message:
            self.update_status("No message entered.", "red")
            return

        # Get output filename
        output_video = tk.simpledialog.askstring("Output", "Output video name (optional):", initialvalue=OUTPUT_VIDEO)
        if not output_video:
            output_video = OUTPUT_VIDEO

        # Process
        try:
            self.update_status("Processing...")
            self.root.update() # Update UI to show "Processing..."

            frame_extraction(video_path)

            # Extract audio if exists
            has_audio = False
            audio_path = os.path.join(TEMP_DIR, "audio.mp3")
            try:
                with open(os.devnull, "w") as devnull:
                    call([
                        "ffmpeg", "-i", video_path,
                        "-q:a", "0", "-map", "a",
                        audio_path, "-y"
                    ], stdout=devnull, stderr=STDOUT)
                has_audio = True
            except Exception:
                pass # Silent fail for audio

            # Encode message into frames
            encode_string(message)

            # Recompile video
            frames_pattern = os.path.join(TEMP_DIR, "%d.png")
            temp_video = os.path.join(TEMP_DIR, "temp_video.mov")
            with open(os.devnull, "w") as devnull:
                call([
                    "ffmpeg", "-r", "30", "-i", frames_pattern,
                    "-vcodec", "png", temp_video, "-y"
                ], stdout=devnull, stderr=STDOUT)

            # Merge with audio if present
            if has_audio:
                with open(os.devnull, "w") as devnull:
                    call([
                        "ffmpeg", "-i", temp_video,
                        "-i", audio_path,
                        "-codec", "copy", output_video, "-y"
                    ], stdout=devnull, stderr=STDOUT)
            else:
                shutil.copyfile(temp_video, output_video)

            self.update_status(f"Success! Saved as: {output_video}")
            messagebox.showinfo("Success", f"Message hidden successfully!\nSaved as:\n{output_video}")

        except Exception as e:
            self.update_status(f"Error: {str(e)}", "red")
            messagebox.showerror("Process Failed", f"An error occurred:\n{str(e)}")
        finally:
            clean_tmp()

    def reveal_mode(self):
        self.update_status("")
        # Select video
        video_path = filedialog.askopenfilename(
            title="Select Video to Reveal Message From",
            filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv *.webm")]
        )
        if not video_path:
            self.update_status("No video selected.", "red")
            return

        # Process
        try:
            self.update_status("Decoding...")
            self.root.update() 

            decoded = decode_string(video_path)

            if decoded:
                self.update_status("Message decoded successfully.")
                messagebox.showinfo("Decoded Message", f"Hidden message:\n{decoded}")
            else:
                self.update_status("No message found.", "red")
                messagebox.showinfo("No Message", "No hidden message was found in this video.")

        except Exception as e:
            self.update_status(f"Decode Error: {str(e)}", "red")
            messagebox.showerror("Decode Error", f"Failed to extract message:\n{str(e)}")

if __name__ == "__main__":
    import tkinter.simpledialog
    root = tk.Tk()
    app = StegApp(root)
    root.mainloop()