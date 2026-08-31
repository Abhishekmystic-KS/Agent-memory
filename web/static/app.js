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

// Renders neural network styled graph representation of entity relationships
function updateSemanticGraph(edges) {
    const container = document.getElementById('semantic-graph');
    if (!container) return;

    if (!edges || edges.length === 0) {
        container.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding-top: 120px; font-size: 0.85rem;">No synaptic links mapped. Run Sleep Consolidation to build connections.</div>';
        nodeCountBadge.innerText = '0 NODES';
        if (network) {
            network.destroy();
            network = null;
        }
        return;
    }

    // Map degree count of node connection occurrences
    const nodeDegree = {};
    const nodeSet = new Set();
    const visEdges = [];
    
    edges.forEach(e => {
        nodeSet.add(e.source);
        nodeSet.add(e.target);
        
        nodeDegree[e.source] = (nodeDegree[e.source] || 0) + 1;
        nodeDegree[e.target] = (nodeDegree[e.target] || 0) + 1;

        visEdges.push({
            from: e.source,
            to: e.target,
            label: e.relation,
            arrows: 'to',
            color: { color: 'rgba(99, 102, 241, 0.25)', highlight: 'rgba(0, 242, 254, 0.85)' },
            font: { color: 'rgba(255, 255, 255, 0.45)', size: 9, strokeWidth: 0, face: 'Space Grotesk' },
            width: 1.5,
            smooth: { type: 'continuous', roundness: 0.3 }
        });
    });

    const visNodes = Array.from(nodeSet).map(name => {
        // Glowing Organic Colors matching developer, stacks, configs
        let nodeColor = '#3b82f6'; // default neon blue
        let nodeGlowColor = 'rgba(59, 130, 246, 0.4)';
        const nameLower = name.toLowerCase();

        if (nameLower === 'user' || nameLower === 'developer' || nameLower === 'kali') {
            nodeColor = '#10b981'; // emerald neuron
            nodeGlowColor = 'rgba(16, 185, 129, 0.4)';
        } else if (nameLower === 'project' || nameLower === 'codebase' || nameLower === 'app' || nameLower === 'server') {
            nodeColor = '#8b5cf6'; // purple neuron
            nodeGlowColor = 'rgba(139, 92, 246, 0.4)';
        } else if (nameLower.includes('python') || nameLower.includes('js') || nameLower.includes('react') || nameLower.includes('fastapi') || nameLower.includes('rust')) {
            nodeColor = '#f59e0b'; // amber stack neuron
            nodeGlowColor = 'rgba(245, 158, 11, 0.4)';
        }

        const degree = nodeDegree[name] || 1;
        const nodeSize = 10 + (degree * 4); // Scale size by network connection weight

        return {
            id: name,
            label: name,
            color: {
                background: nodeColor,
                border: nodeColor,
                highlight: { background: '#ffffff', border: '#ffffff' }
            },
            font: { color: '#ffffff', face: 'Space Grotesk', size: 10, vadjust: -22 },
            shape: 'dot',
            size: nodeSize,
            shadow: {
                enabled: true,
                color: nodeGlowColor,
                size: nodeSize + 4,
                x: 0,
                y: 0
            }
        };
    });

    nodeCountBadge.innerText = `${visNodes.length} NODES`;

    const data = {
        nodes: new vis.DataSet(visNodes),
        edges: new vis.DataSet(visEdges)
    };

    const options = {
        physics: {
            stabilization: true,
            barnesHut: {
                gravitationalConstant: -1800,
                centralGravity: 0.15,
                springLength: 95,
                springConstant: 0.04,
                damping: 0.09
            }
        },
        interaction: {
            dragNodes: true,
            zoomView: true,
            dragView: true
        }
    };

    if (network) {
        network.destroy();
    }
    network = new vis.Network(container, data, options);
}

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
