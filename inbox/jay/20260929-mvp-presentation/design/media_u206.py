"""Verified axis-2 excerpts and silent looping experiment media. No file writes."""
from pathlib import Path
import re

HERE=Path(__file__).resolve().parents[1]
TRIMS={
    **{f'axis2-stop-{m}.mp4':(f'u206-axis2-stop-{m}.mp4','원영상 2.00–8.74초 · 4초에 정지 명령') for m in ('nvidia','v1','v2')},
    'axis2-turn-v2.mp4':('u206-axis2-turn-v2.mp4','원영상 9.00–18.00초 · 정지 → +0.5 → +1.0 → 정지'),
}

def revise_media(slides):
    """Call after research/technical revisions. Existing short clips are not re-encoded."""
    for s in slides:
        if s.get('kind')=='cinema':continue
        body=s['body']
        # Never compare different source times if a future slide adds other turn policies.
        turn_comparison=len(set(re.findall(r'axis2-turn-(?:nvidia|v1|v2)\.mp4',body)))>1
        def figure(match):
            block=match.group(0)
            for old,(new,label) in TRIMS.items():
                if old not in block:continue
                if old.startswith('axis2-turn') and turn_comparison:continue
                assert (HERE/'assets'/new).exists(),new
                block=re.sub(r'src="[^"]*/'+re.escape(old)+r'"',f'src="../assets/{new}"',block)
                if '</figcaption>' in block and label not in block:
                    block=block.replace('</figcaption>',f'<br><span class="media-source-time">{label}</span></figcaption>')
                # The excerpt's actual first frame also survives static/PDF output.
                poster=new.replace('.mp4','.jpg')
                assert (HERE/'assets'/poster).exists(),poster
                block=re.sub(r'\s+poster="[^"]*"','',block)
                block=re.sub(r'<video\b',f'<video poster="../assets/{poster}"',block,count=1)
            return block
        body=re.sub(r'<figure\b[^>]*>[\s\S]*?</figure>',figure,body)
        def video(match):
            tag=match.group(0)
            src=re.search(r'\bsrc="([^"]+)"',tag)
            if not src:return tag
            url=src.group(1).lower()
            if any(x in url for x in ('train-army','flat_army','film-','brand-','opening-','ending-')):return tag
            # Idempotent, preserves controls/source and enables native silent repeats.
            tag=re.sub(r'\s+(?:autoplay|loop|muted|playsinline)(?:="[^"]*")?(?=\s|>)','',tag)
            tag=re.sub(r'\s+preload="[^"]*"','',tag)
            return tag[:-1]+' autoplay loop muted playsinline preload="metadata">'
        s['body']=re.sub(r'<video\b[^>]*>',video,body)
    return slides
