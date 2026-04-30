const body = document.body;
const trinity = document.getElementById('morpheus-container'); // Die ID im HTML lassen wir vorerst gleich
const overlay = document.getElementById('content-overlay');
const closeBtn = document.getElementById('close-btn');
const statusText = document.getElementById('status-text');

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
window.setTrinityState('idle');
