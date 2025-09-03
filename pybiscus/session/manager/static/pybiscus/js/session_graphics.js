
// **** accuracies drawing *****

function drawAccuracyBars(ctx, values, options = {}) {
    const {
        originX = 10,
        originY = 10,
        elementWidth = 12,
        gap = 2,
        maxBarHeight = 50,
        maxAccuracies = 40,
        alignment = 'left', // 'left' or 'right'
    } = options;

    ctx.save();

    // Calculate the total width of the maximum displayable area
    const totalWidth = maxAccuracies * (elementWidth + gap) - gap;
    const totalHeight = maxBarHeight;

    // Draw the background rectangle (light gray with high transparency)
    ctx.fillStyle = 'rgba(200, 200, 200, 0.2)'; // Light gray with 20% opacity
    const cornerRadius = 8;
    
    // Draw rounded rectangle for the maximum occupiable space
    ctx.beginPath();
    ctx.roundRect(originX - gap, originY - totalHeight - gap, totalWidth + 2 * gap, totalHeight + 2 * gap, cornerRadius);
    ctx.fill();

    // Calculate starting position based on alignment
    let startX;
    if (alignment === 'right') {
        // For right alignment, start from the right edge of the max area
        startX = originX + totalWidth - (values.length * (elementWidth + gap) - gap);
    } else {
        // For left alignment (default), start from originX
        startX = originX;
    }

    // Draw the accuracy bars
    for (let i = 0; i < values.length; i++) {
        const val = values[i];       // accuracy (between 0 and 1)
        const error = 1 - val;      // error rate
        const x = startX + i * (elementWidth + gap);

        const correctHeight = val * maxBarHeight;
        const errorHeight = error * maxBarHeight;

        // Green part at bottom (success)
        ctx.fillStyle = '#4CAF50'; // green
        ctx.fillRect(x, originY - correctHeight, elementWidth, correctHeight);

        // Red part on top (error)
        ctx.fillStyle = '#F44336'; // red
        ctx.fillRect(x, originY - correctHeight - errorHeight, elementWidth, errorHeight);
    }

    // Draw horizontal axis line (base of the bars)
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(startX - gap, originY);
    ctx.lineTo(startX + values.length * (elementWidth + gap), originY);
    ctx.stroke();

    ctx.restore();
}

// **** durations drawing *****

