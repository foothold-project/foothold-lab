/* Fixed-size transparent player. Owns no slide-navigation event handlers. */
window.Go2V5Player=class {
  constructor(canvas,baseURL,options={}){
    this.canvas=canvas;this.ctx=canvas.getContext('2d');this.base=baseURL.replace(/\/$/,'');
    this.serial=0;this.cache=new Map();this.loading=new Map();this.cacheLimit=options.cacheLimit||110;this.current={state:null,frame:null};this.onFrame=options.onFrame||(()=>{});
    this.anchors=options.anchors||window.GO2_V5_FRAME_ANCHORS||null;
    const data=options.manifest||window.GO2_V5_MANIFEST;
    this.ready=(data?Promise.resolve(data):fetch(`${this.base}/v5-manifest.json`).then(r=>{if(!r.ok)throw Error('Missing Go2 v5 manifest');return r.json();})).then(m=>{
      this.manifest=m;this.canvas.width=m.canvas.width;this.canvas.height=m.canvas.height;
      return this.setState(options.initial||'front');
    });
  }
  load(path){
    if(!this.cache.has(path))this.cache.set(path,new Promise((resolve,reject)=>{
      const im=new Image();this.loading.set(path,im);
      im.onload=()=>{this.loading.delete(path);resolve(im);};
      im.onerror=()=>{this.loading.delete(path);this.cache.delete(path);reject(Error(`Missing Go2 v5 asset ${path}`));};im.src=`${this.base}/${path}`;
    }));
    const pending=this.cache.get(path);while(this.cache.size>this.cacheLimit)this.cache.delete(this.cache.keys().next().value);
    return pending;
  }
  paint(im,state,frame,anchor=null){
    this.ctx.clearRect(0,0,this.canvas.width,this.canvas.height);
    this.ctx.drawImage(im,0,0,this.canvas.width,this.canvas.height);
    this.current={state,frame};this.onFrame({...this.current,anchors:anchor||this.anchors?.[frame-1]||null});
  }
  async setState(id){
    const state=this.manifest.states[id];if(!state)throw Error(`Unknown Go2 v5 state ${id}`);
    const token=++this.serial;const im=await this.load(state.image);
    if(token!==this.serial)return false;this.paint(im,id,state.frame,state.anchors);return true;
  }
  async playSegment(id,{reverse=false,speed=1}={}){
    const seg=this.manifest.segments[id];if(!seg)throw Error(`Unknown Go2 v5 segment ${id}`);
    if(!(speed>0))throw Error('Playback speed must be positive');
    const token=++this.serial;
    const frames=[];
    for(let f=seg.start;f<=seg.end;f+=8){
      if(token!==this.serial)return false;
      const batch=Array.from({length:Math.min(8,seg.end-f+1)},(_,i)=>this.load(seg.pattern.replace('{frame:04d}',String(f+i).padStart(4,'0'))));
      frames.push(...await Promise.all(batch));
    }
    if(token!==this.serial)return false;
    const duration=(frames.length-1)/seg.fps*1000/speed;const started=performance.now();
    return new Promise((resolve,reject)=>{
      const tick=now=>{
        if(token!==this.serial){resolve(false);return;}
        const t=Math.max(0,Math.min(1,(now-started)/duration));let ix=Math.round(t*(frames.length-1));if(reverse)ix=frames.length-1-ix;
        try{this.paint(frames[ix],id,seg.start+ix);}catch(error){reject(error);return;}
        if(t<1)requestAnimationFrame(tick);else resolve(true);
      };requestAnimationFrame(tick);
    });
  }
  stop(){++this.serial;}
  dispose(){this.stop();this.cache.clear();}
};
