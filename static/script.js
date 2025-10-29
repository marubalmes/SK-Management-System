// Sidebar toggle and accessibility
document.addEventListener('DOMContentLoaded', function () {
  const menuBtn = document.getElementById('menu-toggle');
  const sidebar = document.getElementById('sidebar');

  // Ensure elements exist
  if (!menuBtn || !sidebar) return;

  // Toggle sidebar when menu button is clicked
  menuBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    const isActive = sidebar.classList.toggle('active');
    sidebar.setAttribute('aria-hidden', !isActive);
  });

  // Click outside sidebar to close
  document.addEventListener('click', function (e) {
    if (!sidebar.classList.contains('active')) return;
    const inside = sidebar.contains(e.target);
    const isToggle = e.target.closest('#menu-toggle');
    if (!inside && !isToggle) {
      sidebar.classList.remove('active');
      sidebar.setAttribute('aria-hidden', 'true');
    }
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
