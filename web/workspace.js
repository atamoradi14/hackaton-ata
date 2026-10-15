"use strict";
// Existing map, API, evidence and confirmation workflow are retained in app.js.
const H = FlowHydraulics;
const preparation = document.createElement("details");
preparation.hidden = true;
preparation.innerHTML =
  "<summary>Data preparation · separate from simulation</summary>";
$("job-panel").before(preparation);
preparation.append($("job-panel"));
$("scenario-panel").innerHTML = `
<div id="workflow-state" class="workflow-state">Data ready → Review inputs</div>
<fieldset><legend>Saved SFINCS results</legend><label>Selected scenario<select id="site-run"><option value="">Select saved results</option></select></label><button id="refresh-runs" class="secondary">Refresh saved runs</button><div id="empty-result" class="empty-result">No hydraulic run selected. Select saved results or review inputs below and run SFINCS.</div><div id="scenario-status" class="scenario-status" role="status"></div><label>Hydraulic layer<select id="hydraulic-layer"><option value="depth">Water depth · m</option><option value="maximum">Maximum saved depth · m</option><option value="surface">Water-surface elevation · m NZVD2016</option><option value="velocity">Velocity magnitude · m/s</option><option value="difference">Depth change · m</option><option value="max-difference">Maximum-depth change · m</option><option value="velocity-change">Sampled peak-speed change · m/s</option></select></label><label><input id="flow-arrows" type="checkbox"> Native velocity direction arrows</label><label>Overlay opacity<input id="water-opacity" type="range" min="0.1" max="0.9" step="0.1" value="0.6"></label><button id="fit-simulation" class="secondary">Fit simulation extent</button><p>Central 320 m of an 800 m domain. 4 m hydraulic cells; 1 m terrain subgrid is not a 1 m water solution.</p></fieldset>
<fieldset><legend>Baseline → modified comparison</legend><label>Baseline<select id="baseline-run"><option value="">Choose baseline</option></select></label><button id="compare-runs" class="secondary">Compare with selected scenario</button><div id="comparison-status" class="scenario-status" role="status"></div><button id="swipe-compare" class="secondary">Swipe baseline / modified</button><button id="before-after" class="secondary">Show baseline / modified</button><button id="export-comparison" class="secondary">Export comparison GeoJSON</button><p>Identical numerical inputs required. Orange = increase; blue = decrease. Zero differences remain visible.</p></fieldset>
<fieldset><legend>Hypothetical finite walls</legend><label>Assumed height above sampled DEM (m)<input id="map-wall-height" type="number" min="0.1" max="3" step="0.1" value="0.6"></label><button id="map-draw-wall" class="secondary">Draw wall on map</button><button id="map-finish-wall" class="secondary">Finish polyline</button><button id="map-cancel-wall" class="secondary">Cancel drawing</button><p id="map-wall-help">Click 2–12 ground vertices, then Finish. Drag handles to edit. Moving a vertex preserves its absolute crest for review.</p><div id="map-wall-list"></div><p id="wall-result-note">Proposed wall edits affect the next simulation. Saved water results are immutable.</p><button id="save-walls" class="secondary">Save walls</button><button id="reload-walls" class="secondary">Reload saved walls</button><button id="export-walls" class="secondary">Export walls GeoJSON</button></fieldset>
<fieldset><legend>Reviewed exploratory rainfall</legend><div class="input-pair"><label>Uniform rain (mm/h)<input id="site-rain" type="number" min="0" max="100" value="50"></label><label>Duration (min)<input id="site-duration" type="number" min="10" max="60" value="30"></label><label>Manning roughness<input id="site-manning" type="number" min="0.015" max="0.08" step="0.005" value="0.03"></label><label>Infiltration (mm/h)<input id="site-infiltration" type="number" min="0" max="20" value="0"></label></div><label class="review"><input id="site-review" type="checkbox"> I review assumed rain/roughness/losses, unverified domain/free-outflow perimeter, no external inflow, solid building cells, no roof runoff or pipe drainage, and hypothetical finite crests. Uncalibrated; not HIRDS.</label><button id="site-simulate" class="primary wide">Run actual SFINCS</button><button id="site-baseline" class="secondary wide">Run same inputs without walls</button></fieldset>
<div id="inspect-result" class="inspect-result">Click the map to inspect terrain and saved hydraulic values.</div><button id="workspace-evidence" class="secondary wide">Sources, profiles & exports</button>`;
let workspaceId = null,
  sceneData = null,
  selected = null,
  baseline = null,
  comparisonData = null,
  siteFrame = 0,
  sitePlaying = null,
  runGeneration = 0,
  walls2d = [],
  draft = [],
  drawing = false,
  pollRun = null,
  waterLayer = null,
  aerial = null,
  before = false,
  viewMode = "two",
  wallRenderGeneration = 0;
