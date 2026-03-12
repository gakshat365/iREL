import os
import re
import json
import yt_dlp

def slugify(text):
    text = text.lower()
    # Remove non-alphanumeric characters (except spaces and hyphens)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    # Replace spaces and hyphens with underscores
    text = re.sub(r'[-\s]+', '_', text).strip('_')
    return text

def main():
    # Root dir of 'complex' project
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    links_file = os.path.join(root_dir, 'video_links.txt')
    output_file = os.path.join(root_dir, 'data', 'raw', 'metadata.json')
    
    print(f"Reading video links from {links_file}...")
    
    try:
        with open(links_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: Could not find {links_file}")
        return

    urls = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            urls.append(line)
            
    print(f"Found {len(urls)} URLs to process.")
    
    metadata_list = []
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False # Need full details like duration
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for url in urls:
            print(f"Fetching metadata for {url}...")
            try:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Unknown Title')
                duration = info.get('duration', 0)
                description = info.get('description', '')
                
                video_id = slugify(title)
                # Fallback to youtube ID if title is empty somehow
                if not video_id:
                    video_id = slugify(info.get('id', 'video')) 
                
                metadata_list.append({
                    "video_url": url,
                    "video_id": video_id,
                    "title": title,
                    "duration": duration,
                    "description": description,
                    "domain": "PLACEHOLDER_DOMAIN",
                    "declared_languages": "PLACEHOLDER_LANG",
                    "code_mixing_type": "PLACEHOLDER_TYPE"
                })
                print(f" -> Processed: {title} (ID: {video_id})")
            except Exception as e:
                print(f" -> Error processing {url}: {e}")
                
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print(f"Saving metadata to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as out_f:
        json.dump(metadata_list, out_f, indent=4, ensure_ascii=False)
        
    print("Done! Subtask 1 completed successfully.")

if __name__ == '__main__':
    main()
