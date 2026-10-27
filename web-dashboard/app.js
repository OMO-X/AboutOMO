/**
 * OMOWAY CAN Bus Telemetry Cockpit - Frontend Logic
 */

// Subsystem & CAN ID Dictionary mapping
const CAN_DICTIONARY = {
    '0x142': { name: 'Fast Powertrain Loop', cat: 'powertrain' },
    '0x104': { name: 'Motor Dynamics / MCU Inverter', cat: 'powertrain' },
    '0x112': { name: 'Switch Status / Cluster Mode', cat: 'safety' },
    '0x114': { name: 'VCU Telemetry Loop', cat: 'powertrain' },
    '0x122': { name: 'Vehicle Speed (B4) & Cruise Control (B2)', cat: 'powertrain' },
    '0x132': { name: 'Controller Inverter Status', cat: 'powertrain' },
    '0x143': { name: 'High-Res Rolling Tick Timer', cat: 'powertrain' },
    '0x202': { name: 'VCU Drive Mode & Speed Target', cat: 'powertrain' },
    '0x203': { name: 'Powertrain Feedback Limits', cat: 'powertrain' },
    '0x206': { name: 'Inverter Target Current/Torque', cat: 'powertrain' },
    '0x213': { name: 'Motor BLDC RPM (B3-B4, Offset -0x8000)', cat: 'powertrain' },
    '0x214': { name: 'Thermal Status MCU/Motor', cat: 'powertrain' },
    '0x216': { name: 'Brake Regenerative Status', cat: 'safety' },
    '0x223': { name: 'Trip & Distance Tracking', cat: 'body' },
    '0x224': { name: 'Vehicle Configuration Payload', cat: 'body' },
    '0x226': { name: 'Cluster Tick & Dynamic Brake Flag', cat: 'safety' },
    '0x233': { name: 'Vehicle Speed (B0) & Lighting', cat: 'powertrain' },
    '0x234': { name: 'Auxiliary Power Systems', cat: 'body' },
    '0x236': { name: 'Regen Braking Torque Request', cat: 'safety' },
    '0x244': { name: 'Diagnostic Link Heartbeat', cat: 'body' },
    '0x262': { name: 'Kickstand & Brake Switch (B4)', cat: 'safety' },
    '0x272': { name: 'VCU Hardware Identifiers', cat: 'body' },
    '0x282': { name: 'Cluster Battery SOC Display', cat: 'bms' },
    '0x302': { name: 'Cruise Control & Riding Profiles', cat: 'powertrain' },
    '0x303': { name: 'VCU System Uptime Heartbeat', cat: 'body' },
    '0x304': { name: 'Headlamp & Ambient Light', cat: 'body' },
    '0x306': { name: 'Inverter Operating Mode / Config', cat: 'powertrain' },
    '0x323': { name: 'BLDC Motor (B5) & Inverter MCU (B4) Temp', cat: 'powertrain' },
    '0x502': { name: 'BMS Global Fault & Alarm Flags', cat: 'bms' },
    '0x503': { name: 'BMS Battery Pack Temp Probes (1..4)', cat: 'bms' },
    '0x504': { name: 'BMS Cell Voltages 1 - 4 (mV)', cat: 'bms' },
    '0x512': { name: 'BMS Battery Serial & Security', cat: 'bms' },
    '0x514': { name: 'BMS Cell Voltages 5 - 8 (mV)', cat: 'bms' },
    '0x522': { name: 'BMS Battery SOH & Cycles', cat: 'bms' },
    '0x524': { name: 'BMS Cell Voltages 9 - 12 (mV)', cat: 'bms' },
    '0x534': { name: 'BMS Cell Voltages 13 - 16 (mV)', cat: 'bms' },
    '0x544': { name: 'BMS Cell Voltages 17 - 20 (mV)', cat: 'bms' },
    '0x554': { name: 'BMS Cell Voltages 21 - 24 (mV)', cat: 'bms' },
    '0x564': { name: 'BMS Total Current & Pack Voltage', cat: 'bms' },
    '0x5F4': { name: 'BMS Auxiliary Temperature Module', cat: 'bms' }
};

