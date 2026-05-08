import os

def can_handle(query: str) -> bool:
    router_text = query.lower()
    return any(word in router_text for word in ["game of life", "simulation", "ameisen", "ant", "raumzeit", "krümmung", "pong"])

def execute(query: str, context: dict = None) -> dict:
    lower_query = query.lower()
    title = "Simulation"
    sim_script = ""
    desc = ""
    
    if "raumzeit" in lower_query or "krümmung" in lower_query or "gummi" in lower_query:
        title = "Raumzeitkrümmung"
        desc = "Visualisierung einer Gravitationssenke."
        sim_script = """
        const canvas = document.getElementById('simCanvas');
        const ctx = canvas.getContext('2d');
        let time = 0;
        function draw() {
            ctx.fillStyle = 'rgba(0,0,0,1)';
            ctx.fillRect(0,0,canvas.width,canvas.height);
            ctx.strokeStyle = 'rgba(0, 191, 255, 0.4)';
            ctx.lineWidth = 1;
            
            let cx = canvas.width/2;
            let cy = canvas.height/2 - 50;
            
            for(let x=-12; x<=12; x++) {
                for(let y=-12; y<=12; y++) {
                    let dist = Math.sqrt(x*x + y*y);
                    let depth = 80 / (dist + 1.5); // Gravitationssenke
                    
                    // Isometric projection
                    let isoX = cx + (x - y) * 12;
                    let isoY = cy + (x + y) * 6 + depth + Math.sin(time + dist)*3;
                    
                    if (x < 12) {
                        let ndist = Math.sqrt((x+1)*(x+1) + y*y);
                        let ndepth = 80 / (ndist + 1.5);
                        let nisoX = cx + (x+1 - y) * 12;
                        let nisoY = cy + (x+1 + y) * 6 + ndepth + Math.sin(time + ndist)*3;
                        ctx.beginPath(); ctx.moveTo(isoX, isoY); ctx.lineTo(nisoX, nisoY); ctx.stroke();
                    }
                    if (y < 12) {
                        let ndist = Math.sqrt(x*x + (y+1)*(y+1));
                        let ndepth = 80 / (ndist + 1.5);
                        let nisoX = cx + (x - (y+1)) * 12;
                        let nisoY = cy + (x + (y+1)) * 6 + ndepth + Math.sin(time + ndist)*3;
                        ctx.beginPath(); ctx.moveTo(isoX, isoY); ctx.lineTo(nisoX, nisoY); ctx.stroke();
                    }
                }
            }
            
            // Masse im Zentrum
            ctx.beginPath();
            ctx.arc(cx, cy + 60 + Math.sin(time)*3, 12, 0, Math.PI*2);
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
        sim_script = """
        const canvas = document.getElementById('simCanvas');
        const ctx = canvas.getContext('2d');
        const res = 5;
        const cols = canvas.width / res;
        const rows = canvas.height / res;
        let grid = Array(cols).fill().map(() => Array(rows).fill(0));
        let x = Math.floor(cols/2);
        let y = Math.floor(rows/2);
        let dir = 0; // 0=up, 1=right, 2=down, 3=left
        
        ctx.fillStyle = '#000';
        ctx.fillRect(0,0,canvas.width,canvas.height);

        function draw() {
            for(let n=0; n<50; n++) { // 50 Schritte pro Frame
                let state = grid[x][y];
                if (state === 0) {
                    dir = (dir + 1) % 4; // Rechts drehen
                    grid[x][y] = 1;
                    ctx.fillStyle = '#00bfff';
                } else {
                    dir = (dir + 3) % 4; // Links drehen
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
        sim_script = """
        const canvas = document.getElementById('simCanvas');
        const ctx = canvas.getContext('2d');
        let ball = {x: 155, y: 155, vx: 4, vy: 3, radius: 5};
        let pad1 = {y: 130, width: 6, height: 50};
        let pad2 = {y: 130, width: 6, height: 50};
        
        function draw() {
            ctx.fillStyle = '#000';
            ctx.fillRect(0,0,canvas.width,canvas.height);
            
            // Mittellinie
            ctx.setLineDash([5, 15]);
            ctx.beginPath(); ctx.moveTo(155, 0); ctx.lineTo(155, 310);
            ctx.strokeStyle = '#333'; ctx.stroke(); ctx.setLineDash([]);
            
            // Physik
            ball.x += ball.vx;
            ball.y += ball.vy;
            if(ball.y <= 0 || ball.y >= 310) ball.vy *= -1;
            
            // AI (Paddles folgen dem Ball mit leichter Verzögerung)
            pad1.y += (ball.y - (pad1.y + 25)) * 0.1;
            pad2.y += (ball.y - (pad2.y + 25)) * 0.12;
            
            // Kollision
            if(ball.x - ball.radius <= 16 && ball.y >= pad1.y && ball.y <= pad1.y+50) { ball.vx *= -1; ball.x = 16 + ball.radius; }
            if(ball.x + ball.radius >= 294 && ball.y >= pad2.y && ball.y <= pad2.y+50) { ball.vx *= -1; ball.x = 294 - ball.radius; }
            
            // Reset
            if(ball.x < 0 || ball.x > 310) { ball.x = 155; ball.y = 155; ball.vx *= -1; }
            
            // Zeichnen
            ctx.fillStyle = '#fff';
            ctx.fillRect(10, pad1.y, pad1.width, pad1.height);
            ctx.fillRect(294, pad2.y, pad2.width, pad2.height);
            
            ctx.beginPath();
            ctx.arc(ball.x, ball.y, ball.radius, 0, Math.PI*2);
            ctx.fillStyle = '#00bfff';
            ctx.fill();
            
            requestAnimationFrame(draw);
        }
        draw();
        """
    else:
        title = "Conway's Game of Life"
        desc = "Zellulärer Automat mit simplen Überlebensregeln."
        sim_script = """
        const canvas = document.getElementById('simCanvas');
        const ctx = canvas.getContext('2d');
        const res = 10;
        const cols = canvas.width / res;
        const rows = canvas.height / res;
        let grid = Array(cols).fill().map(() => Array(rows).fill(0).map(() => Math.floor(Math.random() * 2)));

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
    <div style="width: 100%; display: flex; justify-content: center;">
        <canvas id="simCanvas" width="310" height="310" style="background: #000; border-radius: 10px;"></canvas>
    </div>
    <script>
        {sim_script}
    </script>
    """
    
    search_context = f"--- AGENTIC ACTION ---\nDu hast soeben erfolgreich die JavaScript-Simulation '{title}' im UI gestartet. Bestätige dem Nutzer kurz, dass die Simulation nun im Nebenfenster läuft und erkläre in einem Satz das grundlegende Konzept hinter dieser Simulation.\n\n"
    
    return {
        "has_payload": True,
        "html_payload": html_payload,
        "search_context": search_context
    }