let swipeLayer=null,swipeOn=false;
let sceneEngine='native';
const earthButton=document.createElement('button');earthButton.type='button';earthButton.dataset.view='earth';earthButton.textContent='Earth studio';earthButton.title='Georeferenced LiDAR with optional Google neighbourhood context';document.querySelector('[aria-label="View mode"]').append(earthButton);
const swipeControl=document.createElement('div');swipeControl.className='compare-swipe';swipeControl.hidden=true;swipeControl.innerHTML='<strong>Baseline ← | → Modified</strong><input id=compare-swipe type=range min=0 max=100 value=50 aria-label="Comparison divider">';document.querySelector('.map-shell').append(swipeControl);
function stopSwipe(){if(swipeLayer){map.removeLayer(swipeLayer);swipeLayer=null;}swipeOn=false;swipeControl.hidden=true;if(waterLayer?.canvas)waterLayer.canvas.style.clipPath='';}
function clipSwipe(){if(!swipeOn)return;const p=Number($('compare-swipe').value);waterLayer.canvas.style.clipPath=`inset(0 0 0 ${p}%)`;swipeLayer.canvas.style.clipPath=`inset(0 ${100-p}% 0 0)`;}
$('compare-swipe').oninput=clipSwipe;
$('swipe-compare').onclick=()=>{if(!baseline){toast('Compare two compatible completed runs first.');return;}if(swipeOn){stopSwipe();renderWalls();return;}setView('two');before=false;$('hydraulic-layer').value='depth';swipeLayer=new Raster();swipeLayer.runOverride=baseline;swipeLayer.layerOverride='depth';swipeLayer.addTo(map);swipeOn=true;swipeControl.hidden=false;wallGroup.clearLayers();setFrame(siteFrame);clipSwipe();};
const wallGroup = L.layerGroup().addTo(map),
  draftGroup = L.layerGroup().addTo(map);
