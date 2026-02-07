import yt_dlp
import sys
from pathlib import Path
import tempfile

def download_youtube_video(url, output_dir=None, quality='720p'):
    """
    Download YouTube video as MP4 at specified quality (default: 720p)
    """
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir()) / 'yt_downloads'
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if ffmpeg is available
    import shutil
    has_ffmpeg = shutil.which('ffmpeg') is not None
    
    if has_ffmpeg:
        # If ffmpeg is available, we can merge video+audio for best quality
        format_selector = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]'
    else:
        # If no ffmpeg, try to get pre-merged formats only
        format_selector = 'best[height<=720][ext=mp4]/best[height<=720]/worst[height<=720]'
    
    ydl_opts = {
        'format': format_selector,
        'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'quiet': False,
        'no_warnings': False,
    }
    
    if not has_ffmpeg:
        print('Note: ffmpeg not found. Downloading pre-merged formats only (may be lower quality).')
        print('Install ffmpeg for better quality: https://ffmpeg.org/download.html')
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f'Downloading: {url}')
            print(f'Quality: {quality}')
            print(f'Output: {output_dir}')
            print('-' * 50)
            ydl.download([url])
            print('-' * 50)
            print('Download completed!')
            return str(output_dir)
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    urls = [
        'https://www.youtube.com/watch?v=NoM0AT8fBvs',
        'https://www.youtube.com/watch?v=skAdCyew2B8'
    ]
    
    # Save to Church/Youtube folder (sibling of Tools)
    script_dir = Path(__file__).parent  # Church/Tools
    output_dir = script_dir.parent / 'Youtube'  # Church/Youtube
    
    print('=' * 60)
    print('YouTube to MP4 Converter - 720p')
    print('=' * 60)
    
    downloaded_files = []
    for i, url in enumerate(urls, 1):
        print(f'\n[{i}/{len(urls)}] Processing video...')
        result = download_youtube_video(url, output_dir)
        if result:
            downloaded_files.append(result)
    
    print('\n' + '=' * 60)
    print('All downloads completed!')
    print(f'Files saved to: {output_dir}')
    
    # List downloaded files
    if output_dir.exists():
        mp4_files = list(output_dir.glob('*.mp4'))
        if mp4_files:
            print(f'\nDownloaded {len(mp4_files)} file(s):')
            for f in mp4_files:
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f'  - {f.name} ({size_mb:.2f} MB)')
        else:
            print('\nNo MP4 files found in output directory.')
    else:
        print(f'\nOutput directory does not exist: {output_dir}')
    
    print('=' * 60)
