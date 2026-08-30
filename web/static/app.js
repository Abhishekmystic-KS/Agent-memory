// DOM Elements
const geminiKeyInput = document.getElementById('gemini-key');
const btnSleep = document.getElementById('btn-sleep');
const btnClear = document.getElementById('btn-clear');

const weightRecency = document.getElementById('weight-recency');
const weightImportance = document.getElementById('weight-importance');
const weightRelevance = document.getElementById('weight-relevance');

const valRecency = document.getElementById('val-recency');
const valImportance = document.getElementById('val-importance');
const valRelevance = document.getElementById('val-relevance');

const metricPrecision = document.getElementById('metric-precision');
const metricRecall = document.getElementById('metric-recall');
const metricCompression = document.getElementById('metric-compression');
const metricLatency = document.getElementById('metric-latency');

const testQuery = document.getElementById('test-query');
const btnTestQuery = document.getElementById('btn-test-query');
const testResults = document.getElementById('test-results');

const modeBadge = document.getElementById('mode-badge');
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');

const wmSystem = document.getElementById('wm-system-instruction');
const wmSummary = document.getElementById('wm-summary-content');
const wmBufferList = document.getElementById('wm-buffer-list');

const episodicListContainer = document.getElementById('episodic-list-container');
const profileTableBody = document.getElementById('profile-table-body');
const graphEdgesList = document.getElementById('graph-edges-list');
const factsList = document.getElementById('facts-list');

// Tab Switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
    });
});

// Update label on slider input
weightRecency.addEventListener('input', (e) => { valRecency.innerText = parseFloat(e.target.value).toFixed(1); updateConfig(); });
weightImportance.addEventListener('input', (e) => { valImportance.innerText = parseFloat(e.target.value).toFixed(1); updateConfig(); });
weightRelevance.addEventListener('input', (e) => { valRelevance.innerText = parseFloat(e.target.value).toFixed(1); updateConfig(); });

// Update API key
geminiKeyInput.addEventListener('change', () => {
    updateConfig();
});

// Send message on Enter
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

// Direct Query test
btnTestQuery.addEventListener('click', runQueryTest);

// API Call - Update Config
async function updateConfig() {
    const payload = {
        w_recency: parseFloat(weightRecency.value),
        w_importance: parseFloat(weightImportance.value),
        w_relevance: parseFloat(weightRelevance.value),
        gemini_api_key: geminiKeyInput.value.trim() || null
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
    const typingIndicator = appendMessage('assistant', 'Thinking...');
    
    try {
        const start = performance.now();
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg })
        });
        const latency = performance.now() - start;
        const data = await res.json();
        
        // Remove typing indicator and add final response
        typingIndicator.remove();
        appendMessage('assistant', data.reply);
        
        // Update all UI panels with new state
        updateMemoryPanels(data);
        
        // Update Latency Metric
        metricLatency.innerText = `${Math.round(latency)}ms`;
        metricCompression.innerText = `${Math.round(data.compression_ratio * 100)}%`;

        // Automatically run evaluation benchmark on the user message context
        runLiveEval(msg);

    } catch (err) {
        typingIndicator.innerText = `Failed to connect to backend: ${err.message}`;
        typingIndicator.style.color = 'var(--accent-rose)';
    }
}

// Appends message to chat screen
function appendMessage(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerText = content;
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
        wmSummary.innerText = "No dialogue compressed yet. Summary will generate when token/turn thresholds are exceeded.";
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

    // 2. Episodic List
    episodicListContainer.innerHTML = '';
    if (data.episodic.length === 0) {
        episodicListContainer.innerHTML = `
            <div style="color: var(--text-secondary); text-align: center; margin-top: 2rem; font-size: 0.85rem;">
                No memories recorded yet. Send a message to populate the episodic stream!
            </div>`;
    } else {
        // Reverse array to show most recent at the top
        [...data.episodic].reverse().forEach(m => {
            const dateStr = new Date(m.timestamp * 1000).toLocaleTimeString();
            const card = document.createElement('div');
            card.className = 'episode-card';
            card.id = `episode-${m.id}`;
            card.innerHTML = `
                <div class="episode-header">
                    <span>ID: #${m.id}</span>
                    <span>${dateStr}</span>
                </div>
                <div class="episode-text">${escapeHtml(m.content)}</div>
                <div class="badge-row">
                    <span class="badge importance">Importance: ${m.importance}/10</span>
                </div>
            `;
            episodicListContainer.appendChild(card);
        });
    }

    // 3. Semantic Store
    updateSemanticUI(data.semantic);
}

