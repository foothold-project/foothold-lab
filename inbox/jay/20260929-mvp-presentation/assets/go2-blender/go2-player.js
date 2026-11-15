/* Actual Blender-rendered frames. Presentation owns keyboard/remote events. */
window.Go2SpecPlayer = class {
  constructor(canvas, baseURL) {
    this.canvas=canvas;this.ctx=canvas.getContext('2d');this.base=baseURL.replace(/\/$/,'');
    this.images=new Map();this.frame=1;this.generation=0;this.stops=[1,96,156,216,240];
    canvas.width=640;canvas.height=480;
    this.ready=this.draw(1);
  }
  async image(frame) {
    frame=Math.max(1,Math.min(264,Math.round(frame)));
    if (!this.images.has(frame)) this.images.set(frame,new Promise((resolve,reject)=>{
      const im=new Image();im.onload=()=>resolve(im);im.onerror=reject;
      im.src=`${this.base}/web-frames/frame-${String(frame).padStart(4,'0')}.webp`;
    }));
    return this.images.get(frame);
  }
  async draw(frame) {
    const im=await this.image(frame);this.ctx.clearRect(0,0,640,480);this.ctx.drawImage(im,0,0);this.frame=Math.round(frame);
  }
  async stage(index, animate=true) {
    const generation=++this.generation,target=this.stops[Math.max(0,Math.min(4,index))],from=this.frame;
    if(!animate || target===from){await this.draw(target);return;}
    const low=Math.min(from,target),high=Math.max(from,target);
    await Promise.all(Array.from({length:high-low+1},(_,i)=>this.image(low+i)));
    if(generation!==this.generation)return;
    const start=performance.now(),duration=Math.abs(target-from)/24*1000;
    return new Promise(resolve=>{
      const tick=now=>{
        if(generation!==this.generation){resolve();return;}
        const t=Math.min(1,(now-start)/duration),frame=Math.round(from+(target-from)*t);
        this.draw(frame);
        if(t<1)requestAnimationFrame(tick);else resolve();
      };requestAnimationFrame(tick);
    });
  }
};
