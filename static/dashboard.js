// dashboard.js - sidebar behavior + chart generation + simple pagination
document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.getElementById('app-sidebar');
  const hamburger = document.getElementById('hamburger');
  const toggle = document.getElementById('toggle-sidebar');

  // persist expanded/collapsed state in localStorage
  const EXP_KEY = 'db_sidebar_expanded';
  function setExpanded(val){
    if(val){
      sidebar.classList.add('expanded');
    } else {
      sidebar.classList.remove('expanded');
    }
    localStorage.setItem(EXP_KEY, val ? '1' : '0');
  }
  const initial = localStorage.getItem(EXP_KEY) === '1';
  setExpanded(initial);

  hamburger?.addEventListener('click', () => setExpanded(!sidebar.classList.contains('expanded')));
  toggle?.addEventListener('click', () => setExpanded(!sidebar.classList.contains('expanded')));

  // Chart rendering helpers
  const charts = {};

  function createPie(ctx, labels, data) {
    return new Chart(ctx, {
      type: 'pie',
      data: { labels, datasets: [{ data, backgroundColor: ['#007bff','#28a745','#ffc107','#dc3545','#ff8a00'] }] },
      options: { responsive: true, maintainAspectRatio: false, plugins:{ legend:{ position:'bottom' } } }
    });
  }
  function createLine(ctx, labels, data) {
    return new Chart(ctx, {
      type: 'line',
      data: { labels, datasets: [{ label: 'Entries', data, borderColor: '#007bff', tension:0.3, fill:false }] },
      options: { responsive:true, maintainAspectRatio:false, scales:{ y:{ beginAtZero:true } } }
    });
  }
  function createBar(ctx, labels, data) {
    return new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets:[{ label:'Total', data, backgroundColor:'#17a2b8' }] },
      options: { responsive:true, maintainAspectRatio:false, scales:{ y:{ beginAtZero:true } } }
    });
  }

  // Data pagination helper: split array into pages
  function paginateArray(arr, pageSize){
    const pages = [];
    for(let i=0;i<arr.length;i+=pageSize) pages.push(arr.slice(i, i+pageSize));
    return pages;
  }

  // Render charts with pagination support
  function initProjectChart(){
    const ctx = document.getElementById('projectChart');
    if(!ctx) return;
    const raw = (window.PROJECT_DATA || []);
    // produce labels & values; each page will show up to 6 categories
    const labels = raw.map(r=>r.status||r.type||'Unknown');
    const values = raw.map(r=>Number(r.count||0));
    const pages = paginateArray(labels.map((l,i)=>({l, v:values[i]})), 6);

    let current = 0;
    function draw(){
      const page = pages[current] || [];
      const labs = page.map(x=>x.l);
      const vals = page.map(x=>x.v);
      if(charts.project) charts.project.destroy();
      charts.project = createPie(ctx, labs, vals);
      document.getElementById('project-page-info').textContent = `${current+1} / ${Math.max(1,pages.length)}`;
    }

    document.querySelectorAll('.chart-page-btn[data-chart="project"]').forEach(btn=>{
      btn.addEventListener('click', (ev)=>{
        const dir = btn.dataset.dir;
        if(dir==='next') current = Math.min(pages.length-1, current+1);
        else current = Math.max(0, current-1);
        draw();
      });
    });

    draw();
  }

  function initLogbookChart(){
    const ctx = document.getElementById('logbookChart');
    if(!ctx) return;
    const raw = (window.LOGBOOK_DATA || []);
    // raw expected: [{log_date: '2025-10-31', count: 2}, ...]
    // Sort by date to be consistent
    raw.sort((a,b)=> new Date(a.log_date) - new Date(b.log_date));
    const labels = raw.map(r=>r.log_date);
    const values = raw.map(r=>Number(r.count||0));
    const pages = paginateArray(labels.map((l,i)=>({l, v:values[i]})), 10); // show 10 days per page

    let current = 0;
    function draw(){
      const page = pages[current] || [];
      const labs = page.map(x=>x.l);
      const vals = page.map(x=>x.v);
      if(charts.logbook) charts.logbook.destroy();
      charts.logbook = createLine(ctx, labs, vals);
      document.getElementById('logbook-page-info').textContent = `${current+1} / ${Math.max(1,pages.length)}`;
    }

    document.querySelectorAll('.chart-page-btn[data-chart="logbook"]').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const dir = btn.dataset.dir;
        if(dir==='next') current = Math.min(pages.length-1, current+1);
        else current = Math.max(0, current-1);
        draw();
      });
    });

    draw();
  }

  function initReportChart(){
    const ctx = document.getElementById('reportChart');
    if(!ctx) return;
    const raw = (window.REPORT_DATA || []);
    const labels = raw.map(r => r.type || r.status || 'Unknown');
    const values = raw.map(r => Number(r.count||0));
    const pages = paginateArray(labels.map((l,i)=>({l,v:values[i]})), 6);

    let current = 0;
    function draw(){
      const page = pages[current] || [];
      const labs = page.map(x=>x.l);
      const vals = page.map(x=>x.v);
      if(charts.report) charts.report.destroy();
      charts.report = createBar(ctx, labs, vals);
      document.getElementById('report-page-info').textContent = `${current+1} / ${Math.max(1,pages.length)}`;
    }

    document.querySelectorAll('.chart-page-btn[data-chart="report"]').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const dir = btn.dataset.dir;
        if(dir==='next') current = Math.min(pages.length-1, current+1);
        else current = Math.max(0, current-1);
        draw();
      });
    });

    draw();
  }

  // Initialize charts
  initProjectChart();
  initLogbookChart();
  initReportChart();

  // Optional: redraw on window resize (charts are responsive but fix some behavior)
  let resizeTimeout;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      Object.values(charts).forEach(c => c && c.resize && c.resize());
    }, 200);
  });

});
