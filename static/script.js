document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('uploadForm');
    const loader = document.getElementById('loader');
    const results = document.getElementById('results');
    const candidatesList = document.getElementById('candidatesList');
    const countSpan = document.getElementById('count');
    
    // File drop zones UI logic
    ['workday', 'greenhouse', 'resume'].forEach(id => {
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
        
        const wdFile = document.getElementById('workday').files[0];
        const ghFile = document.getElementById('greenhouse').files[0];
        const resFile = document.getElementById('resume').files[0];
        
        if (!wdFile && !ghFile && !resFile) {
            alert('Please select at least one file to resolve.');
            return;
        }

        const formData = new FormData();
        if (wdFile) formData.append('workday', wdFile);
        if (ghFile) formData.append('greenhouse', ghFile);
        if (resFile) formData.append('resume', resFile);

        // Show Loader
        form.parentElement.classList.add('hidden');
        results.classList.add('hidden');
        loader.classList.remove('hidden');

        try {
            const response = await fetch('/api/resolve', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            
            if (response.ok) {
                renderCandidates(data.data);
            } else {
                alert(`Error: ${data.detail}`);
                form.parentElement.classList.remove('hidden');
            }
        } catch (error) {
            alert('Failed to connect to the resolution engine.');
            form.parentElement.classList.remove('hidden');
        } finally {
            loader.classList.add('hidden');
        }
    });

    function renderCandidates(candidates) {
        candidatesList.innerHTML = '';
        countSpan.textContent = candidates.length;
        
        candidates.forEach(cand => {
            const card = document.createElement('div');
            card.className = 'candidate-card glass-panel';
            
            const name = cand.full_name || 'Unknown Candidate';
            const email = (cand.emails && cand.emails.length > 0) ? cand.emails[0] : 'N/A';
            const phone = (cand.phones && cand.phones.length > 0) ? cand.phones[0] : 'N/A';
            const locationStr = cand.location ? `${cand.location.city || ''}, ${cand.location.country || ''}` : 'N/A';
            
            // Confidence Color
            let confClass = 'conf-high';
            if (cand.confidence_score < 0.6) confClass = 'conf-low';
            else if (cand.confidence_score < 0.8) confClass = 'conf-med';
            
            const confPercent = Math.round(cand.confidence_score * 100);
            
            let skillsHtml = '';
            if (cand.skills && cand.skills.length > 0) {
                skillsHtml = `
                    <div class="skills-tags">
                        ${cand.skills.map(s => `<span class="skill-tag">${s}</span>`).join('')}
                    </div>
                `;
            }

            card.innerHTML = `
                <div class="card-header">
                    <div>
                        <div class="candidate-name">${name}</div>
                        <div class="candidate-id">${cand.candidate_id.split('-')[0]}...</div>
                    </div>
                    <div class="confidence-badge ${confClass}">
                        ${confPercent}% Conf
                    </div>
                </div>
                <div class="card-body">
                    <div class="info-row">
                        <i class="fa-solid fa-envelope"></i>
                        <span>${email}</span>
                    </div>
                    <div class="info-row">
                        <i class="fa-solid fa-phone"></i>
                        <span>${phone}</span>
                    </div>
                    <div class="info-row">
                        <i class="fa-solid fa-location-dot"></i>
                        <span>${locationStr}</span>
                    </div>
                    ${skillsHtml}
                    <button class="btn-provenance" data-prov='${JSON.stringify(cand.provenance).replace(/'/g, "&#39;")}'>
                        View Provenance
                    </button>
                </div>
            `;
            
            candidatesList.appendChild(card);
        });

        // Add event listeners for provenance buttons
        document.querySelectorAll('.btn-provenance').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const provData = JSON.parse(e.target.getAttribute('data-prov'));
                showProvenance(provData);
            });
        });

        results.classList.remove('hidden');
    }

    // Modal Logic
    const modal = document.getElementById('provenanceModal');
    const closeBtn = document.querySelector('.close-btn');

    function showProvenance(provenance) {
        if (!provenance) {
            document.getElementById('provenanceData').textContent = 'No provenance data available.';
        } else {
            document.getElementById('provenanceData').textContent = JSON.stringify(provenance, null, 2);
        }
        document.getElementById('provenanceModal').classList.remove('hidden');
    }

    closeBtn.addEventListener('click', () => {
        modal.classList.add('hidden');
    });

    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
        }
    });
});
