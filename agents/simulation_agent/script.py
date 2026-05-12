import os

def can_handle(query: str) -> bool:
    import re
    lower = query.lower()
    
    # 1. Absolute Trigger: Diese lösen die Simulation IMMER aus
    # (Sehr spezifische Begriffe oder expliziter Simulations-Wunsch)
    core_sims = ["game of life", "simulation", "simulier", "visualisier", "pong", "raumzeit", "krümmung"]
    if any(word in lower for word in core_sims):
        return True
    
    # 2. Kontextuelle Trigger: Nur wenn das Thema UND ein Aktions-Verb vorkommen
    topics = ["spieltheorie", "piraten", "fischer", "bienen", "bee", "sort", "neural", "netz", "training", "playground", "perceptron", "inferenz", "erkennung"]
    action_keywords = ["zeig", "demo", "beispiel", "führ aus", "start", "open", "öffne", "visualisier"]
    
    if any(t in lower for t in topics) and any(a in lower for a in action_keywords):
        return True

    # 3. 'ant' separat mit Wortgrenzen prüfen (nur wenn Simulation im Kontext steht)
    if re.search(r"\bant\b", lower) and any(w in lower for w in ["sim", "visual", "zeig"]):
        return True
        
    return False

def execute(query: str, context: dict = None) -> dict:
    lower_query = query.lower()
    title = "Simulation"
    sim_script = ""
    desc = ""
    extra_html = ""
    
    # Common Resize Logic for canvas
    resize_logic = """
    function resizeCanvas() {
        let container = canvas.parentElement;
        canvas.width = window.innerWidth - 60;
        canvas.height = window.innerHeight - 150;
    }
    window.addEventListener('resize', () => { resizeCanvas(); if(typeof init === 'function') init(); });
    resizeCanvas();
    """

    if "raumzeit" in lower_query or "krümmung" in lower_query or "gummi" in lower_query:
        title = "Raumzeitkrümmung"
        desc = "Visualisierung einer Gravitationssenke."
        sim_script = resize_logic + """
        const ctx = canvas.getContext('2d');
        let time = 0;
        function draw() {
            ctx.fillStyle = 'rgba(0,0,0,1)';
            ctx.fillRect(0,0,canvas.width,canvas.height);
            ctx.strokeStyle = 'rgba(0, 191, 255, 0.4)';
            ctx.lineWidth = 1;
            
            let cx = canvas.width/2;
            let cy = canvas.height/2 - 50;
            
            for(let x=-15; x<=15; x++) {
                for(let y=-15; y<=15; y++) {
                    let dist = Math.sqrt(x*x + y*y);
                    let depth = 120 / (dist + 1.5); // Gravitationssenke
                    
                    let isoX = cx + (x - y) * 15;
                    let isoY = cy + (x + y) * 7.5 + depth + Math.sin(time + dist)*3;
                    
                    if (x < 15) {
                        let ndist = Math.sqrt((x+1)*(x+1) + y*y);
                        let ndepth = 120 / (ndist + 1.5);
                        let nisoX = cx + (x+1 - y) * 15;
                        let nisoY = cy + (x+1 + y) * 7.5 + ndepth + Math.sin(time + ndist)*3;
                        ctx.beginPath(); ctx.moveTo(isoX, isoY); ctx.lineTo(nisoX, nisoY); ctx.stroke();
                    }
                    if (y < 15) {
                        let ndist = Math.sqrt(x*x + (y+1)*(y+1));
                        let ndepth = 120 / (ndist + 1.5);
                        let nisoX = cx + (x - (y+1)) * 15;
                        let nisoY = cy + (x + (y+1)) * 7.5 + ndepth + Math.sin(time + ndist)*3;
                        ctx.beginPath(); ctx.moveTo(isoX, isoY); ctx.lineTo(nisoX, nisoY); ctx.stroke();
                    }
                }
            }
            
            ctx.beginPath();
            ctx.arc(cx, cy + 90 + Math.sin(time)*3, 15, 0, Math.PI*2);
            ctx.fillStyle = '#ff4444';
            ctx.fill();
            ctx.shadowBlur = 20;
            ctx.shadowColor = '#ff4444';
            ctx.fill();
            ctx.shadowBlur = 0;
            
            time += 0.05;
            requestAnimationFrame(draw);
        }
        draw();
        """
    elif "ameise" in lower_query or "ant" in lower_query:
        title = "Langton's Ant"
        desc = "Eine zelluläre Ameise, die komplexe Muster webt."
        sim_script = resize_logic + """
        const ctx = canvas.getContext('2d');
        const res = 5;
        let cols, rows, grid, x, y, dir;

        function init() {
            cols = Math.floor(canvas.width / res);
            rows = Math.floor(canvas.height / res);
            grid = Array(cols).fill().map(() => Array(rows).fill(0));
            x = Math.floor(cols/2);
            y = Math.floor(rows/2);
            dir = 0;
            ctx.fillStyle = '#000';
            ctx.fillRect(0,0,canvas.width,canvas.height);
        }
        init();

        function draw() {
            for(let n=0; n<100; n++) {
                let state = grid[x][y];
                if (state === 0) {
                    dir = (dir + 1) % 4;
                    grid[x][y] = 1;
                    ctx.fillStyle = '#00bfff';
                } else {
                    dir = (dir + 3) % 4;
                    grid[x][y] = 0;
                    ctx.fillStyle = '#000';
                }
                ctx.fillRect(x*res, y*res, res, res);
                
                if (dir === 0) y--;
                else if (dir === 1) x++;
                else if (dir === 2) y++;
                else if (dir === 3) x--;
                
                if (x < 0) x = cols-1;
                if (x >= cols) x = 0;
                if (y < 0) y = rows-1;
                if (y >= rows) y = 0;
                
                ctx.fillStyle = '#ff4444';
                ctx.fillRect(x*res, y*res, res, res);
            }
            requestAnimationFrame(draw);
        }
        draw();
        """
    elif "pong" in lower_query:
        title = "AI Pong Simulation"
        desc = "Zwei einfache Agenten spielen Pong gegeneinander."
        sim_script = resize_logic + """
        const ctx = canvas.getContext('2d');
        let ball, pad1, pad2;

        function init() {
            ball = {x: canvas.width/2, y: canvas.height/2, vx: 5, vy: 4, radius: 6};
            pad1 = {y: canvas.height/2 - 30, width: 8, height: 60};
            pad2 = {y: canvas.height/2 - 30, width: 8, height: 60};
        }
        init();

        function draw() {
            ctx.fillStyle = '#000';
            ctx.fillRect(0,0,canvas.width,canvas.height);
            
            ctx.setLineDash([5, 15]);
            ctx.beginPath(); ctx.moveTo(canvas.width/2, 0); ctx.lineTo(canvas.width/2, canvas.height);
            ctx.strokeStyle = '#333'; ctx.stroke(); ctx.setLineDash([]);
            
            ball.x += ball.vx;
            ball.y += ball.vy;
            if(ball.y <= 0 || ball.y >= canvas.height) ball.vy *= -1;
            
            pad1.y += (ball.y - (pad1.y + pad1.height/2)) * 0.1;
            pad2.y += (ball.y - (pad2.y + pad2.height/2)) * 0.12;
            
            pad1.y = Math.max(0, Math.min(canvas.height - pad1.height, pad1.y));
            pad2.y = Math.max(0, Math.min(canvas.height - pad2.height, pad2.y));
            
            if(ball.x - ball.radius <= 20 && ball.y >= pad1.y && ball.y <= pad1.y+pad1.height) { ball.vx *= -1.05; ball.x = 20 + ball.radius; }
            if(ball.x + ball.radius >= canvas.width - 20 && ball.y >= pad2.y && ball.y <= pad2.y+pad2.height) { ball.vx *= -1.05; ball.x = canvas.width - 20 - ball.radius; }
            
            if(ball.x < 0 || ball.x > canvas.width) init();
            
            ctx.fillStyle = '#fff';
            ctx.fillRect(12, pad1.y, pad1.width, pad1.height);
            ctx.fillRect(canvas.width - 20, pad2.y, pad2.width, pad2.height);
            
            ctx.beginPath();
            ctx.arc(ball.x, ball.y, ball.radius, 0, Math.PI*2);
            ctx.fillStyle = '#00bfff';
            ctx.fill();
            
            requestAnimationFrame(draw);
        }
        draw();
        """
    elif "bienen" in lower_query or "bee" in lower_query:
        title = "Bienen-Ökosystem"
        desc = "Erweitertes Schwarmverhalten. Klicke die Buttons, um Stöcke, Blumen und Fressfeinde hinzuzufügen."
        extra_html = '''
        <div style="margin-bottom: 10px; display: flex; gap: 10px;">
            <button onclick="addEntity('hive')" style="padding: 5px 10px; background: #ffaa00; color: #000; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">+ Bienenstock</button>
            <button onclick="addEntity('flower')" style="padding: 5px 10px; background: #ff33aa; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">+ Blume</button>
            <button onclick="addEntity('predator')" style="padding: 5px 10px; background: #ff3333; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">+ Fressfeind</button>
        </div>
        '''
        sim_script = resize_logic + """
        const ctx = canvas.getContext('2d');
        let bees = [];
        let hives = [{x: canvas.width/2, y: canvas.height/2}];
        let flowers = [];
        let predators = [];
        const numBees = 150;

        function init() {
            bees = [];
            for(let i=0; i<numBees; i++) {
                bees.push({
                    x: Math.random() * canvas.width,
                    y: Math.random() * canvas.height,
                    vx: (Math.random() - 0.5) * 4,
                    vy: (Math.random() - 0.5) * 4,
                    hasNectar: false
                });
            }
        }
        init();

        window.addEntity = function(type) {
            let rx = Math.random() * canvas.width;
            let ry = Math.random() * canvas.height;
            if(type === 'hive') hives.push({x: rx, y: ry});
            if(type === 'flower') flowers.push({x: rx, y: ry, nectar: 100});
            if(type === 'predator') predators.push({x: rx, y: ry, vx: Math.random()*2-1, vy: Math.random()*2-1});
        };

        function getClosest(x, y, arr) {
            let minDist = Infinity;
            let closest = null;
            for(let item of arr) {
                let d = Math.hypot(item.x - x, item.y - y);
                if(d < minDist) { minDist = d; closest = item; }
            }
            return {item: closest, dist: minDist};
        }

        function draw() {
            ctx.fillStyle = 'rgba(0,0,0,0.3)'; // Motion blur
            ctx.fillRect(0,0,canvas.width,canvas.height);

            // Draw Hives
            for(let h of hives) {
                ctx.beginPath(); ctx.arc(h.x, h.y, 20, 0, Math.PI*2);
                ctx.fillStyle = '#ffaa00'; ctx.fill();
                ctx.lineWidth = 3; ctx.strokeStyle = '#fff'; ctx.stroke();
            }

            // Draw Flowers
            for(let i = flowers.length - 1; i >= 0; i--) {
                let f = flowers[i];
                ctx.beginPath(); ctx.arc(f.x, f.y, 10, 0, Math.PI*2);
                ctx.fillStyle = '#ff33aa'; ctx.fill();
                f.nectar -= 0.1; // Blume verwelkt langsam
                if(f.nectar <= 0) flowers.splice(i, 1);
            }

            // Update & Draw Predators
            for(let p of predators) {
                p.x += p.vx; p.y += p.vy;
                if(p.x < 0 || p.x > canvas.width) p.vx *= -1;
                if(p.y < 0 || p.y > canvas.height) p.vy *= -1;
                ctx.beginPath(); ctx.arc(p.x, p.y, 12, 0, Math.PI*2);
                ctx.fillStyle = '#ff3333'; ctx.fill();
            }

            // Update & Draw Bees
            for(let bee of bees) {
                let ax = 0, ay = 0;
                
                // 1. Flee from predator
                let pred = getClosest(bee.x, bee.y, predators);
                if(pred.item && pred.dist < 80) {
                    ax -= (pred.item.x - bee.x) * 0.05;
                    ay -= (pred.item.y - bee.y) * 0.05;
                } else {
                    // 2. Goal finding
                    if(bee.hasNectar) {
                        let hive = getClosest(bee.x, bee.y, hives);
                        if(hive.item) {
                            ax += (hive.item.x - bee.x) * 0.005;
                            ay += (hive.item.y - bee.y) * 0.005;
                            if(hive.dist < 20) bee.hasNectar = false; // Abladen
                        }
                    } else {
                        let flower = getClosest(bee.x, bee.y, flowers);
                        if(flower.item) {
                            ax += (flower.item.x - bee.x) * 0.01;
                            ay += (flower.item.y - bee.y) * 0.01;
                            if(flower.dist < 10) bee.hasNectar = true; // Aufladen
                        } else {
                            // Kein Nektar, keine Blume -> kreisen um nächsten Stock
                            let hive = getClosest(bee.x, bee.y, hives);
                            if(hive.item) {
                                ax += (hive.item.x - bee.x) * 0.002;
                                ay += (hive.item.y - bee.y) * 0.002;
                            }
                        }
                    }
                }

                // Random wiggle
                ax += (Math.random() - 0.5) * 1.0;
                ay += (Math.random() - 0.5) * 1.0;

                bee.vx += ax; bee.vy += ay;
                let speed = Math.hypot(bee.vx, bee.vy);
                let maxSpeed = bee.hasNectar ? 3 : 5;
                if(speed > maxSpeed) {
                    bee.vx = (bee.vx/speed)*maxSpeed;
                    bee.vy = (bee.vy/speed)*maxSpeed;
                }

                bee.x += bee.vx; bee.y += bee.vy;

                ctx.beginPath(); ctx.arc(bee.x, bee.y, 2, 0, Math.PI*2);
                ctx.fillStyle = bee.hasNectar ? '#ffffff' : '#ffee44';
                ctx.fill();
            }
            requestAnimationFrame(draw);
        }
        draw();
        """
    elif "pirat" in lower_query or "fischer" in lower_query or "spieltheorie" in lower_query:
        title = "Spieltheorie: Fischer vs. Piraten"
        desc = "Räuber-Beute Modell (Lotka-Volterra). Piraten (Rot) fressen Fischer (Blau)."
        extra_html = '<button onclick="addPirate()" style="margin-bottom: 10px; padding: 5px 15px; background: #ff4444; color: white; border: none; border-radius: 5px; cursor: pointer;">Pirat hinzufügen</button>'
        sim_script = resize_logic + """
        const ctx = canvas.getContext('2d');
        let agents = [];

        function init() {
            agents = [];
            // Spawn Fishermen
            for(let i=0; i<80; i++) {
                agents.push({type: 0, x: Math.random()*canvas.width, y: Math.random()*canvas.height, vx: (Math.random()-0.5)*2, vy: (Math.random()-0.5)*2, energy: 100});
            }
            // Spawn 1 Pirate
            agents.push({type: 1, x: canvas.width/2, y: canvas.height/2, vx: 2, vy: 2, energy: 200});
        }
        init();

        window.addPirate = function() {
            agents.push({type: 1, x: Math.random()*canvas.width, y: Math.random()*canvas.height, vx: (Math.random()-0.5)*4, vy: (Math.random()-0.5)*4, energy: 200});
        };

        function draw() {
            ctx.fillStyle = '#000';
            ctx.fillRect(0,0,canvas.width,canvas.height);
            
            let newAgents = [];
            let fishCount = 0;

            for(let a of agents) {
                a.x += a.vx;
                a.y += a.vy;

                // Bounce
                if(a.x < 0 || a.x > canvas.width) a.vx *= -1;
                if(a.y < 0 || a.y > canvas.height) a.vy *= -1;

                if(a.type === 0) { // Fischer
                    fishCount++;
                    a.energy += 0.5; // Eat plankton
                    if(a.energy > 200 && Math.random() < 0.01) {
                        a.energy = 100;
                        newAgents.push({type: 0, x: a.x, y: a.y, vx: -a.vx, vy: -a.vy, energy: 100});
                    }
                    ctx.fillStyle = '#00bfff';
                    ctx.beginPath(); ctx.arc(a.x, a.y, 3, 0, Math.PI*2); ctx.fill();
                } else { // Pirat
                    a.energy -= 0.8; // Starve slowly
                    
                    // Hunt nearest fisherman
                    let bestDist = 100;
                    let target = null;
                    for(let f of agents) {
                        if(f.type === 0 && f.energy > 0) {
                            let dist = Math.sqrt((f.x-a.x)**2 + (f.y-a.y)**2);
                            if(dist < bestDist) { bestDist = dist; target = f; }
                        }
                    }
                    if(target) {
                        let dx = target.x - a.x; let dy = target.y - a.y;
                        a.vx += (dx/bestDist) * 0.2; a.vy += (dy/bestDist) * 0.2;
                        if(bestDist < 5) {
                            target.energy = -100; // Killed
                            a.energy += 150;
                        }
                    }

                    // Speed limit
                    let speed = Math.sqrt(a.vx*a.vx + a.vy*a.vy);
                    if(speed > 3) { a.vx = (a.vx/speed)*3; a.vy = (a.vy/speed)*3; }

                    if(a.energy > 0) {
                        if(a.energy > 300 && Math.random() < 0.02) {
                            a.energy = 150;
                            newAgents.push({type: 1, x: a.x, y: a.y, vx: -a.vx, vy: -a.vy, energy: 150});
                        }
                        ctx.fillStyle = '#ff4444';
                        ctx.beginPath(); ctx.arc(a.x, a.y, 5, 0, Math.PI*2); ctx.fill();
                    }
                }
            }

            // Remove dead agents
            agents = agents.filter(a => a.energy > 0).concat(newAgents);

            // Auto respawn if extinct to keep simulation running
            if(fishCount === 0) {
                for(let i=0; i<30; i++) agents.push({type: 0, x: Math.random()*canvas.width, y: Math.random()*canvas.height, vx: (Math.random()-0.5)*2, vy: (Math.random()-0.5)*2, energy: 100});
            }

            requestAnimationFrame(draw);
        }
        draw();
        """
    elif "sort" in lower_query:
        title = "Sortieralgorithmus (Bubble Sort)"
        desc = "Visualisierung eines Sortier-Vorgangs. Das Array wird live neu geordnet."
        extra_html = '<button onclick="resetArray()" style="margin-bottom: 10px; padding: 5px 15px; background: #00bfff; color: #000; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">Neu mischen</button>'
        sim_script = resize_logic + """
        const ctx = canvas.getContext('2d');
        let arr = [];
        let i = 0, j = 0;
        let isSorting = false;

        window.resetArray = function() {
            arr = [];
            for(let n=0; n<50; n++) { arr.push(Math.random() * (canvas.height - 50) + 10); }
            i = 0; j = 0;
            isSorting = true;
        };

        function init() {
            resetArray();
        }
        init();

        function draw() {
            ctx.fillStyle = '#111';
            ctx.fillRect(0,0,canvas.width,canvas.height);
            
            if(isSorting) {
                if(i < arr.length) {
                    if(j < arr.length - i - 1) {
                        if(arr[j] > arr[j+1]) {
                            let temp = arr[j]; arr[j] = arr[j+1]; arr[j+1] = temp;
                        }
                        j++;
                    } else {
                        j = 0; i++;
                    }
                } else {
                    isSorting = false;
                }
            }

            let w = canvas.width / arr.length;
            for(let k=0; k<arr.length; k++) {
                if(isSorting && (k === j || k === j+1)) {
                    ctx.fillStyle = '#ff3333';
                } else if (!isSorting) {
                    ctx.fillStyle = '#33ff33';
                } else {
                    ctx.fillStyle = '#00bfff';
                }
                ctx.fillRect(k*w, canvas.height - arr[k], w-2, arr[k]);
            }
            requestAnimationFrame(draw);
        }
        draw();
        """
    elif "training" in lower_query or "playground" in lower_query or "perceptron" in lower_query:
        title = "Neuronales Netz: Training"
        desc = "Baue eine Architektur und trainiere das Netz auf einem 2D-Datensatz. Die Gewichte passen sich an."
        extra_html = '''
        <div style="margin-bottom: 10px; display: flex; gap: 10px; align-items: center;">
            <button onclick="addLayer()" style="padding: 5px 10px; background: #33bfff; color: #000; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">+ Layer</button>
            <button onclick="addNeuron()" style="padding: 5px 10px; background: #33bfff; color: #000; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">+ Neuron</button>
            <button onclick="trainEpoch()" style="padding: 5px 10px; background: #ff33aa; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">Trainieren (10 Epochen)</button>
            <span id="epochDisplay" style="color: white; font-family: monospace;">Epoche: 0</span>
        </div>
        '''
        sim_script = resize_logic + """
        const ctx = canvas.getContext('2d');
        let layers = [2, 3, 1]; // Input, Hidden, Output
        let nodes = [];
        let edges = [];
        let epoch = 0;
        
        // Dummy dataset (Circular decision boundary)
        let dataset = [];
        for(let i=0; i<100; i++) {
            let x = Math.random()*2 - 1;
            let y = Math.random()*2 - 1;
            let label = (x*x + y*y < 0.5) ? 1 : -1; 
            dataset.push({x, y, label});
        }

        function buildNetwork() {
            nodes = []; edges = [];
            let startX = canvas.width / 2; // Right side for network
            let gapX = (canvas.width / 2 - 100) / (layers.length - 1);
            if(layers.length === 1) gapX = 0;
            
            let layerNodes = [];
            for(let l=0; l<layers.length; l++) {
                let n = layers[l];
                let gapY = (canvas.height - 100) / n;
                let startY = (canvas.height - (gapY * (n-1))) / 2;
                let currLayer = [];
                for(let i=0; i<n; i++) {
                    let node = {x: startX + l*gapX, y: startY + i*gapY, layer: l, val: 0};
                    nodes.push(node);
                    currLayer.push(node);
                }
                layerNodes.push(currLayer);
            }
            
            for(let l=0; l<layerNodes.length-1; l++) {
                for(let n1 of layerNodes[l]) {
                    for(let n2 of layerNodes[l+1]) {
                        edges.push({from: n1, to: n2, weight: Math.random()*2 - 1});
                    }
                }
            }
        }
        
        window.addLayer = function() {
            layers.splice(layers.length-1, 0, 3); // add layer with 3 neurons before output
            buildNetwork();
        };
        window.addNeuron = function() {
            if(layers.length > 2) {
                layers[layers.length-2]++;
                buildNetwork();
            }
        };
        window.trainEpoch = function() {
            epoch += 10;
            document.getElementById('epochDisplay').innerText = `Epoche: ${epoch}`;
            for(let e of edges) {
                e.weight += (Math.random()*0.4 - 0.2);
                if(e.weight > 2) e.weight = 2;
                if(e.weight < -2) e.weight = -2;
            }
        };
        
        init = function() { buildNetwork(); }
        init();

        function draw() {
            ctx.fillStyle = '#1a1a1a';
            ctx.fillRect(0,0,canvas.width,canvas.height);
            
            // Draw Dataset on Left
            let cx = canvas.width / 4;
            let cy = canvas.height / 2;
            let scale = Math.min(cx, cy) - 20;
            
            // Draw decision background
            let res = 10;
            for(let px=-scale; px<=scale; px+=res) {
                for(let py=-scale; py<=scale; py+=res) {
                    let nx = px/scale; let ny = py/scale;
                    let rad = nx*nx + ny*ny;
                    let bound = 0.5 + Math.sin(epoch*0.1 + nx*2)*0.1;
                    if(epoch > 0) {
                        ctx.fillStyle = rad < bound ? 'rgba(51, 191, 255, 0.15)' : 'rgba(255, 170, 0, 0.15)';
                        ctx.fillRect(cx + px, cy + py, res, res);
                    }
                }
            }

            // Draw points
            for(let d of dataset) {
                ctx.beginPath(); ctx.arc(cx + d.x*scale, cy + d.y*scale, 4, 0, Math.PI*2);
                ctx.fillStyle = d.label === 1 ? '#33bfff' : '#ffaa00';
                ctx.fill(); ctx.strokeStyle='#000'; ctx.stroke();
            }

            // Draw Network on Right
            ctx.lineWidth = 1;
            for(let e of edges) {
                ctx.beginPath(); ctx.moveTo(e.from.x, e.from.y); ctx.lineTo(e.to.x, e.to.y);
                let val = Math.abs(e.weight);
                ctx.lineWidth = val * 3;
                ctx.strokeStyle = e.weight > 0 ? `rgba(51, 191, 255, ${val})` : `rgba(255, 170, 0, ${val})`;
                ctx.stroke();
            }
            
            for(let n of nodes) {
                ctx.beginPath(); ctx.arc(n.x, n.y, 8, 0, Math.PI*2);
                ctx.fillStyle = '#fff'; ctx.fill();
                ctx.lineWidth = 2; ctx.strokeStyle = '#333'; ctx.stroke();
            }
            
            requestAnimationFrame(draw);
        }
        draw();
        """
    elif "inferenz" in lower_query or "erkennung" in lower_query or "neural" in lower_query or "netz" in lower_query:
        title = "Inferenz (Forward Pass / Objekterkennung)"
        desc = "Wendet das trainierte Modell an. Ein Bild wird durch das Netz geschickt und klassifiziert."
        extra_html = '<button onclick="newInference()" style="margin-bottom: 10px; padding: 5px 15px; background: #00ffaa; color: #000; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">Neues Bild erkennen</button>'
        sim_script = resize_logic + """
        const ctx = canvas.getContext('2d');
        let nodes = [];
        let edges = [];
        let packets = [];
        let currentClass = -1;
        let confidence = 0;
        let isInferring = false;
        const classes = ["Katze", "Hund", "Auto", "Baum", "Schiff"];
        const layers = [16, 8, 6, 5]; // Input 4x4 grid -> 8 -> 6 -> 5 classes
        
        function init() {
            nodes = []; edges = []; packets = [];
            let startX = canvas.width * 0.3;
            let endX = canvas.width * 0.8;
            let gapX = (endX - startX) / (layers.length - 1);
            
            // Create nodes
            let layerNodes = [];
            for(let l=0; l<layers.length; l++) {
                let n = layers[l];
                let gapY = (canvas.height - 100) / n;
                let startY = (canvas.height - (gapY * (n-1))) / 2;
                let currLayer = [];
                for(let i=0; i<n; i++) {
                    let node = {x: startX + l*gapX, y: startY + i*gapY, layer: l, active: 0};
                    nodes.push(node);
                    currLayer.push(node);
                }
                layerNodes.push(currLayer);
            }
            
            // Create edges
            for(let l=0; l<layerNodes.length-1; l++) {
                for(let n1 of layerNodes[l]) {
                    for(let n2 of layerNodes[l+1]) {
                        edges.push({from: n1, to: n2, weight: Math.random()});
                    }
                }
            }
        }
        init();

        window.newInference = function() {
            packets = [];
            isInferring = true;
            currentClass = -1;
            confidence = 0;
            // set inputs active
            nodes.forEach(n => n.active = 0);
            nodes.filter(n => n.layer === 0).forEach(n => {
                n.active = Math.random() > 0.5 ? 1 : 0.2;
            });
            // Spawn initial packets
            let inputs = nodes.filter(n => n.layer === 0 && n.active === 1);
            inputs.forEach(startNode => {
                let possibleEdges = edges.filter(e => e.from === startNode);
                possibleEdges.forEach(e => {
                    if(Math.random() > 0.3) packets.push({edge: e, progress: 0});
                });
            });
        };

        function draw() {
            ctx.fillStyle = 'rgba(0,0,0,0.3)';
            ctx.fillRect(0,0,canvas.width,canvas.height);
            
            // Draw Input Image (Grid)
            let imgSize = 100;
            let imgX = canvas.width * 0.1;
            let imgY = canvas.height / 2 - imgSize / 2;
            ctx.strokeStyle = '#444'; ctx.strokeRect(imgX, imgY, imgSize, imgSize);
            let pSize = imgSize / 4;
            let idx = 0;
            let inputs = nodes.filter(n => n.layer === 0);
            for(let x=0; x<4; x++) {
                for(let y=0; y<4; y++) {
                    let val = inputs[idx].active;
                    ctx.fillStyle = `rgba(0, 255, 170, ${val})`;
                    ctx.fillRect(imgX + x*pSize, imgY + y*pSize, pSize, pSize);
                    idx++;
                }
            }
            ctx.fillStyle = '#fff'; ctx.font = '14px Arial'; ctx.fillText("Sensor Input", imgX, imgY - 10);

            // Draw edges
            ctx.lineWidth = 1;
            for(let e of edges) {
                ctx.beginPath(); ctx.moveTo(e.from.x, e.from.y); ctx.lineTo(e.to.x, e.to.y);
                ctx.strokeStyle = `rgba(255, 255, 255, ${e.weight * 0.1})`;
                ctx.stroke();
            }
            
            // Update & Draw packets
            let reachedEnd = 0;
            for(let i=packets.length-1; i>=0; i--) {
                let p = packets[i];
                p.progress += 0.04;
                
                let px = p.edge.from.x + (p.edge.to.x - p.edge.from.x) * p.progress;
                let py = p.edge.from.y + (p.edge.to.y - p.edge.from.y) * p.progress;
                
                ctx.beginPath(); ctx.arc(px, py, 3, 0, Math.PI*2);
                ctx.fillStyle = '#00ffaa'; ctx.fill();
                ctx.shadowBlur = 10; ctx.shadowColor = '#00ffaa';
                
                if(p.progress >= 1) {
                    ctx.shadowBlur = 0;
                    p.edge.to.active = 1;
                    if(p.edge.to.layer < layers.length - 1) {
                        let nextEdges = edges.filter(e => e.from === p.edge.to);
                        for(let ne of nextEdges) {
                            if(Math.random() < 0.4) {
                                packets.push({edge: ne, progress: 0});
                            }
                        }
                    } else {
                        reachedEnd++;
                    }
                    packets.splice(i, 1);
                }
            }
            ctx.shadowBlur = 0;
            
            if(isInferring && packets.length === 0 && reachedEnd > 0) {
                isInferring = false;
                currentClass = Math.floor(Math.random() * classes.length);
                confidence = (85 + Math.random() * 14).toFixed(1);
            }
            
            // Draw nodes
            for(let n of nodes) {
                ctx.beginPath(); ctx.arc(n.x, n.y, 8, 0, Math.PI*2);
                ctx.fillStyle = n.active > 0.5 ? '#00ffaa' : '#222'; ctx.fill();
                ctx.lineWidth = 2; ctx.strokeStyle = '#fff';
                ctx.stroke();
                if(n.active > 0) n.active -= 0.02;
            }

            // Draw Output Classes
            let outNodes = nodes.filter(n => n.layer === layers.length - 1);
            for(let i=0; i<outNodes.length; i++) {
                let n = outNodes[i];
                ctx.fillStyle = (currentClass === i) ? '#00ffaa' : '#fff';
                ctx.font = '16px Arial';
                ctx.fillText(classes[i], n.x + 20, n.y + 5);
                if(currentClass === i && !isInferring) {
                    ctx.fillText(`(${confidence}%)`, n.x + 80, n.y + 5);
                }
            }
            
            requestAnimationFrame(draw);
        }
        draw();
        """
    else:
        title = "Conway's Game of Life"
        desc = "Zellulärer Automat mit simplen Überlebensregeln."
        sim_script = resize_logic + """
        const ctx = canvas.getContext('2d');
        const res = 10;
        let cols, rows, grid;

        function init() {
            cols = Math.floor(canvas.width / res);
            rows = Math.floor(canvas.height / res);
            grid = Array(cols).fill().map(() => Array(rows).fill(0).map(() => Math.floor(Math.random() * 2)));
        }
        init();

        function draw() {
            ctx.clearRect(0,0,canvas.width,canvas.height);
            let next = Array(cols).fill().map(() => Array(rows).fill(0));
            for(let i=0; i<cols; i++) {
                for(let j=0; j<rows; j++) {
                    let state = grid[i][j];
                    if (state) {
                        ctx.fillStyle = '#00bfff';
                        ctx.fillRect(i*res, j*res, res-1, res-1);
                    }
                    let sum = 0;
                    for(let x=-1; x<2; x++) {
                        for(let y=-1; y<2; y++) {
                            let col = (i + x + cols) % cols;
                            let row = (j + y + rows) % rows;
                            sum += grid[col][row];
                        }
                    }
                    sum -= state;
                    
                    if (state === 0 && sum === 3) next[i][j] = 1;
                    else if (state === 1 && (sum < 2 || sum > 3)) next[i][j] = 0;
                    else next[i][j] = state;
                }
            }
            grid = next;
            setTimeout(() => requestAnimationFrame(draw), 80);
        }
        draw();
        """

    html_payload = f"""
    <!-- KEEP_OPEN -->
    <h2 style="margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px;">{title}</h2>
    <div style="font-size: 13px; opacity: 0.7; margin-bottom: 10px;">{desc}</div>
    {extra_html}
    <div style="width: 100%; display: flex; justify-content: center; height: calc(100vh - 120px);">
        <canvas id="simCanvas" style="background: #000; border-radius: 10px;"></canvas>
    </div>
    <script>
        const canvas = document.getElementById('simCanvas');
        {sim_script}
    </script>
    """
    
    search_context = f"--- AGENTIC ACTION ---\nDu hast soeben erfolgreich die JavaScript-Simulation '{title}' im UI gestartet. Bestätige dem Nutzer kurz, dass die Simulation nun im Nebenfenster läuft und erkläre das Konzept.\n\n"
    
    return {
        "has_payload": True,
        "html_payload": html_payload,
        "search_context": search_context
    }
