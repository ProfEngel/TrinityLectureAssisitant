import os

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(word in router_text for word in ["game of life", "simulation", "ameisen", "ant", "raumzeit", "krümmung", "pong", "bienen", "bee", "piraten", "fischer", "spieltheorie", "sort", "neural", "netz"])

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
    elif "neural" in lower_query or "netz" in lower_query:
        title = "Neuronales Netz (Forward Pass)"
        desc = "Animierte Visualisierung eines neuronalen Netzes. Datenpakete fließen von links nach rechts."
        sim_script = resize_logic + """
        const ctx = canvas.getContext('2d');
        let nodes = [];
        let edges = [];
        let packets = [];
        const layers = [4, 6, 6, 3];
        
        function init() {
            nodes = []; edges = []; packets = [];
            let startX = 100;
            let gapX = (canvas.width - 200) / (layers.length - 1);
            
            // Create nodes
            let layerNodes = [];
            for(let l=0; l<layers.length; l++) {
                let n = layers[l];
                let gapY = (canvas.height - 100) / n;
                let startY = (canvas.height - (gapY * (n-1))) / 2;
                let currLayer = [];
                for(let i=0; i<n; i++) {
                    let node = {x: startX + l*gapX, y: startY + i*gapY, layer: l};
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

        function draw() {
            ctx.fillStyle = 'rgba(0,0,0,0.2)';
            ctx.fillRect(0,0,canvas.width,canvas.height);
            
            // Randomly spawn packets from input layer
            if(Math.random() < 0.1) {
                let inputNodes = nodes.filter(n => n.layer === 0);
                let startNode = inputNodes[Math.floor(Math.random() * inputNodes.length)];
                let possibleEdges = edges.filter(e => e.from === startNode);
                if(possibleEdges.length > 0) {
                    let edge = possibleEdges[Math.floor(Math.random() * possibleEdges.length)];
                    packets.push({edge: edge, progress: 0});
                }
            }
            
            // Draw edges
            ctx.lineWidth = 1;
            for(let e of edges) {
                ctx.beginPath(); ctx.moveTo(e.from.x, e.from.y); ctx.lineTo(e.to.x, e.to.y);
                ctx.strokeStyle = `rgba(255, 255, 255, ${e.weight * 0.2})`;
                ctx.stroke();
            }
            
            // Update & Draw packets
            for(let i=packets.length-1; i>=0; i--) {
                let p = packets[i];
                p.progress += 0.02;
                
                let px = p.edge.from.x + (p.edge.to.x - p.edge.from.x) * p.progress;
                let py = p.edge.from.y + (p.edge.to.y - p.edge.from.y) * p.progress;
                
                ctx.beginPath(); ctx.arc(px, py, 3, 0, Math.PI*2);
                ctx.fillStyle = '#00ffff'; ctx.fill();
                ctx.shadowBlur = 10; ctx.shadowColor = '#00ffff';
                
                if(p.progress >= 1) {
                    ctx.shadowBlur = 0;
                    if(p.edge.to.layer < layers.length - 1) {
                        let nextEdges = edges.filter(e => e.from === p.edge.to);
                        for(let ne of nextEdges) {
                            if(Math.random() < 0.3) {
                                packets.push({edge: ne, progress: 0});
                            }
                        }
                    }
                    packets.splice(i, 1);
                }
            }
            ctx.shadowBlur = 0;
            
            // Draw nodes
            for(let n of nodes) {
                ctx.beginPath(); ctx.arc(n.x, n.y, 10, 0, Math.PI*2);
                ctx.fillStyle = '#222'; ctx.fill();
                ctx.lineWidth = 2; ctx.strokeStyle = n.layer === 0 ? '#00bfff' : (n.layer === layers.length-1 ? '#ff33aa' : '#ffffff');
                ctx.stroke();
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
