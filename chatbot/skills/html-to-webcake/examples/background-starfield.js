(function(){
  if (window.__javisBg) return; window.__javisBg = 1;
  function init(){
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var c = document.createElement("canvas");
    c.id = "javisBg";
    c.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:-1;pointer-events:none;display:block";
    var body = document.body || document.documentElement;
    body.insertBefore(c, body.firstChild);
    var ctx = c.getContext("2d"), W = 0, H = 0, ps = [];
    function resize(){ W = c.width = window.innerWidth; H = c.height = window.innerHeight; }
    resize(); window.addEventListener("resize", resize);
    var N = window.innerWidth < 768 ? 55 : 110;
    for (var i = 0; i < N; i++) ps.push({
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.0004, vy: (Math.random() - 0.5) * 0.0004,
      r: Math.random() * 1.6 + 0.5, c: Math.random() < 0.75 ? "139,92,246" : "34,211,238"
    });
    function draw(move){
      ctx.fillStyle = "#05060f"; ctx.fillRect(0, 0, W, H);
      var i, j, a, b, dx, dy, d;
      for (i = 0; i < ps.length; i++){
        a = ps[i];
        if (move){ a.x += a.vx; a.y += a.vy; if (a.x < 0 || a.x > 1) a.vx *= -1; if (a.y < 0 || a.y > 1) a.vy *= -1; }
        ctx.beginPath(); ctx.arc(a.x * W, a.y * H, a.r, 0, 6.283);
        ctx.fillStyle = "rgba(" + a.c + ",0.85)"; ctx.fill();
      }
      for (i = 0; i < ps.length; i++) for (j = i + 1; j < ps.length; j++){
        a = ps[i]; b = ps[j]; dx = (a.x - b.x) * W; dy = (a.y - b.y) * H; d = dx * dx + dy * dy;
        if (d < 14000){
          ctx.beginPath(); ctx.moveTo(a.x * W, a.y * H); ctx.lineTo(b.x * W, b.y * H);
          ctx.strokeStyle = "rgba(139,92,246," + (0.16 * (1 - d / 14000)).toFixed(3) + ")";
          ctx.lineWidth = 1; ctx.stroke();
        }
      }
    }
    if (reduce){ draw(false); return; }
    (function tick(){ draw(true); requestAnimationFrame(tick); })();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
