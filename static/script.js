document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('uploadForm');
    const loader = document.getElementById('loader');
    const results = document.getElementById('results');
    const candidatesList = document.getElementById('candidatesList');
    const countSpan = document.getElementById('count');

    // File drop zones UI logic
    ['recruiter', 'ats', 'resume', 'github', 'notes'].forEach(id => {
        const input = document.getElementById(id);
        const dropArea = document.getElementById(`${id}Drop`);
        const msg = dropArea.querySelector('.file-msg');

        input.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                msg.textContent = e.target.files[0].name;
                dropArea.style.borderColor = 'var(--success-color)';
                dropArea.querySelector('i').style.color = 'var(--success-color)';
            }
        });

        input.addEventListener('dragenter', () => dropArea.classList.add('dragover'));
        input.addEventListener('dragleave', () => dropArea.classList.remove('dragover'));
        input.addEventListener('drop', () => dropArea.classList.remove('dragover'));
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const recFile = document.getElementById('recruiter').files[0];
        const atsFile = document.getElementById('ats').files[0];
        const resFile = document.getElementById('resume').files[0];

        const ghUrl = document.getElementById('github_url').value.trim();
        const liUrl = document.getElementById('linkedin_url').value.trim();
        const atsUrl = document.getElementById('ats_url').value.trim();

        const hasStructured = recFile || atsFile || atsUrl;
        const hasUnstructured = resFile || ghUrl || liUrl;

        if (!hasStructured || !hasUnstructured) {
            alert('Assignment Requirement: Please provide at least one structured source (Recruiter CSV, ATS JSON, etc.) AND at least one unstructured source (Resume PDF, GitHub Profile).');
            return;
        }

        const formData = new FormData();
        if (recFile) formData.append('recruiter', recFile);
        if (atsFile) formData.append('ats', atsFile);
        if (resFile) formData.append('resume', resFile);
        if (ghUrl) formData.append('github_url', ghUrl);
        if (liUrl) formData.append('linkedin_url', liUrl);
        if (atsUrl) formData.append('ats_url', atsUrl);

        form.parentElement.classList.add('hidden');
        results.classList.add('hidden');
        loader.classList.remove('hidden');

        try {
            const response = await fetch('/api/resolve', { method: 'POST', body: formData });
            const data = await response.json();

            if (response.ok) {
                renderCandidates(data.data);
            } else {
                alert(`Error: ${data.detail}`);
                form.parentElement.classList.remove('hidden');
            }
        } catch (error) {
            console.error(error);
            alert('Frontend Error: ' + error.message);
            form.parentElement.classList.remove('hidden');
        } finally {
            loader.classList.add('hidden');
        }
    });

    // ─── Helpers ──────────────────────────────────────────────────────────
    function esc(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }

    function val(v, fallback = 'N/A') {
        if (v === null || v === undefined || v === '') return fallback;
        return v;
    }

    function skillName(s) {
        return typeof s === 'object' ? (s.name || '') : s;
    }

    // ─── Render Cards ─────────────────────────────────────────────────────
    function renderCandidates(candidates) {
        candidatesList.innerHTML = '';
        countSpan.textContent = candidates.length;

        candidates.forEach(cand => {
            const card = document.createElement('div');
            card.className = 'candidate-card glass-panel';

            // -- Basic Fields --
            const name = val(cand.full_name, 'Unknown Candidate');
            const candidateId = val(cand.candidate_id, '');
            const shortId = candidateId ? candidateId.split('-')[0] + '...' : 'N/A';

            const emails = (cand.emails && cand.emails.length > 0) ? cand.emails : null;
            const phones = (cand.phones && cand.phones.length > 0) ? cand.phones : null;
            const headline = val(cand.headline, null);
            const yearsExp = cand.years_experience != null ? cand.years_experience + ' yrs' : null;

            // -- Location --
            let locationStr = null;
            if (cand.location) {
                const parts = [cand.location.city, cand.location.region, cand.location.country].filter(Boolean);
                if (parts.length > 0) locationStr = parts.join(', ');
            }

            // -- Links --
            const links = cand.links || {};

            // -- Confidence --
            const rawConf = cand.overall_confidence || 0;
            let confClass = rawConf >= 0.8 ? 'conf-high' : rawConf >= 0.6 ? 'conf-med' : 'conf-low';
            const confPercent = Math.round(rawConf * 100);

            // -- Skills HTML --
            let skillsHtml = '';
            if (cand.skills && cand.skills.length > 0) {
                const names = cand.skills.map(skillName).filter(Boolean);
                skillsHtml = `<div class="skills-tags">${names.map(s => `<span class="skill-tag">${esc(s)}</span>`).join('')}</div>`;
            }

            // -- Experience HTML --
            let expHtml = '';
            if (cand.experience && cand.experience.length > 0) {
                const rows = cand.experience.map(ex => `
                    <tr>
                        <td>${esc(ex.company || ex.current_company || '—')}</td>
                        <td>${esc(ex.title || '—')}</td>
                        <td>${esc(ex.start || '—')}</td>
                        <td>${esc(ex.end || 'Present')}</td>
                    </tr>`).join('');
                expHtml = `
                    <div class="section-block">
                        <div class="section-label"><i class="fa-solid fa-briefcase"></i> Experience</div>
                        <table class="data-table">
                            <thead><tr><th>Company</th><th>Title</th><th>Start</th><th>End</th></tr></thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>`;
            }

            // -- Education HTML --
            let eduHtml = '';
            if (cand.education && cand.education.length > 0) {
                const rows = cand.education.map(ed => `
                    <tr>
                        <td>${esc(ed.institution || ed.school || '—')}</td>
                        <td>${esc(ed.degree || '—')}</td>
                        <td>${esc(ed.field || '—')}</td>
                        <td>${esc(ed.end_year ? String(ed.end_year) : '—')}</td>
                    </tr>`).join('');
                eduHtml = `
                    <div class="section-block">
                        <div class="section-label"><i class="fa-solid fa-graduation-cap"></i> Education</div>
                        <table class="data-table">
                            <thead><tr><th>Institution</th><th>Degree</th><th>Field</th><th>End Year</th></tr></thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>`;
            }

            // -- Provenance Table HTML --
            let provHtml = '';
            if (cand.provenance && cand.provenance.length > 0) {
                const rows = cand.provenance.map(p => `
                    <tr>
                        <td><code>${esc(p.field || '—')}</code></td>
                        <td>${esc(p.source || '—')}</td>
                        <td>${esc(p.method || '—')}</td>
                    </tr>`).join('');
                provHtml = `
                    <div class="section-block provenance-block">
                        <div class="section-label"><i class="fa-solid fa-sitemap"></i> Provenance — Where each value came from</div>
                        <table class="data-table prov-table">
                            <thead>
                                <tr>
                                    <th>Field</th>
                                    <th>Source</th>
                                    <th>Method</th>
                                </tr>
                                <tr class="type-row">
                                    <td>string</td>
                                    <td>string</td>
                                    <td>string</td>
                                </tr>
                                <tr class="note-row">
                                    <td>canonical field name</td>
                                    <td>data origin system</td>
                                    <td>how value was resolved</td>
                                </tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>`;
            }

            // -- Links HTML --
            let linksHtml = '';
            const linkItems = [];
            if (links.linkedin) linkItems.push(`<a href="${esc(links.linkedin)}" target="_blank" class="link-chip"><i class="fa-brands fa-linkedin"></i> LinkedIn</a>`);
            if (links.github) linkItems.push(`<a href="${esc(links.github)}" target="_blank" class="link-chip"><i class="fa-brands fa-github"></i> GitHub</a>`);
            if (links.portfolio) linkItems.push(`<a href="${esc(links.portfolio)}" target="_blank" class="link-chip"><i class="fa-solid fa-globe"></i> Portfolio</a>`);
            if (links.other && links.other.length > 0) {
                links.other.forEach(u => linkItems.push(`<a href="${esc(u)}" target="_blank" class="link-chip"><i class="fa-solid fa-link"></i> Link</a>`));
            }
            if (linkItems.length > 0) {
                linksHtml = `<div class="section-block"><div class="section-label"><i class="fa-solid fa-link"></i> Links</div><div class="links-row">${linkItems.join('')}</div></div>`;
            }

            // -- Full Card HTML --
            card.innerHTML = `
                <div class="card-header">
                    <div>
                        <div class="candidate-name">${esc(name)}</div>
                        <div class="candidate-id">${esc(shortId)}</div>
                        ${headline ? `<div class="candidate-headline">${esc(headline)}</div>` : ''}
                    </div>
                    <div class="confidence-badge ${confClass}">${confPercent}% Conf</div>
                </div>
                <div class="card-body">
                    <!-- Contact Info -->
                    <div class="section-block">
                        <div class="section-label"><i class="fa-solid fa-address-card"></i> Contact Info</div>
                        <table class="data-table contact-table">
                            <thead>
                                <tr><th>Field</th><th>Value</th><th>Type / Shape</th><th>Notes</th></tr>
                                <tr class="type-row"><td>emails</td><td>${emails ? emails.join(', ') : '—'}</td><td>string[]</td><td>primary contact email</td></tr>
                                <tr class="type-row"><td>phones</td><td>${phones ? phones.join(', ') : '—'}</td><td>string[]</td><td>E.164 format</td></tr>
                                <tr class="type-row"><td>location</td><td>${locationStr || '—'}</td><td>{ city, region, country }</td><td>ISO-3166 alpha-2 country</td></tr>
                                <tr class="type-row"><td>years_experience</td><td>${yearsExp || '—'}</td><td>number | null</td><td>total years</td></tr>
                            </thead>
                        </table>
                    </div>

                    <!-- Skills -->
                    ${cand.skills && cand.skills.length > 0 ? `
                    <div class="section-block">
                        <div class="section-label"><i class="fa-solid fa-code"></i> Skills <span class="schema-note">[ { name, confidence, sources[] } ]</span></div>
                        ${skillsHtml}
                    </div>` : ''}

                    <!-- Links -->
                    ${linksHtml}

                    <!-- Experience -->
                    ${expHtml}

                    <!-- Education -->
                    ${eduHtml}

                    <!-- Provenance -->
                    ${provHtml}
                </div>
            `;

            candidatesList.appendChild(card);
        });

        results.classList.remove('hidden');
    }

    // Modal Logic — kept for backward compat but provenance is now inline
    const modal = document.getElementById('provenanceModal');
    const closeBtn = document.querySelector('.close-btn');

    if (closeBtn) {
        closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
    }
    if (modal) {
        window.addEventListener('click', (e) => {
            if (e.target === modal) modal.classList.add('hidden');
        });
    }
});