map.createPane("hydraulics");
map.getPane("hydraulics").style.zIndex = 420;
map.getPane("hydraulics").style.pointerEvents = "none";
const Raster = L.Layer.extend({
  onAdd(m) {
    this._map = m;
    this.canvas = L.DomUtil.create("canvas", "hydraulic-canvas");
    this.canvas.style.position = "absolute";
    m.getPane("hydraulics").append(this.canvas);
    m.on("moveend zoomend resize", this.draw, this);
    this.draw();
  },
  onRemove(m) {
    m.off("moveend zoomend resize", this.draw, this);
    this.canvas.remove();
  },
  draw() {
    if (!selected || !this._map) return;
    const m = this._map,
      size = m.getSize(),
      origin = m.containerPointToLayerPoint([0, 0]);
    L.DomUtil.setPosition(this.canvas, origin);
    this.canvas.width = size.x;
    this.canvas.height = size.y;
    const ctx = this.canvas.getContext("2d"),
      run = this.runOverride || (before && baseline ? baseline : selected),
      g = run.grid,
      f = run.frames[siteFrame],
      mode = this.layerOverride || $("hydraulic-layer").value,
      difference = ["difference", "max-difference", "velocity-change"].includes(
        mode,
      );
    if (difference && !comparisonData) return;
    const vals = H.values(run, siteFrame, mode, comparisonData),
      range = displayRange(run, mode);
    ctx.globalAlpha = Number($("water-opacity").value);
    const p = g.corners_latlon.map((v) => m.latLngToContainerPoint(v));
    for (let r = 0; r < g.rows; r++)
      for (let c = 0; c < g.cols; c++) {
        const i = r * g.cols + c;
        if (
          !g.active[i] ||
          (!difference && mode !== "maximum" && f.depth_mm[i] < 1) ||
          (!difference && mode === "maximum" && vals[i] < 0.001)
        )
          continue;
        const a = r * (g.cols + 1) + c,
          b = a + 1,
          d = a + g.cols + 1,
          e = d + 1;
        if (p[e].x < 0 || p[a].x > size.x || p[e].y < 0 || p[a].y > size.y)
          continue;
        const rgb = H.color(
          vals[i],
          difference ? "difference" : "depth",
          ...range,
        );
        ctx.fillStyle = `rgb(${rgb.join(",")})`;
        ctx.beginPath();
        for (const [j, k] of [a, b, e, d].entries()) {
          if (j) ctx.lineTo(p[k].x, p[k].y);
          else ctx.moveTo(p[k].x, p[k].y);
        }
        ctx.closePath();
        ctx.fill();
        if (
          $("flow-arrows").checked &&
          r % 5 === 2 &&
          c % 5 === 2 &&
          f.depth_mm[i] >= 5
        ) {
          const u = f.u_cm_s[i] / 100,
            v = f.v_cm_s[i] / 100,
            speed = Math.hypot(u, v);
          if (speed < 0.01) continue;
          const center = L.point((p[a].x + p[e].x) / 2, (p[a].y + p[e].y) / 2),
            next = m.latLngToContainerPoint(
              localLatLon(
                g,
                g.west + (c + 0.5) * g.cell_m + (u / speed) * g.cell_m,
                g.north - (r + 0.5) * g.cell_m + (v / speed) * g.cell_m,
              ),
            );
          const angle = Math.atan2(next.y - center.y, next.x - center.x),
            len = 12;
          ctx.strokeStyle = "#112c39";
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.moveTo(center.x, center.y);
          const ex = center.x + Math.cos(angle) * len,
            ey = center.y + Math.sin(angle) * len;
          ctx.lineTo(ex, ey);
          ctx.lineTo(
            ex - Math.cos(angle - 0.5) * 4,
            ey - Math.sin(angle - 0.5) * 4,
          );
          ctx.moveTo(ex, ey);
          ctx.lineTo(
            ex - Math.cos(angle + 0.5) * 4,
            ey - Math.sin(angle + 0.5) * 4,
          );
          ctx.stroke();
        }
      }
  },
});
// Only for arrow display offsets; all walls/inspection use authoritative pyproj API.
function localLatLon(g, x, n) {
  const row = (g.north - n) / g.cell_m,
    col = (x - g.west) / g.cell_m,
    r = Math.max(0, Math.min(g.rows - 1, Math.floor(row))),
    c = Math.max(0, Math.min(g.cols - 1, Math.floor(col))),
    a = g.corners_latlon[r * (g.cols + 1) + c],
    b = g.corners_latlon[r * (g.cols + 1) + c + 1],
    d = g.corners_latlon[(r + 1) * (g.cols + 1) + c];
  return [
    a[0] + (b[0] - a[0]) * (col - c) + (d[0] - a[0]) * (row - r),
    a[1] + (b[1] - a[1]) * (col - c) + (d[1] - a[1]) * (row - r),
  ];
}
function displayRange(run, mode) {
  if (["difference", "max-difference"].includes(mode)) return [0, 0.1];
  if (mode === "surface") {
    let lo = Infinity,
      hi = -Infinity;
    run.grid.bed.forEach((v, i) => {
      if (run.grid.active[i]) {
        lo = Math.min(lo, v);
        hi = Math.max(hi, v);
      }
    });
    return [lo, hi];
  }
  return [0, mode === "velocity" ? 1 : 1];
}
function message(text) {
  $("scenario-status").textContent = text;
}
function postScene(type, payload = {}) {
  const frame = $("scene-frame");
  if (!frame.hidden)
    frame.contentWindow.postMessage(
      { type, job: workspaceId, ...payload },
      location.origin,
    );
}
function wallsEdited() {
  return (
    !!selected &&
    JSON.stringify(
      walls2d.filter((w) => w.enabled !== false).map((w) => w.points),
    ) !== JSON.stringify(selected.parameters.walls.map((w) => w.points))
  );
}
function syncScene() {
  if ($("wall-result-note"))
    $("wall-result-note").textContent = wallsEdited()
      ? "Wall edits differ from selected results. Run SFINCS to compute their effect."
      : "Walls match the selected scenario, or no hydraulic scenario is selected.";
  postScene("flowlab-state", {
    editedWalls: wallsEdited(),
    opacity:Number($('water-opacity').value),
    arrows:$('flow-arrows').checked,
    runId: selected?.id || null,
    frame: siteFrame,
    walls:
      before && baseline
        ? baseline.parameters.walls
        : walls2d.filter((w) => w.enabled !== false),
    layer: $("hydraulic-layer").value,
    comparison: comparisonData
      ? { baseline: baseline.id, modified: selected.id, before }
      : null,
  });
}
window.addEventListener("message", (event) => {
  if (
    event.origin !== location.origin ||
    event.source !== $("scene-frame").contentWindow ||
    event.data?.job !== workspaceId
  )
    return;
  if (event.data.type === "flowlab-ready") syncScene();
  if (event.data.type === 'flowlab-google-context') {
    // No non-Google geocoding controls while Google's context is displayed.
    document.querySelector('.search-bar').hidden=!!event.data.active;
  }
  if(event.data.type==='flowlab-hybrid-unavailable'){
    sceneEngine='native';setView('three');toast('Earth view unavailable on this device. Opened the measured terrain studio.');
  }
  if (event.data.type === "flowlab-time") {
    setFrame(event.data.frame);
  }
  if (event.data.type === "flowlab-walls") {
    walls2d = event.data.walls;
    renderWalls();
  }
});
function setView(mode) {
  if(mode==='earth')sceneEngine='earth';
  if(mode==='three')sceneEngine='native';
  document.querySelector('.search-bar').hidden=false;
  postScene('flowlab-visibility',{visible:mode!=='two'});
  if(mode!=='two'&&swipeOn){stopSwipe();renderWalls();}
  if (mode !== "two" && !sceneData) {
    toast("Prepare real terrain before opening 3D.");
    return;
  }
  viewMode = mode;
  const shell = document.querySelector(".map-shell");
  shell.classList.toggle("split", mode === "split");
  shell.classList.toggle("three", mode === "three" || mode==='earth');
  $("scene-frame").hidden = mode === "two";
  const desired=`/${sceneEngine==='earth'?'hybrid':'scene'}.html?job=${workspaceId}&embed=1`;
  if (mode !== "two" && $("scene-frame").getAttribute("src")!==desired)
    $("scene-frame").src = desired;
  document
    .querySelectorAll("[data-view]")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === mode));
  map.invalidateSize();
  syncScene();
  postScene('flowlab-visibility',{visible:mode!=='two'});
}
document
  .querySelectorAll("[data-view]")
  .forEach((b) => (b.onclick = () => setView(b.dataset.view)));
