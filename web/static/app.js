// DOM Elements
const geminiKeyInput = document.getElementById('gemini-key');
const btnSleep = document.getElementById('btn-sleep');
const btnClear = document.getElementById('btn-clear');

const modeBadge = document.getElementById('mode-badge');
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');

const wmSystem = document.getElementById('wm-system-instruction');
const wmSummary = document.getElementById('wm-summary-content');
const wmBufferList = document.getElementById('wm-buffer-list');

const profileTableBody = document.getElementById('profile-table-body');
const factsList = document.getElementById('facts-list');
const vaultEpisodicList = document.getElementById('vault-episodic-list');
const nodeCountBadge = document.getElementById('node-count-badge');

// Cognitive Core Parameters
const decayFunction = document.getElementById('decay-function');
const uncertaintyMode = document.getElementById('uncertainty-mode');
const ymylEnabled = document.getElementById('ymyl-enabled');

const chatConfidenceBadge = document.getElementById('chat-confidence-badge');
const ymylStatusItem = document.getElementById('ymyl-status-item');
const chatYmylBadge = document.getElementById('chat-ymyl-badge');
const chatImmuneBadge = document.getElementById('chat-immune-badge');

const safetyAlertBar = document.getElementById('safety-alert-bar');
const safetyAlertText = document.getElementById('safety-alert-text');

const conflictResolutionBox = document.getElementById('conflict-resolution-box');
const conflictQuestion = document.getElementById('conflict-question');
const btnResolveNew = document.getElementById('btn-resolve-new');
const btnResolveOld = document.getElementById('btn-resolve-old');

// Tab Switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
    });
});

// Plugin Snippet Tab Switching
document.querySelectorAll('.snippet-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.snippet-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.snippet-content').forEach(c => c.style.display = 'none');
        
        btn.classList.add('active');
        document.getElementById(btn.dataset.snippet).style.display = 'block';
    });
});

// Copy integration snippet to clipboard
window.copySnippet = function(lang) {
    const code = document.querySelector(`#snippet-${lang} code`).innerText;
    navigator.clipboard.writeText(code).then(() => {
        const btn = document.getElementById(`btn-copy-${lang}`);
        const orig = btn.innerText;
        btn.innerText = "Copied!";
        btn.style.background = "var(--primary)";
        btn.style.color = "#ffffff";
        setTimeout(() => {
            btn.innerText = orig;
            btn.style.background = "";
            btn.style.color = "";
        }, 1500);
    });
};

// Bind configuration change listeners
geminiKeyInput.addEventListener('change', updateConfig);
decayFunction.addEventListener('change', updateConfig);
uncertaintyMode.addEventListener('change', updateConfig);
ymylEnabled.addEventListener('change', updateConfig);

// Send message trigger
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});
btnSend.addEventListener('click', sendMessage);

// Trigger Consolidation (Sleep)
btnSleep.addEventListener('click', triggerSleep);

// Reset System
btnClear.addEventListener('click', resetSystem);

// Initialize settings
updateConfig();

// API Call - Update Config
async function updateConfig() {
    const payload = {
        w_recency: 1.0,
        w_importance: 1.0,
        w_relevance: 1.0,
        gemini_api_key: geminiKeyInput.value.trim() || null,
        decay_function: decayFunction.value,
        uncertainty_mode: uncertaintyMode.value,
        ymyl_enabled: ymylEnabled.checked
    };

    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.config.gemini_mode_active) {
            modeBadge.innerText = "Gemini API Active";
            modeBadge.style.background = "rgba(16, 185, 129, 0.15)";
            modeBadge.style.color = "#34d399";
        } else {
            modeBadge.innerText = "Local Heuristic Mode";
            modeBadge.style.background = "rgba(255,255,255,0.08)";
            modeBadge.style.color = "var(--text-secondary)";
        }
    } catch (err) {
        console.error("Failed to update config:", err);
    }
}

