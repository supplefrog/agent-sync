// SPDX-License-Identifier: AGPL-3.0-only
import { deflateSync } from 'node:zlib';
import { DRAWING_WIDTH, DRAWING_HEIGHT, validDrawing } from './drawing.mjs';
import { FileSessionStore, requireState } from './store.mjs';

const WIDTH=500, HEIGHT=300;
function crc(bytes) {
  let value=0xffffffff;
  for (const byte of bytes) {
    value^=byte;
    for(let bit=0;bit<8;bit++) value=(value>>>1)^((value&1)?0xedb88320:0);
  }
  return (value^0xffffffff)>>>0;
}

function chunk(type,data) {
  const start=Buffer.alloc(8), end=Buffer.alloc(4);
  start.writeUInt32BE(data.length);start.write(type,4,'ascii');
  end.writeUInt32BE(crc(Buffer.concat([start.subarray(4),data])));
  return Buffer.concat([start,data,end]);
}

export function drawingPng(drawing) {
  requireState(validDrawing(drawing),'invalid_drawing','No valid drawing is saved.');
  const stride=WIDTH+1, image=Buffer.alloc(stride*HEIGHT,255);
  for(let row=0;row<HEIGHT;row++)image[row*stride]=0;
  function stamp(x,y,pressure) {
    const radius=1+pressure/4;
    for(let row=Math.max(0,Math.floor(y-radius));row<Math.min(HEIGHT,y+radius);row++) {
      for(let column=Math.max(0,Math.floor(x-radius));column<Math.min(WIDTH,x+radius);column++) {
        if(Math.hypot(x-column,y-row)<=radius)image[row*stride+column+1]=30;
      }
    }
  }
  for(const stroke of drawing) {
    const points=stroke.map(([x,y,p])=>[x*(WIDTH-1)/DRAWING_WIDTH,y*(HEIGHT-1)/DRAWING_HEIGHT,p]);
    stamp(...points[0]);
    for(let i=1;i<points.length;i++){
      const [x1,y1,p1]=points[i-1], [x2,y2,p2]=points[i];
      const steps=Math.ceil(Math.hypot(x2-x1,y2-y1));
      for(let at=1;at<=steps;at++) {
        const t=at/steps;
        stamp(x1+(x2-x1)*t,y1+(y2-y1)*t,p1+(p2-p1)*t);
      }
    }
  }
  const header=Buffer.alloc(13);
  header.writeUInt32BE(WIDTH);header.writeUInt32BE(HEIGHT,4);header[8]=8;
  return Buffer.concat([Buffer.from('89504e470d0a1a0a','hex'),chunk('IHDR',header),
    chunk('IDAT',deflateSync(image)),chunk('IEND',Buffer.alloc(0))]);
}

export function readLearnerDrawing(binding,messageId) {
  requireState(typeof messageId==='string'&&messageId.length<=100,'invalid_drawing','Use the saved response message ID.');
  const record=new FileSessionStore(binding.root).read(binding.chatId);
  const message=record.messages.find(item=>item.id===messageId);
  requireState(message?.role==='toolResult'||(message?.role==='custom'&&message.customType==='practice-thinking'),
    'unknown_drawing','This lesson response has no saved drawing.');
  return drawingPng(message.details?.drawing);
}
