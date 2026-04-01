(function () {
  const API_BASE = '';
  const POLL_INTERVAL_MS = 20000;
  var DAY_MS = 24 * 60 * 60 * 1000;
  var TIME_FILTERS = {
    '1': 1 * DAY_MS,
    '2': 2 * DAY_MS,
    '5': 5 * DAY_MS,
    '14': 14 * DAY_MS,
    '30': 30 * DAY_MS,
    '45': 45 * DAY_MS,
    '60': 60 * DAY_MS,
    '90': 90 * DAY_MS,
    '180': 180 * DAY_MS,
    '365': 365 * DAY_MS,
  };

  let map = null;
  let heatmap = null;
  let routes = [];
  let drivers = [];
  let selectedRouteId = null;
  let routeMarkers = [];
  let focusPolyline = null;
  let directionsService = null;
  let focusRouteSummaryEl = null;
  const MILE_TOLERANCE = 25;
  let mapsApiKey = '';
  let zoneActive = false;
  let zoneCenter = null;
  let zoneRadiusMiles = 50;
  let zoneCircle = null;
  let zoneCenterMarker = null;
  let lastUpdated = null;

  function get(path) {
    return fetch(API_BASE + path).then(r => r.json());
  }

  function patch(path, body) {
    return fetch(API_BASE + path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(r => r.json());
  }

  function initMap() {
    get('/api/config').then(function (config) {
      mapsApiKey = config.mapsApiKey || '';
      function createMap() {
        if (map) return;
        var naBounds = new google.maps.LatLngBounds(
          new google.maps.LatLng(14.0, -130.0),
          new google.maps.LatLng(72.0, -50.0)
        );
        map = new google.maps.Map(document.getElementById('mapContainer'), {
          center: { lat: 39.5, lng: -98.35 },
          zoom: 4,
          styles: darkMapStyles(),
          restriction: { latLngBounds: naBounds, strictBounds: false },
        });
        loadData();
      }
      if (window.google && window.google.maps) {
        createMap();
        return;
      }
      window.__mapsReady = createMap;
      const script = document.createElement('script');
      script.src = 'https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(mapsApiKey) + '&libraries=visualization,geometry&callback=window.__mapsReady';
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    });
  }

  function darkMapStyles() {
    return [
      { elementType: 'geometry', stylers: [{ color: '#1d2c4d' }] },
      { elementType: 'labels.text.fill', stylers: [{ color: '#8ec3b9' }] },
      { elementType: 'labels.text.stroke', stylers: [{ color: '#1a3646' }] },
      { featureType: 'administrative.country', elementType: 'geometry.stroke', stylers: [{ color: '#4b6878' }] },
      { featureType: 'administrative.land_parcel', elementType: 'labels.text.fill', stylers: [{ color: '#64779e' }] },
      { featureType: 'administrative.province', elementType: 'geometry.stroke', stylers: [{ color: '#4b6878' }] },
      { featureType: 'landscape.man_made', elementType: 'geometry.stroke', stylers: [{ color: '#334e87' }] },
      { featureType: 'landscape.natural', elementType: 'geometry', stylers: [{ color: '#023e58' }] },
      { featureType: 'poi', elementType: 'geometry', stylers: [{ color: '#283d6a' }] },
      { featureType: 'poi', elementType: 'labels.text.fill', stylers: [{ color: '#6f9ba5' }] },
      { featureType: 'poi', elementType: 'labels.text.stroke', stylers: [{ color: '#1d2c4d' }] },
      { featureType: 'road', elementType: 'geometry.fill', stylers: [{ color: '#304a7d' }] },
      { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: '#255763' }] },
      { featureType: 'road', elementType: 'labels.text.fill', stylers: [{ color: '#98a5be' }] },
      { featureType: 'road', elementType: 'labels.text.stroke', stylers: [{ color: '#1d2c4d' }] },
      { featureType: 'road.highway', elementType: 'geometry.fill', stylers: [{ color: '#2c6675' }] },
      { featureType: 'road.highway', elementType: 'geometry.stroke', stylers: [{ color: '#255763' }] },
      { featureType: 'transit', elementType: 'labels.text.fill', stylers: [{ color: '#98a5be' }] },
      { featureType: 'transit', elementType: 'labels.text.stroke', stylers: [{ color: '#1d2c4d' }] },
      { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0e1626' }] },
      { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#4e6d70' }] },
    ];
  }

  function updateLastUpdatedLabel() {
    var el = document.getElementById('lastUpdated');
    if (!el) return;
    if (lastUpdated) {
      var t = lastUpdated;
      var label = 'Last updated: ' + t.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', second: '2-digit' });
      el.textContent = label;
    } else {
      el.textContent = '—';
    }
  }

  function getRouteTimestamp(r) {
    if (r.date && typeof r.date === 'string') {
      var parts = r.date.trim().match(/^(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?/);
      if (parts) {
        var year = parseInt(parts[3], 10);
        if (!parts[3] || isNaN(year)) {
          var y = new Date();
          year = y.getFullYear();
        } else if (year < 100) year += 2000;
        var month = parseInt(parts[1], 10) - 1;
        var day = parseInt(parts[2], 10);
        var d = new Date(year, month, day);
        if (!isNaN(d.getTime())) return d.getTime();
      }
    }
    if (r.posted_at) {
      var t = new Date(r.posted_at).getTime();
      if (!isNaN(t)) return t;
    }
    return Date.now();
  }

  function routeInZone(route) {
    if (!zoneActive || !zoneCenter || !zoneRadiusMiles) return true;
    if (!window.google || !window.google.maps || !window.google.maps.geometry) return true;
    var centerLatLng = new google.maps.LatLng(zoneCenter.lat, zoneCenter.lng);
    var radiusMeters = zoneRadiusMiles * 1609.344;
    if (typeof route.origin_lat === 'number' && typeof route.origin_lng === 'number') {
      var originLatLng = new google.maps.LatLng(route.origin_lat, route.origin_lng);
      if (google.maps.geometry.spherical.computeDistanceBetween(centerLatLng, originLatLng) <= radiusMeters) return true;
    }
    if (typeof route.dest_lat === 'number' && typeof route.dest_lng === 'number') {
      var destLatLng = new google.maps.LatLng(route.dest_lat, route.dest_lng);
      if (google.maps.geometry.spherical.computeDistanceBetween(centerLatLng, destLatLng) <= radiusMeters) return true;
    }
    return false;
  }

  function filterRoutes() {
    var timeVal = document.getElementById('timeFilter').value;
    var routeTypeVal = document.getElementById('routeTypeFilter').value;
    var now = Date.now();
    var filtered = routes.filter(function (r) {
      var t = getRouteTimestamp(r);
      if (timeVal !== 'all') {
        var ms = TIME_FILTERS[timeVal];
        if (ms != null && (now - t) > ms) return false;
      }
      if (routeTypeVal !== 'all') {
        var types = r.route_types || [];
        var match = types.some(function (rt) {
          return String(rt).toLowerCase() === routeTypeVal.toLowerCase();
        });
        if (!match) return false;
      }
      return true;
    });
    if (zoneActive && zoneCenter && zoneRadiusMiles) {
      filtered = filtered.filter(routeInZone);
    }
    return filtered;
  }

  function getHeatmapPoints(filtered) {
    const points = [];
    filtered.forEach(function (r) {
      if (typeof r.origin_lat === 'number' && typeof r.origin_lng === 'number') {
        points.push(new google.maps.LatLng(r.origin_lat, r.origin_lng));
      }
      if (typeof r.dest_lat === 'number' && typeof r.dest_lng === 'number') {
        points.push(new google.maps.LatLng(r.dest_lat, r.dest_lng));
      }
    });
    return points;
  }

  function updateHeatmap() {
    const filtered = filterRoutes();
    const points = getHeatmapPoints(filtered);
    if (!map || !window.google) return;
    if (heatmap) heatmap.setMap(null);
    if (points.length > 0) {
      heatmap = new google.maps.visualization.HeatmapLayer({ data: points, map: map });
    }
  }

  function clearZone() {
    zoneActive = false;
    zoneCenter = null;
    zoneRadiusMiles = 50;
    if (zoneCircle) {
      zoneCircle.setMap(null);
      zoneCircle = null;
    }
    if (zoneCenterMarker) {
      zoneCenterMarker.setMap(null);
      zoneCenterMarker = null;
    }
    var zoneControls = document.getElementById('zoneControls');
    var zoneToggle = document.getElementById('zoneToggle');
    if (zoneControls) zoneControls.style.display = 'none';
    if (zoneToggle) zoneToggle.setAttribute('aria-pressed', 'false');
    renderCards();
    updateHeatmap();
  }

  function applyZoneCenterAndCircle() {
    if (!map || !window.google || !zoneCenter) return;
    if (zoneCircle) zoneCircle.setMap(null);
    zoneCircle = new google.maps.Circle({
      center: zoneCenter,
      radius: zoneRadiusMiles * 1609.344,
      map: map,
      fillColor: '#58a6ff',
      fillOpacity: 0.08,
      strokeColor: '#58a6ff',
      strokeWeight: 2,
    });
    if (zoneCenterMarker) zoneCenterMarker.setMap(null);
    zoneCenterMarker = new google.maps.Marker({
      position: zoneCenter,
      map: map,
      draggable: true,
      title: 'Zone center (drag to move)',
    });
    zoneCenterMarker.addListener('dragend', function () {
      var pos = zoneCenterMarker.getPosition();
      zoneCenter = { lat: pos.lat(), lng: pos.lng() };
      if (zoneCircle) zoneCircle.setCenter(zoneCenter);
      renderCards();
      updateHeatmap();
    });
  }

  function setupZoneTool() {
    var zoneToggle = document.getElementById('zoneToggle');
    var zoneControls = document.getElementById('zoneControls');
    var zoneRadius = document.getElementById('zoneRadius');
    var zoneClear = document.getElementById('zoneClear');
    if (!zoneToggle || !zoneControls || !map) return;

    zoneToggle.addEventListener('click', function () {
      if (zoneActive) {
        clearZone();
      } else {
        zoneActive = true;
        zoneControls.style.display = 'block';
        zoneToggle.setAttribute('aria-pressed', 'true');
      }
    });

    zoneRadius.addEventListener('change', function () {
      zoneRadiusMiles = parseInt(zoneRadius.value, 10) || 50;
      if (zoneCircle && zoneCenter) {
        zoneCircle.setRadius(zoneRadiusMiles * 1609.344);
      }
      renderCards();
      updateHeatmap();
    });

    zoneClear.addEventListener('click', function () {
      clearZone();
    });

    map.addListener('click', function (event) {
      if (!zoneActive) return;
      zoneCenter = { lat: event.latLng.lat(), lng: event.latLng.lng() };
      zoneRadiusMiles = parseInt(zoneRadius.value, 10) || 50;
      applyZoneCenterAndCircle();
      renderCards();
      updateHeatmap();
    });
  }

  function clearFocus() {
    routeMarkers.forEach(function (m) { m.setMap(null); });
    routeMarkers = [];
    if (focusPolyline) {
      focusPolyline.setMap(null);
      focusPolyline = null;
    }
    if (focusRouteSummaryEl) {
      focusRouteSummaryEl.textContent = '';
      focusRouteSummaryEl.className = 'route-focus-summary';
      focusRouteSummaryEl.style.display = 'none';
    }
  }

  function showRouteSummary(drivingMiles, estimatedMiles) {
    if (!focusRouteSummaryEl) {
      focusRouteSummaryEl = document.getElementById('routeFocusSummary');
    }
    if (!focusRouteSummaryEl) return;
    var msg = 'Driving route: ' + Math.round(drivingMiles) + ' mi';
    var within = true;
    if (estimatedMiles != null && estimatedMiles > 0) {
      var diff = Math.abs(drivingMiles - estimatedMiles);
      within = diff <= MILE_TOLERANCE;
      msg += ' \u00B7 Est. ' + estimatedMiles + ' mi';
      if (within) {
        msg += ' \u2713 Within range';
      } else {
        msg += ' \u2014 Verify (diff ' + Math.round(diff) + ' mi)';
      }
    }
    focusRouteSummaryEl.textContent = msg;
    focusRouteSummaryEl.className = 'route-focus-summary' + (within ? '' : ' route-focus-summary-warn');
    focusRouteSummaryEl.style.display = 'block';
  }

  function focusRoute(route) {
    clearFocus();
    if (!route || !map || !window.google) return;
    var originLat = route.origin_lat;
    var originLng = route.origin_lng;
    var destLat = route.dest_lat;
    var destLng = route.dest_lng;
    if (typeof originLat !== 'number' || typeof originLng !== 'number' || typeof destLat !== 'number' || typeof destLng !== 'number') {
      return;
    }
    var origin = new google.maps.LatLng(originLat, originLng);
    var dest = new google.maps.LatLng(destLat, destLng);
    routeMarkers.push(new google.maps.Marker({ position: origin, map: map, title: route.origin }));
    routeMarkers.push(new google.maps.Marker({ position: dest, map: map, title: route.destination }));

    if (!directionsService) directionsService = new google.maps.DirectionsService();

    directionsService.route({
      origin: origin,
      destination: dest,
      travelMode: google.maps.TravelMode.DRIVING,
    }, function (result, status) {
      if (status === google.maps.DirectionsStatus.OK && result.routes && result.routes[0]) {
        var r = result.routes[0];
        var path = r.overview_path || [];
        if (path.length === 0 && r.legs && r.legs[0]) {
          r.legs[0].steps.forEach(function (step) {
            path = path.concat(step.path);
          });
        }
        if (path.length > 0) {
          focusPolyline = new google.maps.Polyline({
            path: path,
            geodesic: true,
            strokeColor: '#58a6ff',
            strokeOpacity: 0.9,
            strokeWeight: 4,
            map: map,
          });
          var bounds = new google.maps.LatLngBounds();
          path.forEach(function (p) { bounds.extend(p); });
          map.fitBounds(bounds, 60);
        }
        var drivingMeters = 0;
        if (r.legs) {
          r.legs.forEach(function (leg) {
            if (leg.distance && leg.distance.value) drivingMeters += leg.distance.value;
          });
        }
        var drivingMiles = drivingMeters / 1609.344;
        showRouteSummary(drivingMiles, route.routed_miles != null ? route.routed_miles : route.miles);
      } else {
        var fallbackPath = [origin, dest];
        focusPolyline = new google.maps.Polyline({
          path: fallbackPath,
          geodesic: true,
          strokeColor: '#58a6ff',
          strokeOpacity: 0.7,
          strokeWeight: 3,
          map: map,
        });
        map.fitBounds(new google.maps.LatLngBounds(origin, dest), 80);
        if (focusRouteSummaryEl) {
          focusRouteSummaryEl.textContent = 'Driving route unavailable; showing straight line.';
          focusRouteSummaryEl.className = 'route-focus-summary route-focus-summary-warn';
          focusRouteSummaryEl.style.display = 'block';
        }
      }
    });
  }

  function renderCards() {
    var filtered = filterRoutes();
    var container = document.getElementById('routeCards');

    if (filtered.length === 0) {
      container.innerHTML = '<div class="empty-state">No routes in this range. Adjust filters or clear the zone.</div>';
      updateHeatmap();
      return;
    }

    // Sort by most recent first (time received/posted), then descend to oldest — within current filters (time, route type, zone)
    function recencyMs(r) {
      if (r.posted_at) {
        var t = new Date(r.posted_at).getTime();
        if (!isNaN(t)) return t;
      }
      return getRouteTimestamp(r);
    }
    const sorted = filtered.slice().sort(function (a, b) {
      return recencyMs(b) - recencyMs(a);
    });

    container.innerHTML = '';
    sorted.forEach(function (r) {
      const card = document.createElement('div');
      card.className = 'route-card' + (selectedRouteId === r.id ? ' selected' : '');
      card.dataset.routeId = r.id;
      var routeLine = (r.chase && r.chase.trim()) ? r.chase : ((r.origin || '') + ' \u2192 ' + (r.destination || ''));
      var parts = [];
      if (r.routed_miles != null) parts.push(r.routed_miles + ' routed mi');
      else if (r.miles != null) parts.push(r.miles + ' mi');
      if (r.date) parts.push(r.date);
      var metaLine = parts.join(' \u00B7 ');
      var companyDisplay = (r.company && r.company.trim()) ? escapeHtml(r.company.trim()) : '\u2014';
      var dotMcParts = [];
      if (r.dot) dotMcParts.push('DOT: ' + escapeHtml(r.dot));
      if (r.mc) dotMcParts.push('MC: ' + escapeHtml(r.mc));
      var dotMcLine = dotMcParts.length ? ('<div class="route-dotmc"><span class="route-label">Licenses</span> ' + dotMcParts.join(' \u00B7 ') + '</div>') : '';
      var contactText = r.phone ? (escapeHtml(r.phone) + (r.phone_text_only ? ' (Text Only)' : '')) : '';
      var payDisplay = (r.pay && r.pay.trim()) ? escapeHtml(r.pay.trim()) : '\u2014';
      var locationDetail = '';
      if (r.origin_detail && r.origin_detail.trim()) locationDetail += '<div class="route-location-detail"><span class="route-label">Origin</span> ' + escapeHtml(r.origin_detail.trim()) + '</div>';
      if (r.dest_detail && r.dest_detail.trim()) locationDetail += '<div class="route-location-detail"><span class="route-label">Destination</span> ' + escapeHtml(r.dest_detail.trim()) + '</div>';
      card.innerHTML =
        '<div class="route-route">' + escapeHtml(routeLine) + '</div>' +
        (metaLine ? '<div class="route-meta">' + metaLine + '</div>' : '') +
        '<div class="route-company"><span class="route-label">Company</span> ' + companyDisplay + '</div>' +
        dotMcLine +
        '<div class="route-pay"><span class="route-label">Pay</span> ' + payDisplay + '</div>' +
        locationDetail +
        (contactText ? '<div class="route-contact"><span class="route-label">Contact</span> ' + contactText + '</div>' : '') +
        '<div class="route-status"><span class="status-' + (r.status || 'new') + '">' + (r.status === 'assigned' ? 'Assigned' : 'New') + (r.assigned_driver ? ' \u00B7 ' + escapeHtml(r.assigned_driver) : '') + '</span></div>' +
        '<select class="driver-select" data-route-id="' + escapeHtml(r.id) + '"><option value="">Assign driver...</option></select>';
      const sel = card.querySelector('.driver-select');
      drivers.forEach(function (d) {
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = d;
        if (r.assigned_driver === d) opt.selected = true;
        sel.appendChild(opt);
      });
      sel.addEventListener('change', function () {
        const id = this.dataset.routeId;
        const driver = this.value || null;
        patch('/api/routes/' + encodeURIComponent(id), { assigned_driver: driver || '', status: driver ? 'assigned' : 'new' }).then(function (updated) {
          const idx = routes.findIndex(function (x) { return x.id === id; });
          if (idx >= 0) {
            routes[idx] = updated;
            renderCards();
          }
        });
      });
      card.addEventListener('click', function (e) {
        if (e.target.tagName === 'SELECT') return;
        selectedRouteId = r.id;
        renderCards();
        focusRoute(r);
      });
      container.appendChild(card);
    });

    updateHeatmap();
  }

  function escapeHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function loadData() {
    Promise.all([get('/api/routes'), get('/api/drivers')]).then(function (results) {
      routes = results[0] || [];
      drivers = results[1] || [];
      lastUpdated = new Date();
      updateLastUpdatedLabel();
      document.getElementById('timeFilter').addEventListener('change', renderCards);
      document.getElementById('routeTypeFilter').addEventListener('change', renderCards);
      var refreshBtn = document.getElementById('refreshBtn');
      if (refreshBtn) refreshBtn.addEventListener('click', refreshRoutes);
      renderCards();
      setupZoneTool();
    });
  }

  function poll() {
    get('/api/routes').then(function (data) {
      routes = data || [];
      lastUpdated = new Date();
      updateLastUpdatedLabel();
      renderCards();
    });
  }

  function refreshRoutes() {
    var btn = document.getElementById('refreshBtn');
    if (btn) btn.disabled = true;
    get('/api/routes').then(function (data) {
      routes = data || [];
      lastUpdated = new Date();
      updateLastUpdatedLabel();
      renderCards();
      if (btn) btn.disabled = false;
    }).catch(function () {
      if (btn) btn.disabled = false;
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMap);
  } else {
    initMap();
  }

  setInterval(poll, POLL_INTERVAL_MS);
})();
