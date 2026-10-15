/* Shared numerical display contract. No synthetic interpolation or water motion. */
(function (root) {
  const ramp = [
    [218, 241, 250],
    [113, 195, 221],
    [34, 137, 189],
    [16, 79, 143],
    [24, 39, 88],
  ];
  function color(value, mode = "depth", low = 0, high = 1) {
    if (mode === "difference") {
      const end = value < 0 ? [49, 115, 185] : [198, 69, 48],
        t = Math.min(1, Math.abs(value) / (high || 0.1));
      return [245, 245, 238].map((v, i) => Math.round(v + (end[i] - v) * t));
    }
    const t =
        Math.max(0, Math.min(1, (value - low) / (high - low || 1))) *
        (ramp.length - 1),
      a = Math.floor(t),
      b = Math.min(a + 1, ramp.length - 1);
    return ramp[a].map((v, i) => Math.round(v + (ramp[b][i] - v) * (t - a)));
  }
  function values(run, index, mode, comparison) {
    const frame = run.frames[index];
    if (mode === "maximum") return run.maximum_depth_mm.map((v) => v / 1000);
    if (mode === "difference")
      return comparison.frames[index].delta_depth_mm.map((v) => v / 1000);
    if (mode === "max-difference")
      return comparison.delta_maximum_depth_mm.map((v) => v / 1000);
    if (mode === "velocity-change")
      return comparison.delta_peak_sampled_speed_m_s;
    if (mode === "velocity")
      return frame.u_cm_s.map((v, i) => Math.hypot(v, frame.v_cm_s[i]) / 100);
    if (mode === "surface")
      return frame.depth_mm.map((v, i) => v / 1000 + run.grid.bed[i]);
    return frame.depth_mm.map((v) => v / 1000);
  }
  root.FlowHydraulics = { color, values };
})(globalThis);
