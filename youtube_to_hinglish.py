"""
YouTube to Hinglish Transliterative Tool
-----------------------------------------
"""

from youtube_transcript_api import YouTubeTranscriptApi
from googletrans import Translator

def transliterate_youtube_video(video_url):
    print("\n[1/3] Processing Link...")
    # Extract the Video ID from the YouTube URL
    if "youtu.be" in video_url:
        video_id = video_url.split("/")[-1].split("?")[0]
    else:
        try:
            video_id = video_url.split("v=")[-1].split("&")[0]
        except IndexError:
            return "Error: Invalid YouTube URL format."
        
    print(f"[2/3] Fetching transcript for video ID [{video_id}]...")
    try:
        # Modern API call format
        api = YouTubeTranscriptApi()
        fetched_transcript = api.fetch(video_id, languages=['hi', 'hi-IN', 'en'])
        transcript = fetched_transcript.to_raw_data()
    except Exception as e:
        return f"Could not fetch transcript. Make sure the video has captions enabled.\nError: {e}"

    print("[3/3] Transliterating to Hinglish (Processing lines)...")
    translator = Translator()
    final_hinglish_text = []
    
    # We process it line-by-line to avoid Google Translate's character limits
    for entry in transcript:
        original_text = entry['text']
        
        # Skip empty lines
        if not original_text.strip():
            continue
            
        try:
            # The trick: We "translate" Hindi to Hindi. 
            # This forces Google to generate the Romanized version in the background.
            translated = translator.translate(original_text, dest='hi')
            
            # The 'pronunciation' attribute contains the exact Hinglish you want
            romanized_text = translated.pronunciation if translated.pronunciation else original_text
            
            final_hinglish_text.append(romanized_text)
            
        except Exception as e:
            # If a line fails, keep the original text so we don't lose data
            final_hinglish_text.append(original_text)

    # Combine all the processed lines into one big paragraph
    return " ".join(final_hinglish_text)

if __name__ == "__main__":
    print("Welcome to the YouTube Hinglish Transliterated Tool")
    print("--------------------------------------------------")
    url = input("Enter YouTube Link: ").strip()
    
    if url:
        result = transliterate_youtube_video(url)
        print("\n--- FINAL HINGLISH TRANSCRIPT ---\n")
        print(result)
        print("\n--- END OF TRANSCRIPT ---")
    else:
        print("Error: No URL provided.")