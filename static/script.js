document.addEventListener('DOMContentLoaded', function () {
    const menuBtn = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    
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
        
        // Update Lucide icons after toggle
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    });

    // Close sidebar when overlay is clicked (mobile only)
    if (overlay) {
        overlay.addEventListener('click', function () {
            if (window.innerWidth <= 1024) {
                sidebar.classList.remove('active');
                sidebar.setAttribute('aria-hidden', 'true');
            }
        });
    }

    // Close sidebar when clicking on sidebar links (mobile only)
    const navItems = sidebar.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', function () {
            if (window.innerWidth <= 1024) {
                sidebar.classList.remove('active');
                sidebar.setAttribute('aria-hidden', 'true');
            }
        });
    });

    // ESC key closes sidebar
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && sidebar.classList.contains('active')) {
            sidebar.classList.remove('active');
            sidebar.setAttribute('aria-hidden', 'true');
        }
    });
});

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

function parseDate(value) {
  if (!value) return null;
  return new Date(value + 'T00:00:00');
}

function confirmDelete(ev, url) {
  ev.preventDefault();
  if (confirm('Are you sure you want to delete this?')) {
    window.location = url;
  }
}

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