// Global App State
const state = {
    source: 'live', // 'live' or 'replay'
    connected: false,
    totalFrames: 0,
    fps: 0,
    cells: Array(24).fill(3288), // 24 LFP cells in mV
    temps: [31, 31, 31, 31],
    tempModule: 30,
    brakeSwitch: false,
    brakeDyn: false,
    brakeRawSwitch: '0x00',
    brakeRawDyn: '0x00',
    regenTorque: 0,
    drl: {
        bytes: [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
        mode: 'off',
        lastMode: 'off',
        candidateMode: 'off',
        candidateSince: 0,
        pwmLeft: 0,
        pwmRight: 0,
        activeCount: 0
    },
    frames: {}, // cid -> { lastBytes, prevBytes, count, freq, lastSeen, dlc }
    filterCat: 'all',
    searchQuery: '',
    ignitionStatus: 0,
    lastCANMessageTime: Date.now(),
    speed: 0,
    cruise: false,
    rpm: 0,
    tempMcu: 31,
    tempBldc: 26,
    odoKm: 2117.0,
    tripStartOdo: null
};

// Initialize BMS 24-Cell Grid DOM
function initBMSGrid() {
    const grid = document.getElementById('cells-grid');
    grid.innerHTML = '';
    for (let i = 1; i <= 24; i++) {
        const cell = document.createElement('div');
        cell.className = 'cell-card';
        cell.id = `cell-${i}`;
        cell.innerHTML = `
            <span class="cell-num">CELL ${i.toString().padStart(2, '0')}</span>
            <span class="cell-voltage" id="cell-val-${i}">3.288 V</span>
            <div class="cell-bar-wrap">
                <div class="cell-bar" id="cell-bar-${i}" style="width: 75%;"></div>
            </div>
        `;
        grid.appendChild(cell);
    }
}

// Initialize Physical DRL Component (32 Addressable Diode Nodes)
function initDRLComponent() {
    const leftWing = document.getElementById('drl-left-wing');
    const rightWing = document.getElementById('drl-right-wing');
    if (!leftWing || !rightWing) return;

    leftWing.innerHTML = '';
    rightWing.innerHTML = '';

    // Left Wing: 16 Addressable Segments (L01..L16)
    // L01..L09 -> Driver Channel 0 (Outer Left)
    // L10..L16 -> Driver Channel 1 (Inner Left)
    for (let i = 1; i <= 16; i++) {
        const ch = i <= 9 ? 'CH0' : 'CH1';
        const seg = document.createElement('div');
        seg.className = 'drl-led-segment';
        seg.id = `drl-seg-L-${i}`;
        seg.title = `Left Diode L${i.toString().padStart(2, '0')} (Driver ${ch})`;
        seg.innerHTML = `
            <span class="led-addr-label">L${i.toString().padStart(2, '0')}</span>
            <div class="led-diode-core"></div>
            <span class="led-bit-label">${ch}</span>
        `;
        leftWing.appendChild(seg);
    }

    // Right Wing: 16 Addressable Segments (R01..R16)
    // R01..R07 -> Driver Channel 2 (Inner Right)
    // R08..R16 -> Driver Channel 3 (Outer Right)
    for (let i = 1; i <= 16; i++) {
        const ch = i <= 7 ? 'CH2' : 'CH3';
        const seg = document.createElement('div');
        seg.className = 'drl-led-segment';
        seg.id = `drl-seg-R-${i}`;
        seg.title = `Right Diode R${i.toString().padStart(2, '0')} (Driver ${ch})`;
        seg.innerHTML = `
            <span class="led-addr-label">R${i.toString().padStart(2, '0')}</span>
            <div class="led-diode-core"></div>
            <span class="led-bit-label">${ch}</span>
        `;
        rightWing.appendChild(seg);
    }
}

// Update BMS Telemetry Visuals
function updateBMSVisuals() {
    let totalMv = 0;
    let minMv = Infinity;
    let maxMv = -Infinity;

    state.cells.forEach((mv, idx) => {
        totalMv += mv;
        if (mv < minMv) minMv = mv;
        if (mv > maxMv) maxMv = mv;

        const valElem = document.getElementById(`cell-val-${idx + 1}`);
        const barElem = document.getElementById(`cell-bar-${idx + 1}`);
        if (valElem && barElem) {
            valElem.textContent = (mv / 1000).toFixed(3) + ' V';
            // Scale bar between 3000mV (0%) and 3650mV (100%)
            const percent = Math.min(100, Math.max(0, ((mv - 3000) / 650) * 100));
            barElem.style.width = percent.toFixed(1) + '%';
        }
    });

    const packVoltage = (totalMv / 1000).toFixed(2);
    const avgMv = Math.round(totalMv / 24);
    const deltaMv = maxMv - minMv;

    document.getElementById('pack-voltage-val').textContent = packVoltage;
    document.getElementById('cell-avg-val').textContent = `${avgMv} mV`;
    document.getElementById('cell-delta-val').textContent = `${deltaMv} mV`;

    // Temperature widgets
    document.getElementById('pack-temp-val').textContent = state.temps[0] || 31;
    document.getElementById('temp-probes-val').textContent = state.temps.map(t => `${t}°C`).join(' / ');
    document.getElementById('temp-module-val').textContent = `${state.tempModule}°C`;
}

// Unpack 40-bit CAN registers (B1..B5) into 4 driver channels (9 bits each = 36 data bits)
function unpackDRLBits(b1, b2, b3, b4, b5) {
    const high = ((b1 << 24) | (b2 << 16) | (b3 << 8) | b4) >>> 0;
    const low = b5;
    const bitstr40 = high.toString(2).padStart(32, '0') + low.toString(2).padStart(8, '0');

    // 4 channels of 10 bits each, drop leading bit 0 to get 9 data bits per channel:
    // Ch0: bits 1..9   (9 bits) -> Left Wing Outer
    // Ch1: bits 11..19 (9 bits) -> Left Wing Inner
    // Ch2: bits 21..29 (9 bits) -> Right Wing Inner
    // Ch3: bits 31..39 (9 bits) -> Right Wing Outer
    const ch0 = bitstr40.slice(1, 10);
    const ch1 = bitstr40.slice(11, 20);
    const ch2 = bitstr40.slice(21, 30);
    const ch3 = bitstr40.slice(31, 40);

    const left18 = ch0 + ch1;   // 18 bits for Left Wing
    const right18 = ch2 + ch3;  // 18 bits for Right Wing

    // Each wing has 16 physical LED segments
    const left16 = left18.slice(0, 16);
    const right16 = right18.slice(0, 16);

    const leftAllLit = (left16 === '1111111111111111');
    const rightAllLit = (right16 === '1111111111111111');
    const allOn = leftAllLit && rightAllLit;

    return { bitstr40, ch0, ch1, ch2, ch3, left18, right18, left16, right16, leftAllLit, rightAllLit, allOn };
}

// Update DRL Headlight Visuals and Stable Telemetry
function updateDRLVisuals(bytes) {
    if (!bytes || bytes.length < 8) return;

    state.drl.bytes = bytes;
    const b0 = bytes[0];
    const b1 = bytes[1];
    const b2 = bytes[2];
    const b3 = bytes[3];
    const b4 = bytes[4];
    const b5 = bytes[5];
    const dutyL = bytes[6];
    const dutyR = bytes[7];

    state.drl.pwmLeft = dutyL;
    state.drl.pwmRight = dutyR;

    const unpacked = unpackDRLBits(b1, b2, b3, b4, b5);
    const isOffPayload = bytes.every(x => x === 0);
    const isPowered = (dutyL > 0 || dutyR > 0) && !isOffPayload;
    const isIgnitionOn = (state.ignitionStatus === 0x03) || (state.frames['0x112'] && state.frames['0x112'].bytes[1] === 0x03);

    let detectedMode = 'off';
    let modeLabel = 'DRL MATI (STANDBY)';
    let dotClass = 'mode-off';
    let statusTag = 'Mati (0V / 0%)';

    if (!isPowered) {
        // No PWM power or all bytes 0 -> DRL is completely OFF
        detectedMode = 'off';
        modeLabel = 'DRL MATI (STANDBY)';
        dotClass = 'mode-off';
        statusTag = 'Mati (0V / 0%)';
    } else if (unpacked.allOn || (isIgnitionOn && dutyL >= 100)) {
        // All 16 left & 16 right diodes active, or Ignition is ON with normal operating PWM (120 / 47%) -> 100% Solid Continuous ON!
        detectedMode = 'solid';
        modeLabel = 'DRL NYALA FULL (SOLID)';
        dotClass = 'mode-solid';
        statusTag = 'Solid Statis (Nyala Penuh)';
    } else {
        // Channels are cycling patterns -> Breathing / Running Sweep
        detectedMode = 'breathing';
        modeLabel = 'DRL BERNAFAS / BERGERAK';
        dotClass = 'mode-breathing';
        statusTag = 'Animasi Ritmik Dinamis';
    }

    // Update UI elements for mode
    state.drl.mode = detectedMode;
    const modeDot = document.getElementById('drl-mode-dot');
    const modeName = document.getElementById('drl-mode-name');
    const animSpeed = document.getElementById('drl-anim-speed');
    const housing = document.querySelector('.headlight-housing');

    if (modeDot && !modeDot.classList.contains(dotClass)) {
        modeDot.className = `drl-mode-dot ${dotClass}`;
    }
    if (modeName && modeName.textContent !== modeLabel) {
        modeName.textContent = modeLabel;
    }
    if (animSpeed && animSpeed.textContent !== statusTag) {
        animSpeed.textContent = statusTag;
    }
    if (housing) {
        if (detectedMode === 'breathing') {
            housing.classList.add('mode-breathing');
        } else {
            housing.classList.remove('mode-breathing');
        }
    }

    // Stable numeric values & progress bars
    const isLampOn = (detectedMode === 'solid' || detectedMode === 'breathing');
    const displayDutyL = isLampOn ? dutyL : 0;
    const displayDutyR = isLampOn ? dutyR : 0;
    const pctL = ((displayDutyL / 255) * 100).toFixed(1);
    const pctR = ((displayDutyR / 255) * 100).toFixed(1);

    const numL = document.getElementById('drl-pwm-left-num');
    const pctElemL = document.getElementById('drl-pwm-left-pct');
    const barL = document.getElementById('drl-pwm-left-bar');
    if (numL) numL.textContent = displayDutyL;
    if (pctElemL) {
        pctElemL.textContent = (detectedMode === 'breathing') ? `(Puncak ${pctL}%)` : `(${pctL}%)`;
    }
    if (barL) barL.style.width = `${pctL}%`;

    const numR = document.getElementById('drl-pwm-right-num');
    const pctElemR = document.getElementById('drl-pwm-right-pct');
    const barR = document.getElementById('drl-pwm-right-bar');
    if (numR) numR.textContent = displayDutyR;
    if (pctElemR) {
        pctElemR.textContent = (detectedMode === 'breathing') ? `(Puncak ${pctR}%)` : `(${pctR}%)`;
    }
    if (barR) barR.style.width = `${pctR}%`;

    // Update Register Chips
    const r1 = document.getElementById('reg-b1');
    const r2 = document.getElementById('reg-b2');
    const r3 = document.getElementById('reg-b3');
    const r4 = document.getElementById('reg-b4');
    const r5 = document.getElementById('reg-b5');
    if (r1) r1.textContent = '0x' + b1.toString(16).toUpperCase().padStart(2, '0');
    if (r2) r2.textContent = '0x' + b2.toString(16).toUpperCase().padStart(2, '0');
    if (r3) r3.textContent = '0x' + b3.toString(16).toUpperCase().padStart(2, '0');
    if (r4) r4.textContent = '0x' + b4.toString(16).toUpperCase().padStart(2, '0');
    if (r5) r5.textContent = '0x' + b5.toString(16).toUpperCase().padStart(2, '0');

    const preview = document.getElementById('drl-raw-can-preview');
    if (preview) {
        preview.textContent = `Payload: ${bytes.map(b => b.toString(16).toUpperCase().padStart(2, '0')).join(' ')}`;
    }

    // Update Individual 16 Left Wing LED Segments
    let activeLeftCount = 0;
    for (let i = 1; i <= 16; i++) {
        const seg = document.getElementById(`drl-seg-L-${i}`);
        if (!seg) continue;

        let isLit = false;
        if (isLampOn) {
            if (detectedMode === 'solid') {
                isLit = true; // All 16 left segments solid lit
            } else {
                isLit = (unpacked.left16[i - 1] === '1');
            }
        }

        if (isLit) {
            seg.classList.add('lit');
            seg.style.setProperty('--led-brightness', '1.0');
            seg.style.setProperty('--glow-intensity', (dutyL / 255).toFixed(2));
            activeLeftCount++;
        } else {
            seg.classList.remove('lit');
            seg.style.removeProperty('--led-brightness');
            seg.style.removeProperty('--glow-intensity');
        }
    }

    // Update Individual 16 Right Wing LED Segments (Symmetrical to Left Wing)
    let activeRightCount = 0;
    for (let i = 1; i <= 16; i++) {
        const seg = document.getElementById(`drl-seg-R-${i}`);
        if (!seg) continue;

        let isLit = false;
        if (isLampOn) {
            if (detectedMode === 'solid') {
                isLit = true; // All 16 right segments solid lit
            } else {
                isLit = (unpacked.right16[i - 1] === '1');
            }
        }

        if (isLit) {
            seg.classList.add('lit');
            seg.style.setProperty('--led-brightness', '1.0');
            seg.style.setProperty('--glow-intensity', (dutyR / 255).toFixed(2));
            activeRightCount++;
        } else {
            seg.classList.remove('lit');
            seg.style.removeProperty('--led-brightness');
            seg.style.removeProperty('--glow-intensity');
        }
    }

    // Center Emblem projector dot
    const centerDot = document.getElementById('center-drl-dot');
    if (centerDot) {
        if (isLampOn) {
            centerDot.classList.add('active');
        } else {
            centerDot.classList.remove('active');
        }
    }

    // Total active count number
    const totalActive = activeLeftCount + activeRightCount;
    state.drl.activeCount = totalActive;
    const activeElem = document.getElementById('drl-active-led-count');
    if (activeElem) {
        activeElem.textContent = isLampOn ? `${totalActive} / 32` : '0 / 32';
    }

    // Ground spill reflection intensity
    const groundSpill = document.getElementById('drl-ground-spill');
    if (groundSpill) {
        if (!isLampOn || totalActive === 0) {
            groundSpill.style.opacity = '0';
        } else {
            const spillOpacity = (totalActive / 32) * (dutyL / 255) * 0.95;
            groundSpill.style.opacity = spillOpacity.toFixed(2);
        }
    }
}

// Update Brake & Powertrain Hero Cards
function updateBrakeAndPowertrainVisuals() {
    const brakeCard = document.getElementById('card-brake');
    const brakeText = document.getElementById('brake-status-text');
    const brakeSwitchVal = document.getElementById('brake-switch-val');
    const brakeDynVal = document.getElementById('brake-dyn-val');
    const brakeIcon = document.getElementById('brake-icon');

    brakeSwitchVal.textContent = state.brakeRawSwitch;
    brakeDynVal.textContent = state.brakeRawDyn;

    const b4 = parseInt(state.brakeRawSwitch, 16) || 0;
    const isBrakeActive = Boolean(b4 & 0x20); // Bit 5
    const isParkActive = Boolean(b4 & 0x40);  // Bit 6

    if (isBrakeActive) {
        brakeCard.classList.add('active');
        brakeText.textContent = isParkActive ? 'PARKIR + REM' : 'REM DITEKAN';
        brakeIcon.textContent = '🚨';
    } else if (isParkActive) {
        brakeCard.classList.remove('active');
        brakeText.textContent = 'PARKIR / STANDBY (P)';
        brakeIcon.textContent = '🅿️';
    } else {
        brakeCard.classList.remove('active');
        brakeText.textContent = 'REM BEBAS (READY)';
        brakeIcon.textContent = '🛑';
    }

    // Regen Torque
    const regenVal = document.getElementById('regen-torque-val');
    const regenFill = document.getElementById('regen-bar-fill');
    const regenCaption = document.getElementById('regen-status-caption');

    regenVal.textContent = state.regenTorque;
    if (state.regenTorque < 0) {
        const magnitude = Math.min(100, Math.abs(state.regenTorque) * 12);
        regenFill.style.width = magnitude + '%';
        regenCaption.textContent = `Regenerative E-Braking Active (${state.regenTorque} Nm deceleration)`;
    } else {
        regenFill.style.width = '0%';
        regenCaption.textContent = 'E-Braking Inactive (Standstill / Free)';
    }
}

// Render CAN Frame Sniffer Table Row
function updateCANTableRow(cid, frame) {
    const tbody = document.getElementById('can-tbody');
    let row = document.getElementById(`can-row-${cid}`);

    const meta = CAN_DICTIONARY[cid] || { name: 'Unknown Sensor', cat: 'body' };

    // Apply Filter check
    const matchesFilter = (state.filterCat === 'all' || meta.cat === state.filterCat);
    const matchesSearch = (!state.searchQuery || 
                           cid.toLowerCase().includes(state.searchQuery) || 
                           meta.name.toLowerCase().includes(state.searchQuery));

    if (!matchesFilter || !matchesSearch) {
        if (row) row.style.display = 'none';
        return;
    }

    if (!row) {
        row = document.createElement('tr');
        row.id = `can-row-${cid}`;
        tbody.appendChild(row);
    } else {
        row.style.display = '';
    }

    // Build Byte Pills with Flash Diff
    const bytePills = frame.bytes.map((b, idx) => {
        const hex = b.toString(16).toUpperCase().padStart(2, '0');
        const prev = frame.prevBytes ? frame.prevBytes[idx] : b;
        const changed = (prev !== b);
        return `<span class="byte-pill ${changed ? 'diff-flash' : ''}">${hex}</span>`;
    }).join('');

    // Rolling Counter & CRC preview
    let rollingInfo = '-';
    if (frame.bytes.length >= 8 && ['0x104', '0x112', '0x122', '0x262', '0x213'].includes(cid)) {
        const counterNibble = (frame.bytes[6] >> 4) & 0x0F;
        const crcByte = frame.bytes[7].toString(16).toUpperCase().padStart(2, '0');
        rollingInfo = `Cnt: <span class="font-mono" style="color: var(--accent-cyan);">${counterNibble}</span> | CRC: <span class="font-mono">${crcByte}</span>`;
    }

    row.innerHTML = `
        <td><span class="id-badge">${cid}</span></td>
        <td><strong>${meta.name}</strong></td>
        <td><span class="font-mono">${(frame.freq || 0).toFixed(1)} Hz</span></td>
        <td><span class="font-mono">${frame.dlc}</span></td>
        <td><div class="payload-bytes">${bytePills}</div></td>
        <td>${rollingInfo}</td>
        <td><span class="font-mono" style="font-size: 11px;">${new Date().toLocaleTimeString()}</span></td>
    `;
}

// Process incoming CAN packet from SSE or Replay
function handleCANMessage(pkt) {
    state.totalFrames++;
    const cid = pkt.id;
    const bytes = pkt.bytes;

    if (!state.frames[cid]) {
        state.frames[cid] = {
            bytes: bytes,
            prevBytes: bytes,
            count: 1,
            freq: pkt.freq || 10,
            dlc: bytes.length
        };
    } else {
        state.frames[cid].prevBytes = state.frames[cid].bytes;
        state.frames[cid].bytes = bytes;
        state.frames[cid].count++;
        if (pkt.freq) state.frames[cid].freq = pkt.freq;
    }

    // 1. Decode BMS Voltages
    if (cid === '0x504') {
        state.cells[0] = (bytes[0] << 8) | bytes[1];
        state.cells[1] = (bytes[2] << 8) | bytes[3];
        state.cells[2] = (bytes[4] << 8) | bytes[5];
        state.cells[3] = (bytes[6] << 8) | bytes[7];
    } else if (cid === '0x514') {
        state.cells[4] = (bytes[0] << 8) | bytes[1];
        state.cells[5] = (bytes[2] << 8) | bytes[3];
        state.cells[6] = (bytes[4] << 8) | bytes[5];
        state.cells[7] = (bytes[6] << 8) | bytes[7];
    } else if (cid === '0x524') {
        state.cells[8] = (bytes[0] << 8) | bytes[1];
        state.cells[9] = (bytes[2] << 8) | bytes[3];
        state.cells[10] = (bytes[4] << 8) | bytes[5];
        state.cells[11] = (bytes[6] << 8) | bytes[7];
    } else if (cid === '0x534') {
        state.cells[12] = (bytes[0] << 8) | bytes[1];
        state.cells[13] = (bytes[2] << 8) | bytes[3];
        state.cells[14] = (bytes[4] << 8) | bytes[5];
        state.cells[15] = (bytes[6] << 8) | bytes[7];
    } else if (cid === '0x544') {
        state.cells[16] = (bytes[0] << 8) | bytes[1];
        state.cells[17] = (bytes[2] << 8) | bytes[3];
        state.cells[18] = (bytes[4] << 8) | bytes[5];
        state.cells[19] = (bytes[6] << 8) | bytes[7];
    } else if (cid === '0x554') {
        state.cells[20] = (bytes[0] << 8) | bytes[1];
        state.cells[21] = (bytes[2] << 8) | bytes[3];
        state.cells[22] = (bytes[4] << 8) | bytes[5];
        state.cells[23] = (bytes[6] << 8) | bytes[7];
    }

    // 2. Decode BMS Temperatures
    if (cid === '0x503' && bytes.length >= 4) {
        state.temps = [bytes[0] - 40, bytes[1] - 40, bytes[2] - 40, bytes[3] - 40];
    } else if (cid === '0x5F4' && bytes.length >= 2) {
        state.tempModule = bytes[0] - 40;
    }

    // 3. Decode Brake Signals
    if (cid === '0x262' && bytes.length >= 5) {
        state.brakeRawSwitch = '0x' + bytes[4].toString(16).toUpperCase().padStart(2, '0');
        // Bit 5 is 0x20. In current test, 0x60 has 0x40 and 0x20.
        // Let's check 0x226 Bit 0 (0x01) as well:
        state.brakeSwitch = Boolean(bytes[4] & 0x20);
    }
    if (cid === '0x226' && bytes.length >= 3) {
        state.brakeRawDyn = '0x' + bytes[2].toString(16).toUpperCase().padStart(2, '0');
        state.brakeDyn = Boolean(bytes[2] & 0x01); // Bit 0
    }

    // 4. Decode Regen Torque
    if (cid === '0x236' && bytes.length >= 2) {
        let rawTorque = (bytes[0] << 8) | bytes[1];
        if (rawTorque & 0x8000) rawTorque -= 0x10000; // 16-bit signed
        state.regenTorque = rawTorque;
    }

    // 5. Decode Odometer, Sisa Jarak, & Trip Meter (0x272)
    if (cid === '0x272' && bytes.length >= 8) {
        const odoRaw = (bytes[5] << 8) | bytes[6];
        const odoKm = (odoRaw / 10.0);
        state.odoKm = odoKm;
        const rangeKm = bytes[7];

        if (state.tripStartOdo === null) {
            state.tripStartOdo = odoKm;
        }
        const tripKm = Math.max(0, odoKm - state.tripStartOdo).toFixed(1);
        const tripMeters = Math.round(tripKm * 1000);
        
        const odoElem = document.getElementById('odo-val');
        const odoRawElem = document.getElementById('odo-raw');
        const rangeElem = document.getElementById('range-val');
        const rangeRawElem = document.getElementById('range-raw');
        const tripElem = document.getElementById('trip-val');
        const tripMElem = document.getElementById('trip-m-val');
        
        if (odoElem) odoElem.textContent = odoKm.toFixed(1);
        if (odoRawElem) odoRawElem.textContent = `0x${odoRaw.toString(16).toUpperCase().padStart(4, '0')} (${odoRaw})`;
        if (rangeElem) rangeElem.textContent = rangeKm;
        if (rangeRawElem) rangeRawElem.textContent = `0x${rangeKm.toString(16).toUpperCase().padStart(2, '0')}`;
        if (tripElem) tripElem.textContent = tripKm;
        if (tripMElem) tripMElem.textContent = `${tripMeters} meter`;
    }

    // 6. Decode Speedometer & Cruise Control (0x122)
    if (cid === '0x122' && bytes.length >= 5) {
        const speedKmh = bytes[4];
        const isCruise = Boolean(bytes[2] & 0x10);
        state.speed = speedKmh;
        state.cruise = isCruise;

        const speedElem = document.getElementById('speed-val');
        const cruiseBadge = document.getElementById('cruise-status-badge');
        if (speedElem) speedElem.textContent = speedKmh;
        if (cruiseBadge) {
            if (isCruise) {
                cruiseBadge.textContent = `CRUISE AKTIF (${speedKmh} km/h)`;
                cruiseBadge.style.color = 'var(--accent-cyan)';
            } else {
                cruiseBadge.textContent = 'STANDBY (OFF)';
                cruiseBadge.style.color = 'var(--text-muted)';
            }
        }
    }

    // 7. Decode Motor BLDC RPM (0x213: Bytes 3 & 4 Big-Endian with -0x8000 Offset)
    if (cid === '0x213' && bytes.length >= 5) {
        const raw = (bytes[3] << 8) | bytes[4];
        let rpm = raw - 0x8000;
        if (rpm < 0 || raw === 0x7FFF) rpm = 0;
        state.rpm = rpm;
        const rpmElem = document.getElementById('rpm-val');
        const rpmBar = document.getElementById('rpm-bar-fill');
        const rpmRawElem = document.getElementById('rpm-raw');
        if (rpmElem) rpmElem.textContent = rpm;
        if (rpmBar) {
            const pct = Math.min(100, (rpm / 3000) * 100);
            rpmBar.style.width = `${pct.toFixed(1)}%`;
        }
        if (rpmRawElem) {
            rpmRawElem.textContent = `0x${raw.toString(16).toUpperCase().padStart(4, '0')} (${rpm} RPM)`;
        }
    }

    // 8. Decode BLDC Motor & Controller MCU Temperatures (0x323)
    if (cid === '0x323' && bytes.length >= 6) {
        const mcuTemp = bytes[4] - 40;
        const bldcTemp = bytes[5] - 40;
        state.tempMcu = mcuTemp;
        state.tempBldc = bldcTemp;

        const mcuElem = document.getElementById('mcu-temp-val');
        const mcuRaw = document.getElementById('mcu-temp-raw');
        const bldcElem = document.getElementById('bldc-temp-val');
        const bldcRaw = document.getElementById('bldc-temp-raw');

        if (mcuElem) mcuElem.textContent = mcuTemp;
        if (mcuRaw) mcuRaw.textContent = `0x${bytes[4].toString(16).toUpperCase()} (${bytes[4]} - 40)`;
        if (bldcElem) bldcElem.textContent = bldcTemp;
        if (bldcRaw) bldcRaw.textContent = `0x${bytes[5].toString(16).toUpperCase()} (${bytes[5]} - 40)`;
    }

    // 9. Decode DRL Status, Address Bits & Duty Cycle (0x233)
    if (cid === '0x233' && bytes.length >= 8) {
        updateDRLVisuals(bytes);
    }

    // 10. Decode Ignition Status (0x112)
    if (cid === '0x112' && bytes.length >= 2) {
        const ignVal = bytes[1];
        state.ignitionStatus = ignVal;
        const ignElem = document.getElementById('ignition-status-val');
        if (ignElem) {
            if (ignVal === 0x03) {
                ignElem.textContent = 'ON (0x03)';
                ignElem.style.color = 'var(--accent-green)';
            } else if (ignVal === 0x00) {
                ignElem.textContent = 'OFF (0x00)';
                ignElem.style.color = 'var(--accent-red)';
            } else {
                ignElem.textContent = `0x${ignVal.toString(16).toUpperCase()}`;
            }
        }
    }

    updateCANTableRow(cid, state.frames[cid]);
}

// Connect to Backend Server via Server-Sent Events (SSE)
function connectSSE() {
    const statusDot = document.getElementById('status-indicator');
    const statusLabel = document.getElementById('status-label');

    try {
        const evtSource = new EventSource('/api/stream');

        evtSource.onopen = () => {
            state.connected = true;
            statusDot.className = 'status-dot connected';
            statusLabel.textContent = 'Hardware COM3 Terhubung (500 kbps)';
            // Initial load of latest frames from server snapshot
            fetch('/api/snapshot')
                .then(res => res.json())
                .then(snap => {
                    if (snap.frames) {
                        Object.keys(snap.frames).forEach(cid => {
                            const f = snap.frames[cid];
                            handleCANMessage({ id: cid, bytes: f.bytes, freq: f.freq || 10 });
                        });
                    }
                })
                .catch(err => console.warn('Snapshot fetch warning:', err));
        };

        evtSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.type === 'stats') {
                    document.getElementById('bus-fps').textContent = data.fps || 0;
                    document.getElementById('total-frames').textContent = data.totalFrames || state.totalFrames;
                } else if (data.type === 'frame') {
                    state.lastCANMessageTime = Date.now();
                    handleCANMessage(data);
                }
            } catch (err) {
                console.error('Error parsing SSE data:', err);
            }
        };

        // Inactivity Watchdog: If no CAN frames for > 1.2s, motorcycle is asleep / motor off
        setInterval(() => {
            const now = Date.now();
            if (state.lastCANMessageTime && (now - state.lastCANMessageTime > 1200)) {
                const fpsElem = document.getElementById('bus-fps');
                if (fpsElem) fpsElem.textContent = '0';
                
                const ignElem = document.getElementById('ignition-status-val');
                if (ignElem) {
                    ignElem.textContent = 'OFF (0x00)';
                    ignElem.style.color = 'var(--accent-red)';
                }
                state.ignitionStatus = 0;
                state.speed = 0;
                state.rpm = 0;
                state.cruise = false;
                state.tripStartOdo = null;

                const speedElem = document.getElementById('speed-val');
                if (speedElem) speedElem.textContent = '0';
                const cruiseBadge = document.getElementById('cruise-status-badge');
                if (cruiseBadge) {
                    cruiseBadge.textContent = 'STANDBY (OFF)';
                    cruiseBadge.style.color = 'var(--text-muted)';
                }
                const rpmElem = document.getElementById('rpm-val');
                if (rpmElem) rpmElem.textContent = '0';
                const rpmBar = document.getElementById('rpm-bar-fill');
                if (rpmBar) rpmBar.style.width = '0%';

                state.drl.bytes = [0, 0, 0, 0, 0, 0, 0, 0];
                updateDRLVisuals([0, 0, 0, 0, 0, 0, 0, 0]);
            }
        }, 400);

        evtSource.onerror = () => {
            state.connected = false;
            statusDot.className = 'status-dot disconnected';
            statusLabel.textContent = 'Offline / Simulasi Replay Mode';
            // Start simulation fallback if server is unreachable
            startOfflineSimulation();
        };
    } catch (e) {
        console.warn('SSE not supported or failed to init:', e);
        startOfflineSimulation();
    }
}

