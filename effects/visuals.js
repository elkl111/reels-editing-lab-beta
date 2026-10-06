// Pop-up explainer pieces for the Lab's stage. One library; every member's kit dresses it differently.
// Timeline: TL.visuals = [{kind, start, end, at?, ...props, items?: [{text, icon?, t?}]}], TL.icons = {name: svg body}.
// Each piece is placed in a zone around the speaker's face (top / left / right / chest), scaled to fit,
// and animated with the kit's motion style. renderVisuals(t) returns a key: same key = same frame.
(function () {
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const ease = x => 1 - Math.pow(1 - clamp(x, 0, 1), 3);
  // on-screen text: no em dashes (they read as AI-written); a comma does the same job
  const esc = s => String(s == null ? '' : s).replace(/\s*—\s*/g, ', ').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const rich = s => esc(s).replace(/\*([^*]+)\*/g, '<em>$1</em>');
  const Q = x => Math.round(clamp(x, 0, 1) * 30);

  let M = { dur: 0.32, over: 1.35, rise: 18, rot: 0 };           // motion, set from the kit
  const MOTION = {
    gentle: { dur: 0.45, over: 0.0, rise: 26, rot: 0 },
    snappy: { dur: 0.24, over: 1.35, rise: 14, rot: 0 },
    bouncy: { dur: 0.38, over: 2.0, rise: 30, rot: 4 },
    blur: { dur: 0.22, over: 0.0, rise: 0, rot: 0, blur: 22, from: 1.22 },      // blur-pop: sharpens into place
    rise: { dur: 0.5, over: 0.0, rise: 40, rot: 0, blur: 8, from: 1.0 },         // calm editorial rise
  };
  function backC(x, c) { x = clamp(x, 0, 1); return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); }
  // entrance at t0 → {o, tf, k}: opacity, CSS transform, and a key fragment
  function enter(t, t0, extra) {
    const x = (t - t0) / M.dur;
    if (x <= 0) return { o: 0, tf: 'scale(.8)', k: 0, on: false };
    const s = M.from ? M.from + (1 - M.from) * ease(x) : M.over > 0 ? 0.8 + 0.2 * backC(x, M.over) : 0.92 + 0.08 * ease(x);
    const y = (1 - ease(x)) * M.rise, r = (1 - ease(x)) * M.rot;
    const bl = M.blur ? M.blur * (1 - ease(x)) : 0;
    return { o: ease(x * 1.5), tf: `translateY(${y}px) scale(${s}) rotate(${r}deg) ${extra || ''}`, k: Q(x), on: true, bl };
  }
  const st = e => `opacity:${e.o};transform:${e.tf}${e.bl > 0.3 ? `;filter:blur(${e.bl.toFixed(1)}px)` : ''}`;
  const icon = n => n && window.TL.icons && window.TL.icons[n]
    ? `<span class="v-icon"><svg viewBox="0 0 24 24">${window.TL.icons[n]}</svg></span>` : '';
  const itemTimes = (v, items, gap) => items.map((it, k) => (typeof it === 'object' && it.t != null) ? it.t : v.start + 0.15 + k * (gap || 0.35));
  const txt = it => typeof it === 'object' ? it.text : it;

  window.setupVisuals = function (TL) {
    const k = TL.kit, C = k.colors, R = k.roles, V = Object.assign({ card: 'solid', motion: 'snappy', icon_stroke: 2 }, k.visuals || {});
    const col = n => C[n] || n;
    M = MOTION[V.motion] || MOTION.snappy;
    const s = document.documentElement.style;
    const card = col(V.card_color || R.hook_card), ink = col(V.ink || R.hook_text || R.ink);
    const accent = col(V.accent || (R.highlight_blocks || [])[0] || R.accent_pill);
    const strong = col(V.strong || R.statement_bg), strongText = col(V.strong_text || R.statement_text);
    const alert = col(V.alert || R.accent_pill || (R.highlight_blocks || [])[1] || strong);
    s.setProperty('--v-card', V.card === 'glass' ? `color-mix(in srgb, ${card} 92%, transparent)` : card);
    s.setProperty('--v-ink', ink);
    s.setProperty('--v-accent', accent);
    s.setProperty('--v-accent-text', col(V.accent_text || ink));
    s.setProperty('--v-accent-deep', strong);
    s.setProperty('--v-strong', strong);
    s.setProperty('--v-strong-text', strongText);
    s.setProperty('--v-alert', alert);
    s.setProperty('--v-soft', `color-mix(in srgb, ${ink} 7%, ${card})`);
    s.setProperty('--v-track', `color-mix(in srgb, ${ink} 20%, ${card})`);
    s.setProperty('--v-word', col(V.word || R.hook_text || R.ink));
    const glowC = col(V.glow || R.hook_card);
    s.setProperty('--v-glow', `0 0 24px ${glowC}, 0 0 48px ${glowC}, 0 0 90px color-mix(in srgb, ${glowC} 70%, transparent)`);
    s.setProperty('--v-radius', (V.radius != null ? V.radius : (k.style && k.style.radius != null ? k.style.radius : 28)) + 'px');
    s.setProperty('--v-icon-stroke', V.icon_stroke);
    s.setProperty('--v-shadow', V.card === 'outline' ? 'none' : '0 14px 40px rgba(20, 10, 5, 0.22)');
    s.setProperty('--v-border', V.card === 'outline' ? `4px solid ${ink}` : V.card === 'glass' ? '2px solid rgba(255,255,255,.65)' : 'none');
    // colourful kits: chips and tiles rotate through these fills, text picks dark or light for contrast
    const lum = hex => { const m = String(hex).replace('#', '').match(/.{2}/g); if (!m) return 1;
      const [r, g, b] = m.map(x => parseInt(x, 16) / 255).map(c => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
      return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    window.V_ROT = (V.rotate || []).map(n => { const bg = col(n); return { bg, fg: lum(bg) > 0.35 ? ink : col(V.strong_text || R.statement_text || card) }; });
  };

  // Zones around the face, in stage pixels
  function zones() {
    const S = window.TL.safe || {};
    const ft = S.face_top || 420, fb = S.face_bottom || 1000, fl = S.face_left || 300, fr = S.face_right || 780;
    const head = ft - 90;
    // top band runs down to the hairline: pieces may overlap hair, never the face
    // everything stays inside Instagram's safe zone (stage.html SAFE_ZONE): below its header, above its
    // username and caption, and clear of the like / comment / share column on the right
    const SZ = window.SAFE_ZONE || { top: 170, bottom: 1470 };
    const top = { x: 50, y: SZ.top, w: 980, h: Math.max(ft - 10 - SZ.top, 300) };
    let cy = fb + 70, ch = Math.min(SZ.bottom - cy, 560);
    if (ch < 240) { cy = SZ.bottom - 260; ch = 260; }
    return {
      top, chest: { x: 100, y: cy, w: 880, h: ch },
      left: { x: 40, y: Math.max(head - 60, SZ.top), w: Math.max(fl - 50, 250), h: fb - head + 160 },
      right: { x: Math.min(fr + 10, 1040 - 250), y: Math.max(head - 60, SZ.top), w: Math.max(1040 - fr - 10, 250), h: fb - head + 160 },
      full: { x: 60, y: SZ.top, w: 920, h: SZ.bottom - SZ.top },
    };
  }

  const K = {};   // piece builders: (v, t) → {parts: [{zone, html}], key}

  K.chips = (v, t) => {
    const items = v.items || [], ts = itemTimes(v, items);
    const ct = v.close ? items.map((it, k) => (typeof it === 'object' && it.close_t != null) ? it.close_t
      : (v.close_start || v.start + (v.end - v.start) * 0.55) + k * 0.3) : null;
    let key = 'ch';
    const chip = (it, k) => {
      let e = enter(t, ts[k]);
      if (ct && t >= ct[k]) { const g = ease((t - ct[k]) / 0.25); e = { o: 1 - g, tf: `scale(${1 - 0.3 * g})`, k: 40 + Q(g) }; }
      key += e.k + ',';
      const rot = window.V_ROT && window.V_ROT.length ? window.V_ROT[k % window.V_ROT.length] : null;
      const fill = rot ? `;background:${rot.bg};color:${rot.fg}` : '';
      return `<span class="v-card v-ui v-chip${rot ? ' filled' : ''}" style="${st(e)}${fill}">${icon(it.icon)}${esc(txt(it))}${v.close ? '<span class="x">×</span>' : ''}</span>`;
    };
    const Z = zones();
    const roomy = Math.min(Z.left.w, Z.right.w) >= 300;      // a big face leaves no room beside it: line up on top
    const layout = v.at || (items.length <= 6 && roomy ? 'around' : 'top');
    if (layout === 'around') {
      const L = [], Rr = [];
      items.forEach((it, k) => (k % 2 ? Rr : L).push(chip(it, k)));
      return { parts: [{ zone: 'left', html: `<div class="v-col">${L.join('')}</div>` },
                       { zone: 'right', html: `<div class="v-col">${Rr.join('')}</div>` }], key };
    }
    return { parts: [{ zone: layout, html: `<div class="v-row">${items.map(chip).join('')}</div>` }], key };
  };

  K.number = (v, t) => {
    const e = enter(t, v.start);
    const m = String(v.value).match(/^([^\d]*)([\d.,]+)(.*)$/);
    let shown = esc(v.value);
    let k = '';
    if (m && v.count !== false) {
      const target = parseFloat(m[2].replace(/,/g, '')), p = ease((t - v.start) / 0.7);
      const n = target * p, dec = (m[2].split('.')[1] || '').length;
      // symbols (+ % € $) in the label font: some display fonts ship blank glyphs for them
      const sym = x => x ? `<span class="sym">${esc(x)}</span>` : '';
      shown = sym(m[1]) + (dec ? n.toFixed(dec) : Math.round(n).toLocaleString('en-US')) + sym(m[3]);
      k = Q(p);
    }
    return { parts: [{ zone: v.at || 'top', html: `<div class="v-number" style="${st(e)}">${v.pre ? `<span class="v-ui pre">${esc(v.pre)}</span>` : ''}
      <span class="v-disp val">${shown}</span>${v.label ? `<span class="v-ital lab">${esc(v.label)}</span>` : ''}</div>` }], key: 'n' + e.k + ':' + k + ':' + shown };
  };

  K.word = (v, t) => {
    if (v.style === 'type') {
      const plain = v.text.replace(/\*/g, ''), n = Math.floor((t - v.start) / 0.055);
      const done = n >= plain.length, blink = Math.floor((t - v.start) * 2.2) % 2 === 0;
      const body = done ? rich(v.text) : esc(plain.slice(0, Math.max(n, 0)));
      const cur = !done || blink ? '<span class="cur"></span>' : '';
      return { parts: [{ zone: v.at || 'top', html: `<div class="v-disp v-word">${body}${cur}</div>` }], key: 'wt' + Math.min(n, 999) + (blink ? 1 : 0) };
    }
    const style = v.style || (window.TL.kit.visuals || {}).word_style;
    if (style === 'rise') {
      // each letter rises out of its own line, one after another
      let k = 0, key = 'wr';
      const words = String(v.text).split(/(\s+)/).map(w => {
        if (/^\s+$/.test(w)) return ' ';
        const it = /^\*.*\*$/.test(w), bare = w.replace(/\*/g, '');
        return `<span class="rw${it ? ' it' : ''}">` + [...bare].map(ch => {
          const p = ease((t - v.start - 0.028 * k++) / 0.55); key += Math.round(p * 12);
          return `<span class="rl"><span style="transform:translateY(${(1 - p) * 115}%)">${esc(ch)}</span></span>`;
        }).join('') + '</span>';
      }).join('');
      return { parts: [{ zone: v.at || 'top', html: `<div class="v-disp v-word v-rise">${words}</div>` }], key };
    }
    const e = enter(t, v.start);
    return { parts: [{ zone: v.at || 'top', html: `<div class="v-disp v-word" style="${st(e)}">${rich(v.text)}</div>` }], key: 'w' + e.k };
  };

  K.strike = (v, t) => {
    const e = enter(t, v.start), s0 = v.strike_t != null ? v.strike_t : v.start + (v.end - v.start) * 0.5;
    const p = ease((t - s0) / 0.3);
    return { parts: [{ zone: v.at || 'top', html: `<div class="v-strike" style="${st(e)}">${v.pre ? `<span class="v-ui pre">${esc(v.pre)}</span>` : ''}
      <span class="v-disp txt">${esc(v.text)}<span class="line" style="width:${108 * p}%"></span></span></div>` }], key: 's' + e.k + ':' + Q(p) };
  };

  K.chat = (v, t) => {
    // typed → sent → thinking (→ reply). Fixed size, so nothing jumps while it types.
    const e = enter(t, v.start), t0 = v.start + 0.45, prompt = v.prompt || '';
    const n = clamp(Math.floor((t - t0) / 0.045), 0, prompt.length), typing = n < prompt.length;
    const sendT = t0 + prompt.length * 0.045 + 0.35;
    const sent = t >= sendT, sp = ease((t - sendT) / 0.3);
    const rt = v.reply_t != null ? v.reply_t : sendT + 0.9;
    const blink = Math.floor(t * 2.2) % 2 === 0;
    const press = sent ? 1 + 0.25 * Math.sin(Math.PI * clamp((t - sendT) / 0.18, 0, 1)) : 1;
    let convo = `<div class="greet v-disp" style="opacity:${1 - sp}">${esc(v.greeting || 'How can I help today?')}</div>`;
    let ck = '';
    if (sent) {
      const dots = !v.reply || t < rt;
      const dk = Math.floor(t * 4) % 3;
      ck = 'S' + Q(sp) + (dots ? 'd' + dk : '');
      convo = `<div class="convo">
        <div class="bubble me" style="opacity:${sp};transform:translateY(${(1 - sp) * 70}px)">${esc(prompt)}</div>
        ${dots && sp > 0.6 ? `<div class="bubble ai dots">${[0, 1, 2].map(k => `<i style="opacity:${k === dk ? 1 : .35}"></i>`).join('')}</div>` : ''}
        ${!dots ? (() => { const re = enter(t, rt); ck += 'r' + re.k; return `<div class="bubble ai" style="${st(re)}">${esc(v.reply)}</div>`; })() : ''}
      </div>`;
    }
    const html = `<div class="v-card v-ui v-chat" style="${st(e)}">
      <div class="bar"><i></i><i></i><i></i><span style="margin-left:10px">${esc(v.title || 'Chat')}</span></div>
      <div class="area">${convo}</div>
      <div class="input"><span class="txt">${sent ? `<span class="ph">${esc(v.placeholder || 'Ask anything')}</span>`
        : n ? esc(prompt.slice(0, n)) : `<span class="ph">${esc(v.placeholder || 'Ask anything')}</span>`}${!sent && (typing || blink) ? '<span class="cur-ink"></span>' : ''}</span>
        <span class="send" style="transform:scale(${press})">${icon('arrow-up')}</span></div></div>`;
    return { parts: [{ zone: v.at || 'top', html }], key: 'c' + e.k + ':' + n + ':' + (!sent && (typing || blink) ? 1 : 0) + ':' + ck + ':' + Math.round(press * 20) };
  };

  K.notify = (v, t) => {
    const x = ease((t - v.start) / 0.35);
    const html = `<div class="v-card v-ui v-notify" style="opacity:${x};transform:translateY(${-70 * (1 - x)}px)">
      <span class="v-tile">${icon(v.icon || 'bell')}</span>
      <div style="flex:1"><div class="t"><span>${esc(v.app || 'Messages')}</span><span>${esc(v.when || 'now')}</span></div>
      <div class="h">${esc(v.title || '')}</div>${v.text ? `<div class="b">${esc(v.text)}</div>` : ''}</div></div>`;
    return { parts: [{ zone: v.at || 'top', html }], key: 'no' + Q(x) };
  };

  K.checklist = (v, t) => {
    const items = v.items || [], e = enter(t, v.start);
    const ts = itemTimes(v, items, Math.max(0.5, (v.end - v.start - 0.6) / Math.max(items.length, 1)));
    let key = 'cl' + e.k;
    const rows = items.map((it, k) => {
      const p = ease((t - ts[k]) / 0.2); key += Q(p);
      return `<div class="row"><span class="box${p > 0.5 ? ' on' : ''}" style="transform:scale(${1 + 0.18 * Math.sin(Math.PI * p)})">${p > 0.5 ? icon('check') : ''}</span>
        <span style="opacity:${0.6 + 0.4 * p}">${esc(txt(it))}</span></div>`;
    }).join('');
    return { parts: [{ zone: v.at || 'top', html: `<div class="v-card v-ui v-check" style="${st(e)}">${v.title ? `<div class="title">${esc(v.title)}</div>` : ''}${rows}</div>` }], key };
  };

  K.step = (v, t) => {
    const e = enter(t, v.start);
    return { parts: [{ zone: v.at || 'top', html: `<div class="v-step" style="${st(e)}"><span class="v-ui n">${esc(v.label || ('step ' + (v.n || 1)))}</span>
      <span class="v-disp t">${rich(v.text)}</span></div>` }], key: 'st' + e.k };
  };

  K.flow = (v, t) => {
    const items = v.items || [], ts = itemTimes(v, items, 0.6);
    let key = 'fl';
    const out = items.map((it, k) => {
      const e = enter(t, ts[k]); key += e.k + ',';
      const rot = window.V_ROT && window.V_ROT.length && k < items.length - 1 ? window.V_ROT[k % window.V_ROT.length] : null;
      const node = `<div class="node" style="${st(e)}"><span class="v-tile${k === items.length - 1 ? ' dark' : ''}" ${rot ? `style="background:${rot.bg};color:${rot.fg}"` : ''}>${icon(it.icon || 'circle')}</span>
        ${it.text ? `<span class="v-card v-ui lab">${esc(it.text)}</span>` : ''}</div>`;
      if (!k) return node;
      const p = ease((t - (ts[k] - 0.3)) / 0.3); key += Q(p);
      return `<div class="link" style="transform:scaleX(${p})"></div>` + node;
    }).join('');
    return { parts: [{ zone: v.at || 'top', html: `<div class="v-flow">${out}</div>` }], key };
  };

  K.hub = (v, t) => {
    const nodes = v.nodes || [], e = enter(t, v.start), ts = itemTimes(v, nodes, 0.45).map(x => Math.max(x, v.start + 0.3));
    const slots = [[20, 30], [80, 30], [16, 80], [84, 80], [50, 14], [50, 95]];
    let key = 'hb' + e.k, lines = '', nd = '';
    nodes.forEach((n, k) => {
      const [x, y] = slots[k % slots.length], p = ease((t - ts[k]) / 0.3); key += Q(p);
      if (p > 0) lines += `<line x1="50%" y1="55%" x2="${50 + (x - 50) * p}%" y2="${55 + (y - 55) * p}%"/>`;
      const ee = enter(t, ts[k] + 0.1);
      nd += `<span class="nd v-ui" style="left:${x}%;top:${y}%;opacity:${ee.o};transform:translate(-50%,-50%) scale(${ee.on ? 1 : .8})">${icon(n.icon)}${esc(txt(n))}</span>`;
    });
    const c = v.center || { icon: 'sparkles', text: 'AI' };
    const html = `<div class="v-card v-hub" style="${st(e)}">${v.title ? `<div class="title">${esc(v.title)}</div>` : ''}
      <svg class="lines">${lines}</svg><div class="center"><span class="v-tile dark">${icon(c.icon)}</span>
      ${c.text ? `<span class="lab v-ui">${esc(c.text)}</span>` : ''}</div>${nd}</div>`;
    return { parts: [{ zone: v.at || 'top', html }], key };
  };

  K.scale = (v, t) => {
    const marks = v.marks || [], n = Math.max(marks.length - 1, 1), e = enter(t, v.start);
    const a = (v.from || 0) / n, b = (v.to != null ? v.to : n) / n;
    const m0 = v.move_t != null ? v.move_t : v.start + 0.4, m1 = v.move_end_t != null ? v.move_end_t : Math.max(m0 + 0.6, v.end - 0.4);
    const p = ease((t - m0) / (m1 - m0)), pos = (a + (b - a) * p) * 100;
    const mk = marks.map((m, k) => `<span class="mk v-ui" style="left:${k / n * 100}%"><span class="tick" style="left:50%"></span>${esc(m)}</span>`).join('');
    const html = `<div class="v-scale" style="${st(e)}"><div class="track"><div class="fill" style="width:${pos}%"></div>
      <div class="knob" style="left:${pos}%"></div></div><div class="marks">${mk}</div></div>`;
    return { parts: [{ zone: v.at || 'top', html }], key: 'sc' + e.k + ':' + Math.round(pos * 2) };
  };

  K.person = (v, t) => {
    const e = enter(t, v.start), of = v.of || 3, on = v.meter != null ? v.meter : 0;
    const mt = v.meter_t != null ? v.meter_t : v.start + 0.5, mp = ease((t - mt) / 0.8);
    const lit = Math.round(on * mp);
    const meter = v.meter != null ? `<div class="meter">${Array.from({ length: of }, (_, k) => `<i class="${k < lit ? 'on' : ''}"></i>`).join('')}</div>` : '';
    const html = `<div class="v-card v-person" style="${st(e)}"><span class="av"><span class="v-tile">${icon(v.icon || 'user')}</span></span>
      <span class="v-disp nm">${esc(v.name)}</span>${v.note ? `<span class="v-ui nt">${esc(v.note)}</span>` : ''}${meter}</div>`;
    return { parts: [{ zone: v.at || 'right', html }], key: 'p' + e.k + ':' + lit };
  };

  K.versus = (v, t) => {
    const L = v.left || {}, Rr = v.right || {}, el = enter(t, v.start);
    const rt = v.right_t != null ? v.right_t : v.start + (v.end - v.start) * 0.4, er = enter(t, rt);
    const side = (s, e, good) => `<div class="v-card v-ui side ${good ? 'good' : 'bad'}" style="${st(e)}${good ? '' : ';filter:saturate(.6)'}">
      ${icon(s.icon)}<span class="tx">${esc(s.text)}</span><span class="mark">${icon(good ? 'check' : 'x')}</span></div>`;
    return { parts: [{ zone: v.at || 'top', html: `<div class="v-vs">${side(L, el, false)}${side(Rr, er, true)}</div>` }], key: 'vs' + el.k + ':' + er.k };
  };

  K.phone = (v, t) => {
    const x = ease((t - v.start) / 0.45);
    const html = `<div style="opacity:${x};transform:translateX(${(1 - x) * 160}px) rotate(${4 - 4 * x + 4}deg);display:flex;flex-direction:column;align-items:center">
      <div class="v-phone"><div class="scr" style="background-image:url('${v.image_url || ''}')"></div></div>
      ${v.caption ? `<div class="v-disp v-phone-cap">${rich(v.caption)}</div>` : ''}</div>`;
    return { parts: [{ zone: v.at || 'right', html }], key: 'ph' + Q(x) };
  };

  K.gif = (v, t) => {
    // A frame with a see-through window; the moving GIF is laid in underneath by the build (ffmpeg),
    // at the window's settled position. Full-screen: only the caption is drawn here.
    if (v.at === 'full') {
      const e = enter(t, v.start);
      return { parts: v.caption ? [{ zone: 'top', html: `<div class="v-disp v-word v-gif-full" style="${st(e)}">${rich(v.caption)}</div>` }] : [],
               key: 'gf' + e.k };
    }
    const e = enter(t, v.start), w = v.win_w || 560, h = Math.round(w * (v.h || 1) / (v.w || 1));
    const html = `<div class="v-gif" style="${st(e)}">
      <div class="frame" style="width:${w}px;height:${Math.min(h, 640)}px"><div class="win" data-gif="${v._i}" style="${t - v.start < 0.3 ? 'background:var(--v-soft)' : ''}"></div></div>
      ${v.caption ? `<div class="cap v-disp">${rich(v.caption)}</div>` : ''}
      ${v.handle ? `<div class="handle v-ui">@${esc(String(v.handle).replace(/^@/, ''))}</div>` : ''}</div>`;
    return { parts: [{ zone: v.at || 'top', html }], key: 'g' + e.k + (t - v.start < 0.3 ? 'f' : '') };
  };

  K.insert = (v, t) => {
    // a custom animated insert (its own transparent video), laid in by the build at this window
    const e = enter(t, v.start), w = v.width || 640, h = Math.round(w * (v.h || 1) / (v.w || 1));
    return { parts: [{ zone: v.at || 'top', html: `<div style="opacity:${e.o}"><div class="win" data-gif="${v._i}" style="width:${w}px;height:${h}px"></div></div>` }],
             key: 'i' + e.k };
  };

  K.profile = (v, t) => {
    // an Instagram-style profile: real numbers only (brand/instagram.json), Follow tapped, optional comment keyword
    const P = window.TL.profile || {}, e = enter(t, v.start);
    const tapT = v.tap_t != null ? v.tap_t : v.start + 0.8, tapped = t >= tapT;
    const dot = Math.max(0, 1 - Math.abs(t - tapT) / 0.25);
    const grid = (window.TL.reels || []).slice(0, 6).map(r => `<i style="background-image:url('${r.thumb_url}')"></i>`).join('')
      || Array.from({ length: 6 }, () => '<i></i>').join('');
    let sheet = '', sk = '';
    if (v.keyword) {
      const kt = v.keyword_t != null ? v.keyword_t : tapT + 0.7, sp = ease((t - kt) / 0.3);
      const n = clamp(Math.floor((t - kt - 0.3) / 0.07), 0, v.keyword.length);
      const posted = t >= kt + 0.3 + v.keyword.length * 0.07 + 0.25;
      sk = Q(sp) + ':' + n + (posted ? 'p' : '');
      sheet = `<div class="sheet" style="transform:translateY(${(1 - sp) * 110}%)"><div class="grab"></div>
        <div class="row"><span class="av sm"></span><span class="in">${esc(v.keyword.slice(0, n))}${!posted ? '<span class="cur-ink"></span>' : ''}</span>
        <span class="post${posted ? ' on' : ''}">Post</span></div></div>`;
    }
    const fmt = x => x == null ? '' : esc(x);
    const html = `<div class="v-profile" style="${st(e)}">
      <div class="head"><span class="av" ${P.avatar_url ? `style="background-image:url('${P.avatar_url}')"` : ''}></span>
        <div class="stats"><div><b>${fmt(P.posts)}</b><span>posts</span></div><div><b>${fmt(P.followers)}</b><span>followers</span></div>
        <div><b>${fmt(P.following)}</b><span>following</span></div></div></div>
      <div class="nm">${esc(P.name || '')}</div><div class="bio">${esc(P.bio || '')}</div>
      <div class="btns"><span class="fol${tapped ? ' done' : ''}">${tapped ? 'Following' : 'Follow'}</span><span class="msg">Message</span>
        ${dot > 0 ? `<span class="tap" style="opacity:${dot};transform:scale(${1.4 - 0.4 * dot})"></span>` : ''}</div>
      <div class="grid">${grid}</div>${sheet}</div>`;
    return { parts: [{ zone: v.at || 'chest', html }], key: 'pr' + e.k + (tapped ? 'T' : '') + Math.round(dot * 8) + ':' + sk };
  };

  window.visualUsesTop = v => {
    if (v.at) return v.at === 'top' || v.at === 'full';
    if (['person', 'phone', 'profile'].includes(v.kind)) return false;
    if (v.kind === 'chips') { const Z = zones(); return !((v.items || []).length <= 6 && Math.min(Z.left.w, Z.right.w) >= 300); }
    return true;
  };
  window.VISUAL_KINDS = Object.keys(K);

  window.renderVisuals = function (t) {
    const TL = window.TL, el = document.getElementById('L-visuals');
    const act = (TL.visuals || []).filter(v => t >= v.start && t < v.end);
    TL._busy = new Set();
    if (!act.length) { el.innerHTML = ''; return 'v:-'; }
    const Z = zones();
    let html = '', keys = [];
    const fits = [];
    act.forEach((v, i) => {
      const b = K[v.kind];
      if (!b) return;
      const r = b(v, t), out = ease((v.end - t) / 0.25);
      keys.push(i + r.key + ':' + Q(out));
      r.parts.forEach(p => {
        const z = Z[p.zone] || Z.top;
        TL._busy.add(p.zone);
        html += `<div class="zone" style="left:${z.x}px;top:${z.y}px;width:${z.w}px;height:${z.h}px;opacity:${out}">
          <div class="fit" data-w="${z.w}" data-h="${z.h}">${p.html}</div></div>`;
      });
      if (TL.catalog) html += `<div class="v-catlabel">${esc(v.cat || v.kind)}</div>`;
    });
    el.innerHTML = html;
    el.querySelectorAll('.fit').forEach(f => {
      const w = f.scrollWidth, h = f.scrollHeight, zw = +f.dataset.w, zh = +f.dataset.h;
      const s = Math.min(1, zw / Math.max(w, 1), zh / Math.max(h, 1));
      if (s < 1) f.style.transform = `scale(${s})`;
    });
    return 'v:' + keys.join('|');
  };
})();