$("collapse-panel").onclick = () => {
  const collapsed = document
    .querySelector(".workspace-grid")
    .classList.toggle("collapsed");
  $("collapse-panel").setAttribute("aria-expanded", String(!collapsed));
  map.invalidateSize();
};
async function refreshRuns() {
  if (!workspaceId) return;
  const id = workspaceId,
    result = await api(`/api/jobs/${id}/hydraulics`);
  if (id !== workspaceId) return;
  for (const key of ["site-run", "baseline-run"]) {
    const value = $(key).value;
    $(key).replaceChildren(
      new Option(
        key === "site-run" ? "Select saved results" : "Choose baseline",
        "",
      ),
    );
    for (const r of result.runs)
      $(key).add(new Option(`${r.name} · ${r.status}`, r.id));
    $(key).value = value;
  }
  if (!selected)
    message(
      result.runs.length
        ? "Saved results available. Choose a completed run."
        : "No saved hydraulic run in this workspace. Review inputs to create one.",
    );
}
async function chooseRun(id) {
  stopSwipe();
  pauseSite();
  $("site-time").disabled = $("site-play").disabled = true;
  const request = ++runGeneration,
    workspace = workspaceId;
  message("Loading saved numerical outputs…");
  const result = await api(`/api/jobs/${workspace}/hydraulics/${id}`);
  if (request !== runGeneration || workspace !== workspaceId) return;
  if (result.status !== "done") {
    message(result.message || result.status);
    $("site-run").value=selected?.id||'';
    $("site-time").disabled = $("site-play").disabled = !selected;
    return;
  }
  selected = result;
  parcelLayer?.setStyle({fillOpacity:.04});
  baseline = null;
  comparisonData = null;
  before = false;
  $("before-after").textContent='Show baseline / modified';
  $("comparison-status").textContent = "";
  $("site-time").max = result.frames.length - 1;
  $("site-playback").hidden = false;
  $("empty-result").hidden = true;
  $("hydraulic-state").textContent = "Results ready";
  $("workflow-state").textContent = "Results ready → Compare scenarios";
  $("map-status").textContent = "Actual SFINCS results";
  message(
    result.limitations.join("\n") +
      "\n" +
      result.maximum_depth_source +
      (result.native_budget
        ? `\nNative rainfall ${result.native_budget.precipitation_m3?.toFixed(2)} m³ · storage ${result.native_budget.final_signed_storage_m3?.toFixed(2)} m³ · negative-storage diagnostic ${result.native_budget.maximum_negative_storage_m3?.toFixed(3)} m³ · outflow unverified`
        : ""),
  );
  for (const [key, value] of [
    ["site-rain", "rain_mm_h"],
    ["site-duration", "duration_minutes"],
    ["site-manning", "manning"],
    ["site-infiltration", "infiltration_mm_h"],
  ])
    $(key).value = result.parameters[value];
  $("site-review").checked = false;
  walls2d = structuredClone(result.parameters.walls);
  await renderWalls();
  if (!waterLayer) waterLayer = new Raster().addTo(map);
  setFrame(0);
  $("site-time").disabled = $("site-play").disabled = false;
}
function setFrame(index) {
  if (!selected) return;
  siteFrame = Math.max(
    0,
    Math.min(selected.frames.length - 1, Number(index) || 0),
  );
  $("site-time").value = siteFrame;
  $("site-time-label").textContent =
    `${selected.frames[siteFrame].seconds} s · ${selected.frames[siteFrame].rain_mm_h} mm/h`;
  waterLayer?.draw();
  swipeLayer?.draw();clipSwipe();
  drawLegend();
  syncScene();
}
function drawLegend() {
  if (!selected) return;
  const mode = $("hydraulic-layer").value,
    diff = ["difference", "max-difference", "velocity-change"].includes(mode),
    range = displayRange(selected, mode);
  $("hydraulic-legend").hidden = false;
  $("hydraulic-legend").innerHTML =
    `<strong>${esc($("hydraulic-layer").selectedOptions[0].textContent)}</strong><div class="legend-ramp" ${diff ? 'style="background:linear-gradient(90deg,#3173b9,#f5f5ee,#c64530)"' : ""}></div><span>${diff ? (mode === "velocity-change" ? "−1 ← 0 → +1 m/s" : "−0.10 ← 0 → +0.10 m (saturated)") : range.map((v) => v.toFixed(1)).join(" → ")}</span><small>${before ? "BASELINE" : "SELECTED SCENARIO"} · ${selected.frames[siteFrame].seconds} s<br>4 m cells · 1 mm depth display precision<br>${diff ? "Modified minus baseline" : mode === "maximum" ? esc(selected.maximum_depth_source) : "Saved native solver frames"}</small>`;
}
function pauseSite() {
  clearInterval(sitePlaying);
  sitePlaying = null;
  $("site-play").textContent = "Play";
}
$("site-play").onclick = () => {
  if (sitePlaying) {
    pauseSite();
    return;
  }
  if (!selected) return;
  if (siteFrame === selected.frames.length - 1) setFrame(0);
  $("site-play").textContent = "Pause";
  sitePlaying = setInterval(() => {
    if (siteFrame >= selected.frames.length - 1) pauseSite();
    else setFrame(siteFrame + 1);
  }, 400);
};
$("site-time").oninput = (e) => {
  pauseSite();
  setFrame(e.target.value);
};
$("site-run").onchange = (e) => {
  if (e.target.value)
    chooseRun(e.target.value).catch((error) => {
      message(error.message);
      $("site-run").value=selected?.id||'';
      $("site-time").disabled=$("site-play").disabled=!selected;
    });
};
$("refresh-runs").onclick = () =>
  refreshRuns().catch((error) => message(error.message));
