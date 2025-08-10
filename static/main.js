// this file assumes the socket.io client is already loaded
const socket = io();
let myId = null;
let currentRoom = null; // NEW
let WORLD = { w: 800, h: 600 };
let players = {};
let joined = false;

//chat messaging
const chatDiv = document.getElementById('chat');
const messagesDiv = document.getElementById('messages');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
let typing = false;
let speechBubbles = {};

chatInput.addEventListener("focus",()=>{typing=true})
chatInput.addEventListener("blur",()=>{typing=false})

// canvas setup
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
function resize() {
  const scale = Math.min(window.innerWidth / WORLD.w, window.innerHeight / WORLD.h) * 0.95;
  canvas.width = Math.round(WORLD.w * scale);
  canvas.height = Math.round(WORLD.h * scale);
  ctx.setTransform(canvas.width / WORLD.w, 0, 0, canvas.height / WORLD.h, 0, 0);
}
window.addEventListener('resize', resize);

socket.on('init', (d) => {
  myId = d.id;
  currentRoom = d.room; 
  WORLD.w = d.w; WORLD.h = d.h;
  joined = true;
  resize();
});

socket.on('state', (d) => {
  if (d.room !== currentRoom) return;
  players = d.players || {};
  console.log('STATE RECEIVED', d.room, d.players ? Object.keys(d.players).length : 0);
});

// input handling
let keys = { up:false, down:false, left:false, right:false };
function sendInput(){
  if(!joined) return; // don't spam server before joining
  let dx = 0, dy = 0;
  if(keys.left) dx -= 1;
  if(keys.right) dx += 1;
  if(keys.up) dy -= 1;
  if(keys.down) dy += 1;
  socket.emit('input', {dx, dy});
}

chatForm.addEventListener('submit', e => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if(text){
    socket.emit('chat_message', text);
    chatInput.value = '';
  }
});

socket.on('chat_message', data => {
  const msgElem = document.createElement('div');
  const nameSpan = document.createElement('span');
  nameSpan.textContent = data.username + ': ';
  nameSpan.style.color = data.color;
  const textSpan = document.createElement('span');
  textSpan.textContent = data.text;
  msgElem.appendChild(nameSpan);
  msgElem.appendChild(textSpan);
  messagesDiv.appendChild(msgElem);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  speechBubbles[data.id] = { text: data.text, color: data.color, timer: Date.now() };
});

socket.on('init', () => {
  chatDiv.style.display = 'block';
});

socket.on('left_room', () => {
  chatDiv.style.display = 'none';
  messagesDiv.innerHTML = '';
  speechBubbles = {};
});

window.addEventListener('keydown', (e)=>{
  if(!typing){
    if(e.key === 'ArrowUp' || e.key === 'w') keys.up = true;
    if(e.key === 'ArrowDown' || e.key === 's') keys.down = true;
    if(e.key === 'ArrowLeft' || e.key === 'a') keys.left = true;
    if(e.key === 'ArrowRight' || e.key === 'd') keys.right = true;
    sendInput();
  }
});
window.addEventListener('keyup', (e)=>{
  if(e.key === 'ArrowUp' || e.key === 'w') keys.up = false;
  if(e.key === 'ArrowDown' || e.key === 's') keys.down = false;
  if(e.key === 'ArrowLeft' || e.key === 'a') keys.left = false;
  if(e.key === 'ArrowRight' || e.key === 'd') keys.right = false;
  sendInput();
});

// rendering
function render(){
  window.addEventListener("blur",()=>{
    keys.right =false;
    keys.left =false;
    keys.up =false;
    keys.down =false;
  })
  ctx.clearRect(0,0,WORLD.w,WORLD.h);
  ctx.save();
  ctx.globalAlpha = 0.06;
  for(let x=0;x<WORLD.w;x+=40){ctx.fillRect(x,0,1,WORLD.h)}
  for(let y=0;y<WORLD.h;y+=40){ctx.fillRect(0,y,WORLD.w,1)}
  ctx.restore();

  for(const sid in players){
    console.log("test")
    const p = players[sid];
    const x = p.x; const y = p.y; const r = p.r || 16;
    ctx.beginPath();
    ctx.arc(x,y,r,0,Math.PI*2);
    ctx.fillStyle = p.color || '#999';
    ctx.fill();
    if(sid === myId){
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = '#fff';
      ctx.stroke();
    } else {
      ctx.lineWidth = 1.0;
      ctx.strokeStyle = 'rgba(255,255,255,0.08)';
      ctx.stroke();
    }
    
    // draw username
    if(p.username){
        ctx.fillStyle = '#fff';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(p.username, x, y - r - 6);
    }

    //draw speech bubbles if active
    if (speechBubbles[p.id] && Date.now() - speechBubbles[p.id].timer < 3000) {
      const bubbleText = speechBubbles[p.id].text;
      const padding = 10;
      ctx.font = '10px sans-serif';
      const textWidth = ctx.measureText(bubbleText).width;
      const bubbleWidth = textWidth + padding * 2;
      const bubbleX = p.x - bubbleWidth / 2;
      const bubbleY = p.y - 50;

      ctx.fillStyle = 'rgba(0,0,0,0.7)';
      ctx.fillRect(bubbleX, bubbleY, bubbleWidth, 20);
      ctx.fillStyle = 'white';
      ctx.fillText(bubbleText, p.x, p.y - 36);
    } else if (speechBubbles[p.id] && Date.now() - speechBubbles[p.id].timer >= 3000) {
      delete speechBubbles[p.id];
    }
  }
  requestAnimationFrame(render);
}


requestAnimationFrame(render);

// function draw() {
//   ctx.clearRect(0, 0, WORLD.w, WORLD.h);
//   for (const id in players) {
//     const p = players[id];
//     ctx.fillStyle = p.color;
//     ctx.beginPath();
//     ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
//     ctx.fill();
//   }
//   requestAnimationFrame(draw);
// }
// draw();

// send input regularly
setInterval(sendInput, 100);