/* Offcut forecast: dependency-free evaluator for the exported gradient-boosted trees.
 * Usage:
 *   const model = await OffcutForecast.load("pre_marker_model.json");
 *   const r = OffcutForecast.predict(model, {garment:"tee", fibre:"cotton", size_mix:"standard",
 *                                            fabric_width_m:1.8, gsm:180, fabric_metres:18000});
 *   // r = {input_kg, ratio:{p10,p50,p90}, kg:{p10,p50,p90}}
 */
(function (root) {
  "use strict";
  function walk(tree, x) {
    let n = 0;
    while (tree.l[n] !== -1) n = Math.fround(x[tree.f[n]]) <= tree.t[n] ? tree.l[n] : tree.r[n];  // float32, as scikit-learn
    return tree.v[n];
  }
  function quantile(m, x) {
    let s = 0;
    for (const t of m.trees) s += walk(t, x);
    return m.init + m.lr * s;
  }
  function encode(model, order) {
    return model.features.map(function (name) {
      const i = name.indexOf("=");
      if (i > -1) return order[name.slice(0, i)] === name.slice(i + 1) ? 1 : 0;
      return Number(order[name]);
    });
  }
  function predict(model, order) {
    const x = encode(model, order);
    const qs = ["p10", "p50", "p90"].map(function (q) { return quantile(model.quantiles[q], x); }).sort(function (a, b) { return a - b; });
    const inputKg = order.fabric_metres * order.fabric_width_m * order.gsm / 1000;
    return {
      input_kg: inputKg,
      ratio: { p10: qs[0], p50: qs[1], p90: qs[2] },
      kg: { p10: qs[0] * inputKg, p50: qs[1] * inputKg, p90: qs[2] * inputKg },
    };
  }
  async function load(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error("model fetch failed: " + res.status);
    return res.json();
  }
  root.OffcutForecast = { load: load, predict: predict, encode: encode };
})(typeof window !== "undefined" ? window : globalThis);