// Render Semantic structures
function updateSemanticUI(semantic) {
    // Profile key values
    profileTableBody.innerHTML = '';
    const profileKeys = Object.keys(semantic.profile);
    if (profileKeys.length === 0) {
        profileTableBody.innerHTML = `
            <tr>
                <td colspan="2" style="color: var(--text-secondary); text-align: center;">
                    No profile keys extracted yet. Run Sleep Consolidation to build.
                </td>
            </tr>`;
    } else {
        profileKeys.forEach(k => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<th>${escapeHtml(k)}</th><td>${escapeHtml(semantic.profile[k])}</td>`;
            profileTableBody.appendChild(tr);
        });
    }

    // Entity Relation graph elements
    graphEdgesList.innerHTML = '';
    if (semantic.edges.length === 0) {
        graphEdgesList.innerHTML = '<span style="color: var(--text-secondary); text-align: center; font-size: 0.85rem;">No relationship links mapped.</span>';
    } else {
        semantic.edges.forEach(e => {
            const div = document.createElement('div');
            div.className = 'graph-edge-item';
            div.innerHTML = `
                <span class="node source">${escapeHtml(e.source)}</span>
                <span class="relation-link">--[${escapeHtml(e.relation)}]--></span>
                <span class="node target">${escapeHtml(e.target)}</span>
            `;
            graphEdgesList.appendChild(div);
        });
    }

    // Facts list
    factsList.innerHTML = '';
    if (semantic.facts.length === 0) {
        factsList.innerHTML = '<span style="color: var(--text-secondary);">No facts generated.</span>';
    } else {
        semantic.facts.forEach(f => {
            const li = document.createElement('li');
            li.innerText = f;
            factsList.appendChild(li);
        });
    }
}

// API Call - Run Live evaluation
async function runLiveEval(query) {
    try {
        const res = await fetch('/api/eval', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });
        const data = await res.json();
        
        metricPrecision.innerText = data.precision !== null ? `${Math.round(data.precision * 100)}%` : "N/A";
        metricRecall.innerText = data.recall !== null ? `${Math.round(data.recall * 100)}%` : "N/A";
    } catch (err) {
        console.error("Live evaluation failed:", err);
    }
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
        
        // Refresh semantic view
        updateSemanticUI(data.semantic);
        
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
        await fetch('/api/clear', { method: 'POST' });
        chatMessages.innerHTML = '';
        appendMessage('assistant', "System Reset! All sensory buffers, working dialogue sessions, episodic memory logs, and semantic knowledge stores have been cleared.");
        
        // Reset local views
        updateMemoryPanels({
            short_term: { messages: [], rolling_summary: "", system_instruction: "You are a helpful AI assistant with memory." },
            episodic: [],
            semantic: { profile: {}, facts: [], edges: [] },
            compression_ratio: 0.0
        });
        
        metricPrecision.innerText = "N/A";
        metricRecall.innerText = "N/A";
        metricCompression.innerText = "0%";
        metricLatency.innerText = "0ms";
        testResults.innerHTML = '';
        testQuery.value = '';
    } catch (err) {
        console.error("Reset failed:", err);
    }
}

// API Call - Run query search debug testing
async function runQueryTest() {
    const query = testQuery.value.trim();
    if (!query) return;

    btnTestQuery.innerText = "Searching...";
    btnTestQuery.disabled = true;
    
    try {
        const res = await fetch('/api/eval', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });
        
        const data = await res.json();
        
        testResults.innerHTML = '';
        if (!data.retrieved || data.retrieved.length === 0) {
            testResults.innerHTML = '<span style="color: var(--text-secondary);">No matching memories found.</span>';
            return;
        }

        data.retrieved.forEach(r => {
            const div = document.createElement('div');
            div.className = 'profile-card';
            div.style.padding = '0.5rem';
            div.style.background = 'rgba(255, 255, 255, 0.02)';
            div.style.border = '1px solid var(--border-color)';
            div.style.fontSize = '0.75rem';
            div.innerHTML = `
                <div style="font-weight: 600; margin-bottom: 0.25rem;">#${r.id}: "${escapeHtml(r.content)}"</div>
                <div style="display: flex; justify-content: space-between; color: var(--text-secondary); margin-top: 0.25rem;">
                    <span>Recency: ${r.s_recency.toFixed(2)}</span>
                    <span>Importance: ${r.s_importance.toFixed(2)}</span>
                    <span>Relevance: ${r.s_relevance.toFixed(2)}</span>
                    <strong style="color: var(--primary);">Total: ${r.total_score.toFixed(2)}</strong>
                </div>
            `;
            testResults.appendChild(div);
            
            // Highlight matching episode card if it exists in DOM
            const card = document.getElementById(`episode-${r.id}`);
            if (card) {
                card.classList.add('retrieved-pulse');
                setTimeout(() => {
                    card.classList.remove('retrieved-pulse');
                }, 4000);
            }
        });

        // Switch to the episodic tab so the user can see the glowing card!
        const tabBtn = document.querySelector('.tab-btn[data-tab="episodic-tab"]');
        if (tabBtn) {
            tabBtn.click();
        }
        
    } catch (err) {
        testResults.innerHTML = `<span style="color: var(--accent-rose);">Error: ${err.message}</span>`;
    } finally {
        btnTestQuery.disabled = false;
        btnTestQuery.innerText = "Run Query Test";
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
