const body = document.body;
const trinity = document.getElementById('morpheus-container'); // Die ID im HTML lassen wir vorerst gleich
const overlay = document.getElementById('content-overlay');
const closeBtn = document.getElementById('close-btn');
const statusText = document.getElementById('status-text');

let heartInterval = null;
let angryInterval = null;

function spawnHeart() {
    if (!body.classList.contains('love')) return;
    const heart = document.createElement('div');
    heart.className = 'floating-heart';
    heart.innerText = ['❤️', '💖', '💝', '💕'][Math.floor(Math.random() * 4)];
    
    // Zufällige Position rund um Trinity
    const x = Math.random() * 80 - 10;
    heart.style.left = x + 'px';
    heart.style.top = '10px';
    heart.style.fontSize = (Math.random() * 10 + 10) + 'px';
    
    trinity.appendChild(heart);
    setTimeout(() => heart.remove(), 2000);
}

function spawnAngryParticle() {
    if (!body.classList.contains('angry')) return;
    const p = document.createElement('div');
    p.className = 'angry-particle';
    p.innerText = ['⚡', '🔥', '💢', '☄️'][Math.floor(Math.random() * 4)];
    p.style.color = 'red';
    
    const x = Math.random() * 100 - 20;
    const y = Math.random() * 40 - 20;
    p.style.left = x + 'px';
    p.style.top = y + 'px';
    p.style.fontSize = (Math.random() * 15 + 10) + 'px';
    
    trinity.appendChild(p);
    setTimeout(() => p.remove(), 600);
}

// State Manager global verfügbar machen, damit Python (runJavaScript) ihn aufrufen kann
window.setTrinityState = (state) => {
    if (state === 'invisible') {
        body.classList.add('hidden-mode');
        return;
    } else if (state === 'visible') {
        body.classList.remove('hidden-mode');
        return;
    }

    const isHidden = body.classList.contains('hidden-mode');
    body.className = state;
    if (isHidden) body.classList.add('hidden-mode');
    
    statusText.innerText = state === 'idle' ? 'Trinity' : state.charAt(0).toUpperCase() + state.slice(1);
    
    if (state === 'reporting') {
        overlay.classList.remove('hidden');
    } else {
        overlay.classList.add('hidden');
    }

    // Intervalle aufräumen
    clearInterval(heartInterval);
    clearInterval(angryInterval);

    if (state === 'love') {
        heartInterval = setInterval(spawnHeart, 300);
        for(let i=0; i<3; i++) setTimeout(spawnHeart, i*100);
    } else if (state === 'angry') {
        angryInterval = setInterval(spawnAngryParticle, 150);
        for(let i=0; i<3; i++) setTimeout(spawnAngryParticle, i*50);
    }
};

window.setBubbleColor = (color) => {
    const bubble = document.getElementById('notification-bubble');
    if (!color || color === 'none') {
        bubble.className = 'hidden';
    } else {
        bubble.className = `bubble-${color}`;
    }
};



// Klick auf Trinity simuliert Zustandswechsel (nur für optisches Feedback)
trinity.addEventListener('click', () => {
    if (body.classList.contains('idle')) {
        window.setTrinityState('listening');
    } else if (body.classList.contains('listening')) {
        window.setTrinityState('thinking');
    } else {
        window.setTrinityState('idle');
    }
});

// Doppel-Klick öffnet das Dashboard mit den Infos
trinity.addEventListener('dblclick', () => {
    window.setTrinityState('reporting');
});

closeBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    window.setTrinityState('idle');
});

// Funktion für den Agenten, um Content im Hintergrund zu speichern
window.displayContent = (title, html) => {
    document.getElementById('content-title').innerText = title;
    document.getElementById('content-body').innerHTML = html;
    window.setTrinityState('thinking'); 
};

// Startzustand
document.addEventListener('DOMContentLoaded', () => {
    if (typeof window.setTrinityState === 'function') {
        window.setTrinityState('idle');
    }

    // Slogan nach Verzögerung einblenden
    const slogan = document.getElementById('slogan-text');
    setTimeout(() => {
        if (slogan) slogan.classList.add('visible');
    }, 1500);

    // Hover-Effekte für Slogan
    trinity.addEventListener('mouseenter', () => {
        if (slogan) slogan.classList.add('visible');
    });
    
    // Optional: Slogan nach einiger Zeit im Idle wieder ausblenden (für extremen Minimalismus)
    // setTimeout(() => {
    //     if (slogan && body.classList.contains('idle')) slogan.classList.remove('visible');
    // }, 10000);
});
