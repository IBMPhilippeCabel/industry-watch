
  var selectedCat = 'all';
  var selectedBrand = 'all';
  var cards = document.querySelectorAll('.grid .card');

  function updateCardVisibility() {
    cards.forEach(function(c) {
      var matchCat = (selectedCat === 'all' || c.dataset.cat === selectedCat);
      var brandsList = (c.dataset.brands || '').split(',').filter(Boolean);
      var matchBrand = (selectedBrand === 'all' || brandsList.indexOf(selectedBrand) !== -1);
      c.classList.toggle('hidden', !(matchCat && matchBrand));
    });
  }

  document.querySelectorAll('nav.cat-filters button').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.querySelectorAll('nav.cat-filters button').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      selectedCat = btn.dataset.cat;
      updateCardVisibility();
    });
  });

  document.querySelectorAll('nav.brand-filters button').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.querySelectorAll('nav.brand-filters button').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      selectedBrand = btn.dataset.brand;
      updateCardVisibility();
    });
  });

  function initDropdown(btnId, dropId) {
    var btn = document.getElementById(btnId);
    var drop = document.getElementById(dropId);
    if (!btn || !drop) return;
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      drop.classList.toggle('open');
    });
    document.addEventListener('click', function() {
      drop.classList.remove('open');
    });
    drop.addEventListener('click', function(e) { e.stopPropagation(); });
  }
  initDropdown('src-btn', 'src-dropdown');
  initDropdown('arc-btn', 'arc-dropdown');
  initDropdown('sites-btn', 'sites-dropdown');
