/**
 * DataLens AI Knowledge Wiki - Frontend Controller
 * Handles Explorer, Ingest Queue, Chat assistant, and Force-Directed Graph Visualizer.
 */

// Global namespaces and elements
const Wiki = {
    pages: [],
    activePage: null,
    graph: {
        nodes: [],
        links: [],
        selectedNode: null,
        draggedNode: null
    },
    ingestInterval: null,
    
    // Config elements
    elements: {
        section: null,
        subtabs: [],
        tabContents: [],
        treeContainer: null,
        pageTitle: null,
        pageContent: null,
        backlinksPanel: null,
        backlinksList: null,
        searchBox: null,
        sessionsBody: null,
        progressBarFill: null,
        progressRatio: null,
        progressStatus: null,
        progressActiveFile: null,
        progressEmpty: null,
        progressContainer: null,
        consoleLogs: null,
        chatBox: null,
        chatInput: null,
        chatSendBtn: null,
        canvas: null,
        saveCfgBtn: null,
        cfgGeminiKey: null,
        cfgSupabaseUrl: null,
        cfgSupabaseKey: null,
        cfgStatusMsg: null,
        selectAllBtn: null,
        compileStartBtn: null
    },

    init() {
        console.log("Initializing AI Knowledge Wiki Module...");
        
        // Generate/load persistent local session ID for Supabase bucket storage memory
        if (!localStorage.getItem('wiki_session_id')) {
            localStorage.setItem('wiki_session_id', 'session_' + Math.random().toString(36).substring(2, 11));
        }
        this.sessionId = localStorage.getItem('wiki_session_id');

        this.cacheElements();
        this.bindEvents();
        this.initGraphSimulation();
        this.loadWikiStatus();
        this.loadSessionsList();
        this.loadSuggestedQuestions();
    },

    cacheElements() {
        this.elements.section = document.getElementById('wiki-section');
        this.elements.subtabs = document.querySelectorAll('.wiki-subtab');
        this.elements.tabContents = document.querySelectorAll('.wiki-tab-content');
        this.elements.treeContainer = document.getElementById('wiki-tree-container');
        this.elements.pageTitle = document.getElementById('wiki-page-title');
        this.elements.pageContent = document.getElementById('wiki-page-content');
        this.elements.backlinksPanel = document.getElementById('wiki-backlinks-panel');
        this.elements.backlinksList = document.getElementById('wiki-backlinks-list');
        this.elements.searchBox = document.getElementById('wiki-search-box');
        this.elements.sessionsBody = document.getElementById('wiki-sessions-list-body');
        this.elements.progressBarFill = document.getElementById('wiki-progress-bar-fill');
        this.elements.progressRatio = document.getElementById('wiki-progress-ratio');
        this.elements.progressStatus = document.getElementById('wiki-progress-status');
        this.elements.progressActiveFile = document.getElementById('wiki-progress-active-file');
        this.elements.progressEmpty = document.getElementById('wiki-progress-empty');
        this.elements.progressContainer = document.getElementById('wiki-progress-container');
        this.elements.consoleLogs = document.getElementById('wiki-console-logs');
        this.elements.chatBox = document.getElementById('wiki-chat-box');
        this.elements.chatInput = document.getElementById('wiki-chat-input');
        this.elements.chatSendBtn = document.getElementById('btn-wiki-chat-send');
        this.elements.chatClearBtn = document.getElementById('btn-wiki-chat-clear');
        this.elements.canvas = document.getElementById('wiki-graph-canvas');
        
        // Settings elements
        this.elements.saveCfgBtn = document.getElementById('btn-save-cfg');
        this.elements.cfgGeminiKey = document.getElementById('cfg-gemini-key');
        this.elements.cfgSupabaseUrl = document.getElementById('cfg-supabase-url');
        this.elements.cfgSupabaseKey = document.getElementById('cfg-supabase-key');
        this.elements.cfgStatusMsg = document.getElementById('cfg-status-msg');
        
        // Buttons
        this.elements.selectAllBtn = document.getElementById('btn-wiki-select-all');
        this.elements.compileStartBtn = document.getElementById('btn-wiki-compile-start');
        this.elements.compileAbortBtn = document.getElementById('btn-wiki-compile-abort');
        this.elements.compileAbortMiniBtn = document.getElementById('btn-wiki-compile-abort-mini');
    },

    bindEvents() {
        const self = this;

        // Hook navigation buttons in sidebar
        const navWikiBtn = document.getElementById('nav-wiki');
        if (navWikiBtn) {
            navWikiBtn.addEventListener('click', function() {
                // Remove active class from all navs
                document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
                navWikiBtn.classList.add('active');
                
                // Show wiki section, hide others
                document.querySelectorAll('.dashboard-section').forEach(sec => sec.classList.remove('active'));
                self.elements.section.classList.add('active');
                
                // Refresh trees and canvas sizing
                self.loadWikiPages();
                self.resizeCanvas();
            });
        }

        // Subtabs Navigation
        this.elements.subtabs.forEach(tab => {
            tab.addEventListener('click', function() {
                self.elements.subtabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                const targetId = tab.getAttribute('data-tab');
                self.elements.tabContents.forEach(c => {
                    c.style.display = c.id === targetId ? 'block' : 'none';
                });
                
                if (targetId === 'wiki-tab-explore') {
                    self.resizeCanvas();
                    self.loadWikiPages();
                } else if (targetId === 'wiki-tab-ingest') {
                    self.loadSessionsList();
                    self.startProgressPolling();
                }
            });
        });

        // Search Filter Explorer
        if (this.elements.searchBox) {
            this.elements.searchBox.addEventListener('input', function(e) {
                self.filterExplorerTree(e.target.value);
            });
        }

        // Configuration Save
        if (this.elements.saveCfgBtn) {
            this.elements.saveCfgBtn.addEventListener('click', function() {
                self.saveConfiguration();
            });
        }

        // Ingestion Select All / Actions
        if (this.elements.selectAllBtn) {
            this.elements.selectAllBtn.addEventListener('click', function() {
                const checkboxes = self.elements.sessionsBody.querySelectorAll('input[type="checkbox"]');
                const allChecked = Array.from(checkboxes).every(c => c.checked);
                checkboxes.forEach(c => c.checked = !allChecked);
            });
        }

        if (this.elements.compileStartBtn) {
            this.elements.compileStartBtn.addEventListener('click', function() {
                self.triggerSelectedCompilation();
            });
        }

        const handleAbort = function() {
            if (self.elements.compileAbortBtn) {
                self.elements.compileAbortBtn.disabled = true;
                self.elements.compileAbortBtn.innerText = "Aborting...";
            }
            if (self.elements.compileAbortMiniBtn) {
                self.elements.compileAbortMiniBtn.disabled = true;
                self.elements.compileAbortMiniBtn.innerText = "Aborting...";
            }
            
            fetch('/api/v1/wiki/ingest/abort', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    if (window.showNotification) {
                        window.showNotification("🛑 Abort request sent to compiler queue", "warning");
                    }
                })
                .catch(err => {
                    console.error("Error aborting ingestion:", err);
                    if (self.elements.compileAbortBtn) {
                        self.elements.compileAbortBtn.disabled = false;
                        self.elements.compileAbortBtn.innerText = "Abort Ingestion";
                    }
                    if (self.elements.compileAbortMiniBtn) {
                        self.elements.compileAbortMiniBtn.disabled = false;
                        self.elements.compileAbortMiniBtn.innerText = "Abort";
                    }
                });
        };

        if (this.elements.compileAbortBtn) {
            this.elements.compileAbortBtn.addEventListener('click', handleAbort);
        }
        if (this.elements.compileAbortMiniBtn) {
            this.elements.compileAbortMiniBtn.addEventListener('click', handleAbort);
        }

        // Chat Input actions
        if (this.elements.chatSendBtn) {
            this.elements.chatSendBtn.addEventListener('click', function() {
                self.sendChatMessage();
            });
        }

        if (this.elements.chatClearBtn) {
            this.elements.chatClearBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                self.clearChatMemory();
            });
        }

        if (this.elements.chatInput) {
            this.elements.chatInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    self.sendChatMessage();
                }
            });
        }

        // Click to expand RAG Chat panel
        const ragContainer = document.getElementById('wiki-rag-container');
        if (ragContainer) {
            ragContainer.addEventListener('click', function(e) {
                e.stopPropagation(); // Avoid immediately triggering document click
                if (!ragContainer.classList.contains('expanded')) {
                    ragContainer.classList.add('expanded');
                    if (self.elements.chatInput) {
                        self.elements.chatInput.focus();
                    }
                }
            });
        }

        // Click outside RAG Chat panel to collapse
        document.addEventListener('click', function(e) {
            if (ragContainer && ragContainer.classList.contains('expanded')) {
                if (!ragContainer.contains(e.target)) {
                    ragContainer.classList.remove('expanded');
                }
            }
        });

        // Wiki link delegates in document reader
        this.elements.pageContent.addEventListener('click', function(e) {
            if (e.target.classList.contains('wiki-link')) {
                const targetPage = e.target.getAttribute('data-page');
                self.loadPageContent(targetPage);
            }
        });

        // Resize Canvas on viewport adjustments
        window.addEventListener('resize', () => this.resizeCanvas());
    },

    // ─── DATA LOADING ────────────────────────────────────────────────────────

    loadWikiStatus() {
        const self = this;
        fetch('/api/v1/wiki/status')
            .then(res => res.json())
            .then(data => {
                if (!data.initialized) {
                    // Auto-initialize if empty
                    fetch('/api/v1/wiki/initialize', { method: 'POST' })
                        .then(() => self.loadWikiPages());
                }
                
                // Show AI provider status popup
                const provider = data.ai_provider || 'offline';
                if (provider === 'groq') {
                    // Fetch real-time limits instead of hardcoding
                    fetch('/api/v1/wiki/groq-limits')
                        .then(r => r.json())
                        .then(limitData => {
                            if (limitData.remaining_requests && limitData.remaining_requests !== 'Unknown') {
                                if (window.showNotification) window.showNotification(`⚡ Groq AI (Llama 3.3 70B) — ${limitData.remaining_requests} API calls remaining today`, "success");
                            } else {
                                if (window.showNotification) window.showNotification("⚡ Groq AI (Llama 3.3 70B) Active", "success");
                            }
                        })
                        .catch(() => {
                            if (window.showNotification) window.showNotification("⚡ Groq AI (Llama 3.3 70B) Active", "success");
                        });
                } else if (provider === 'gemini') {
                    if (window.showNotification) window.showNotification("✅ Gemini AI active (Groq not configured or rate limited)", "success");
                } else {
                    if (window.showNotification) window.showNotification("⚠️ No AI key found — add GROQ_API_KEY to HF Secrets", "error");
                }
            })
            .catch(err => console.error("Error loading wiki status:", err));
    },

    loadWikiPages() {
        const self = this;
        fetch('/api/v1/wiki/pages')
            .then(res => res.json())
            .then(data => {
                self.pages = data.pages || [];
                self.buildExplorerTree();
                self.buildGraphData();
            })
            .catch(err => console.error("Error loading pages tree:", err));
    },

    loadPageContent(filepath) {
        const self = this;
        fetch(`/api/v1/wiki/pages/${filepath}`)
            .then(res => res.json())
            .then(data => {
                self.activePage = filepath;
                self.elements.pageTitle.innerText = filepath.split('/').pop();
                self.elements.pageContent.innerHTML = data.html;
                
                // Categorise file badge
                const catBadge = document.getElementById('wiki-badge-category');
                let category = "System";
                if (filepath.startsWith('events/')) category = "Event Summary";
                else if (filepath.startsWith('speakers/')) category = "Speaker Profile";
                else if (filepath.startsWith('concepts/')) category = "Concept Hub";
                else if (filepath.startsWith('suggestions/')) category = "Suggestion Track";
                
                catBadge.innerText = category;
                
                // Highlight nodes in the Force Graph when corresponding file loaded
                self.highlightGraphNode(filepath);
                
                // Display backlinks if applicable
                self.loadBacklinks(filepath);
            })
            .catch(err => console.error(`Error loading page content for '${filepath}':`, err));
    },

    loadBacklinks(filepath) {
        this.elements.backlinksPanel.style.display = 'none';
        this.elements.backlinksList.innerHTML = '';
        
        // Find other pages linking to this file
        const backlinks = [];
        // Extract filename without path and extension
        const cleanName = filepath.split('/').pop().replace('.md', '');
        
        // Scan nodes/links in active local corpus
        this.graph.links.forEach(l => {
            if (l.targetId === filepath && l.sourceId !== filepath) {
                backlinks.push(l.sourceId);
            }
        });

        const uniqueBacklinks = Array.from(new Set(backlinks));
        if (uniqueBacklinks.length > 0) {
            this.elements.backlinksPanel.style.display = 'block';
            uniqueBacklinks.forEach(link => {
                const badge = document.createElement('span');
                badge.className = 'file-badge wiki-link';
                badge.style.cursor = 'pointer';
                badge.style.background = 'rgba(191, 85, 255, 0.08)';
                badge.style.color = '#ca7bff';
                badge.style.borderColor = 'rgba(191, 85, 255, 0.2)';
                badge.setAttribute('data-page', link);
                badge.innerText = link.split('/').pop().replace('_', ' ').replace('.md', '');
                this.elements.backlinksList.appendChild(badge);
            });
        }
    },

    // ─── EXPLORER RENDERER ───────────────────────────────────────────────────

    buildExplorerTree() {
        const self = this;
        this.elements.treeContainer.innerHTML = '';
        
        // Organize pages into groups
        const groups = {
            "🎤 Speakers": [],
            "📅 Events": [],
            "💡 Concepts": [],
            "🛠️ Suggestions": [],
            "⚙️ Core Logs": []
        };

        this.pages.forEach(p => {
            if (p.startsWith('speakers/')) groups["🎤 Speakers"].push(p);
            else if (p.startsWith('events/')) groups["📅 Events"].push(p);
            else if (p.startsWith('concepts/')) groups["💡 Concepts"].push(p);
            else if (p.startsWith('suggestions/')) groups["🛠️ Suggestions"].push(p);
            else groups["⚙️ Core Logs"].push(p);
        });

        for (const [groupName, files] of Object.entries(groups)) {
            if (files.length === 0 && groupName !== "⚙️ Core Logs") continue;

            const folderDiv = document.createElement('div');
            folderDiv.className = 'wiki-explorer-folder';
            folderDiv.style.marginBottom = '8px';
            
            const header = document.createElement('div');
            header.style.cursor = 'pointer';
            header.style.fontWeight = '600';
            header.style.color = 'var(--text-primary)';
            header.style.display = 'flex';
            header.style.alignItems = 'center';
            header.style.gap = '6px';
            header.innerHTML = `<span class="folder-arrow">▼</span> ${groupName}`;
            
            const list = document.createElement('div');
            list.className = 'folder-list';
            list.style.paddingLeft = '14px';
            list.style.borderLeft = '1px solid var(--glass-border)';
            list.style.marginLeft = '6px';
            list.style.display = 'block';

            header.addEventListener('click', function() {
                const arrow = header.querySelector('.folder-arrow');
                if (list.style.display === 'none') {
                    list.style.display = 'block';
                    arrow.innerText = '▼';
                } else {
                    list.style.display = 'none';
                    arrow.innerText = '▶';
                }
            });

            files.forEach(f => {
                const item = document.createElement('div');
                item.className = 'wiki-explorer-item';
                item.style.cursor = 'pointer';
                item.style.padding = '4px 6px';
                item.style.borderRadius = '4px';
                item.style.fontSize = '12px';
                item.style.color = 'var(--text-muted)';
                item.style.marginTop = '2px';
                item.setAttribute('data-file', f);
                
                // Human friendly name (remove dates/paths/underscores)
                const dispName = f.split('/').pop().replace('_', ' ').replace('.md', '');
                item.innerText = dispName;

                item.addEventListener('click', function(e) {
                    e.stopPropagation();
                    self.elements.treeContainer.querySelectorAll('.wiki-explorer-item').forEach(i => {
                        i.style.background = 'none';
                        i.style.color = '#a6abbb';
                    });
                    item.style.background = 'rgba(0, 255, 255, 0.08)';
                    item.style.color = '#00ffff';
                    self.loadPageContent(f);
                });

                list.appendChild(item);
            });

            folderDiv.appendChild(header);
            folderDiv.appendChild(list);
            this.elements.treeContainer.appendChild(folderDiv);
        }
    },

    filterExplorerTree(query) {
        const q = query.toLowerCase();
        const items = this.elements.treeContainer.querySelectorAll('.wiki-explorer-item');
        items.forEach(item => {
            const text = item.innerText.toLowerCase();
            const file = item.getAttribute('data-file').toLowerCase();
            if (text.includes(q) || file.includes(q)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    },

    // ─── INGESTION MANAGER ───────────────────────────────────────────────────

    loadSessionsList() {
        const self = this;
        fetch('/api/v1/wiki/sessions')
            .then(res => res.json())
            .then(data => {
                self.elements.sessionsBody.innerHTML = '';
                const sessions = data.sessions || [];
                
                if (sessions.length === 0) {
                    self.elements.sessionsBody.innerHTML = `<tr><td colspan="5" style="padding: 20px; text-align: center; color: #8b8b9e;">No sessions found in SQL database.</td></tr>`;
                    return;
                }

                sessions.forEach(s => {
                    const row = document.createElement('tr');
                    row.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                    
                    const badgeClass = s.compiled ? 'badge-success' : 'badge-warning';
                    const badgeText = s.compiled ? 'Compiled' : 'Not Compiled';
                    const badgeStyle = s.compiled ? 'background:rgba(52,211,153,0.1); color:#34d399; border:1px solid rgba(52,211,153,0.2);' : 'background:rgba(251,191,36,0.1); color:#fbbf24; border:1px solid rgba(251,191,36,0.2);';

                    row.innerHTML = `
                        <td style="padding: 12px; text-align: center;">
                            <input type="checkbox" data-speaker="${s.alumni_speaker_name}" data-date="${s.date_of_lecture}" />
                        </td>
                        <td style="padding: 12px; color: #fff; font-weight: 500;">${s.alumni_speaker_name}</td>
                        <td style="padding: 12px; font-family: monospace;">${s.date_of_lecture}</td>
                        <td style="padding: 12px; text-align: center; font-weight:600;">${s.cnt}</td>
                        <td style="padding: 12px; text-align: center;">
                            <span class="file-badge" style="padding: 2px 6px; font-size:10px; border-radius:4px; ${badgeStyle}">${badgeText}</span>
                        </td>
                    `;
                    self.elements.sessionsBody.appendChild(row);
                });
            })
            .catch(err => console.error("Error loading db sessions:", err));
    },

    triggerSelectedCompilation() {
        const checkboxes = this.elements.sessionsBody.querySelectorAll('input[type="checkbox"]:checked');
        const selected = Array.from(checkboxes).map(cb => ({
            speaker: cb.getAttribute('data-speaker'),
            date: cb.getAttribute('data-date')
        }));

        if (selected.length === 0) {
            alert("Please select at least one lecture session to compile.");
            return;
        }

        const self = this;
        fetch('/api/v1/wiki/ingest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sessions: selected })
        })
        .then(res => res.json())
        .then(data => {
            self.elements.consoleLogs.innerHTML += `\n[SYSTEM] ${data.message || 'Queued ingestion.'}`;
            self.startProgressPolling();
        })
        .catch(err => console.error("Error triggering compile ingest:", err));
    },

    startProgressPolling() {
        if (this.ingestInterval) clearInterval(this.ingestInterval);
        
        const self = this;
        this.ingestInterval = setInterval(function() {
            fetch('/api/v1/wiki/ingest/status')
                .then(res => res.json())
                .then(data => {
                    const prog = data.progress;
                    const logs = data.logs || [];
                    
                    // Render logs console
                    if (logs.length > 0) {
                        self.elements.consoleLogs.innerHTML = logs.join('\n');
                        self.elements.consoleLogs.scrollTop = self.elements.consoleLogs.scrollHeight;
                    }

                    if (prog.status === 'PROCESSING' || prog.status === 'ABORTING') {
                        self.elements.progressEmpty.style.display = 'none';
                        self.elements.progressContainer.style.display = 'block';
                        
                        if (self.elements.compileAbortBtn) {
                            self.elements.compileAbortBtn.style.display = 'inline-block';
                            self.elements.compileAbortBtn.disabled = (prog.status === 'ABORTING');
                            self.elements.compileAbortBtn.innerText = prog.status === 'ABORTING' ? "Aborting..." : "Abort Ingestion";
                        }
                        if (self.elements.compileAbortMiniBtn) {
                            self.elements.compileAbortMiniBtn.disabled = (prog.status === 'ABORTING');
                            self.elements.compileAbortMiniBtn.innerText = prog.status === 'ABORTING' ? "Aborting..." : "Abort";
                        }

                        const pct = Math.round((prog.current / prog.total) * 100);
                        self.elements.progressBarFill.style.width = `${pct}%`;
                        self.elements.progressRatio.innerText = `${prog.current} / ${prog.total}`;
                        self.elements.progressStatus.innerText = prog.status === 'ABORTING' ? "ABORTING QUEUE..." : "COMPILING CHANNELS...";
                        self.elements.progressActiveFile.innerText = prog.active_session;
                    } else {
                        self.elements.progressEmpty.style.display = 'block';
                        self.elements.progressContainer.style.display = 'none';
                        
                        if (self.elements.compileAbortBtn) {
                            self.elements.compileAbortBtn.style.display = 'none';
                        }
                        
                        if (prog.status === 'COMPLETE' || prog.status === 'ABORTED') {
                            clearInterval(self.ingestInterval);
                            self.loadSessionsList();
                            self.loadWikiPages();
                            self.loadSuggestedQuestions();
                            
                            if (prog.status === 'ABORTED') {
                                if (window.showNotification) {
                                    window.showNotification("🛑 Ingestion queue aborted.", "warning");
                                }
                            } else {
                                if (window.showNotification) {
                                    window.showNotification("✅ Ingestion queue completed successfully!", "success");
                                }
                            }
                        }
                    }
                })
                .catch(err => {
                    console.error("Error polling compile status:", err);
                    clearInterval(self.ingestInterval);
                });
        }, 1000);
    },

    // ─── CHAT / RAG ASSISTANT ────────────────────────────────────────────────

    sendChatMessage() {
        if (!this.chatHistory) this.chatHistory = [];
        
        const text = this.elements.chatInput.value.trim();
        if (!text) return;

        this.elements.chatInput.value = '';
        this.appendChatMessage('user', text);
        
        // Push user message to history
        this.chatHistory.push({ role: 'user', content: text });

        const self = this;
        // Show indicator
        const loadingDiv = self.appendChatMessage('ai', 'Searching wiki channels & synthesizing answer...');
        
        // Acknowledge if the request takes more than 3 seconds
        const waitTimeout = setTimeout(() => {
            if (loadingDiv && loadingDiv.parentNode) {
                loadingDiv.innerHTML = '<span class="markdown-body">Thinking... this is taking a bit longer than 3 seconds, please wait!</span>';
            }
        }, 3000);
        
        fetch('/api/v1/wiki/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                question: text,
                history: this.chatHistory,
                session_id: this.sessionId
            })
        })
        .then(res => res.json())
        .then(data => {
            clearTimeout(waitTimeout);
            // Remove loading msg
            loadingDiv.remove();
            
            // Render result with parsed links
            self.appendChatMessage('ai', data.answer);
            
            // Push assistant response to history
            self.chatHistory.push({ role: 'assistant', content: data.answer });
        })
        .catch(err => {
            clearTimeout(waitTimeout);
            console.error("Error sending query:", err);
            loadingDiv.innerText = "Error: Failed to fetch answer from service.";
        });
    },

    clearChatMemory() {
        this.chatHistory = [];
        const self = this;
        
        if (this.elements.chatBox) {
            this.elements.chatBox.innerHTML = '<div class="chat-msg system" style="color: var(--text-muted); font-style: italic;">Clearing memory from cloud...</div>';
        }
        
        fetch('/api/v1/wiki/clear-memory', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: this.sessionId })
        })
        .then(res => res.json())
        .then(data => {
            if (self.elements.chatBox) {
                self.elements.chatBox.innerHTML = '<div class="chat-msg system" style="color: var(--text-muted); font-style: italic;">Brain memory cleared. Ask new questions regarding compiled speakers and sessions!</div>';
            }
            if (window.showNotification) window.showNotification("AI memory cleared successfully.", "success");
        })
        .catch(err => {
            console.error("Error clearing memory:", err);
            if (self.elements.chatBox) {
                self.elements.chatBox.innerHTML = '<div class="chat-msg system" style="color: var(--text-muted); font-style: italic;">Local memory cleared, but cloud sync failed. Ready for new questions.</div>';
            }
            if (window.showNotification) window.showNotification("Memory cleared locally only.", "warning");
        });
    },

    appendChatMessage(sender, text) {
        const div = document.createElement('div');
        div.className = `chat-msg ${sender}`;
        div.style.padding = '8px 12px';
        div.style.borderRadius = '8px';
        div.style.fontSize = '12px';
        div.style.lineHeight = '1.5';
        
        if (sender === 'user') {
            div.style.background = 'rgba(168, 85, 247, 0.15)';
            div.style.color = '#000000';
            div.style.alignSelf = 'flex-end';
            div.style.maxWidth = '85%';
            div.innerText = text;
        } else {
            div.style.background = 'rgba(0, 0, 0, 0.05)';
            div.style.color = '#000000';
            div.style.alignSelf = 'flex-start';
            div.style.maxWidth = '90%';
            
            // Custom parser for double bracket links in chat responses
            let parsedText = text
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/\*\*(.*?)\*\*/g, '<strong>\1</strong>')
                .replace(/- (.*?)$/gm, '<li>\1</li>')
                .replace(/\[\[([^\]|]+)\]\]/g, (match, link) => {
                    const label = link.split('/').pop().replace('_', ' ').replace('.md', '');
                    return `<span class="wiki-link" style="color:var(--purple); cursor:pointer; text-decoration:underline;" data-page="${link}">${label}</span>`;
                });
            
            div.innerHTML = parsedText;
            
            // Delegate clicks in chat elements
            div.querySelectorAll('.wiki-link').forEach(linkSpan => {
                linkSpan.addEventListener('click', () => {
                    const page = linkSpan.getAttribute('data-page');
                    this.loadPageContent(page);
                });
            });
        }
        
        this.elements.chatBox.appendChild(div);
        this.elements.chatBox.scrollTop = this.elements.chatBox.scrollHeight;
        return div;
    },

    loadSuggestedQuestions() {
        const container = document.getElementById('wiki-suggested-questions');
        if (!container) return;
        
        container.innerHTML = '<div style="color: var(--text-muted); font-style: italic; font-size: 11px;">Generating smart options...</div>';
        
        const self = this;
        fetch('/api/v1/wiki/suggest-questions')
            .then(res => res.json())
            .then(data => {
                container.innerHTML = '';
                const questions = data.questions || [];
                if (questions.length === 0) {
                    container.innerHTML = '<div style="color: var(--text-muted); font-style: italic; font-size: 11px;">No options available.</div>';
                    return;
                }
                questions.forEach(q => {
                    const chip = document.createElement('div');
                    chip.className = 'wiki-suggest-chip';
                    
                    // Format WikiLink labels if present in question string
                    let label = q;
                    if (q.includes('[[') && q.includes(']]')) {
                        label = q.replace(/\[\[.*?\/([^\]]+)\]\]/g, '$1').replace(/_/g, ' ');
                    }
                    
                    chip.innerText = label;
                    chip.title = q;
                    chip.addEventListener('click', function(e) {
                        e.stopPropagation(); // Stop parent click from expanding/collapsing container
                        self.elements.chatInput.value = q;
                        self.sendChatMessage();
                    });
                    container.appendChild(chip);
                });
            })
            .catch(err => {
                console.error("Error loading suggested questions:", err);
                container.innerHTML = '';
            });
    },

    // ─── CONFIGURATION MANAGEMENT ────────────────────────────────────────────

    saveConfiguration() {
        const gemini = this.elements.cfgGeminiKey.value.trim();
        const url = this.elements.cfgSupabaseUrl.value.trim();
        const key = this.elements.cfgSupabaseKey.value.trim();

        if (!gemini && !url) {
            this.showConfigMsg("Please fill in at least one credential.", "error");
            return;
        }

        const self = this;
        fetch('/api/v1/wiki/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                gemini_key: gemini,
                supabase_url: url,
                supabase_key: key
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                self.showConfigMsg(data.error, "error");
            } else {
                self.showConfigMsg(data.message, "success");
                self.elements.cfgGeminiKey.value = '';
                self.elements.cfgSupabaseUrl.value = '';
                self.elements.cfgSupabaseKey.value = '';
                self.loadWikiPages();
            }
        })
        .catch(err => {
            console.error("Config save failed:", err);
            self.showConfigMsg("Error connecting to settings API.", "error");
        });
    },

    showConfigMsg(text, type) {
        const msg = this.elements.cfgStatusMsg;
        msg.style.display = 'block';
        msg.innerText = text;
        if (type === 'success') {
            msg.style.background = 'rgba(52,211,153,0.1)';
            msg.style.color = '#34d399';
            msg.style.border = '1px solid rgba(52,211,153,0.2)';
        } else {
            msg.style.background = 'rgba(239,68,68,0.1)';
            msg.style.color = '#ef4444';
            msg.style.border = '1px solid rgba(239,68,68,0.2)';
        }
        setTimeout(() => msg.style.display = 'none', 4000);
    },

    // ─── CANVAS KNOWLEDGE GRAPH SIMULATOR ────────────────────────────────────

    initGraphSimulation() {
        const canvas = this.elements.canvas;
        const ctx = canvas.getContext('2d');
        const self = this;

        // Physics parameters
        const kRepulsion = 400; // Coulomb repulsion constant
        const kLink = 0.05;     // Spring stiffness
        const friction = 0.85;  // Velocity friction
        const minDistance = 60; // Desired spring length

        // Drag states
        let mouseX = 0, mouseY = 0;
        let isMouseDown = false;

        // Resize Canvas to fit wrapper card
        this.resizeCanvas = function() {
            const rect = canvas.parentNode.getBoundingClientRect();
            canvas.width = rect.width;
            canvas.height = rect.height;
        };

        // Track mouse coordinates
        canvas.addEventListener('mousemove', function(e) {
            const rect = canvas.getBoundingClientRect();
            mouseX = e.clientX - rect.left;
            mouseY = e.clientY - rect.top;

            if (isMouseDown && self.graph.draggedNode) {
                self.graph.draggedNode.x = mouseX;
                self.graph.draggedNode.y = mouseY;
            }
        });

        canvas.addEventListener('mousedown', function(e) {
            isMouseDown = true;
            const rect = canvas.getBoundingClientRect();
            mouseX = e.clientX - rect.left;
            mouseY = e.clientY - rect.top;
            
            // Detect if clicked node
            self.graph.draggedNode = self.findNodeAt(mouseX, mouseY);
            if (self.graph.draggedNode) {
                self.graph.selectedNode = self.graph.draggedNode;
                // Auto load corresponding page if it has path
                if (self.graph.selectedNode.id) {
                    self.loadPageContent(self.graph.selectedNode.id);
                }
            }
        });

        window.addEventListener('mouseup', function() {
            isMouseDown = false;
            self.graph.draggedNode = null;
        });

        // Animation Loop
        function tick() {
            self.updateForces();
            self.drawGraph(ctx);
            requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    },

    resizeCanvas() {
        // Overridden by initGraphSimulation
    },

    findNodeAt(x, y) {
        for (const n of this.graph.nodes) {
            const dist = Math.hypot(n.x - x, n.y - y);
            if (dist < n.radius + 6) return n;
        }
        return null;
    },

    highlightGraphNode(filepath) {
        this.graph.nodes.forEach(n => {
            n.highlighted = n.id === filepath;
            if (n.highlighted) {
                n.radius = 12;
            } else {
                n.radius = n.type === 'concept' ? 8 : (n.type === 'speaker' ? 10 : 7);
            }
        });
    },

    buildGraphData() {
        const self = this;
        fetch('/api/v1/wiki/graph')
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    console.error("Graph fetch error:", data.error);
                    return;
                }
                const oldNodes = new Map(self.graph.nodes.map(n => [n.id, n]));
                self.graph.nodes = [];
                self.graph.links = [];

                data.nodes.forEach(nData => {
                    const nid = nData.id;
                    const existing = oldNodes.get(nid);
                    
                    let type = "core";
                    let color = "#3b82f6";
                    let radius = 6;
                    if (nid.startsWith('events/')) {
                        type = "event";
                        color = "#34d399";
                        radius = 7;
                    } else if (nid.startsWith('speakers/')) {
                        type = "speaker";
                        color = "#ca7bff";
                        radius = 10;
                    } else if (nid.startsWith('concepts/')) {
                        type = "concept";
                        color = "#00ffff";
                        radius = 8;
                    } else if (nid.startsWith('suggestions/')) {
                        type = "suggestion";
                        color = "#ff716c";
                        radius = 7;
                    }

                    self.graph.nodes.push({
                        id: nid,
                        type: type,
                        color: color,
                        radius: radius,
                        x: existing ? existing.x : Math.random() * 300 + 50,
                        y: existing ? existing.y : Math.random() * 200 + 50,
                        vx: existing ? existing.vx : 0,
                        vy: existing ? existing.vy : 0,
                        label: nid.split('/').pop().replace('.md', '').replace(/_/g, ' '),
                        highlighted: existing ? existing.highlighted : false
                    });
                });

                data.links.forEach(rl => {
                    const sNode = self.graph.nodes.find(n => n.id === rl.source);
                    const tNode = self.graph.nodes.find(n => n.id === rl.target);
                    if (sNode && tNode) {
                        self.graph.links.push({
                            source: sNode,
                            target: tNode,
                            sourceId: rl.source,
                            targetId: rl.target
                        });
                    }
                });
                
                // Restart physics simulation with new nodes
                self.drawGraph(self.elements.canvas.getContext('2d'));
            })
            .catch(err => console.error("Error loading graph data:", err));
    },

    updateForces() {
        const nodes = this.graph.nodes;
        const links = this.graph.links;
        if (nodes.length === 0) return;

        const canvas = this.elements.canvas;
        const W = canvas.width || 300;
        const H = canvas.height || 240;

        // 1. Repulsion force between ALL node pairs (Coulomb's Law)
        for (let i = 0; i < nodes.length; i++) {
            const n1 = nodes[i];
            for (let j = i + 1; j < nodes.length; j++) {
                const n2 = nodes[j];
                
                const dx = n2.x - n1.x;
                const dy = n2.y - n1.y;
                const dist = Math.hypot(dx, dy) || 1.0;
                
                // Repel forces
                if (dist < 220) {
                    const force = (400) / (dist * dist);
                    const fx = (dx / dist) * force;
                    const fy = (dy / dist) * force;
                    
                    n1.vx -= fx;
                    n1.vy -= fy;
                    n2.vx += fx;
                    n2.vy += fy;
                }
            }
        }

        // 2. Attraction forces along edges (Hooke's Law Springs)
        links.forEach(link => {
            const s = link.source;
            const t = link.target;
            
            const dx = t.x - s.x;
            const dy = t.y - s.y;
            const dist = Math.hypot(dx, dy) || 1.0;
            
            const delta = dist - 70; // Target link distance
            const force = delta * 0.03; // Spring stiffness
            
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            
            s.vx += fx;
            s.vy += fy;
            t.vx -= fx;
            t.vy -= fy;
        });

        // 3. Gravity pulling nodes towards center
        const centerX = W / 2;
        const centerY = H / 2;
        nodes.forEach(n => {
            const dx = centerX - n.x;
            const dy = centerY - n.y;
            n.vx += dx * 0.005;
            n.vy += dy * 0.005;
        });

        // 4. Update coordinates & apply damping
        nodes.forEach(n => {
            if (n === this.graph.draggedNode) return; // Skip dragged node to follow mouse
            
            n.x += n.vx;
            n.y += n.vy;
            
            n.vx *= 0.85; // Damping
            n.vy *= 0.85;
            
            // Constrain within boundaries
            n.x = Math.max(n.radius + 5, Math.min(W - n.radius - 5, n.x));
            n.y = Math.max(n.radius + 5, Math.min(H - n.radius - 5, n.y));
        });
    },

    drawGraph(ctx) {
        const canvas = this.elements.canvas;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw Links (lines)
        ctx.lineWidth = 1;
        this.graph.links.forEach(l => {
            ctx.beginPath();
            ctx.moveTo(l.source.x, l.source.y);
            ctx.lineTo(l.target.x, l.target.y);
            
            // Glowing neon connection color
            const grad = ctx.createLinearGradient(l.source.x, l.source.y, l.target.x, l.target.y);
            grad.addColorStop(0, l.source.color + '33'); // Low opacity
            grad.addColorStop(1, l.target.color + '33');
            ctx.strokeStyle = grad;
            ctx.stroke();
        });

        // Draw Nodes
        this.graph.nodes.forEach(n => {
            // Draw glow shadow if highlighted
            if (n.highlighted) {
                ctx.beginPath();
                ctx.arc(n.x, n.y, n.radius + 8, 0, 2 * Math.PI);
                ctx.fillStyle = n.color + '22';
                ctx.fill();
            }

            ctx.beginPath();
            ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
            ctx.fillStyle = n.color;
            ctx.fill();
            
            // Node border
            ctx.strokeStyle = '#080e1a';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Label text drawing
            ctx.fillStyle = n.highlighted ? '#1e293b' : '#475569';
            ctx.font = n.highlighted ? 'bold 10px Inter' : '9px Inter';
            ctx.textAlign = 'center';
            ctx.fillText(n.label, n.x, n.y - n.radius - 4);
        });
    }
};

// Bootstrap Wiki on Document ready
document.addEventListener('DOMContentLoaded', function() {
    Wiki.init();
});
