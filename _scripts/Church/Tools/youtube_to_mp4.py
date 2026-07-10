import shutil
import sys
from datetime import date
from pathlib import Path
import tempfile

import yt_dlp


def _js_runtime_opts() -> dict:
    """Enable Node.js for YouTube JS challenges when available."""
    if shutil.which('node'):
        return {'js_runtimes': {'node': {}}}
    return {}


def _format_selector(quality: str, has_ffmpeg: bool) -> str:
    """Build yt-dlp format string for merged MP4 output."""
    q = (quality or '720p').lower().strip()

    if not has_ffmpeg:
        if q in ('best', 'max', 'highest'):
            return 'best[ext=mp4]/best'
        if q.endswith('p') and q[:-1].isdigit():
            h = int(q[:-1])
            return f'best[height<={h}][ext=mp4]/best[height<={h}]'
        return 'best[ext=mp4]/best'

    if q in ('best', 'max', 'highest'):
        # Best separate streams, remux to MP4 (requires ffmpeg).
        return 'bestvideo+bestaudio/best'

    if q.endswith('p') and q[:-1].isdigit():
        h = int(q[:-1])
        return (
            f'bestvideo[height<={h}]+bestaudio/'
            f'best[height<={h}][ext=mp4]/best[height<={h}]'
        )

    return 'bestvideo+bestaudio/best'


def download_youtube_video(url, output_dir=None, quality='720p'):
    """
    Download YouTube video as MP4 at specified quality.

    quality: height like 720p, 1080p, 1440p, 2160p / 4k, or best/max for
    the highest available merged streams (recommended when ffmpeg is installed).
    """
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir()) / 'yt_downloads'
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    has_ffmpeg = shutil.which('ffmpeg') is not None
    q = (quality or '720p').lower().strip()
    if q in ('4k', '2160p'):
        q = '2160p'

    format_selector = _format_selector(q, has_ffmpeg)
    
    ydl_opts = {
        'format': format_selector,
        'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        # Safer paths on Windows (invalid path characters → #).
        'windowsfilenames': True,
        'quiet': False,
        'no_warnings': False,
        **_js_runtime_opts(),
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


def _parse_cli(argv):
    quality = '720p'
    output_dir = None
    urls = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith('--quality='):
            quality = arg.split('=', 1)[1].strip()
        elif arg == '--quality' and i + 1 < len(argv):
            quality = argv[i + 1].strip()
            i += 1
        elif arg.startswith('--output-dir='):
            output_dir = Path(arg.split('=', 1)[1].strip())
        elif arg == '--output-dir' and i + 1 < len(argv):
            output_dir = Path(argv[i + 1].strip())
            i += 1
        elif arg.strip():
            urls.append(arg.strip())
        i += 1
    return quality, output_dir, urls


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    quality, cli_output_dir, urls = _parse_cli(sys.argv[1:])
    if not urls:
        print(
            'Usage: python youtube_to_mp4.py [--quality best|1080p|720p|...] '
            '[--output-dir PATH] <youtube-url> [more-urls...]',
            file=sys.stderr,
        )
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent
    day = date.today().isoformat()
    output_dir = cli_output_dir or (script_dir.parent / 'Youtube' / day)

    print('=' * 60)
    print(f'YouTube to MP4 Converter - quality: {quality}')
    print(f'Date folder: {day}')
    print('=' * 60)

    failed = False
    for i, url in enumerate(urls, 1):
        print(f'\n[{i}/{len(urls)}] Processing video...')
        result = download_youtube_video(url, output_dir, quality=quality)
        if not result:
            failed = True

    print('\n' + '=' * 60)
    if failed:
        print('Completed with errors.')
        sys.exit(1)
    print('All downloads completed!')
    print(f'Files saved to: {output_dir}')

    if output_dir.exists():
        mp4_files = sorted(output_dir.glob('*.mp4'))
        if mp4_files:
            print(f'\nDownloaded {len(mp4_files)} file(s):')
            for f in mp4_files:
                size_mb = f.stat().st_size / (1024 * 1024)
                line = f'  - {f.name} ({size_mb:.2f} MB)'
                try:
                    print(line)
                except UnicodeEncodeError:
                    enc = getattr(sys.stdout, 'encoding', None) or 'ascii'
                    print(line.encode(enc, errors='replace').decode(enc))
        else:
            print('\nNo MP4 files found in output directory.')
    else:
        print(f'\nOutput directory does not exist: {output_dir}')

    print('=' * 60)