// API Call - Chat message exchange
async function sendMessage() {
    const msg = chatInput.value.trim();
    if (!msg) return;

    chatInput.value = '';
    
    // Render user bubble
    appendMessage('user', msg);
    
    // Add temporary typing indicator
    const typingIndicator = appendMessage('assistant', '<div class="typing-indicator"><span></span><span></span><span></span></div>');
    
    const start = performance.now();
    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg })
        });
        
        const data = await res.json();
        
        // Remove typing indicator and add final response
        typingIndicator.remove();
        appendMessage('assistant', data.reply);
        
        // Update all UI panels with new state
        updateMemoryPanels(data);
        
        // Update prompt sanitization warning
        if (data.sanitization) {
            safetyAlertText.innerHTML = `Prompt sanitization active! Redacted: <strong>${data.sanitization.categories.join(', ')}</strong>`;
            safetyAlertBar.style.display = 'flex';
        } else {
            safetyAlertBar.style.display = 'none';
        }

        // Update retrieval confidence
        const conf = data.confidence || 'none';
        chatConfidenceBadge.innerText = conf.toUpperCase();
        chatConfidenceBadge.className = `badge badge-${conf.toLowerCase()}`;

        // Update YMYL badges
        if (data.ymyl && data.ymyl.category) {
            chatYmylBadge.innerText = data.ymyl.category.toUpperCase();
            chatImmuneBadge.style.display = data.ymyl.decay_immune ? 'inline-block' : 'none';
            ymylStatusItem.style.display = 'flex';
        } else {
            ymylStatusItem.style.display = 'none';
        }

        // Handle contradiction conflicts
        if (data.contradiction_detected && data.contradiction_memory_id) {
            conflictQuestion.innerText = `[Contradiction Detected] ${data.contradiction_question}`;
            conflictResolutionBox.style.display = 'block';
            
            // Rebind conflict buttons
            btnResolveNew.onclick = () => resolveConflict(data.contradiction_memory_id, data.contradiction_new_fact, 'keep_new');
            btnResolveOld.onclick = () => resolveConflict(data.contradiction_memory_id, data.contradiction_new_fact, 'keep_old');
        } else {
            conflictResolutionBox.style.display = 'none';
        }

    } catch (err) {
        typingIndicator.remove();
        appendMessage('assistant', `[Communication Error] ${err.message}`);
    }
}

// API Call - Resolve contradiction conflict
async function resolveConflict(memoryId, newFact, resolution) {
    try {
        const res = await fetch('/api/resolve_conflict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                memory_id: memoryId,
                new_fact: newFact,
                resolution: resolution
            })
        });
        const data = await res.json();
        
        conflictResolutionBox.style.display = 'none';
        appendMessage('assistant', `Memory conflict resolved. State updated to keep target facts.`);
        
        // Update all UI panels with new state
        updateMemoryPanels(data);
    } catch (err) {
        console.error("Conflict resolution failed:", err);
    }
}