$("hydraulic-layer").onchange = () => {
  if(swipeOn){stopSwipe();renderWalls();}
  if (
    ["difference", "max-difference", "velocity-change"].includes(
      $("hydraulic-layer").value,
    ) &&
    !comparisonData
  ) {
    toast("Choose a compatible baseline and compare first.");
    $("hydraulic-layer").value = "depth";
  }
  setFrame(siteFrame);
};
$("water-opacity").oninput = () => {waterLayer?.draw();swipeLayer?.draw();clipSwipe();syncScene();};
$("flow-arrows").onchange = () => {waterLayer?.draw();swipeLayer?.draw();clipSwipe();syncScene();};
$("fit-simulation").onclick = () => {
  if (selected)
    map.fitBounds(L.latLngBounds(selected.grid.corners_latlon), {
      padding: [25, 25],
    });
};
$("compare-runs").onclick = async () => {
  if(swipeOn){stopSwipe();renderWalls();}
  try {
    if (!selected || !$("baseline-run").value)
      throw Error("Choose two completed runs.");
    const id = workspaceId,
      modified = selected.id,
      base = $("baseline-run").value;
    $("comparison-status").textContent =
      "Checking native inputs and computing spatial differences…";
    const comp = await api(`/api/jobs/${id}/comparison`, {
      baseline: base,
      modified,
    });
    const run = await api(`/api/jobs/${id}/hydraulics/${base}`);
    if (id !== workspaceId || modified !== selected?.id) return;
    comparisonData = comp;
    baseline = run;
    before = false;
    const m = comp.metrics;
    $("comparison-status").textContent =
      `Modified minus baseline\nMax increase ${m.maximum_increase_m.toFixed(3)} m; decrease ${m.maximum_decrease_m.toFixed(3)} m\nChanged area ≥1 mm: ${m.changed_area_m2} m²\nMax sampled speed change ${m.max_abs_sampled_speed_change_m_s.toFixed(3)} m/s\nSaved-frame peaks may miss brief events.`;
    $("workflow-state").textContent = "Scenario comparison · compatible inputs";
    $("hydraulic-layer").value = "max-difference";
    setFrame(siteFrame);
  } catch (error) {
    comparisonData = null;
    baseline = null;
    $("comparison-status").textContent = error.message;
    $("hydraulic-layer").value='depth';setFrame(siteFrame);
  }
};
$("before-after").onclick = () => {
  if(swipeOn)stopSwipe();
  if (!baseline) {
    toast("Compare two compatible runs first.");
    return;
  }
  before = !before;
  if(before)wallGroup.clearLayers();
  else renderWalls().catch(error=>toast(error.message));
  $("hydraulic-layer").value = "depth";
  $("before-after").textContent = before
    ? "Showing baseline · show modified"
    : "Showing modified · show baseline";
  setFrame(siteFrame);
};
async function spatial(points, mode = "local") {
  return (await api(`/api/jobs/${workspaceId}/spatial`, { points, mode }))
    .points;
}
async function renderWalls() {
  if(swipeOn)stopSwipe();
  const id = workspaceId,
    request = ++wallRenderGeneration;
  wallGroup.clearLayers();
  $("map-wall-list").replaceChildren();
  for (const [i, w] of walls2d.entries()) {
    const samples = await spatial(w.points.map((p) => p.slice(0, 2)));
    if (id !== workspaceId || request !== wallRenderGeneration) return;
    w.latlon = samples.map((p) => p.latlon);
    const enabled = w.enabled !== false;
    L.polyline(w.latlon, {
      color: enabled ? "#c28a26" : "#888",
      weight: 4,
      dashArray: enabled ? null : "5 5",
    })
      .bindTooltip(`Hypothetical wall ${i + 1} · finite NZVD2016 crests`)
      .addTo(wallGroup);
    const item = document.createElement("div");
    item.className = "wall-item";
    item.innerHTML = `<strong>Hypothetical wall ${i + 1}</strong> · ${w.points.length} vertices<br><label><input type="checkbox" ${enabled ? "checked" : ""}> Enabled in next run</label><button class="secondary">Delete</button>`;
    item.querySelector("input").onchange = (e) => {
      w.enabled = e.target.checked;
      renderWalls();
    };
    item.querySelector("button").onclick = () => {
      walls2d.splice(i, 1);
      renderWalls();
    };
    for (const [j, p] of w.points.entries()) {
      const marker = L.marker(w.latlon[j], {
        draggable: true,
        icon: L.divIcon({
          className: "wall-vertex-handle",
          iconSize: [12, 12],
        }),
      }).addTo(wallGroup);
      marker.on("dragend", async () => {
        try {
          const ll = marker.getLatLng(),
            sample = (await spatial([[ll.lat, ll.lng]], "latlon"))[0];
          if (sample.local.some((v) => Math.abs(v) > 160))
            throw Error("Wall must stay within the central 320 m scene.");
          w.points[j] = [...sample.local, p[2]];
          await renderWalls();
        } catch (error) {
          toast(error.message);
          renderWalls();
        }
      });
      const vertex = document.createElement("label");
      vertex.className = "wall-vertex";
      vertex.innerHTML = `V${j + 1} ground ${samples[j].ground_m.toFixed(2)} m · crest <input type="number" min="-10" max="150" step="0.1" value="${p[2].toFixed(3)}">`;
      vertex.querySelector("input").onchange = (e) => {
        const value = Number(e.target.value);
        if (Number.isFinite(value) && value >= -10 && value <= 150) {
          p[2] = value;
          syncScene();
        }
      };
      item.append(vertex);
    }
    $("map-wall-list").append(item);
  }
  syncScene();
}
function cancelDraw() {
  drawing = false;
  draft = [];
  draftGroup.clearLayers();
  renderWalls();
  $("map-wall-help").textContent =
    "Drawing cancelled. Existing walls preserved.";
}
$("map-draw-wall").onclick = () => {
  stopSwipe();
  if (!sceneData) {
    toast("Prepare terrain first.");
    return;
  }
  drawing = true;
  draft = [];
  draftGroup.clearLayers();
  wallGroup.clearLayers();
  setView("two");
  $("map-wall-help").textContent =
    "Click 2–12 vertices on exposed ground, then Finish. Crest = sampled DEM + reviewed assumed height.";
};
$("map-cancel-wall").onclick = cancelDraw;
$("map-finish-wall").onclick = () => {
  if (draft.length < 2) {
    toast("At least two vertices required.");
    return;
  }
  walls2d.push({
    status: "hypothetical",
    crest_source: "assumed_height_above_measured_dem",
    enabled: true,
    points: draft.map((p) => p.point),
  });
  drawing = false;
  draft = [];
  draftGroup.clearLayers();
  renderWalls().catch((error) => toast(error.message));
  $("map-wall-help").textContent =
    "Hypothetical finite wall added. Review crests and assumptions before solving.";
};
map.on("click", async (event) => {
  if (!workspaceId) return;
  try {
    const id = workspaceId,
      sample = (
        await spatial([[event.latlng.lat, event.latlng.lng]], "latlon")
      )[0];
    if (id !== workspaceId) return;
    if (drawing) {
      if (sample.local.some((v) => Math.abs(v) > 160))
        throw Error("Draw inside the central 320 m terrain scene.");
      if (draft.length >= 12)
        throw Error("Finish this wall; at most 12 vertices.");
      const height = Number($("map-wall-height").value);
      if (!Number.isFinite(height) || height < 0.1 || height > 3)
        throw Error("Review assumed wall height (0.1–3 m).");
      draft.push({
        point: [...sample.local, sample.ground_m + height],
        latlon: sample.latlon,
      });
      $("map-wall-help").textContent =
        `${draft.length} vertices · latest ground ${sample.ground_m.toFixed(3)} m NZVD2016. Finish when ready.`;
      draftGroup.clearLayers();
      L.polyline(
        draft.map((p) => p.latlon),
        { color: "#e2ae54", weight: 4, dashArray: "4 4" },
      ).addTo(draftGroup);
      draft.forEach((p) =>
        L.circleMarker(p.latlon, { radius: 5, color: "#b68022" }).addTo(
          draftGroup,
        ),
      );
      return;
    }
    let text = `Ground ${sample.ground_m.toFixed(3)} m NZVD2016 · measured DEM sample`;
    if (selected) {
      const g = selected.grid,
        c = Math.floor((sample.local[0] - g.west) / g.cell_m),
        r = Math.floor((g.north - sample.local[1]) / g.cell_m),
        i = r * g.cols + c;
      if (r >= 0 && r < g.rows && c >= 0 && c < g.cols && g.active[i]) {
        const f = selected.frames[siteFrame];
        text += `\n${f.seconds} s · depth ${(f.depth_mm[i] / 1000).toFixed(3)} m · surface ${(g.bed[i] + f.depth_mm[i] / 1000).toFixed(3)} m NZVD2016 · speed ${(Math.hypot(f.u_cm_s[i], f.v_cm_s[i]) / 100).toFixed(2)} m/s · computational cell values`;
        if (sample.ground_m > g.bed[i] + f.depth_mm[i] / 1000)
          text +=
            "\nSampled ground is above the cell water surface; within-cell wetness is unresolved by this display.";
        if (comparisonData)
          text += `\nDepth change ${(comparisonData.frames[siteFrame].delta_depth_mm[i] / 1000).toFixed(3)} m · max-depth change ${(comparisonData.delta_maximum_depth_mm[i] / 1000).toFixed(3)} m`;
      } else text += "\nOutside result crop or inactive building cell.";
    }
    $("inspect-result").textContent = text;
    postScene("flowlab-inspect", { point: sample.local });
  } catch (error) {
    toast(error.message);
  }
});
$("save-walls").onclick = async () => {
  try {
    await api(`/api/jobs/${workspaceId}/walls`, {
      walls: walls2d.map(({ latlon, ...w }) => w),
    });
    toast("Saved reviewed hypothetical geometry in this workspace.");
  } catch (error) {
    toast(error.message);
  }
};
$("reload-walls").onclick = async () => {
  try {
    walls2d = (await api(`/api/jobs/${workspaceId}/walls`)).walls;
    await renderWalls();
  } catch (error) {
    toast(error.message);
  }
};
function downloadJson(value, name) {
  const url = URL.createObjectURL(
      new Blob([JSON.stringify(value)], { type: "application/geo+json" }),
    ),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("export-walls").onclick = () =>
  downloadJson(
    {
      type: "FeatureCollection",
      metadata: {
        workspace: workspaceId,
        horizontal_crs: "EPSG:4326",
        vertical_datum: "NZVD2016",
        status: "hypothetical",
        local_origin_nztm: sceneData?.origin_nztm,
      },
      features: walls2d.map((w) => ({
        type: "Feature",
        properties: {
          status: w.status,
          enabled: w.enabled !== false,
          crest_datum: "NZVD2016",
          crest_elevations_m: w.points.map(p=>p[2]),
          crest_profile_nzvd2016_json: JSON.stringify(w.points.map((p,i)=>({vertex:i+1,crest_m:p[2]}))),
          crest_source: w.crest_source || 'reviewed hypothetical absolute crest',
        },
        geometry: {
          type: "LineString",
          coordinates: w.latlon.map(p => [p[1], p[0]]),
        },
      })),
    },
    "hypothetical-walls.geojson",
  );
$("export-comparison").onclick = () => {
  if (!comparisonData) {
    toast("Compare runs first.");
    return;
  }
  const g = comparisonData.grid,
    features = [];
  for (let r = 0; r < g.rows; r++)
    for (let c = 0; c < g.cols; c++) {
      const i = r * g.cols + c;
      if (!g.active[i]) continue;
      const a = r * (g.cols + 1) + c,
        ring = [a, a + g.cols + 1, a + g.cols + 2, a + 1, a].map((j) => [
          g.corners_latlon[j][1],
          g.corners_latlon[j][0],
        ]);
      features.push({
        type: "Feature",
        properties: {
          baseline_maximum_depth_m: baseline.maximum_depth_mm[i]/1000,
          modified_maximum_depth_m: selected.maximum_depth_mm[i]/1000,
          delta_maximum_depth_m:
            comparisonData.delta_maximum_depth_mm[i] / 1000,
          delta_peak_sampled_speed_m_s:
            comparisonData.delta_peak_sampled_speed_m_s[i],
        },
        geometry: { type: "Polygon", coordinates: [ring] },
      });
    }
  downloadJson(
    {
      type: "FeatureCollection",
      metadata: {
        baseline: baseline.id,
        modified: selected.id,
        convention: comparisonData.convention,
        parameters: selected.parameters,
        limitations: comparisonData.limitations,
        horizontal_crs: "EPSG:4326",
        source_crs: "EPSG:2193",
        cell_m: g.cell_m,
      },
      features,
    },
    "hydraulic-comparison.geojson",
  );
};
async function simulate(withoutWalls) {
  try {
    if (!$("site-review").checked)
      throw Error("Review explicit exploratory assumptions first.");
    if (drawing) throw Error("Finish or cancel the draft wall first.");
    const id = workspaceId,
      payload = {
        reviewed: true,
        rain_mm_h: Number($("site-rain").value),
        duration_minutes: Number($("site-duration").value),
        manning: Number($("site-manning").value),
        infiltration_mm_h: Number($("site-infiltration").value),
        walls: withoutWalls
          ? []
          : walls2d
              .filter((w) => w.enabled !== false)
              .map(({ latlon, ...w }) => w),
      };
    const run = await api(`/api/jobs/${id}/hydraulics`, payload);
    $("site-simulate").disabled = $("site-baseline").disabled = true;
    $("workflow-state").textContent =
      "Simulation running · one processing slot";
    message(run.message);
    const check = async () => {
      if (id !== workspaceId) return;
      try {
        const result = await api(`/api/jobs/${id}/hydraulics/${run.id}`);
        if (id !== workspaceId) return;
        message(result.message || result.status);
        if (["done", "failed", "interrupted"].includes(result.status)) {
          $("site-simulate").disabled = $("site-baseline").disabled = false;
          await refreshRuns();
          if (result.status === "done") {
            $("site-run").value = run.id;
            await chooseRun(run.id);
          } else $("workflow-state").textContent = "Simulation needs attention";
        } else pollRun = setTimeout(check, 3000);
      } catch (error) {
        message(error.message);
        pollRun = setTimeout(check, 5000);
      }
    };
    pollRun = setTimeout(check, 2000);
  } catch (error) {
    message(error.message);
  }
}
$("site-simulate").onclick = () => simulate(false);
$("site-baseline").onclick = () => simulate(true);
$("workspace-evidence").onclick = () => {
  $("evidence-dialog").showModal();
};
$("basemap").onclick = async () => {
  if (!sceneData?.imagery) {
    toast(
      "Recorded aerial imagery is not available for this workspace. Street basemap retained.",
    );
    return;
  }
  if (aerial) {
    map.removeLayer(aerial);
    aerial = null;
    tiles.setOpacity(1);
  } else {
    const id=workspaceId;
    let image;
    try { image=await api(`/api/jobs/${id}/aerial`); }
    catch(error){toast(error.message);return;}
    if(id!==workspaceId)return;
    aerial = L.imageOverlay(
      `/api/jobs/${id}/files/map-aerial.png`,
      image.bounds,
      { opacity: 1, pane: "tilePane" },
    ).addTo(map);
    tiles.setOpacity(0.15);
  }
};
window.addEventListener("flowlab-job", async (event) => {
  const data = event.detail;
  preparation.hidden = false;
  preparation.querySelector("summary").textContent =
    data.status === "preparing"
      ? "Data preparation running"
      : "Data preparation complete · expand evidence checks";
  if (workspaceId === data.id) {
    if (!sceneData && data.status !== "preparing") {
      sceneData = await api(`/api/jobs/${data.id}/scene`).catch(() => null);
    }
    return;
  }
  workspaceId = data.id;
  $("scenario-panel").hidden = false;
  $("workflow-state").textContent =
    data.status === "preparing"
      ? "Data preparation running · simulation separate"
      : "Data prepared → Review inputs / select saved results";
  await refreshRuns();
  try {
    const id = workspaceId;
    sceneData = await api(`/api/jobs/${id}/scene`);
    if (id !== workspaceId) return;
    walls2d = (await api(`/api/jobs/${id}/walls`)).walls;
    await renderWalls();
  } catch (error) {
    message("Terrain scene not ready: " + error.message);
  }
});
window.addEventListener("flowlab-reset", () => {
  sceneEngine='native';
  stopSwipe();
  workspaceId = null;
  preparation.hidden = true;
  runGeneration++;
  pauseSite();
  clearTimeout(pollRun);
  selected = baseline = comparisonData = sceneData = null;
  walls2d = [];
  wallGroup.clearLayers();
  draftGroup.clearLayers();
  if (waterLayer) {
    map.removeLayer(waterLayer);
    waterLayer = null;
  }
  if (aerial) {
    map.removeLayer(aerial);
    aerial = null;
    tiles.setOpacity(1);
  }
  $("scenario-panel").hidden = true;
  $("site-playback").hidden = true;
  $("hydraulic-legend").hidden = true;
  $("scene-frame").hidden = true;
  $("scene-frame").removeAttribute("src");
  setView("two");
});
new ResizeObserver(() => map.invalidateSize()).observe(
  document.querySelector(".map-shell"),
);
