import os
from PIL import Image
from moviepy import *
from moviepy.video.fx import Resize
import os
 
def clean_images(path):
    for filename in os.listdir(path):
        if filename.endswith(".webp"):
            # Define paths
            webp_path = os.path.join(path, filename)
            jpg_path = os.path.join(path, filename.replace(".webp", ".jpg"))
            
            try:
                # Convert and save
                img = Image.open(webp_path).convert("RGB")
                img.save(jpg_path, "JPEG", quality=90)
                
                # Close the image object explicitly before deleting
                img.close()
                
                # Delete the original webp file
                os.remove(webp_path)
                print(f"Success: Converted and deleted {filename}")
                
            except Exception as e:
                print(f"Error processing {filename}: {e}")


def slideshow(path,audio_file):
    clean_images(path) 

    images = sorted([os.path.join(path, f)
                    for f in os.listdir(path)])

    audio = AudioFileClip(audio_file)
    duration = audio.duration
    slide_duration = duration / len(images)

    clips = []
    for img in images:
        clip = (
            ImageClip(img)
            .with_duration(slide_duration)
            .with_effects([Resize((1920,1080))])
        )
        clips.append(clip)

    video = concatenate_videoclips(clips)
    final = video.with_audio(audio)

    final.write_videofile("slideshow70.mp4", fps=24)
            