function drawDurations(ctx, durations, options = {}) {

    if (durations.length === 0) return;

    const {
        originX = 10,
        originY = 10,
        barWidth = 40,
        maxBarHeight = 64,
        gap = 10,
    } = options;

    ctx.save();

    const max = Math.max(...durations);

    durations.forEach((duration, i) => {
        const scale = duration / max;
        const barHeight = scale * maxBarHeight;

        const x = originX + i * (barWidth + gap);
        const y = originY - barHeight;

        ctx.fillStyle = '#4A90E2';
        ctx.fillRect(x, y, barWidth, barHeight);

        ctx.fillStyle = '#000';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${duration}s`, x + barWidth / 2, y - 5);
    });        

    ctx.restore();
}

// **** sparkbar drawing *****

function drawSparkbar(ctx, values, options = {}) {

    const {
        originX = 10,
        originY = 10,
        elementWidth = 6,
        gap = 2,
        maxBarHeight = 32,
        epsilon = 0.01,
    } = options;

    ctx.save();

    const maxAbs = Math.max(...values.map(v => Math.abs(v)), epsilon);

    for (let i = 0; i < values.length; i++) {
        const val = values[i];
        const x = originX + i * (elementWidth + gap);
        const height = (Math.abs(val) / maxAbs) * maxBarHeight;

        let color;
        if (Math.abs(val) < epsilon) {
        color = '#9E9E9E'; // gris pour proche de 0
        } else if (val > 0) {
        color = '#4CAF50'; // vert pour positif
        } else {
        color = '#F44336'; // rouge pour négatif
        }

        ctx.fillStyle = color;

        if (Math.abs(val) < epsilon) {
        // Barre proche de zéro: une ligne horizontale fine
        ctx.fillRect(x, originY - 1, elementWidth, 2);
        } else if (val > 0) {
        // barre vers le haut
        ctx.fillRect(x, originY - height, elementWidth, height);
        } else {
        // barre vers le bas
        ctx.fillRect(x, originY, elementWidth, height);
        }
    }

    // Dessiner la ligne d'axe horizontal
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(originX - gap, originY);
    ctx.lineTo(originX + values.length * (elementWidth + gap), originY);
    ctx.stroke();

    ctx.restore();
}

// **** session graph drawing *****

const sessionStatusColors = {
    "paramsUndefined": {
        ringColor: "#FFA500"  // orange
    },
    "paramsDefined": {
        ringColor: "green"
    },
    "sessionCompleted": {
        ringColor: "black"
    },
};

const agentStatusColors = {
    "declared": {
        diskColor: "#D3D3D3", // lightgray
        ringColor: "#696969"  // dimgray
    },
    "validating": {
        diskColor: "#FFD700", // gold
        ringColor: "#FFA500"  // orange
    },
    "validated": {
        diskColor: "#90EE90", // lightgreen
        ringColor: "#006400"  // darkgreen
    },
    "not validated" : {
        diskColor: "#FF6B6B",    // light red
        ringColor: "#B22222"     // Firebrick
    },
    "executing": {
        diskColor: "#4682B4", // steelblue
        ringColor: "#00008B"  // darkblue
    },
    "terminated": {
        diskColor: "#FFFFFF", // white
        ringColor: "#228B22"  // forestgreen (or "#000000" for black)
    }
};

class SessionGraph {
    constructor() {

        this.rotation = 0;
        this.rotation_increment = 0.05;
    }

    draw(ctx,session,servers,clients, options = {}) {

        ctx.save();

        const {
            centerX = 150,
            centerY = 150,
        } = options;

        const radius = 120;
        const angleStep = (2 * Math.PI) / clients.length;
        
        // --- bouquet circle ---

        const sessionRingColor = sessionStatusColors[session.sessionState].ringColor;

        ctx.strokeStyle = sessionRingColor;
        ctx.setLineDash([5, 5]); // dashed circle
        ctx.lineWidth = 2.5;

        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
        ctx.stroke();

        ctx.setLineDash([]); // reset dash style

        servers.forEach((server, i) => {

            // --- Draw server ---
            const { diskColor, ringColor } = agentStatusColors[session.getAgentState(server)];
            ctx.fillStyle   = diskColor;
            ctx.strokeStyle = ringColor;

            ctx.beginPath();
            ctx.lineWidth = 5;
            ctx.arc(centerX, centerY, 30, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
            ctx.fillStyle = "white";
            ctx.font = "12px Arial";
            ctx.textAlign = "center";
            ctx.fillText("Server", centerX, centerY + 4);

            ctx.fillStyle = "black";

            if ([0, 1, 2, 3, 10, 11].includes(session.roundNumber % 12)) {
                ctx.fillText(server, centerX, centerY + 48);
            } else {
                ctx.fillText(server, centerX, centerY - 48);
            }

            // --- Draw roundNumber ---
            const roundNumber_radius = 54;
            const roundNumber_diameter = 14;

            const sector = 2 * Math.PI / 12;
            const angle = sector * (session.roundNumber - 3);

            const x = centerX + roundNumber_radius * Math.cos(angle);
            const y = centerY + roundNumber_radius * Math.sin(angle);

            ctx.beginPath();
            ctx.lineWidth = 2;
            ctx.fillStyle   = "red";
            ctx.strokeStyle = "black";
            ctx.beginPath();
            ctx.arc(x, y, roundNumber_diameter, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
            ctx.fillStyle = "white";
            ctx.fillText(session.roundNumber, x, y + 4 );
        });

        clients.forEach((client, i) => {
            const angle = this.rotation + i * angleStep;
            const x = centerX + radius * Math.cos(angle);
            const y = centerY + radius * Math.sin(angle);

            // --- Draw client ---
            const { diskColor, ringColor } = agentStatusColors[session.getAgentState(client)];
            ctx.fillStyle   = diskColor;
            ctx.strokeStyle = ringColor;

            ctx.beginPath();
            ctx.lineWidth = 5;
            ctx.arc(x, y, 20, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
            ctx.fillStyle = "black";
            ctx.font = "12px Arial";
            ctx.textAlign = "center";
            ctx.fillText(client, x, y + 32);
        });

        this.rotation += this.rotation_increment;

        ctx.restore();
    }
}

