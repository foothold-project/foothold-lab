"""실제 영상에서 검토용 접촉 시트와 PDF용 장면을 추출한다."""
from pathlib import Path
import json
import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 16)

def read_frame(cap, seconds):
    cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError(f'Cannot read {seconds}s')
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

def main():
    videos = json.loads((ROOT/'inventory.json').read_text(encoding='utf-8'))['videos']
    qa=ROOT/'qa';qa.mkdir(exist_ok=True)
    choices_path=ROOT/'frame-selection.json'
    choices=json.loads(choices_path.read_text(encoding='utf-8')) if choices_path.exists() else {}
    metadata=[]
    for batch in range(0,len(videos),4):
        sheet=Image.new('RGB',(1600,4*202),'#f6f5f1');d=ImageDraw.Draw(sheet)
        for row,video in enumerate(videos[batch:batch+4]):
            cap=cv2.VideoCapture(str(ROOT/'source/media'/video['file']))
            fps=cap.get(cv2.CAP_PROP_FPS);count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));duration=count/fps
            times=[max(0,min(duration-1/fps,duration*f)) for f in [.05,.22,.4,.58,.76,.97]]
            d.text((8,row*202+2),f'{video["id"]} {video["file"]} | {duration:.2f}s {count} frames',font=FONT,fill='#161c26')
            for col,t in enumerate(times):
                im=read_frame(cap,t);im.thumbnail((262,148));sheet.paste(im,(col*266,row*202+25))
                d.text((col*266+6,row*202+175),f'{t:.2f}s',font=FONT,fill='#161c26')
            choice=choices.get(video['file'],{'seconds':times[-1],'reason':'검토 전 임시 선택'})
            frame=read_frame(cap,choice['seconds']);(ROOT/'stills').mkdir(exist_ok=True)
            frame.save(ROOT/'stills'/video['file'].replace('.mp4','.jpg'),quality=93)
            for extra in choice.get('extra_seconds', []):
                read_frame(cap,extra).save(ROOT/'stills'/video['file'].replace('.mp4',f'-{extra:g}s.jpg'),quality=93)
            metadata.append({**video,'duration':duration,'fps':fps,'frame_count':count,
                'width':int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),'height':int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'selected':choice,'still':'stills/'+video['file'].replace('.mp4','.jpg')})
            cap.release()
        sheet.save(qa/f'contact-{batch//4+1:02d}.jpg',quality=95)
    (ROOT/'video-scenes.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print('videos',len(metadata),'contact_sheets',(len(videos)+3)//4)

if __name__=='__main__':
    main()