// Helper - Append message bubble to chat panel
function appendMessage(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerHTML = content;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

// Updates working, episodic, and semantic tabs
function updateMemoryPanels(data) {
    // 1. Working Memory (Short-Term)
    wmSystem.innerText = data.short_term.system_instruction;
    if (data.short_term.rolling_summary) {
        wmSummary.innerText = data.short_term.rolling_summary;
        wmSummary.classList.remove('empty');
    } else {
        wmSummary.innerText = "No dialogue compressed yet.";
        wmSummary.classList.add('empty');
    }
    
    // Buffer list
    wmBufferList.innerHTML = '';
    if (data.short_term.messages.length === 0) {
        wmBufferList.innerHTML = '<span style="color: var(--text-secondary);">Buffer is empty.</span>';
    } else {
        data.short_term.messages.forEach(m => {
            const span = document.createElement('div');
            span.innerHTML = `<strong>${m.role.toUpperCase()}:</strong> ${escapeHtml(m.content)}`;
            span.style.padding = '0.2rem 0';
            wmBufferList.appendChild(span);
        });
    }

    // 2. Memory Vault - Developer Profile Fields
    profileTableBody.innerHTML = '';
    const profileKeys = Object.keys(data.semantic.profile);
    if (profileKeys.length === 0) {
        profileTableBody.innerHTML = `
            <tr>
                <td colspan="3" style="color: var(--text-secondary); text-align: center;">
                    No profile keys extracted yet. Run Sleep Consolidation to build.
                </td>
            </tr>`;
    } else {
        profileKeys.forEach(k => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <th>${escapeHtml(k)}</th>
                <td>${escapeHtml(data.semantic.profile[k])}</td>
                <td style="text-align: center;">
                    <button class="btn-delete-row" onclick="deleteMemory('profile', { target_key: '${k}' })">Delete</button>
                </td>`;
            profileTableBody.appendChild(tr);
        });
    }

    // 3. Memory Vault - Consolidated Facts List
    factsList.innerHTML = '';
    if (data.semantic.facts.length === 0) {
        factsList.innerHTML = '<span style="color: var(--text-secondary); padding: 0.5rem;">No facts consolidated yet.</span>';
    } else {
        data.semantic.facts.forEach(f => {
            const li = document.createElement('li');
            li.className = 'vault-fact-item';
            // Need to escape fact string for inline JS trigger safely
            const safeFact = f.replace(/'/g, "\\'");
            li.innerHTML = `
                <span>${escapeHtml(f)}</span>
                <button class="btn-delete-row" onclick="deleteMemory('fact', { target_text: '${safeFact}' })">Delete</button>
            `;
            factsList.appendChild(li);
        });
    }

    // 4. Memory Vault - Episodic logs
    vaultEpisodicList.innerHTML = '';
    if (data.episodic.length === 0) {
        vaultEpisodicList.innerHTML = '<span style="color: var(--text-secondary); padding: 0.5rem;">No logs stored yet.</span>';
    } else {
        [...data.episodic].reverse().forEach(m => {
            const card = document.createElement('div');
            card.className = 'vault-episodic-item';
            card.innerHTML = `
                <div style="flex: 1;">
                    <strong style="color: var(--primary);">#${m.id}</strong>: ${escapeHtml(m.content)}
                    <div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 0.15rem;">
                        Importance: ${m.importance} | YMYL: ${m.ymyl_category || 'None'}
                    </div>
                </div>
                <button class="btn-delete-row" onclick="deleteMemory('episodic', { target_id: ${m.id} })">Delete</button>
            `;
            vaultEpisodicList.appendChild(card);
        });
    }

    // 5. Update Interactive Synaptic Graph
    updateSemanticGraph(data.semantic.edges);
}

// Programmatic deletion of memories
window.deleteMemory = async function(type, params) {
    const payload = {
        memory_type: type,
        ...params
    };
    try {
        const res = await fetch('/api/delete_memory', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === "success") {
            updateMemoryPanels(data);
        }
    } catch (err) {
        console.error("Failed to delete memory:", err);
    }
};

let network = null;

// ── Demo seed edges shown before consolidation ────────────────────────────────
const DEMO_EDGES = [
    // Developer identity
    { source: 'Developer',   target: 'Python',       relation: 'uses' },
    { source: 'Developer',   target: 'FastAPI',      relation: 'builds with' },
    { source: 'Developer',   target: 'Project',      relation: 'owns' },
    { source: 'Developer',   target: 'Claude',       relation: 'works with' },
    { source: 'Developer',   target: 'VS Code',      relation: 'edits in' },
    { source: 'Developer',   target: 'Git',          relation: 'versions with' },
    { source: 'Developer',   target: 'Linux',        relation: 'runs on' },
    { source: 'Developer',   target: 'Terminal',     relation: 'uses' },
    { source: 'Developer',   target: 'Docker',       relation: 'containerises with' },
    { source: 'Developer',   target: 'REST API',     relation: 'designs' },

    // Project
    { source: 'Project',     target: 'FastAPI',      relation: 'powered by' },
    { source: 'Project',     target: 'Bottleneck',   relation: 'uses' },
    { source: 'Project',     target: 'PostgreSQL',   relation: 'stores data in' },
    { source: 'Project',     target: 'Redis',        relation: 'caches with' },
    { source: 'Project',     target: 'Docker',       relation: 'deployed via' },
    { source: 'Project',     target: 'GitHub',       relation: 'hosted on' },
    { source: 'Project',     target: 'REST API',     relation: 'exposes' },
    { source: 'Project',     target: 'Port 8000',    relation: 'serves on' },
    { source: 'Project',     target: 'Tests',        relation: 'validated by' },
    { source: 'Project',     target: 'CI/CD',        relation: 'automated by' },

    // Bottleneck memory system
    { source: 'Bottleneck',  target: 'Memory',       relation: 'manages' },
    { source: 'Bottleneck',  target: 'Agent',        relation: 'powers' },
    { source: 'Bottleneck',  target: 'Dashboard',    relation: 'serves' },
    { source: 'Bottleneck',  target: 'REST API',     relation: 'exposes' },
    { source: 'Bottleneck',  target: 'vis.js',       relation: 'renders with' },

    // Memory architecture
    { source: 'Memory',      target: 'Episodic',     relation: 'tier' },
    { source: 'Memory',      target: 'Semantic',     relation: 'tier' },
    { source: 'Memory',      target: 'Sensory',      relation: 'tier' },
    { source: 'Memory',      target: 'Short-Term',   relation: 'tier' },
    { source: 'Memory',      target: 'Consolidation',relation: 'uses' },
    { source: 'Memory',      target: 'Decay',        relation: 'applies' },
    { source: 'Episodic',    target: 'Timestamp',    relation: 'records' },
    { source: 'Episodic',    target: 'Importance',   relation: 'scores' },
    { source: 'Semantic',    target: 'Graph',        relation: 'builds' },
    { source: 'Semantic',    target: 'Facts',        relation: 'stores' },
    { source: 'Semantic',    target: 'Profile',      relation: 'extracts' },
    { source: 'Sensory',     target: 'Buffer',       relation: 'holds' },
    { source: 'Short-Term',  target: 'Context',      relation: 'stores' },
    { source: 'Short-Term',  target: 'Summary',      relation: 'compresses to' },
    { source: 'Consolidation',target: 'Gemini',      relation: 'calls' },
    { source: 'Consolidation',target: 'Heuristics',  relation: 'fallback to' },

    // Claude / AI layer
    { source: 'Claude',      target: 'Bottleneck',   relation: 'integrates' },
    { source: 'Claude',      target: 'Developer',    relation: 'assists' },
    { source: 'Claude',      target: 'Context',      relation: 'reads' },
    { source: 'Claude',      target: 'Gemini',       relation: 'sibling model' },
    { source: 'Claude',      target: 'Codex',        relation: 'related to' },
    { source: 'Codex',       target: 'Codebase',     relation: 'understands' },
    { source: 'Gemini',      target: 'Embeddings',   relation: 'generates' },
    { source: 'Embeddings',  target: 'Semantic',     relation: 'feeds into' },

    // Python stack
    { source: 'Python',      target: 'FastAPI',      relation: 'runs' },
    { source: 'Python',      target: 'Pydantic',     relation: 'validates with' },
    { source: 'Python',      target: 'Pytest',       relation: 'tested by' },
    { source: 'Python',      target: 'Uvicorn',      relation: 'served by' },
    { source: 'Python',      target: 'asyncio',      relation: 'async via' },
    { source: 'Python',      target: 'Type Hints',   relation: 'enforced with' },
    { source: 'FastAPI',     target: 'Uvicorn',      relation: 'uses' },
    { source: 'FastAPI',     target: 'Pydantic',     relation: 'schema via' },
    { source: 'FastAPI',     target: 'Port 8000',    relation: 'listens on' },
    { source: 'FastAPI',     target: 'Endpoints',    relation: 'defines' },
    { source: 'Endpoints',   target: '/api/chat',    relation: 'includes' },
    { source: 'Endpoints',   target: '/api/sleep',   relation: 'includes' },
    { source: 'Endpoints',   target: '/api/file',    relation: 'includes' },
    { source: 'Tests',       target: 'Pytest',       relation: 'uses' },

    // Frontend stack
    { source: 'Dashboard',   target: 'HTML',         relation: 'structured with' },
    { source: 'Dashboard',   target: 'CSS',          relation: 'styled with' },
    { source: 'Dashboard',   target: 'JavaScript',   relation: 'scripted with' },
    { source: 'Dashboard',   target: 'vis.js',       relation: 'graphs with' },
    { source: 'Dashboard',   target: 'Neural Map',   relation: 'shows' },
    { source: 'Dashboard',   target: 'Memory Vault', relation: 'shows' },
    { source: 'Dashboard',   target: 'Codebase',     relation: 'browses' },
    { source: 'vis.js',      target: 'Neural Map',   relation: 'renders' },
    { source: 'Neural Map',  target: 'Nodes',        relation: 'displays' },
    { source: 'Neural Map',  target: 'Edges',        relation: 'displays' },
    { source: 'Nodes',       target: 'Glow',         relation: 'animated by' },
    { source: 'CSS',         target: 'Glow',         relation: 'creates' },
    { source: 'JavaScript',  target: 'Fetch API',    relation: 'uses' },
    { source: 'Fetch API',   target: 'Endpoints',    relation: 'calls' },

    // DevOps / infra
    { source: 'Docker',      target: 'Container',    relation: 'runs' },
    { source: 'Container',   target: 'Port 8000',    relation: 'exposes' },
    { source: 'CI/CD',       target: 'GitHub',       relation: 'triggered by' },
    { source: 'GitHub',      target: 'Git',          relation: 'hosts' },
    { source: 'Linux',       target: 'Terminal',     relation: 'uses' },
    { source: 'Linux',       target: 'Docker',       relation: 'runs' },
    { source: 'PostgreSQL',  target: 'SQL',          relation: 'queries' },
    { source: 'Redis',       target: 'Cache',        relation: 'stores' },

    // Skills / concepts
    { source: 'Profile',     target: 'Style Guide',  relation: 'records' },
    { source: 'Profile',     target: 'Language Pref',relation: 'records' },
    { source: 'Profile',     target: 'Project Paths',relation: 'records' },
    { source: 'Style Guide', target: 'PEP 8',        relation: 'follows' },
    { source: 'Style Guide', target: 'Docstrings',   relation: 'enforces' },
    { source: 'Context',     target: 'Prompt',       relation: 'builds' },
    { source: 'Prompt',      target: 'Claude',       relation: 'sent to' },
    { source: 'Facts',       target: 'Contradiction',relation: 'checked for' },
    { source: 'Contradiction',target: 'Resolver',    relation: 'handled by' },
    { source: 'Resolver',    target: 'Developer',    relation: 'asks' },
    { source: 'Decay',       target: 'Exponential',  relation: 'mode' },
    { source: 'Decay',       target: 'Linear',       relation: 'mode' },
    { source: 'Importance',  target: 'YMYL',         relation: 'boosted by' },
    { source: 'YMYL',        target: 'Health',       relation: 'category' },
    { source: 'YMYL',        target: 'Finance',      relation: 'category' },
    { source: 'Buffer',      target: 'Token Count',  relation: 'tracks' },
    { source: 'Token Count', target: 'Summary',      relation: 'triggers' },
    { source: 'Summary',     target: 'Short-Term',   relation: 'replaces buffer in' },
    { source: 'Codebase',    target: 'Python',       relation: 'written in' },
    { source: 'Codebase',    target: 'Project Paths',relation: 'stored in' },
    { source: 'VS Code',     target: 'Codebase',     relation: 'opens' },
];

// Pick a colour + glow for a node by name
function _nodeStyle(name) {
    const n = name.toLowerCase();
    if (['developer','user','kali'].some(k => n.includes(k)))
        return { color: '#10b981', glow: 'rgba(16,185,129,0.55)' };
    if (['project','codebase','app','server','bottleneck'].some(k => n.includes(k)))
        return { color: '#8b5cf6', glow: 'rgba(139,92,246,0.55)' };
    if (['python','js','react','fastapi','rust','node'].some(k => n.includes(k)))
        return { color: '#f59e0b', glow: 'rgba(245,158,11,0.55)' };
    if (['memory','episodic','semantic','graph','claude'].some(k => n.includes(k)))
        return { color: '#00f2fe', glow: 'rgba(0,242,254,0.45)' };
    return { color: '#3b82f6', glow: 'rgba(59,130,246,0.45)' };
}

function _buildVisNodes(nodeSet, nodeDegree) {
    return Array.from(nodeSet).map(name => {
        const { color, glow } = _nodeStyle(name);
        const degree = nodeDegree[name] || 1;
        const size   = 10 + degree * 4;
        return {
            id: name, label: name,
            color: { background: color, border: color,
                     highlight: { background: '#fff', border: '#fff' } },
            font: { color: '#fff', face: 'Space Grotesk', size: 10, vadjust: -22 },
            shape: 'dot', size,
            shadow: { enabled: true, color: glow, size: size + 6, x: 0, y: 0 }
        };
    });
}

function _buildVisEdges(edges) {
    return edges.map(e => ({
        from: e.source, to: e.target,
        label: e.relation, arrows: 'to',
        color: { color: 'rgba(99,102,241,0.22)', highlight: 'rgba(0,242,254,0.9)' },
        font: { color: 'rgba(255,255,255,0.4)', size: 9, strokeWidth: 0, face: 'Space Grotesk' },
        width: 1.5,
        smooth: { type: 'continuous', roundness: 0.3 }
    }));
}

const GRAPH_OPTIONS = {
    physics: {
        stabilization: { iterations: 120 },
        barnesHut: {
            gravitationalConstant: -1800,
            centralGravity: 0.15,
            springLength: 95,
            springConstant: 0.04,
            damping: 0.09
        }
    },
    interaction: { dragNodes: true, zoomView: true, dragView: true }
};

// Renders neural-network graph; falls back to DEMO_EDGES when no real data
function updateSemanticGraph(edges) {
    const container   = document.getElementById('semantic-graph');
    const placeholder = document.getElementById('graph-placeholder');
    if (!container) return;

    const isDemo  = !edges || edges.length === 0;
    const srcEdges = isDemo ? DEMO_EDGES : edges;

    if (isDemo) {
        if (placeholder) placeholder.style.display = 'none'; // hide text — graph IS the placeholder now
    } else {
        if (placeholder) placeholder.style.display = 'none';
    }

    const nodeDegree = {}, nodeSet = new Set();
    srcEdges.forEach(e => {
        nodeSet.add(e.source); nodeSet.add(e.target);
        nodeDegree[e.source] = (nodeDegree[e.source] || 0) + 1;
        nodeDegree[e.target] = (nodeDegree[e.target] || 0) + 1;
    });

    const visData = {
        nodes: new vis.DataSet(_buildVisNodes(nodeSet, nodeDegree)),
        edges: new vis.DataSet(_buildVisEdges(srcEdges))
    };

    if (network) network.destroy();
    network = new vis.Network(container, visData, GRAPH_OPTIONS);

    const label = isDemo ? `${nodeSet.size} NODES · DEMO` : `${nodeSet.size} NODES`;
    nodeCountBadge.innerText = label;
    if (isDemo) {
        nodeCountBadge.style.background = 'rgba(245,158,11,0.7)';
        nodeCountBadge.title = 'Demo data — run Consolidate (Sleep) to build real graph';
    } else {
        nodeCountBadge.style.background = 'var(--primary)';
        nodeCountBadge.title = '';
    }

    network.once('stabilized', () =>
        network.fit({ animation: { duration: 700, easingFunction: 'easeInOutQuad' } })
    );
}

// Fit / zoom-to-fit all nodes
window.fitGraph = function() {
    if (network) network.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
};

// Toggle fullscreen on the graph panel
window.toggleGraphFullscreen = function() {
    const panel = document.getElementById('graph-panel');
    if (!panel) return;
    const isFs = panel.classList.toggle('graph-fullscreen');
    document.getElementById('btn-graph-fs').innerHTML = isFs ? '⤡' : '⤢';
    document.getElementById('btn-graph-fs').title = isFs ? 'Exit fullscreen' : 'Maximize graph';
    setTimeout(() => { if (network) { network.redraw(); network.fit(); } }, 50);
};

// Redraw graph on window resize
window.addEventListener('resize', () => { if (network) { network.redraw(); } });

// Boot demo graph immediately on load
document.addEventListener('DOMContentLoaded', () => updateSemanticGraph(null));



// API Call - Trigger manual Sleep Consolidation
async function triggerSleep() {
    btnSleep.innerText = "Consolidating...";
    btnSleep.disabled = true;
    
    try {
        const res = await fetch('/api/sleep', { method: 'POST' });
        const data = await res.json();
        
        // Report results as dialogue note
        const rep = data.report;
        let summaryText = "";
        if (rep.mode === "gemini") {
            summaryText = "Consolidation Complete using Google Gemini Model:\n";
        } else {
            summaryText = "Consolidation Complete using Local Rule-based heuristics:\n";
        }
        
        const updates = [];
        if (Object.keys(rep.profile_updates).length > 0) {
            updates.push(`• Updated Profile attributes: ${Object.keys(rep.profile_updates).join(', ')}`);
        }
        if (rep.new_relations && rep.new_relations.length > 0) {
            updates.push(`• Mapped relationship links: ${rep.new_relations.length}`);
        }
        if (rep.new_facts && rep.new_facts.length > 0) {
            updates.push(`• Generalized facts: ${rep.new_facts.length}`);
        }

        if (updates.length > 0) {
            summaryText += updates.join('\n');
        } else {
            summaryText += "No new properties or concepts were found to consolidate from recent conversations.";
        }

        appendMessage('assistant', `[System Consolidation Event]\n${summaryText}`);
        
        // Refresh UI
        updateMemoryPanels({
            short_term: {
                system_instruction: wmSystem.innerText,
                rolling_summary: wmSummary.innerText.includes("No dialogue") ? "" : wmSummary.innerText,
                messages: Array.from(wmBufferList.children).map(div => {
                    const parts = div.innerText.split(': ');
                    return { role: parts[0].toLowerCase(), content: parts[1] || "" };
                })
            },
            episodic: Array.from(vaultEpisodicList.children).map(card => {
                // If it is dummy text, return empty
                if (card.innerText.includes("No logs stored")) return null;
                // Parse out values
                const idMatch = card.innerHTML.match(/#(\d+)/);
                const id = idMatch ? parseInt(idMatch[1]) : 0;
                const textMatch = card.innerHTML.match(/<\/strong>: ([\s\S]*?)<div/);
                const text = textMatch ? textMatch[1].trim() : "";
                return { id: id, content: text, importance: 5 };
            }).filter(Boolean),
            semantic: data.semantic
        });
        
    } catch (err) {
        appendMessage('assistant', `[Consolidation Event Failed] ${err.message}`);
    } finally {
        btnSleep.innerText = "Consolidate (Sleep)";
        btnSleep.disabled = false;
    }
}

// API Call - Reset system memories
async function resetSystem() {
    if (!confirm("Are you sure you want to reset all memory stores? This clears sensory, short-term, episodic, and semantic layers.")) return;
    
    try {
        const res = await fetch('/api/clear', { method: 'POST' });
        const data = await res.json();
        chatMessages.innerHTML = '';
        appendMessage('assistant', "System Reset! All sensory buffers, working dialogue sessions, episodic memory logs, and semantic knowledge stores have been cleared.");
        
        // Reset local views
        updateMemoryPanels(data);
        
        safetyAlertBar.style.display = 'none';
        conflictResolutionBox.style.display = 'none';
        ymylStatusItem.style.display = 'none';
        chatConfidenceBadge.className = 'badge badge-none';
        chatConfidenceBadge.innerText = 'NONE';
    } catch (err) {
        console.error("Reset failed:", err);
    }
}

function escapeHtml(text) {
    if (typeof text !== 'string') return text;
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ── Codebase Explorer ────────────────────────────────────────────────────────

let _codebaseLoaded = false;
let _currentFileContent = '';

// File extension → emoji icon map
const FILE_ICONS = {
    '.py':   '🐍', '.js':  '☕', '.ts':  '🔷', '.html': '🌐',
    '.css':  '🎨', '.md':  '📝', '.txt': '📄', '.json': '📦',
    '.yml':  '⚙️', '.yaml':'⚙️', '.sh':  '🖥️', '.env':  '🔐',
    '.toml': '📋', '.cfg': '📋', '.ini': '📋',
};

function getFileIcon(name) {
    const ext = name.slice(name.lastIndexOf('.')).toLowerCase();
    return FILE_ICONS[ext] || '📄';
}

// Render a tree node recursively
function renderTree(items, container, depth = 0) {
    items.forEach(item => {
        if (item.type === 'dir') {
            const dirEl = document.createElement('div');
            dirEl.className = 'tree-dir';
            dirEl.innerHTML = `<span class="tree-arrow">▶</span><span class="tree-icon">📁</span><span>${escapeHtml(item.name)}</span>`;

            const childContainer = document.createElement('div');
            childContainer.className = 'tree-children';
            childContainer.style.display = 'none';
            renderTree(item.children, childContainer, depth + 1);

            dirEl.addEventListener('click', (e) => {
                e.stopPropagation();
                const isOpen = dirEl.classList.toggle('open');
                childContainer.style.display = isOpen ? 'block' : 'none';
                dirEl.querySelector('.tree-icon').textContent = isOpen ? '📂' : '📁';
            });

            container.appendChild(dirEl);
            container.appendChild(childContainer);
        } else {
            const fileEl = document.createElement('div');
            fileEl.className = 'tree-file';
            fileEl.innerHTML = `<span class="tree-icon">${getFileIcon(item.name)}</span><span title="${escapeHtml(item.path)}">${escapeHtml(item.name)}</span>`;
            fileEl.addEventListener('click', (e) => {
                e.stopPropagation();
                document.querySelectorAll('.tree-file.active').forEach(el => el.classList.remove('active'));
                fileEl.classList.add('active');
                loadFileContent(item.path);
            });
            container.appendChild(fileEl);
        }
    });
}

// Load the whole codebase tree (called once, cached)
window.loadCodebaseTree = async function() {
    if (_codebaseLoaded) return;
    const treeEl = document.getElementById('codebase-tree');
    treeEl.innerHTML = '<div class="codebase-tree-placeholder">Loading project files…</div>';

    try {
        const res = await fetch('/api/codebase');
        const data = await res.json();
        treeEl.innerHTML = '';

        // Root folder label
        const rootLabel = document.createElement('div');
        rootLabel.style.cssText = 'font-size:0.7rem;font-weight:700;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.08em;padding:0.2rem 0.3rem 0.4rem;';
        rootLabel.textContent = `📦 ${data.root}`;
        treeEl.appendChild(rootLabel);

        renderTree(data.tree, treeEl);
        _codebaseLoaded = true;
    } catch (err) {
        treeEl.innerHTML = `<div class="codebase-tree-placeholder" style="color:#f87171;">Failed to load: ${err.message}</div>`;
    }
};

// Load file content and display it in the viewer
async function loadFileContent(path) {
    const placeholder = document.querySelector('.codebase-viewer-placeholder');
    const header = document.getElementById('codebase-file-header');
    const pathLabel = document.getElementById('codebase-file-path');
    const codeEl = document.getElementById('codebase-code');

    if (placeholder) placeholder.style.display = 'none';
    header.style.display = 'flex';
    pathLabel.textContent = path;
    codeEl.textContent = 'Loading…';

    try {
        const res = await fetch(`/api/file?path=${encodeURIComponent(path)}`);
        const data = await res.json();
        _currentFileContent = data.content;
        codeEl.textContent = data.content;
        if (data.truncated) {
            pathLabel.textContent = `${path}  ⚠️ Truncated (file too large)`;
        }
    } catch (err) {
        codeEl.textContent = `Error loading file: ${err.message}`;
    }
}

// Copy displayed file content to clipboard
window.copyFileContent = function() {
    if (!_currentFileContent) return;
    navigator.clipboard.writeText(_currentFileContent).then(() => {
        const btn = document.getElementById('btn-copy-file');
        const orig = btn.innerText;
        btn.innerText = 'Copied!';
        btn.style.background = 'var(--primary)';
        btn.style.color = '#fff';
        setTimeout(() => {
            btn.innerText = orig;
            btn.style.background = '';
            btn.style.color = '';
        }, 1500);
    });
};