// Offline Replay Simulation (runs when physical hardware or server is disconnected)
let simInterval = null;
function startOfflineSimulation() {
    if (simInterval) return;
    console.log('Starting offline simulation based on captured OMOWAY dataset...');

    const sampleFrames = [
        { id: '0x142', bytes: [0x03, 0x20, 0x80, 0x03, 0x00, 0x00, 0x00, 0x00], freq: 100 },
        { id: '0x104', bytes: [0x18, 0xA8, 0x27, 0x16, 0x05, 0x07, 0x60, 0x81], freq: 50 },
        { id: '0x112', bytes: [0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0xA0, 0x61], freq: 50 },
        { id: '0x262', bytes: [0x02, 0x00, 0x04, 0x0A, 0x00, 0x00, 0x06, 0xF0], freq: 10 },
        { id: '0x226', bytes: [0x00, 0x00, 0x00, 0xF8, 0x6A, 0x51, 0xBD, 0x80], freq: 50 },
        { id: '0x236', bytes: [0x00, 0x00, 0x00, 0xF8, 0x6A, 0x51, 0xBD, 0x80], freq: 50 },
        { id: '0x503', bytes: [0x47, 0x47, 0x47, 0x47, 0x08, 0x03, 0xFC, 0x01], freq: 1 },
        { id: '0x504', bytes: [0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8], freq: 1 },
        { id: '0x514', bytes: [0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8], freq: 1 },
        { id: '0x524', bytes: [0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8], freq: 1 },
        { id: '0x534', bytes: [0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8], freq: 1 },
        { id: '0x544', bytes: [0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8], freq: 1 },
        { id: '0x554', bytes: [0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8, 0x0C, 0xD8], freq: 1 },
        { id: '0x5F4', bytes: [0x46, 0x47, 0x46, 0x00, 0x00, 0x00, 0x00, 0x46], freq: 1 },
        { id: '0x233', bytes: [0x00, 0x7F, 0xDF, 0xF7, 0xFD, 0xFF, 0x78, 0x78], freq: 10 }
    ];

    const drlPatterns = [
        [0x00, 0x7F, 0xDF, 0xF7, 0xFD, 0xFF, 0x78, 0x78], // Solid ON
        [0x00, 0x7F, 0xDF, 0xF7, 0xF9, 0xFF, 0x78, 0x78], // Sweep 1
        [0x00, 0x7F, 0xDF, 0xF7, 0xFD, 0xFE, 0x78, 0x78], // Sweep 2
        [0x00, 0x7F, 0xDF, 0xF7, 0xFA, 0x00, 0x78, 0x78], // Sweep 3
        [0x00, 0x7F, 0xDF, 0xF8, 0x01, 0xFE, 0x78, 0x78], // Sweep 4
        [0x00, 0x7F, 0xDF, 0xF8, 0x01, 0xFF, 0x78, 0x78], // Sweep 5
        [0x00, 0x7F, 0xDF, 0xF7, 0xFE, 0x00, 0x78, 0x78], // Sweep 6
        [0x00, 0x7F, 0xDF, 0xF7, 0xFD, 0xFF, 0x78, 0x78]  // Solid ON
    ];

    let brakeToggle = false;
    let stepCount = 0;

    simInterval = setInterval(() => {
        stepCount++;
        // Toggle brake every 6 seconds in demo mode
        if (stepCount % 60 === 0) {
            brakeToggle = !brakeToggle;
        }

        const patternIdx = Math.floor((stepCount / 10) % drlPatterns.length);

        sampleFrames.forEach(f => {
            const frameCopy = { ...f, bytes: [...f.bytes] };
            if (f.id === '0x262') {
                frameCopy.bytes[4] = brakeToggle ? 0x20 : 0x00;
            } else if (f.id === '0x226') {
                frameCopy.bytes[2] = brakeToggle ? 0x01 : 0x00;
            } else if (f.id === '0x236') {
                if (brakeToggle) {
                    frameCopy.bytes[0] = 0xFF;
                    frameCopy.bytes[1] = 0xFA; // -6 Nm
                } else {
                    frameCopy.bytes[0] = 0x00;
                    frameCopy.bytes[1] = 0x00; // 0 Nm
                }
            } else if (f.id === '0x233') {
                frameCopy.bytes = drlPatterns[patternIdx];
            }
            handleCANMessage(frameCopy);
        });

        document.getElementById('bus-fps').textContent = '870';
        document.getElementById('total-frames').textContent = state.totalFrames;
    }, 100);
}

