document.addEventListener('DOMContentLoaded', function () {
    const menuBtn = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    
    // Initialize Lucide icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // Ensure elements exist
    if (!menuBtn || !sidebar) {
        console.error('Menu button or sidebar not found');
        return;
    }

    // ✅ AUTO-OPEN SIDEBAR ON LOGIN (check for URL parameter)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('login') || urlParams.has('sidebar')) {
        sidebar.classList.add('active');
        sidebar.setAttribute('aria-hidden', 'false');
    }

    // Toggle sidebar when menu button is clicked
    menuBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        const isActive = sidebar.classList.toggle('active');
        sidebar.setAttribute('aria-hidden', !isActive);
        
        // Update Lucide icons after toggle (in case menu icon needs change)
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    });

    // ESC key closes sidebar (optional - you can remove this too if you want)
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && sidebar.classList.contains('active')) {
            sidebar.classList.remove('active');
            sidebar.setAttribute('aria-hidden', 'true');
        }
    });

    // REMOVED: Click outside sidebar to close functionality
    // This keeps the sidebar open until the menu button is clicked again
});

function filterTable() {
  const searchValue = document.getElementById('searchName').value.toLowerCase();
  const fromDate = document.getElementById('fromDate').value;
  const toDate = document.getElementById('toDate').value;
  const rows = document.querySelectorAll('tbody tr');

  rows.forEach(row => {
    const name = row.cells[0].textContent.toLowerCase();
    const date = row.cells[4].textContent;
    let visible = true;

    if (searchValue && !name.includes(searchValue)) visible = false;
    if (fromDate && date < fromDate) visible = false;
    if (toDate && date > toDate) visible = false;

    row.style.display = visible ? '' : 'none';
  });
}

function parseDate(value) {
  if (!value) return null;
  return new Date(value + 'T00:00:00');
}

function filterTable() {
  const searchValue = (document.getElementById('searchName') || {value:''}).value.toLowerCase();
  const fromDateRaw = (document.getElementById('fromDate') || {value:''}).value;
  const toDateRaw = (document.getElementById('toDate') || {value:''}).value;
  const filterSitio = (document.getElementById('filterSitio') || {value:''}).value;
  const fromDate = parseDate(fromDateRaw);
  const toDate = parseDate(toDateRaw);
  const rows = document.querySelectorAll('tbody tr');

  rows.forEach(row => {
    const cells = row.cells;
    const name = (cells[0] && cells[0].textContent || '').toLowerCase();
    let sitio = (cells[1] && cells[1].textContent || '').trim();
    let dateText = '';

    for (let i=0;i<cells.length;i++){
      const txt = cells[i].textContent.trim();
      if (txt.match(/^\d{4}-\d{2}-\d{2}$/)) {
        dateText = txt;
        break;
      }
    }

    let visible = true;
    if (searchValue && !name.includes(searchValue)) visible = false;
    if (filterSitio && sitio !== filterSitio) visible = false;

    if (fromDate && dateText) {
      const rowDate = parseDate(dateText);
      if (rowDate < fromDate) visible = false;
    }
    if (toDate && dateText) {
      const rowDate = parseDate(dateText);
      if (rowDate > toDate) visible = false;
    }
    row.style.display = visible ? '' : 'none';
  });
}

function confirmDelete(ev, url) {
  ev.preventDefault();
  if (confirm('Are you sure you want to delete this?')) {
    window.location = url;
  }
}

// In the showEvidence function, update the image src URL
function showEvidence(entryId) {
    fetch(`/logbook/evidence/${entryId}`)
        .then(response => response.json())
        .then(data => {
            const evidenceDiv = document.getElementById(`evidence-${entryId}`);
            if (data.evidence_files && data.evidence_files.length > 0) {
                evidenceDiv.innerHTML = data.evidence_files.map(file => `
                    <div style="margin-bottom:10px;">
                        <img src="/uploads/logbook_evidence/${file}" 
                             style="max-width:100%; max-height:200px; border-radius:5px; margin-bottom:5px;" 
                             alt="Evidence photo">
                        <div style="font-size:12px; color:#666;">${file}</div>
                    </div>
                `).join('');
            } else {
                evidenceDiv.innerHTML = '<em>No evidence files</em>';
            }
        });
}