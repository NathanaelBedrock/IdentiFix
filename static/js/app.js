function app() {
  return {
    investigations: [],
    current: null,
    selectedId: null,
    activeTab: 'profiles',
    showNewInv: false,
    showCollectors: false,
    submitting: false,
    collectors: [],
    form: { username: '', email: '', discord_id: '', twitter_handle: '', reddit_username: '' },
    openCards: {},
    showUnconfirmed: false,
    liveDuration: '-',
    _sseSource: null,
    _graphNetwork: null,
    _pollTimer: null,
    _durationTimer: null,

    async init() {
      await this.loadInvestigations();
      await this.loadCollectors();
      this._pollTimer = setInterval(() => this.loadInvestigations(), 5000);
    },

    async loadInvestigations() {
      try {
        const res = await fetch('/api/investigations');
        this.investigations = await res.json();
        if (this.selectedId) {
          const found = this.investigations.find(i => i.id === this.selectedId);
          if (found && ['completed', 'failed', 'cancelled'].includes(found.status)) {
            await this.loadFull(this.selectedId);
          }
        }
      } catch {}
    },

    async loadCollectors() {
      try {
        const res = await fetch('/api/collectors');
        this.collectors = await res.json();
      } catch {}
    },

    async selectInvestigation(id) {
      this.selectedId = id;
      this.activeTab = 'profiles';
      this._stopSSE();
      this._stopDurationTimer();
      await this.loadFull(id);
      this._startDurationTimer();
      if (this.current && !['completed', 'failed', 'cancelled'].includes(this.current.status)) {
        this._startSSE(id);
      }
    },

    async loadFull(id) {
      try {
        const res = await fetch(`/api/investigations/${id}`);
        this.current = await res.json();
      } catch {}
    },

    _startSSE(id) {
      this._sseSource = new EventSource(`/api/investigations/${id}/events`);
      this._sseSource.addEventListener('collector_done', (e) => {
        this.loadFull(id);
      });
      this._sseSource.addEventListener('completed', async (e) => {
        await this.loadFull(id);
        await this.loadInvestigations();
        this._stopSSE();
        this._startDurationTimer();
      });
      this._sseSource.addEventListener('failed', async (e) => {
        await this.loadFull(id);
        await this.loadInvestigations();
        this._stopSSE();
        this._startDurationTimer();
      });
      this._sseSource.addEventListener('cancelled', async (e) => {
        await this.loadFull(id);
        this._stopSSE();
        this._startDurationTimer();
      });
      this._sseSource.addEventListener('graph_ready', () => {
        this.loadFull(id);
      });
    },

    _stopSSE() {
      if (this._sseSource) {
        this._sseSource.close();
        this._sseSource = null;
      }
    },

    _startDurationTimer() {
      this._stopDurationTimer();
      const toUtc = s => s && !s.endsWith('Z') ? s + 'Z' : s;
      const tick = () => {
        if (!this.current?.started_at) { this.liveDuration = '-'; return; }
        const end = this.current.completed_at ? new Date(toUtc(this.current.completed_at)) : new Date();
        this.liveDuration = Math.round((end - new Date(toUtc(this.current.started_at))) / 1000) + 's';
      };
      tick();
      this._durationTimer = setInterval(tick, 1000);
    },

    _stopDurationTimer() {
      if (this._durationTimer) { clearInterval(this._durationTimer); this._durationTimer = null; }
    },

    async submitInvestigation() {
      const payload = {};
      for (const [k, v] of Object.entries(this.form)) {
        if (v.trim()) payload[k] = v.trim();
      }
      if (Object.keys(payload).length === 0) return;

      this.submitting = true;
      try {
        const res = await fetch('/api/investigations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        this.showNewInv = false;
        this.form = { username: '', email: '', discord_id: '', twitter_handle: '', reddit_username: '' };
        await this.loadInvestigations();
        await this.selectInvestigation(data.id);
      } finally {
        this.submitting = false;
      }
    },

    async deleteInvestigation(id) {
      if (!confirm('Delete this investigation?')) return;
      await fetch(`/api/investigations/${id}`, { method: 'DELETE' });
      this.current = null;
      this.selectedId = null;
      this._stopSSE();
      await this.loadInvestigations();
    },

    hitFullName(hit) {
      const m = hit.metadata || {};
      return m.full_name || m.fullname || m.global_name || m.name
        || m.ids?.fullname || m.ids?.full_name || m.ids?.name
        || m.socid?.name || null;
    },

    toggleCard(key) {
      this.openCards[key] = !this.openCards[key];
    },

    areAllCardsExpanded() {
      const hits = this.profileHits();
      return hits.length > 0 && hits.every(h => this.openCards[h.platform + h.url]);
    },

    toggleAllCards() {
      const expand = !this.areAllCardsExpanded();
      for (const hit of this.profileHits()) {
        this.openCards[hit.platform + hit.url] = expand;
      }
    },

    areAllEmailCardsExpanded() {
      const regs = this.emailRegistrations();
      return regs.length > 0 && regs.every(r => this.openCards['email:' + r.site]);
    },

    toggleAllEmailCards() {
      const expand = !this.areAllEmailCardsExpanded();
      for (const reg of this.emailRegistrations()) {
        this.openCards['email:' + reg.site] = expand;
      }
    },

    profileHits() {
      if (!this.current) return [];
      const seen = new Set();
      const hits = [];
      for (const result of (this.current.results || [])) {
        for (const hit of (result.profile_hits || [])) {
          if (!this.showUnconfirmed && !hit.metadata?.confirmed_by_multiple) continue;
          const key = hit.platform.toLowerCase() + ':' + (hit.username || '').toLowerCase();
          if (!seen.has(key)) {
            seen.add(key);
            hits.push(hit);
          } else {
            const existing = hits.find(h =>
              h.platform.toLowerCase() + ':' + (h.username || '').toLowerCase() === key
            );
            if (existing && hit.metadata?.ids && !existing.metadata?.ids) {
              Object.assign(existing.metadata, hit.metadata);
            }
          }
        }
      }
      return hits.sort((a, b) => a.platform.localeCompare(b.platform));
    },

    emailRegistrations() {
      if (!this.current) return [];
      const seen = new Set();
      const regs = [];
      for (const result of (this.current.results || [])) {
        for (const reg of (result.email_registrations || [])) {
          if (reg.registered && !seen.has(reg.site)) {
            seen.add(reg.site);
            regs.push(reg);
          }
        }
      }
      return regs.sort((a, b) => a.site.localeCompare(b.site));
    },

    emailBreaches() {
      if (!this.current) return [];
      const seen = new Set();
      const breaches = [];
      for (const result of (this.current.results || [])) {
        for (const b of (result.email_breaches || [])) {
          if (!seen.has(b.source)) { seen.add(b.source); breaches.push(b); }
        }
      }
      return breaches;
    },

    statCards() {
      if (!this.current) return [];
      const s = this.current;
      const summary = s.summary || {};
      const duration = this.liveDuration;
      return [
        ['Profile Hits', summary.profile_hits ?? 0, 'text-sky-400'],
        ['Email Registrations', summary.email_registrations ?? 0, 'text-purple-400'],
        ['Data Breaches', summary.email_breaches ?? 0, 'text-red-400'],
        ['Duration', duration, 'text-slate-400'],
      ];
    },

    tabLabel(tab) {
      const labels = {
        profiles: 'Profiles',
        email: 'Email Sites',
        breaches: 'Breaches',
        graph: 'Graph',
        ai_report: 'AI Report',
        raw: 'Raw Data',
      };
      return labels[tab] || tab;
    },

    formatTarget(target) {
      if (!target) return '';
      const parts = [];
      if (target.username) parts.push('Username: ' + target.username);
      if (target.email) parts.push('Email: ' + target.email);
      if (target.twitter_handle) parts.push('Twitter: @' + target.twitter_handle);
      if (target.discord_id) parts.push('Discord: ' + target.discord_id);
      if (target.reddit_username) parts.push('Reddit: u/' + target.reddit_username);
      return parts.join('  ·  ');
    },

    renderGraph(graphData) {
      if (!graphData || !graphData.nodes || graphData.nodes.length === 0) return;

      const container = document.getElementById('graph-container');
      if (!container) return;

      const colorMap = {
        person:           { background: '#0ea5e9', border: '#0284c7' },
        username:         { background: '#a855f7', border: '#9333ea' },
        category:         { background: '#1e293b', border: '#475569' },
        platform_profile: { background: '#22c55e', border: '#16a34a' },
        email:            { background: '#eab308', border: '#ca8a04' },
        breach:           { background: '#ef4444', border: '#dc2626' },
        image:            { background: '#f97316', border: '#ea580c' },
      };

      const nodes = graphData.nodes.map(n => {
        const confirmations = n.metadata?.confirmation_count || 1;
        const baseSize = n.type === 'person' ? 28
          : n.type === 'category' ? 20
          : n.type === 'username' ? 18
          : 10 + Math.min(confirmations * 3, 10);
        return {
          id: n.id,
          label: n.label.length > 20 ? n.label.slice(0, 18) + '…' : n.label,
          title: n.label + (confirmations > 1 ? ` (confirmed ×${confirmations})` : ''),
          color: colorMap[n.type] || colorMap.platform_profile,
          font: {
            color: n.type === 'category' ? '#94a3b8' : '#e2e8f0',
            size: n.type === 'category' ? 11 : 12,
          },
          shape: n.type === 'person' ? 'star' : n.type === 'category' ? 'diamond' : 'dot',
          size: baseSize,
        };
      });

      const edges = graphData.edges.map(e => ({
        from: e.source,
        to: e.target,
        label: e.label,
        color: { color: '#334155', highlight: '#60a5fa' },
        font: { color: '#64748b', size: 10, align: 'middle' },
        width: e.weight,
        arrows: 'to',
      }));

      const options = {
        physics: {
          stabilization: { iterations: 150 },
          barnesHut: { gravitationalConstant: -8000, damping: 0.5 },
        },
        interaction: { hover: true, tooltipDelay: 100 },
        edges: { smooth: { type: 'continuous' } },
      };

      if (this._graphNetwork) {
        this._graphNetwork.setData({ nodes, edges });
      } else {
        this._graphNetwork = new vis.Network(
          container,
          { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) },
          options,
        );
      }
    },
  };
}