// UI Setup & Event Listeners
function setupEventListeners() {
    // Search input
    document.getElementById('filter-input').addEventListener('input', (e) => {
        state.searchQuery = e.target.value.toLowerCase().trim();
        Object.keys(state.frames).forEach(cid => {
            updateCANTableRow(cid, state.frames[cid]);
        });
    });

    // Category pills
    document.querySelectorAll('.filter-pill').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.filterCat = btn.dataset.filter;
            Object.keys(state.frames).forEach(cid => {
                updateCANTableRow(cid, state.frames[cid]);
            });
        });
    });

    // Source Toggle Button (Live COM3 vs Simulation)
    document.getElementById('btn-toggle-source').addEventListener('click', () => {
        if (state.source === 'live') {
            state.source = 'replay';
            document.getElementById('source-label').textContent = 'Simulasi Replay';
            startOfflineSimulation();
        } else {
            state.source = 'live';
            document.getElementById('source-label').textContent = 'Hardware COM3';
            if (simInterval) {
                clearInterval(simInterval);
                simInterval = null;
            }
            connectSSE();
        }
    });

    // 60FPS UI Refresh Loop for BMS & Brake widgets
    setInterval(() => {
        updateBMSVisuals();
        updateBrakeAndPowertrainVisuals();

        // Auto-refresh DRL state to detect when transitions cease (e.g. DRL turned OFF)
        if (state.drl && state.drl.bytes) {
            updateDRLVisuals(state.drl.bytes);
        }
    }, 100);
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    initBMSGrid();
    initDRLComponent();
    setupEventListeners();
    connectSSE();
});
