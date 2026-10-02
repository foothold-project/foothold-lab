/* Dedicated technical-asset player. No presentation navigation listeners. */
window.Go2TechnicalPlayer=class {
  constructor(canvas,baseURL,options={}) {
    this.canvas=canvas;this.ctx=canvas.getContext('2d');this.base=baseURL.replace(/\/$/,'');
    this.cache=new Map();this.serial=0;this.current={state:null,frame:null};this.onFrame=options.onFrame||(()=>{});
    const available=options.manifest||window.GO2_TECHNICAL_MANIFEST;
    const data=available?Promise.resolve(available):fetch(`${this.base}/v4-manifest.json`).then(r=>{if(!r.ok)throw Error('Go2 manifest unavailable');return r.json()});
    this.ready=data.then(m=>{this.manifest=m;return this.setState(options.initial||'front');});
  }
  load(relative) {
    if(!this.cache.has(relative))this.cache.set(relative,new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(Error(`Missing Go2 frame: ${relative}`));image.src=`${this.base}/${relative}`;}));
    return this.cache.get(relative);
  }
  paint(image,width,height) {
    if(this.canvas.width!==width || this.canvas.height!==height){this.canvas.width=width;this.canvas.height=height;}
    this.ctx.clearRect(0,0,width,height);this.ctx.drawImage(image,0,0,width,height);
  }
  async setState(id) {
    const serial=++this.serial;const state=this.manifest.states[id]||this.manifest.segments[id];
    if(!state)throw Error(`Unknown Go2 state ${id}`);
    const image=await this.load(state.image||state.poster);if(serial!==this.serial)return;
    this.paint(image,state.image?state.width:1280,state.image?state.height:960);this.current={state:id,frame:null};this.onFrame(this.current);
  }
  async playSegment(id,{reverse=false}={}) {
    const seg=this.manifest.segments[id];if(!seg)throw Error(`Unknown Go2 segment ${id}`);
    const serial=++this.serial;const filename=f=>seg.pattern.replace('{frame:04d}',String(f).padStart(4,'0'));
    const images=await Promise.all(Array.from({length:seg.end-seg.start+1},(_,i)=>this.load(filename(seg.start+i))));
    if(serial!==this.serial)return;const started=performance.now(),duration=(images.length-1)/seg.fps*1000;
    return new Promise(resolve=>{
      const tick=now=>{
        if(serial!==this.serial){resolve();return;}
        const t=Math.min(1,(now-started)/duration);let index=Math.round(t*(images.length-1));if(reverse)index=images.length-1-index;
        this.paint(images[index],seg.width,seg.height);this.current={state:id,frame:seg.start+index};this.onFrame(this.current);
        if(t<1)requestAnimationFrame(tick);else resolve();
      };requestAnimationFrame(tick);
    });
  }
  stop(){++this.serial;}
};
