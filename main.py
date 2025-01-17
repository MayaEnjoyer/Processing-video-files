import sys
import os
import random


FFMPEG_PATH = os.path.join('ffmpeg', 'bin', 'ffmpeg.exe')

FILTERS = {
    "No filter": '',
    "Random color shift": "eq=brightness={br}:contrast={ct}:saturation={sat},hue=h={hue}",
    "Black and white": "hue=s=0",
    "High contrast": "eq=contrast=2.0",
    "Low contrast": "eq=contrast=0.5",
    'Sepia': "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
    "Инверсия": "negate",
    "Blur (light)": "gblur=sigma=2",
    "Blur (strong)": "gblur=sigma=10",
    "Flip horizontally": "hflip",
    "Flip vertically": "vflip",
    "Pixelation": "scale=iw/10:ih/10,scale=iw*10:ih*10:flags=neighbor",
    "VHS": "chromashift=1:1,noise=alls=20:allf=t+u",
    "Blue Tones": "colorbalance=bs=1",
    "Red Tones": "colorbalance=rs=1",
    "Increased Brightness": "eq=brightness=0.2",
    "Decreased Brightness": "eq=brightness=-0.2",
    "Increased Saturation": "eq=saturation=2.0",
    "Decreased Saturation": "eq=saturation=0.5",
    "Green Tones": "colorbalance=gs=1",
    "Posterization": "pp=al",
    "Strong Sepia": "colorchannelmixer=.593:.869:.189:0:.649:.786:.268:0:.472:.734:.331",
    "Strong Red Tones": "colorbalance=rs=1",
    "Strong Green Tones": "colorbalance=gs=1",
    "Strong Blue Tones": "colorbalance=bs=1",
    "Warm Filter": "curves=r='0/0 0.4/0.5 1/1':g='0/0 0.6/0.6 1/1'",
    "Cool Filter": "curves=b='0/0 0.4/0.5 1/1':g='0/0 0.4/0.4 1/1'",
    "Bright and Saturated": "eq=brightness=0.3:saturation=2.0",
    "Grayish Tones": "eq=saturation=0.7:contrast=1.3",
    "Blue-Red": "colorchannelmixer=1:0:0:0:0:0:1:0:0:0:0:1",
    "Purple Tint": "colorbalance=rs=1.2:bs=1.2",
    "Random Filter": "RANDOM_PLACEHOLDER"
}

OVERLAY_POSITIONS = {
    "Top-Left": ("0", "0.07*main_h"),
    "Top-Center": ("(main_w-overlay_w)/2", "0.07*main_h"),
    "Top-Right": ("main_w-overlay_w", "0.07*main_h"),
    "Middle-Left": ("0", "(main_h-overlay_h)/2"),
    "Middle-Center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
    "Middle-Right": ("main_w-overlay_w", "(main_h-overlay_h)/2"),
    "Bottom-Left": ("0", "main_h-overlay_h"),
    "Bottom-Center": ("(main_w-overlay_w)/2", "main_h-overlay_h"),
    "Bottom-Right": ("main_w-overlay_w", "main_h-overlay_h")
}


def is_video_file(path):
    if not os.path.isfile(path):
        return False
    ext = os.path.splitext(path)[1].lower()
    known_ext = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v'}
    if ext in known_ext:
        return True
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type and mime_type.startswith('video')


def find_videos_in_folder(folder):
    found = []
    for root, dirs, files in os.walk(folder):
        for name in files:
            fp = os.path.join(root, name)
            if is_video_file(fp):
                found.append(fp)
    return found


def pick_random_filter():
    possible = [k for k in FILTERS.keys() if k not in ("Random filter", "No filter")]
    if not possible:
        return "No filter"
    return random.choice(possible)


def build_filter_chain(selected_filters):
    arr = []
    for f in selected_filters:

        if f == "Random filter":
            f = pick_random_filter()

        flt = FILTERS.get(f, "")
        if not flt:
            continue

        if f == "Random color shift":
            br = random.uniform(-0.1, 0.1)
            ct = random.uniform(0.8, 1.2)
            sat = random.uniform(0.8, 1.2)
            hue = random.uniform(-30, 30)
            flt = flt.format(
                br=f"{br:.2f}",
                ct=f"{ct:.2f}",
                sat=f"{sat:.2f}",
                hue=f"{hue:.2f}"
            )
        arr.append(flt)

    return ','.join(arr) if arr else ''


def build_scale_filter(scale_p):
    if scale_p == 100:
        return ''
    factor = scale_p / 100
    if factor > 1:

        return f"scale=iw*{factor}:ih*{factor},crop=iw/{factor}:ih/{factor}:(iw-iw/{factor})/2:(ih-ih/{factor})/2"
    else:

        return f"scale=iw*{factor}:ih*{factor},pad=iw/{factor}:ih/{factor}:(ow-iw)/2:(oh-ih)/2"


def build_ffmpeg_cmd(in_path, out_path, filters, scale_p, speed_p, overlay, overlay_pos):
    sp = speed_p / 100.0
    vf_parts = []

    chain = build_filter_chain(filters)

    scale_chain = build_scale_filter(scale_p)

    if chain and scale_chain:
        vf_parts.append(chain + ',' + scale_chain)
    elif chain:
        vf_parts.append(chain)
    elif scale_chain:
        vf_parts.append(scale_chain)

    joined = ",".join(vf_parts) if vf_parts else None

    cmd = [FFMPEG_PATH, '-y', '-i', in_path]

    use_overlay = False
    if overlay and os.path.isfile(overlay):
        use_overlay = True
        cmd += ['-i', overlay]

    fc_parts = []
    if joined:
        fc_parts.append(f"[0:v]{joined}[base]")
    else:

        fc_parts.append("[0:v]null[base]")

    if use_overlay:
        ox, oy = OVERLAY_POSITIONS.get(overlay_pos, ('0', '0'))

        fc_parts.append("[1:v]format=rgba[ovrl]")

        fc_parts.append(f"[base][ovrl]overlay=x={ox}:y={oy}[preSpeed]")

        fc_parts.append(f"[preSpeed]setpts=1/{sp}*PTS[vid]")
    else:
        fc_parts.append(f"[base]setpts=1/{sp}*PTS[vid]")

    fc_parts.append(f"[0:a]atempo={sp}[aud]")

    fc = '; '.join(fc_parts)

    cmd += [
        '-filter_complex', fc,
        '-map', '[vid]',
        '-map', '[aud]',
        '-c:v', 'libx264',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '192k',
        out_path
    ]
    return cmd



















if __name__ == '__main__':
    main()
