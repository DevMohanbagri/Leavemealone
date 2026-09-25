const STATUS = {
  exposed: "Exposed",
  possible: "Possible",
  clear: "Clear",
  blocked: "Check yourself",
  unreachable: "No answer",
  inconclusive: "Unclear",
  skipped: "Skipped",
  queued: "Not sent",
  submitted: "Sent",
  confirmed: "Confirmed",
  reappeared: "Came back",
  overdue: "Overdue",
  breach: "Breach",
};

const CATEGORY = {
  "people-search": "People search",
  "data-aggregator": "Aggregator",
  "marketing-list": "Marketing",
  "background-check": "Background",
  "location-tracking": "Location",
  "financial": "Financial",
  "social-scraper": "Social",
  "public-records": "Public record",
  "employment": "Employment",
  "health": "Health",
  "insurance": "Insurance",
  "political": "Political",
  "real-estate": "Property",
  "tenant-screening": "Tenant",
  "vehicle": "Vehicle",
  other: "Other",
};

const RELIST = {
  certain: "Comes back. Recheck it.",
  high: "Often republished.",
  medium: "Sometimes republished.",
  low: "Usually stays down.",
  none: "Rarely republished.",
};

const state = {
  meta: null,
  profiles: [],
  profileId: null,
  desk: null,
  view: "welcome",
  showForm: false,
  draft: null,
  brokers: [],
  brokerQuery: "",
  brokerCategory: "",
  drawer: null,
  pullMode: "desk",
  pullFilter: "open",
  caseIndex: 0,
  caseDetail: null,
  feed: [],
  scanning: false,
  lastSummary: null,
  letter: null,
  letterBroker: "",
  letterKind: "deletion",
  batches: null,
  help: false,
  redact: false,
  passwordResult: null,
  token: 0,
};

const $app = () => document.getElementById("app");

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 4600);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    method: opts.method || "GET",
    headers: opts.body ? { "Content-Type": "application/json" } : undefined,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
      if (Array.isArray(detail)) detail = detail.map((d) => d.msg || JSON.stringify(d)).join(" ");
      if (detail && typeof detail === "object") detail = JSON.stringify(detail);
    } catch (err) {
      /* keep status text */
    }
    throw new Error(detail);
  }
  const type = res.headers.get("content-type") || "";
  if (type.includes("json")) return res.json();
  return res.text();
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function profile() {
  return state.desk && state.desk.profile;
}

function fullName(p) {
  if (!p) return "";
  return [p.first_name, p.middle_name, p.last_name].filter(Boolean).join(" ");
}

function formatPhone(value) {
  const digits = String(value || "").replace(/\D/g, "");
  const core = digits.length === 11 && digits.startsWith("1") ? digits.slice(1) : digits;
  if (core.length === 10) return `(${core.slice(0, 3)}) ${core.slice(3, 6)}-${core.slice(6)}`;
  return value || "";
}

function addressLine(p) {
  const address = (p.addresses || []).find((a) => a.current) || (p.addresses || [])[0] || {};
  return [address.street, address.city, address.state, address.zip].filter(Boolean).join(", ");
}

function detailsText(p) {
  return [
    fullName(p),
    (p.emails || []).join(", "),
    (p.phones || []).map(formatPhone).join(", "),
    addressLine(p),
    p.residence_state ? `Residence: ${p.residence_state}` : "",
  ].filter(Boolean).join("\n");
}

function ago(iso) {
  if (!iso) return "never";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return iso.slice(0, 10);
  const seconds = Math.max(0, (Date.now() - then) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function daysLabel(iso) {
  if (!iso) return "";
  const days = Math.ceil((Date.parse(iso) - Date.now()) / 86400000);
  if (Number.isNaN(days)) return iso;
  if (days < 0) return `${-days}d overdue`;
  if (days === 0) return "due today";
  return `${days}d left`;
}

function cat(value) {
  return CATEGORY[value] || value || "";
}

function stamp(status) {
  const label = STATUS[status] || status || "";
  return `<span class="stamp ${esc(status)}">${esc(label)}</span>`;
}

function safeUrl(url) {
  return /^https?:\/\//i.test(url || "") ? url : "";
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (err) {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  toast(message || "Copied.");
}

function openUrl(url) {
  const safe = safeUrl(url);
  if (!safe) {
    toast("No link on file for that.");
    return;
  }
  window.open(safe, "_blank", "noopener");
}

function walled(b) {
  return !!(b && (b.cloudflare || b.captcha));
}

function wallNote(b) {
  if (!walled(b)) return "";
  const mail = b.email
    ? ` Send the letter to <span class="pii">${esc(b.email)}</span> from your own mailbox. That request still counts.`
    : " Copy the letter and send it to the privacy address in the site footer.";
  return `<p class="banner warn"><strong>Their security wall may stop this page.</strong> If you see “Sorry, you have been blocked,” that is the site, not this desk. LeaveMeAlone will not try to get around it.${mail}</p>`;
}

function emailButton(b, primary) {
  if (!b || !b.email || !b.id) return "";
  return `<button type="button" class="${primary ? "" : "ghost"}" data-act="email-letter" data-broker="${esc(b.id)}" data-email="${esc(b.email)}">Email the letter</button>`;
}

function openMail(email, subject, body) {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email || "")) return;
  const link = document.createElement("a");
  link.href = `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

async function emailLetter(brokerId, email) {
  const params = new URLSearchParams({ kind: "deletion", broker_id: brokerId || "" });
  const letter = await api(`/api/profiles/${state.profileId}/letters?${params}`);
  await copyText(`${letter.subject}\n\n${letter.body}`, "Letter copied. Paste it into the mail window, then send it yourself.");
  if (email) {
    openMail(email, letter.subject, "The full deletion request is on my clipboard. Paste it below this line, then send.\n\n");
  }
}

function go(view) {
  const next = `#/${view}`;
  if (location.hash === next) render();
  else location.hash = next;
}

function sightingFor(id) {
  return ((state.desk && state.desk.sightings) || []).find((s) => s.broker_id === id);
}

function sortRemoval(a, b) {
  const heat = (row) => {
    if (row.overdue || row.status === "reappeared") return 0;
    const seen = sightingFor(row.broker_id);
    if (seen && seen.display_status === "exposed") return 1;
    if (seen && seen.display_status === "possible") return 2;
    if (seen && seen.display_status === "blocked") return 3;
    return 4;
  };
  const delta = heat(a) - heat(b);
  if (delta) return delta;
  if ((a.priority || 5) !== (b.priority || 5)) return (a.priority || 5) - (b.priority || 5);
  return (a.broker_name || "").localeCompare(b.broker_name || "");
}

function filteredRemovals() {
  const filter = state.pullFilter;
  return (state.desk ? state.desk.removals : []).filter((row) => {
    if (filter === "open") return row.status === "queued" || row.status === "reappeared";
    if (filter === "sent") return row.status === "submitted";
    if (filter === "overdue") return row.overdue;
    if (filter === "people") return row.category === "people-search" && !["confirmed", "skipped"].includes(row.status);
    if (filter === "priority") return row.priority === 1 && !["confirmed", "skipped"].includes(row.status);
    return row.status !== "skipped";
  }).sort(sortRemoval);
}

function currentCase() {
  const list = filteredRemovals();
  if (!list.length) return null;
  if (state.caseIndex >= list.length) state.caseIndex = 0;
  if (state.caseIndex < 0) state.caseIndex = 0;
  return list[state.caseIndex];
}

function exposureCopy(desk) {
  const counts = desk.counts || {};
  const looked = (desk.history || []).length || counts.exposed || counts.possible || counts.blocked || counts.clear || counts.breach;
  if (!looked) return "No scan yet. A quiet number means we have not looked — not that you are hidden.";
  if (desk.score === 0) return "Nothing corroborated in the last look. Brokers who never publish a search can still have you. Keep pulling.";
  if (desk.score < 16) return "A thin leak. A few possible traces, not a wide-open listing.";
  if (desk.score < 36) return "You are findable. Pull the exposed pages first, then the upstream brokers that feed them.";
  if (desk.score < 61) return "Exposed. Your name is easy to attach to a place or a phone. Start with the pages that rank.";
  return "Wide open. Listings are circulating. Pull upstream brokers, then the people-search pages, and treat any breach as permanent.";
}

function scoreClass(score) {
  if (score <= 0) return "quiet";
  if (score < 16) return "thin";
  return "hot";
}

function ticks(score) {
  const filled = Math.round((score / 100) * 28);
  const klass = scoreClass(score);
  return `<div class="ticks ${klass}">${Array.from({ length: 28 }, (_, i) => `<i class="${i < filled ? "on" : ""}"></i>`).join("")}</div>`;
}

function mark() {
  return `<svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="3" fill="#2a241c"/><path d="M6 16h20" stroke="#e7d7c1" stroke-width="2"/><circle cx="16" cy="16" r="6.5" fill="none" stroke="#e07a68" stroke-width="2"/></svg>`;
}

function shell(inner) {
  const unread = state.desk ? state.desk.unread : 0;
  const items = [
    ["desk", "Desk"],
    ["sightings", "Sightings"],
    ["pull", "Pull"],
    ["watch", "Watch"],
    ["brokers", "Brokers"],
    ["letters", "Letters"],
    ["dossier", "Dossier"],
  ];
  const nav = items.map(([id, label]) => {
    const badge = id === "watch" && unread ? `<span class="count">${unread}</span>` : "";
    return `<a href="#/${id}" class="${state.view === id ? "on" : ""}">${label}${badge}</a>`;
  }).join("");
  const others = state.profiles.filter((p) => p.id !== state.profileId).slice(0, 4);
  return `
    <div class="shell">
      <aside class="rail">
        <a class="mark" href="#/desk">${mark()}<span>Leave me<br>alone</span></a>
        <nav>${nav}</nav>
        <div class="rail-foot">
          <button type="button" class="texty" data-act="redact">${state.redact ? "Show names" : "Blur names"}</button>
          <button type="button" class="texty" data-act="help">Shortcuts</button>
          <button type="button" class="texty" data-act="new">New dossier</button>
          ${profile() ? `<p class="who pii">${esc(profile().label)}</p>` : ""}
          <div class="switch">
            ${others.map((p) => `<button type="button" class="texty" data-act="switch" data-id="${p.id}">${esc(p.label)}</button>`).join("")}
          </div>
        </div>
      </aside>
      <main class="main">${inner}</main>
    </div>
    ${state.help ? helpOverlay() : ""}
    ${state.drawer ? drawer() : ""}`;
}

function helpOverlay() {
  return `<div class="help-back" data-act="close-help"><div class="help" data-stop="1">
    <p class="kicker">Shortcuts</p>
    <h2>While you pull</h2>
    <p>J and K move the case. O opens the opt-out, or your mail if that page is behind a block wall. S logs it as sent. G then D, S, P, W, B, or L jumps sections. ? closes this.</p>
    <p class="muted small">Nothing here emails a broker for you. Copy, then send from your own mailbox.</p>
    <button type="button" class="ghost" data-act="close-help">Close</button>
  </div></div>`;
}

function drawer() {
  const b = state.drawer;
  const method = (b.methods || []).find((m) => m.type === "web_form" && m.url) || (b.methods || [])[0];
  const steps = (method && method.steps) || [];
  return `<div class="drawer-back" data-act="close-drawer"><aside class="drawer" data-stop="1">
    <p class="kicker">${esc(cat(b.category))} · ${esc(b.domain || "")}</p>
    <h2>${esc(b.name)}</h2>
    <p>${esc(b.why || b.notes || "Use the official opt-out. Do not buy a report to see yourself.")}</p>
    <p class="tiny muted">${esc((b.data_types || []).join(" · "))} ${b.relisting ? `· ${esc(RELIST[b.relisting] || "")}` : ""}</p>
    ${b.erasable === "partial" ? `<p class="banner warn">Some of this is a public record. The broker can suppress their copy. A court or county recorder may not.</p>` : ""}
    ${wallNote(b)}
    ${steps.length ? `<ol class="steps">${steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>` : ""}
    <div class="row">
      ${emailButton(b, walled(b) || !b.optout_url)}
      ${b.optout_url ? `<button type="button" class="${walled(b) ? "ghost" : ""}" data-act="open" data-url="${esc(b.optout_url)}">${walled(b) ? "Open opt-out anyway" : "Open opt-out"}</button>` : ""}
      ${b.filled_search_url ? `<button type="button" class="ghost" data-act="open" data-url="${esc(b.filled_search_url)}">Open search</button>` : ""}
      <button type="button" class="ghost" data-act="close-drawer">Close</button>
    </div>
    ${b.email ? `<p class="tiny muted">Privacy email: <span class="pii">${esc(b.email)}</span></p>` : ""}
    ${b.postal ? `<p class="tiny muted">Post: ${esc(b.postal)}</p>` : ""}
    <p class="tiny faint">Steps last noted ${esc(b.last_verified || "in the registry")}. If the page moved, use the privacy link in the footer.</p>
  </aside></div>`;
}

function networkLimited() {
  if (state.lastSummary && state.lastSummary.network === "limited") return true;
  const probes = ((state.desk && state.desk.sightings) || []).filter((s) => s.source === "probe");
  if (probes.length < 5) return false;
  const dead = probes.filter((s) => s.display_status === "unreachable").length;
  return dead / probes.length > 0.7;
}

function banners() {
  const p = profile();
  if (!p) return "";
  let html = "";
  if (p.sample) {
    html += `<div class="banner sample"><strong>Sample dossier.</strong> Avery Quinn is not a real person. The listings, the missed deadline, and the breach are staged. Open your own dossier to scan the live web.</div>`;
  }
  if (networkLimited()) {
    html += `<div class="banner warn"><strong>Live checks were blocked.</strong> This network, or the sites, refused the automated look. Open the search links yourself and record what you see. The letters still work. On your own computer, the same scan can reach the public pages.</div>`;
  }
  return html;
}

function renderWelcome() {
  const stats = (state.meta && state.meta.stats) || {};
  const existing = state.profiles.length
    ? `<div class="row" style="margin-top:18px">${state.profiles.map((p) => `<button type="button" class="ghost" data-act="switch" data-id="${p.id}">Continue ${esc(p.label)}</button>`).join("")}</div>`
    : "";
  const left = state.showForm ? dossierForm(state.draft, false) : `
    <p class="kicker">A local desk · not a subscription</p>
    <h1>Leave me<br><em>alone.</em></h1>
    <p class="lede">People-search sites and data brokers are selling your name, phone, address, and relatives. This desk finds the public copies, walks you through the official opt-outs, writes the deletion letters, and checks back when they put you up again.</p>
    <p class="lede" style="font-size:15px">It does not break into websites, skip human checks, or pretend a court record can be erased. You send every request yourself. The dossier stays in a database on the computer running this app. If someone else can open this page, use the sample — don't type a real name into a shared link.</p>
    <div class="row">
      <button type="button" data-act="toggle-form">Open a dossier</button>
      <button type="button" class="ghost" data-act="sample">Walk the sample</button>
    </div>
    ${existing}
    <p class="tiny faint" style="margin-top:auto;padding-top:48px">${esc(stats.active || "700+")} brokers in the directory · ${esc(stats.scannable || "")} with a public search · you send every letter</p>`;
  $app().innerHTML = `
    <section class="welcome">
      <div class="welcome-main">
        <div class="brand-row"><span class="word">LeaveMeAlone</span><span class="kicker">Private desk</span></div>
        ${left}
      </div>
      <aside class="welcome-side">
        <p class="kicker">What it actually does</p>
        <div class="fact"><strong>01 — Where</strong><p>Checks public people-search pages, a web index, and known breach lists. If a site puts up a human check, it stops and hands you the link.</p></div>
        <div class="fact"><strong>02 — Pull</strong><p>Official opt-out pages, a deletion letter under your state's privacy law, and email batches you send from your own mailbox. California residents get pointed at DROP first.</p></div>
        <div class="fact"><strong>03 — Watch</strong><p>Rechecks the pages that had you. When a cleared listing comes back, you get an alert and a follow-up letter. Leave the app running.</p></div>
        <p class="side-foot">Not legal advice. A broker can ignore you, and a public record at the courthouse is not theirs to delete. The point is a paper trail and a watch, not a magic wipe.</p>
      </aside>
    </section>`;
}

function stateOptions(selected) {
  const states = (state.meta && state.meta.states) || {};
  const options = Object.entries(states).map(([code, name]) => `<option value="${code}" ${code === selected ? "selected" : ""}>${esc(name)}</option>`);
  return `<option value="">—</option>${options.join("")}`;
}

function dossierForm(draft, editing) {
  const d = draft || {};
  return `
    <p class="kicker">${editing ? "Dossier" : "New dossier"}</p>
    <h2>${editing ? esc(fullName(profile() || d)) : "Who are we pulling?"}</h2>
    <p class="muted small">Only what you type here is stored, in a database on this machine. A scan sends your name, and city if you add one, to the sites you ask us to check.</p>
    <form class="form" data-act="save-dossier" style="margin-top:18px">
      <label><span>First</span><input name="first_name" required value="${esc(d.first_name)}"></label>
      <label><span>Last</span><input name="last_name" required value="${esc(d.last_name)}"></label>
      <label><span>Middle</span><input name="middle_name" value="${esc(d.middle_name)}"></label>
      <label><span>Also known as</span><input name="alias" value="${esc([d.alias_first, d.alias_last].filter(Boolean).join(" "))}" placeholder="Optional other name"></label>
      <label><span>Email</span><input name="email" type="email" value="${esc(d.email)}" placeholder="you@domain.com"></label>
      <label><span>Second email</span><input name="email2" type="email" value="${esc(d.email2)}"></label>
      <label><span>Phone</span><input name="phone" value="${esc(d.phone)}" placeholder="Optional"></label>
      <label><span>City</span><input name="city" value="${esc(d.city)}"></label>
      <label><span>State</span><select name="state">${stateOptions(d.state)}</select></label>
      <label><span>ZIP</span><input name="zip" value="${esc(d.zip)}"></label>
      <label class="wide"><span>Street</span><input name="street" value="${esc(d.street)}" placeholder="Optional. Needed for some broker forms."></label>
      <label><span>Residence, for the letter</span><select name="residence_state">${stateOptions(d.residence_state || d.state)}</select></label>
      <label><span>Country</span>
        <select name="country">
          ${["US", "CA", "GB", "EU", "OTHER"].map((c) => `<option ${d.country === c ? "selected" : ""}>${c}</option>`).join("")}
        </select>
      </label>
      <label><span>Date of birth</span><input name="dob" value="${esc(d.dob)}" placeholder="YYYY-MM-DD, optional"></label>
      <label class="check wide"><input type="checkbox" name="include_dob" ${d.include_dob ? "checked" : ""}> Include date of birth in letters. Off by default. Some forms ask for it on their own page.</label>
      <label class="check wide"><input type="checkbox" name="scan_phone" ${d.scan_phone ? "checked" : ""}> Allow phone number in search links. Off by default. We still notice if a page we opened already shows it.</label>
      <label class="check wide"><input type="checkbox" name="authorized" ${editing ? "checked" : ""} required> This is my information, or I am allowed to act for this person.</label>
      <div class="row wide">
        <button type="submit">${editing ? "Save dossier" : "Open the desk"}</button>
        ${editing ? "" : `<button type="button" class="ghost" data-act="toggle-form">Back</button>`}
      </div>
    </form>`;
}

function renderDesk() {
  const desk = state.desk;
  const p = desk.profile;
  const c = desk.counts;
  const hot = (desk.sightings || []).filter((s) => ["exposed", "possible"].includes(s.display_status)).slice(0, 5);
  const next = (desk.removals || []).filter((r) => r.status === "queued" || r.status === "reappeared").sort(sortRemoval).slice(0, 5);
  const klass = scoreClass(desk.score);
  $app().innerHTML = shell(`
    ${banners()}
    <div class="top">
      <div>
        <p class="kicker">Dossier · ${esc(p.residence_state || p.country || "local")} · ${desk.monitor.enabled ? `watching · every ${desk.monitor.interval_hours}h` : "watch off"}</p>
        <h1 class="pii">${esc(fullName(p))}</h1>
      </div>
      <div class="row noprint">
        <button type="button" data-act="scan" data-scope="priority">Scan</button>
        <button type="button" class="ghost" data-act="go" data-to="pull">Pull</button>
      </div>
    </div>
    <div class="score-wrap">
      <div>
        <div class="score-num ${klass}">${desk.score}</div>
      </div>
      <div class="score-copy">
        <strong>${esc(desk.exposure_label)}</strong>
        ${ticks(desk.score)}
        <p>${esc(exposureCopy(desk))}</p>
        <p class="tiny muted">Exposure is what we can see. ${c.submitted + c.confirmed} of ${desk.universe} brokers have a request on file. Sent is not the same as obeyed.</p>
      </div>
    </div>
    <div class="stats">
      <div class="stat"><span class="tiny muted">Public listings</span><b>${c.exposed}</b><span class="tiny">+ ${c.possible} possible</span></div>
      <div class="stat"><span class="tiny muted">Breaches</span><b>${c.breach}</b><span class="tiny">cannot be deleted</span></div>
      <div class="stat"><span class="tiny muted">Came back</span><b>${c.reappeared}</b><span class="tiny">${c.blocked} need a human look</span></div>
      <div class="stat"><span class="tiny muted">Overdue</span><b>${c.overdue}</b><span class="tiny">${c.submitted} waiting on a broker</span></div>
    </div>
    <p class="tiny muted">A broker opt-out suppresses a commercial copy. It does not erase a court file, a deed, or a voter roll. If you are in danger, look up your state's address confidentiality program — this desk cannot hide a government record.</p>
    <div class="split" style="margin-top:28px">
      <section>
        <p class="kicker">Latest sightings</p>
        ${hot.length ? hot.map(sightingRow).join("") : `<p class="muted">Nothing corroborated yet. <button type="button" class="texty" data-act="scan" data-scope="priority">Run a scan</button></p>`}
        <p><a href="#/sightings">All sightings</a></p>
      </section>
      <section>
        <p class="kicker">Pull next</p>
        ${next.length ? next.map((r) => `<div class="item"><div>${stamp(r.status === "reappeared" ? "reappeared" : "queued")}</div><div><div class="name">${esc(r.broker_name)}</div><p class="snippet">${esc(cat(r.category))} · ${esc(RELIST[r.relisting] || "")}</p></div><div></div></div>`).join("") : `<p class="muted">No queue yet. The pull page builds one across the directory.</p>`}
        <p><a href="#/pull">Open the pull desk</a></p>
      </section>
    </div>`);
}

function sightingRow(s) {
  const url = safeUrl(s.url);
  return `<div class="item">
    <div>${stamp(s.source === "breach" ? "breach" : s.display_status)}</div>
    <div>
      <div class="name">${esc(s.broker_name || s.title || "Sighting")}</div>
      <p class="snippet pii">${esc(s.snippet || "")}</p>
      <p class="tiny faint">${esc(s.source)} · ${esc(ago(s.last_seen))}</p>
    </div>
    <div class="actions">
      ${url ? `<button type="button" class="ghost" data-act="open" data-url="${esc(url)}">Open</button>` : ""}
      ${s.broker_id ? `<button type="button" class="ghost" data-act="broker" data-id="${esc(s.broker_id)}">How to pull</button>` : ""}
      ${s.id ? `<button type="button" class="ghost" data-act="sighting" data-id="${s.id}" data-status="clear">Mark clear</button>` : ""}
    </div>
  </div>`;
}

function renderSightings() {
  const desk = state.desk;
  const filter = state.sightFilter || "hot";
  const rows = (desk.sightings || []).filter((s) => {
    if (filter === "hot") return ["exposed", "possible"].includes(s.display_status);
    if (filter === "blocked") return ["blocked", "unreachable", "inconclusive"].includes(s.display_status);
    if (filter === "breach") return s.source === "breach";
    if (filter === "clear") return s.display_status === "clear";
    return true;
  });
  const filters = [
    ["hot", "Exposed"],
    ["blocked", "Check yourself"],
    ["breach", "Breaches"],
    ["clear", "Clear"],
    ["all", "All"],
  ];
  $app().innerHTML = shell(`
    ${banners()}
    <div class="top">
      <div>
        <p class="kicker">Where it is</p>
        <h1>Sightings</h1>
      </div>
      <div class="row noprint">
        <button type="button" data-act="scan" data-scope="priority" ${state.scanning ? "disabled" : ""}>Priority scan</button>
        <button type="button" class="ghost" data-act="scan" data-scope="deep" ${state.scanning ? "disabled" : ""}>Deep scan</button>
      </div>
    </div>
    <p class="muted">Priority checks the pages most likely to rank, plus your email against known breaches. Deep walks every scannable site in the directory. Neither bypasses a human check.</p>
    <div id="scan-stats" class="tiny" style="margin:10px 0">${esc(scanStatsText())}</div>
    <div class="feed" id="feed">${state.feed.map((ev) => feedHtml(ev)).join("")}</div>
    <div class="filters noprint">
      ${filters.map(([id, label]) => `<button type="button" class="texty ${filter === id ? "on" : ""}" data-act="sight-filter" data-filter="${id}">${label}</button>`).join("")}
    </div>
    ${rows.length ? rows.map(sightingRow).join("") : `<p class="muted">Nothing in this pile.</p>`}
    <hr class="rule">
    <div class="split">
      <section>
        <p class="kicker">Record a page you opened</p>
        <p class="small muted">If a site blocked the scan, paste the listing URL. We'll attach it to the broker when the domain matches.</p>
        <form data-act="record-url" class="form" style="margin-top:10px">
          <label class="wide"><span>Listing URL</span><input name="url" placeholder="https://" required></label>
          <label><span>What you saw</span>
            <select name="status"><option value="exposed">It's me</option><option value="possible">Maybe</option><option value="clear">Not me / gone</option></select>
          </label>
          <label><span>Note</span><input name="note" placeholder="Optional"></label>
          <div class="wide"><button type="submit">Save sighting</button></div>
        </form>
      </section>
      <section>
        <p class="kicker">Has a password been seen?</p>
        <p class="small muted">Hashed in this browser. Only the first five characters of the hash are sent, which is how the public range check stays anonymous. We don't store the password.</p>
        <form data-act="password" class="form" style="margin-top:10px">
          <label class="wide"><span>Password</span><input name="password" type="password" autocomplete="off"></label>
          <div class="wide"><button type="submit" class="ghost">Check</button></div>
        </form>
        ${state.passwordResult ? `<p>${esc(state.passwordResult)}</p>` : ""}
      </section>
    </div>`);
}

function scanStatsText() {
  if (!state.scanning && !state.feed.length) return "No scan running.";
  const counts = { exposed: 0, possible: 0, clear: 0, blocked: 0, unreachable: 0 };
  for (const ev of state.feed) {
    const status = ev.payload && ev.payload.status;
    if (counts[status] !== undefined) counts[status] += 1;
  }
  const prefix = state.scanning ? "Looking" : "Last look";
  return `${prefix} · ${counts.exposed} exposed · ${counts.possible} possible · ${counts.blocked} blocked · ${counts.clear} clear · ${counts.unreachable} no answer`;
}

function feedHtml(ev) {
  const p = ev.payload || {};
  const status = p.status || ev.kind;
  const name = p.name || p.email || p.query || ev.kind;
  const detail = p.detail || (p.count !== undefined ? `${p.count} results` : "") || "";
  return `<div class="feed-row"><div>${stamp(status === "done" ? "clear" : status)}</div><div>${esc(name)}</div><div class="pii">${esc(detail)}</div></div>`;
}

function renderPull() {
  const desk = state.desk;
  const p = desk.profile;
  const ca = p.residence_state === "CA";
  const queued = (desk.removals || []).length;
  const modes = [
    ["desk", "Case desk"],
    ["email", "Email net"],
    ["mail", "Postal"],
  ];
  $app().innerHTML = shell(`
    ${banners()}
    <div class="top">
      <div>
        <p class="kicker">Pull · you send it</p>
        <h1>Get it off them</h1>
      </div>
      <div class="row noprint">
        <button type="button" data-act="wipe" data-scope="visible">Queue what we can see</button>
        <button type="button" class="ghost" data-act="wipe" data-scope="all">Queue the directory</button>
      </div>
    </div>
    <p class="muted">A complete wipe is a stack of official requests, not a switch. We open the right page and write the letter. You send it. We never email a broker for you, and we never bypass a human check.</p>
    <div class="lanes">
      <article class="lane">
        <p class="kicker">01</p>
        <h3>${ca ? "DROP" : "No one-shot"}</h3>
        <p class="small">${ca ? "You live in California. One state request reaches every registered broker. Do this first. It does not cover unregistered brokers, and it does not erase a courthouse record." : "There is no national equivalent of California's DROP. The wide net is the letter, then the people-search forms."}</p>
        ${ca ? `<div class="row"><button type="button" class="ghost" data-act="open" data-url="https://privacy.ca.gov/drop/">Open DROP</button>${p.flags && p.flags.drop_submitted ? `<span class="stamp confirmed">Filed</span>` : `<button type="button" class="ghost" data-act="flag" data-key="drop_submitted" data-value="1">I filed it</button>`}</div>` : ""}
      </article>
      <article class="lane">
        <p class="kicker">02</p>
        <h3>Email net</h3>
        <p class="small">Hundreds of brokers publish a privacy address. One letter, in batches of 25, from your mailbox. Mark a batch sent and the deadline starts.</p>
        <button type="button" class="ghost" data-act="pull-mode" data-mode="email">Open batches</button>
      </article>
      <article class="lane">
        <p class="kicker">03</p>
        <h3>Forms that rank</h3>
        <p class="small">${queued ? `${queued} brokers are in the queue.` : "Build a queue, then work the case desk."} People-search forms are the pages someone actually finds.</p>
        <button type="button" class="ghost" data-act="pull-mode" data-mode="desk">Open the desk</button>
      </article>
    </div>
    <div class="modes noprint">
      ${modes.map(([id, label]) => `<button type="button" class="texty ${state.pullMode === id ? "on" : ""}" data-act="pull-mode" data-mode="${id}">${label}</button>`).join("")}
    </div>
    ${state.pullMode === "email" ? emailMode() : state.pullMode === "mail" ? mailMode() : caseMode()}
    <p class="tiny faint" style="margin-top:22px">Coverage is requests on file, not proof a broker obeyed. Confirmed means you looked and the listing was gone. <a href="/api/profiles/${p.id}/packet" target="_blank" rel="noopener">Print the record</a>.</p>`);
}

function caseMode() {
  const filters = [
    ["open", "Not sent"],
    ["priority", "Upstream"],
    ["people", "People search"],
    ["overdue", "Overdue"],
    ["sent", "Sent"],
    ["all", "All"],
  ];
  const list = filteredRemovals();
  const item = currentCase();
  if (!list.length) {
    return `<p class="muted">Nothing in this pile. Queue the directory, or switch filters.</p>
      <div class="filters">${filters.map(filterButton).join("")}</div>`;
  }
  const detail = state.caseDetail && state.caseDetail.id === item.broker_id ? state.caseDetail : null;
  const method = detail && ((detail.methods || []).find((m) => m.type === "web_form" && m.url) || detail.methods[0]);
  const steps = (method && method.steps) || [];
  const cluster = detail && detail.cluster;
  const seen = sightingFor(item.broker_id);
  return `<div class="filters">${filters.map(filterButton).join("")}</div>
    <div class="case">
      <article>
        <p class="case-num">Case ${String(state.caseIndex + 1).padStart(3, "0")} / ${String(list.length).padStart(3, "0")}</p>
        <h2>${esc(item.broker_name)}</h2>
        <p>${stamp(item.overdue ? "overdue" : item.status)} <span class="tiny muted">${esc(cat(item.category))} · ${esc(item.domain || "")} · ${esc(RELIST[item.relisting] || "")}</span></p>
        <p>${esc((detail && detail.why) || item.broker_name + " is in the directory. Use their official request, not a paid account.")}</p>
        ${seen ? `<p class="banner"><strong>On file:</strong> <span class="pii">${esc(seen.snippet || seen.display_status)}</span></p>` : ""}
        ${detail && detail.erasable === "partial" ? `<p class="banner warn">Part of this is a public record. Suppress the broker's copy. Don't expect the county to delete a deed.</p>` : ""}
        ${cluster && cluster.members.length > 1 ? `<p class="banner"><strong>${esc(cluster.name)}.</strong> ${esc(cluster.note)}</p>` : ""}
        ${wallNote(detail || item)}
        ${steps.length ? `<ol class="steps">${steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>` : `<p class="muted small">Open the opt-out, search your name, submit the listing that is you, confirm any email they send.</p>`}
        <label><span class="tiny muted">Listing URL, if you copied one</span><input id="listing-url" value="${esc(item.listing_url || (seen && seen.url) || "")}"></label>
        <div class="row" style="margin-top:14px">
          ${emailButton(detail || item, walled(detail || item) || !item.optout_url)}
          ${detail && detail.filled_search_url ? `<button type="button" class="ghost" data-act="open" data-url="${esc(detail.filled_search_url)}">Open search</button>` : ""}
          ${item.optout_url ? `<button type="button" class="${walled(detail || item) ? "ghost" : ""}" data-act="open" data-url="${esc(item.optout_url)}">${walled(detail || item) ? "Open opt-out anyway" : "Open opt-out"}</button>` : ""}
          <button type="button" class="ghost" data-act="copy-details">Copy my details</button>
          <button type="button" class="ghost" data-act="copy-letter" data-broker="${esc(item.broker_id)}" data-kind="deletion">Copy letter</button>
        </div>
        <div class="row" style="margin-top:10px">
          <button type="button" data-act="mark" data-id="${item.id}" data-status="submitted" data-method="${walled(detail || item) ? "email" : "web_form"}">I sent this</button>
          <button type="button" class="ghost" data-act="mark" data-id="${item.id}" data-status="confirmed">It's gone</button>
          <button type="button" class="ghost" data-act="mark" data-id="${item.id}" data-status="skipped">Skip</button>
          ${item.overdue ? `<button type="button" class="ghost" data-act="copy-letter" data-broker="${esc(item.broker_id)}" data-kind="followup">Copy follow-up</button>` : ""}
          ${cluster && cluster.members.length > 1 ? `<button type="button" class="ghost" data-act="cluster" data-ids="${esc(cluster.members.map((m) => m.id).join(","))}">Mark the network sent</button>` : ""}
        </div>
        ${item.deadline_at ? `<p class="tiny muted">Deadline ${esc(item.deadline_at)} · ${esc(daysLabel(item.deadline_at))}</p>` : ""}
      </article>
      <aside class="queue">
        ${list.slice(0, 40).map((row, index) => `<button type="button" class="q ${index === state.caseIndex ? "on" : ""}" data-act="case" data-index="${index}"><span class="tiny">${esc(STATUS[row.overdue ? "overdue" : row.status] || row.status)}</span><br>${esc(row.broker_name)}</button>`).join("")}
        ${list.length > 40 ? `<p class="tiny muted">Showing 40 of ${list.length}. Filter to narrow.</p>` : ""}
      </aside>
    </div>`;
}

function filterButton([id, label]) {
  return `<button type="button" class="texty ${state.pullFilter === id ? "on" : ""}" data-act="pull-filter" data-filter="${id}">${label}</button>`;
}

function emailMode() {
  if (!state.batches) return `<p class="muted">Gathering addresses…</p>`;
  const batches = state.batches.batches || [];
  if (!batches.length) return `<p>No open privacy emails. Either the net is already marked sent, or these brokers only offer a form.</p>`;
  return `<p class="small">Subject: <span class="pii">${esc(state.batches.subject)}</span></p>
    <div class="row" style="margin-bottom:12px">
      <button type="button" data-act="copy-letter" data-kind="blanket">Copy the letter</button>
      <a class="btn ghost" href="/api/profiles/${profile().id}/packet" target="_blank" rel="noopener">Print record</a>
    </div>
    ${batches.map((batch) => `<div class="item">
      <div class="tiny">Batch ${batch.index + 1}</div>
      <div>
        <div class="name">${batch.addresses.length} addresses · ${batch.brokers.length} brokers</div>
        <p class="snippet">${esc(batch.brokers.slice(0, 4).map((b) => b.name).join(", "))}${batch.brokers.length > 4 ? "…" : ""}</p>
      </div>
      <div class="actions">
        <button type="button" class="ghost" data-act="copy-batch" data-index="${batch.index}">Copy BCC</button>
        <a class="btn ghost" href="/api/profiles/${profile().id}/drafts.zip?batch=${batch.index}">Drafts</a>
        <button type="button" data-act="batch-sent" data-index="${batch.index}">I sent this</button>
      </div>
    </div>`).join("")}
    <p class="tiny muted">Paste the BCC list into your mail client, paste the letter, and send. Then mark the batch. Some clients choke on a long BCC — the draft zip is the fallback, one unsent message per address.</p>`;
}

function mailMode() {
  if (!state.brokersLoaded) return `<p class="muted">Loading postal brokers…</p>`;
  const rows = state.brokers.filter((b) => b.postal && !b.defunct);
  if (!rows.length) return `<p class="muted">No postal address on file. Use the email net or the case desk.</p>`;
  return `<p class="small muted">A few brokers still want paper. Print the letter, mail it, mark it sent the day it goes in the box.</p>
    ${rows.map((b) => `<div class="item"><div>${stamp("queued")}</div><div><div class="name">${esc(b.name)}</div><p class="snippet">${esc(b.postal)}</p></div><div class="actions"><button type="button" class="ghost" data-act="copy-letter" data-broker="${esc(b.id)}" data-kind="deletion">Copy letter</button></div></div>`).join("")}`;
}

function renderWatch() {
  const desk = state.desk;
  const mon = desk.monitor;
  const history = (desk.history || []).slice();
  history.push({ exposure_score: desk.score, started_at: new Date().toISOString(), scope: "now" });
  const max = Math.max(10, ...history.map((h) => h.exposure_score || 0));
  const alerts = desk.alerts || [];
  const risky = (desk.sightings || []).filter((s) => ["exposed", "possible", "blocked"].includes(s.display_status)).slice(0, 8);
  $app().innerHTML = shell(`
    ${banners()}
    <div class="top">
      <div>
        <p class="kicker">Watch</p>
        <h1>${mon.enabled ? "Watching" : "Not watching"}</h1>
      </div>
      <div class="row noprint">
        <button type="button" data-act="monitor-run">Check now</button>
        <button type="button" class="ghost" data-act="read-alerts">Mark alerts read</button>
      </div>
    </div>
    <p class="muted">Brokers buy new public-record feeds and put you back. A watch rechecks pages that had you, pages that blocked us, and your email. Leave this app running. It cannot watch while the computer is off.</p>
    <form class="row" data-act="monitor" style="margin:16px 0 22px">
      <label><span>Every</span>
        <select name="interval_hours">
          ${[6, 12, 24, 72, 168].map((h) => `<option value="${h}" ${Number(mon.interval_hours) === h ? "selected" : ""}>${h < 24 ? h + " hours" : h / 24 + " days"}</option>`).join("")}
        </select>
      </label>
      <label class="check"><input type="checkbox" name="enabled" ${mon.enabled ? "checked" : ""}> Watch is on</label>
      <button type="submit" class="ghost">Save watch</button>
      <span class="tiny muted">${mon.next_run ? `Next ${esc(ago(mon.next_run).replace(" ago", ""))}` : ""} ${mon.last_run ? `· last ${esc(ago(mon.last_run))}` : ""}</span>
    </form>
    <p class="kicker">Exposure over looks</p>
    <div class="bars">${history.map((h) => `<div class="bar" style="height:${Math.max(4, Math.round(((h.exposure_score || 0) / max) * 110))}px" title="${esc(h.scope)} ${h.exposure_score}"><span>${h.exposure_score ?? ""}</span></div>`).join("")}</div>
    <div class="chart-note"><span>older</span><span>now</span></div>
    <div class="split" style="margin-top:28px">
      <section>
        <p class="kicker">Alerts</p>
        <div class="timeline">
          ${alerts.length ? alerts.map((a) => `<div class="alert"><div>${stamp(a.kind === "watch" ? "queued" : a.kind)}</div><div><div class="name">${esc(a.title)}</div><p class="snippet">${esc(a.body)}</p><p class="tiny faint">${esc(ago(a.created_at))}${a.read ? "" : " · unread"}</p></div></div>`).join("") : `<p class="muted">No alerts yet. A relist, a new breach, or a missed deadline will land here.</p>`}
        </div>
      </section>
      <section>
        <p class="kicker">Most likely to return</p>
        ${risky.length ? risky.map((s) => `<div class="item"><div>${stamp(s.display_status)}</div><div><div class="name">${esc(s.broker_name)}</div><p class="snippet">${esc(ago(s.last_seen))}</p></div><div></div></div>`).join("") : `<p class="muted">Nothing hot.</p>`}
      </section>
    </div>`);
}

function renderBrokers() {
  const q = state.brokerQuery.toLowerCase();
  const rows = state.brokers.filter((b) => {
    if (state.brokerCategory && b.category !== state.brokerCategory) return false;
    if (!q) return true;
    return `${b.name} ${b.domain} ${b.category}`.toLowerCase().includes(q);
  });
  const cats = Object.keys(CATEGORY);
  $app().innerHTML = shell(`
    <div class="top">
      <div>
        <p class="kicker">${state.brokers.length || ""} in the directory</p>
        <h1>Brokers</h1>
      </div>
    </div>
    <div class="search">
      <label style="flex:1"><span>Search</span><input id="broker-q" value="${esc(state.brokerQuery)}" placeholder="Spokeo, Acxiom, a domain"></label>
    </div>
    <div class="filters">
      <button type="button" class="texty ${state.brokerCategory === "" ? "on" : ""}" data-act="cat" data-category="">All</button>
      ${cats.map((c) => `<button type="button" class="texty ${state.brokerCategory === c ? "on" : ""}" data-act="cat" data-category="${c}">${esc(CATEGORY[c])}</button>`).join("")}
    </div>
    <p class="tiny muted">${rows.length} shown${rows.length > 80 ? " · first 80" : ""}</p>
    ${rows.slice(0, 80).map((b) => `<div class="broker-row">
      <div class="tiny">${esc(cat(b.category))}</div>
      <div><div class="name">${esc(b.name)}</div><p class="snippet">${esc(b.domain || "")} ${b.scannable ? "· searchable" : "· no public search"} ${b.email ? "· email" : ""}</p></div>
      <div class="actions"><button type="button" class="ghost" data-act="broker" data-id="${esc(b.id)}">Open</button></div>
    </div>`).join("")}
    <p class="tiny faint" style="margin-top:18px">Contact data adapted from the <a href="https://github.com/puurpl/datapurge">DataPurge</a> registry (MIT). Opt-out pages move. ${esc((state.meta && state.meta.disclaimer) || "")}</p>`);
}

function renderLetters() {
  const options = state.brokers.slice(0, 400).map((b) => `<option value="${esc(b.id)}" ${state.letterBroker === b.id ? "selected" : ""}>${esc(b.name)}</option>`).join("");
  const letter = state.letter;
  $app().innerHTML = shell(`
    <div class="top">
      <div>
        <p class="kicker">Letters · not legal advice</p>
        <h1>The request</h1>
      </div>
      <div class="row">
        <a class="btn ghost" href="/api/profiles/${profile().id}/packet" target="_blank" rel="noopener">Print the record</a>
      </div>
    </div>
    <p class="muted">The letter cites the privacy law of the residence on the dossier, plus a plain request that works even where no statute applies. Read it. Send it yourself.</p>
    <form class="row" data-act="load-letter" style="margin:16px 0">
      <label><span>Type</span>
        <select name="kind">
          ${["deletion", "blanket", "followup", "escalation"].map((k) => `<option value="${k}" ${state.letterKind === k ? "selected" : ""}>${k}</option>`).join("")}
        </select>
      </label>
      <label style="min-width:220px"><span>Broker</span>
        <select name="broker_id"><option value="">Blanket — no named broker</option>${options}</select>
      </label>
      <button type="submit" class="ghost">Write</button>
      ${letter ? `<button type="button" data-act="copy-current-letter">Copy</button>` : ""}
    </form>
    ${letter ? `<p class="tiny muted">Subject: ${esc(letter.subject)} · ${letter.days} days</p><div class="letter pii" id="letter-body">${esc(letter.body)}</div>` : `<p class="muted">Writing…</p>`}
    <p class="tiny faint" style="margin-top:14px">Complaints, if they ignore you: <a href="https://reportfraud.ftc.gov/" target="_blank" rel="noopener">FTC</a>. California: <a href="https://oag.ca.gov/contact/consumer-complaint-against-business-or-company" target="_blank" rel="noopener">Attorney General</a> and <a href="https://cppa.ca.gov/" target="_blank" rel="noopener">CalPrivacy</a>. Elsewhere, your state attorney general's consumer division.</p>`);
}

function renderDossier() {
  const p = profile();
  const draft = state.draft || draftFrom(p);
  $app().innerHTML = shell(`
    ${banners()}
    ${dossierForm(draft, true)}
    <hr class="rule">
    <div class="split">
      <section>
        <p class="kicker">On this machine</p>
        <div class="row">
          <button type="button" class="ghost" data-act="export">Export dossier</button>
          <button type="button" class="ghost" data-act="delete-dossier">Delete dossier</button>
        </div>
        <p class="tiny muted">Export is a JSON file of this dossier, the sightings, and the removal log. Delete removes it from this database. It does not tell brokers anything.</p>
      </section>
      <section>
        <p class="kicker">Have I Been Pwned key</p>
        <p class="small muted">Optional. Breach checks already use a keyless index. A HIBP key adds their catalog. The key stays in the local database. ${state.meta && state.meta.hibp ? "A key is saved." : "No key saved."}</p>
        <form data-act="hibp" class="form">
          <label class="wide"><span>API key</span><input name="api_key" type="password" autocomplete="off" placeholder="Leave blank to clear"></label>
          <div class="wide"><button type="submit" class="ghost">Save key</button></div>
        </form>
      </section>
    </div>`);
}

function draftFrom(p) {
  const address = (p.addresses || [])[0] || {};
  const alias = (p.aliases || [])[0] || {};
  return {
    first_name: p.first_name || "",
    last_name: p.last_name || "",
    middle_name: p.middle_name || "",
    alias_first: alias.first || "",
    alias_last: alias.last || "",
    email: (p.emails || [])[0] || "",
    email2: (p.emails || [])[1] || "",
    phone: (p.phones || [])[0] || "",
    street: address.street || "",
    city: address.city || "",
    state: address.state || "",
    zip: address.zip || "",
    residence_state: p.residence_state || address.state || "",
    country: p.country || "US",
    dob: p.dob || "",
    include_dob: !!p.include_dob,
    scan_phone: !!p.scan_phone,
  };
}

function render() {
  document.body.classList.toggle("redact", state.redact);
  if (!state.meta) {
    $app().innerHTML = `<p class="boot">Opening the desk…</p>`;
    return;
  }
  if (state.view === "welcome" || !state.desk) {
    renderWelcome();
    return;
  }
  const views = {
    desk: renderDesk,
    sightings: renderSightings,
    pull: renderPull,
    watch: renderWatch,
    brokers: renderBrokers,
    letters: renderLetters,
    dossier: renderDossier,
  };
  (views[state.view] || renderDesk)();
  hydrate();
}

async function hydrate() {
  const token = ++state.token;
  if (!state.profileId) return;
  try {
  await hydrateInner(token);
  } catch (err) {
    toast(err.message || "Couldn't load that.");
  }
}

async function hydrateInner(token) {
  if ((state.view === "brokers" || state.view === "letters" || state.view === "pull") && !state.brokersLoaded && !state.brokersLoading) {
    state.brokersLoading = true;
    try {
      const data = await api("/api/brokers");
      state.brokers = data.brokers || [];
      state.brokersLoaded = true;
    } finally {
      state.brokersLoading = false;
    }
    render();
    return;
  }
  if (state.view === "pull" && state.pullMode === "desk") {
    const item = currentCase();
    if (item && (!state.caseDetail || state.caseDetail.id !== item.broker_id)) {
      const detail = await api(`/api/brokers/${item.broker_id}?profile_id=${state.profileId}`);
      if (token !== state.token) return;
      state.caseDetail = detail;
      render();
      return;
    }
  }
  if (state.view === "pull" && state.pullMode === "email" && !state.batches) {
    state.batches = await api(`/api/profiles/${state.profileId}/batches`);
    if (token !== state.token) return;
    render();
    return;
  }
  if (state.view === "letters" && !state.letter) {
    await loadLetter(token);
  }
}

async function loadLetter(token) {
  const params = new URLSearchParams({ kind: state.letterKind, broker_id: state.letterBroker || "" });
  const letter = await api(`/api/profiles/${state.profileId}/letters?${params}`);
  if (token && token !== state.token) return;
  state.letter = letter;
  render();
}

async function adopt(id) {
  localStorage.setItem("lma-profile", String(id));
  state.profileId = id;
  state.profiles = await api("/api/profiles");
  state.desk = await api(`/api/profiles/${id}/desk`);
  state.letter = null;
  state.batches = null;
  state.caseDetail = null;
  state.caseIndex = 0;
  state.draft = draftFrom(state.desk.profile);
}

async function refresh() {
  if (!state.profileId) return;
  state.desk = await api(`/api/profiles/${state.profileId}/desk`);
  state.batches = null;
  render();
}

function formBody(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const alias = (data.alias || "").trim().split(/\s+/);
  const emails = [data.email, data.email2].map((v) => (v || "").trim()).filter(Boolean);
  const phones = data.phone ? [data.phone] : [];
  return {
    first_name: data.first_name,
    last_name: data.last_name,
    middle_name: data.middle_name,
    aliases: alias.filter(Boolean).length ? [{ first: alias[0] || "", last: alias.slice(1).join(" ") }] : [],
    emails,
    phones,
    addresses: [{
      street: data.street || "",
      city: data.city || "",
      state: data.state || "",
      zip: data.zip || "",
      current: true,
    }],
    residence_state: data.residence_state || data.state || "",
    country: data.country || "US",
    dob: data.dob || "",
    include_dob: form.include_dob.checked,
    scan_phone: form.scan_phone.checked,
    authorized: form.authorized.checked,
    label: `${data.first_name || ""} ${data.last_name || ""}`.trim(),
  };
}

async function startScan(scope) {
  if (profile() && profile().sample) {
    toast("The sample dossier doesn't call out. Open your own to scan.");
    return;
  }
  const scan = await api(`/api/profiles/${state.profileId}/scans`, { method: "POST", body: { scope } });
  state.scanning = true;
  state.feed = [];
  state.lastSummary = null;
  go("sightings");
  poll(scan.id);
}

async function poll(id) {
  let after = 0;
  try {
    while (true) {
      const res = await api(`/api/scans/${id}?after=${after}`);
      for (const ev of res.events || []) {
        after = ev.seq;
        state.feed.push(ev);
        if (ev.kind === "done") state.lastSummary = ev.payload;
        const feed = document.getElementById("feed");
        if (feed) feed.insertAdjacentHTML("beforeend", feedHtml(ev));
        const stats = document.getElementById("scan-stats");
        if (stats) stats.textContent = scanStatsText();
      }
      if (res.status !== "running") break;
      await sleep(700);
    }
  } catch (err) {
    toast(err.message);
  }
  state.scanning = false;
  await refresh();
}

async function onClick(event) {
  const btn = event.target.closest("[data-act]");
  if (!btn) return;
  if (btn.dataset.stop) {
    event.stopPropagation();
    return;
  }
  const act = btn.dataset.act;
  if (act === "close-help" || act === "close-drawer") {
    if (act === "close-help") state.help = false;
    if (act === "close-drawer") state.drawer = null;
    render();
    return;
  }
  try {
    if (act === "help") {
      state.help = !state.help;
      render();
    } else if (act === "redact") {
      state.redact = !state.redact;
      document.body.classList.toggle("redact", state.redact);
      btn.textContent = state.redact ? "Show names" : "Blur names";
    } else if (act === "toggle-form") {
      state.showForm = !state.showForm;
      state.draft = state.draft || draftFrom({});
      render();
    } else if (act === "sample") {
      const created = await api("/api/profiles/sample", { method: "POST" });
      await adopt(created.id);
      go("desk");
    } else if (act === "new") {
      state.showForm = true;
      state.draft = draftFrom({});
      state.view = "welcome";
      location.hash = "#/welcome";
      render();
    } else if (act === "switch") {
      await adopt(Number(btn.dataset.id));
      go("desk");
    } else if (act === "go") {
      go(btn.dataset.to);
    } else if (act === "scan") {
      await startScan(btn.dataset.scope || "priority");
    } else if (act === "wipe") {
      await api(`/api/profiles/${state.profileId}/wipe`, { method: "POST", body: { scope: btn.dataset.scope || "all" } });
      state.pullMode = "desk";
      state.pullFilter = "open";
      state.caseIndex = 0;
      state.caseDetail = null;
      await refresh();
      go("pull");
      toast(btn.dataset.scope === "visible" ? "Queued the visible listings and the upstream brokers." : "Queued the directory. Start at the top.");
    } else if (act === "open") {
      openUrl(btn.dataset.url);
    } else if (act === "copy-details") {
      await copyText(detailsText(profile()));
    } else if (act === "email-letter") {
      await emailLetter(btn.dataset.broker || "", btn.dataset.email || "");
    } else if (act === "copy-letter") {
      const params = new URLSearchParams({
        kind: btn.dataset.kind || "deletion",
        broker_id: btn.dataset.broker || "",
      });
      const letter = await api(`/api/profiles/${state.profileId}/letters?${params}`);
      await copyText(`${letter.subject}\n\n${letter.body}`);
    } else if (act === "copy-current-letter" && state.letter) {
      await copyText(`${state.letter.subject}\n\n${state.letter.body}`);
    } else if (act === "mark") {
      const listing = document.getElementById("listing-url");
      await api(`/api/removals/${btn.dataset.id}`, {
        method: "POST",
        body: {
          status: btn.dataset.status,
          method: btn.dataset.method || "web_form",
          listing_url: listing ? listing.value : undefined,
        },
      });
      state.caseDetail = null;
      if (btn.dataset.status === "submitted" && state.pullFilter === "open") state.caseIndex = Math.max(0, state.caseIndex);
      await refresh();
      toast(btn.dataset.status === "submitted" ? "Logged. The deadline is running." : "Updated.");
    } else if (act === "cluster") {
      const ids = (btn.dataset.ids || "").split(",").filter(Boolean);
      await api(`/api/profiles/${state.profileId}/removals/bulk`, {
        method: "POST",
        body: { broker_ids: ids, status: "submitted", method: "web_form" },
      });
      await refresh();
      toast("Network marked sent. One request, many brands.");
    } else if (act === "case") {
      state.caseIndex = Number(btn.dataset.index);
      state.caseDetail = null;
      render();
    } else if (act === "pull-filter") {
      state.pullFilter = btn.dataset.filter;
      state.caseIndex = 0;
      state.caseDetail = null;
      render();
    } else if (act === "pull-mode") {
      state.pullMode = btn.dataset.mode;
      if (state.pullMode !== "email") state.batches = state.batches;
      render();
    } else if (act === "copy-batch") {
      const batch = (state.batches.batches || [])[Number(btn.dataset.index)];
      await copyText(batch.addresses.join(", "));
    } else if (act === "batch-sent") {
      const batch = (state.batches.batches || [])[Number(btn.dataset.index)];
      await api(`/api/profiles/${state.profileId}/removals/bulk`, {
        method: "POST",
        body: { broker_ids: batch.brokers.map((b) => b.id).slice(0, 250), status: "submitted", method: "email" },
      });
      state.batches = null;
      await refresh();
      toast("Batch logged. Keep the sent mail.");
    } else if (act === "sight-filter") {
      state.sightFilter = btn.dataset.filter;
      render();
    } else if (act === "sighting") {
      await api(`/api/sightings/${btn.dataset.id}`, { method: "POST", body: { user_status: btn.dataset.status } });
      await refresh();
    } else if (act === "broker") {
      state.drawer = await api(`/api/brokers/${btn.dataset.id}?profile_id=${state.profileId || ""}`);
      render();
    } else if (act === "flag") {
      const flags = {};
      flags[btn.dataset.key] = btn.dataset.value === "1" ? true : btn.dataset.value;
      if (btn.dataset.key === "drop_submitted") flags.drop_submitted_at = new Date().toISOString();
      await api(`/api/profiles/${state.profileId}/flags`, { method: "POST", body: { flags } });
      await refresh();
      toast("Noted.");
    } else if (act === "monitor-run") {
      await startScan("monitor");
    } else if (act === "read-alerts") {
      await api(`/api/profiles/${state.profileId}/alerts/read`, { method: "POST" });
      await refresh();
    } else if (act === "export") {
      const data = await api(`/api/profiles/${state.profileId}/export`);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "leavemealone-dossier.json";
      link.click();
    } else if (act === "delete-dossier") {
      if (!confirm("Delete this dossier from this machine? Brokers are not told.")) return;
      await api(`/api/profiles/${state.profileId}`, { method: "DELETE" });
      localStorage.removeItem("lma-profile");
      state.profileId = null;
      state.desk = null;
      state.profiles = await api("/api/profiles");
      go("welcome");
    } else if (act === "cat") {
      state.brokerCategory = btn.dataset.category;
      render();
    }
  } catch (err) {
    toast(err.message || "That didn't work.");
  }
}

async function onSubmit(event) {
  const form = event.target.closest("form[data-act]");
  if (!form) return;
  event.preventDefault();
  const act = form.dataset.act;
  try {
    if (act === "save-dossier") {
      const body = formBody(form);
      if (state.view === "dossier" && profile() && profile().sample) {
        toast("The sample is fixed. Open your own dossier to edit.");
        return;
      }
      if (state.view === "dossier" && profile()) {
        await api(`/api/profiles/${state.profileId}`, { method: "PUT", body });
        await refresh();
        toast("Dossier saved.");
      } else {
        const created = await api("/api/profiles", { method: "POST", body });
        await adopt(created.id);
        state.showForm = false;
        go("desk");
        toast("Dossier open. Scan when you are ready — it looks up the name you just typed.");
      }
    } else if (act === "record-url") {
      const data = Object.fromEntries(new FormData(form).entries());
      await api(`/api/profiles/${state.profileId}/sightings`, { method: "POST", body: data });
      form.reset();
      await refresh();
      toast("Sighting saved.");
    } else if (act === "password") {
      const password = new FormData(form).get("password") || "";
      form.reset();
      if (!password) return;
      const digest = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(password));
      const hex = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("").toUpperCase();
      const res = await api("/api/password-range", { method: "POST", body: { prefix: hex.slice(0, 5) } });
      const suffix = hex.slice(5);
      const line = (res.suffixes || "").split("\n").find((row) => row.toUpperCase().startsWith(suffix));
      state.passwordResult = line
        ? `Seen ${line.split(":")[1] || ""} times in published breaches. Change it anywhere you still use it.`
        : "Not in the published range. That is not a promise it was never stolen.";
      render();
    } else if (act === "monitor") {
      const data = new FormData(form);
      await api(`/api/profiles/${state.profileId}/monitor`, {
        method: "PUT",
        body: { enabled: data.get("enabled") === "on", interval_hours: Number(data.get("interval_hours")) },
      });
      await refresh();
      toast("Watch updated.");
    } else if (act === "load-letter") {
      const data = Object.fromEntries(new FormData(form).entries());
      state.letterKind = data.kind || "deletion";
      state.letterBroker = data.broker_id || "";
      state.letter = null;
      render();
    } else if (act === "hibp") {
      const api_key = new FormData(form).get("api_key") || "";
      await api("/api/settings/hibp", { method: "POST", body: { api_key } });
      state.meta = await api("/api/meta");
      form.reset();
      toast("Key saved on this machine.");
      render();
    }
  } catch (err) {
    toast(err.message || "That didn't work.");
  }
}

function onInput(event) {
  if (event.target.id === "broker-q") {
    state.brokerQuery = event.target.value;
    const main = document.querySelector(".main");
    const scroll = main ? main.scrollTop : 0;
    renderBrokers();
    const again = document.getElementById("broker-q");
    if (again) {
      again.focus();
      again.setSelectionRange(again.value.length, again.value.length);
    }
    if (main) main.scrollTop = scroll;
  }
}

function onKey(event) {
  if (event.target.matches("input, textarea, select")) return;
  if (event.key === "?") {
    state.help = !state.help;
    render();
    return;
  }
  if (state.view === "pull" && state.pullMode === "desk") {
    if (event.key === "j" || event.key === "ArrowDown") {
      state.caseIndex += 1;
      state.caseDetail = null;
      render();
    } else if (event.key === "k" || event.key === "ArrowUp") {
      state.caseIndex = Math.max(0, state.caseIndex - 1);
      state.caseDetail = null;
      render();
    } else if (event.key === "o") {
      const item = currentCase();
      if (item && walled(item) && item.email) {
        emailLetter(item.broker_id, item.email).catch((err) => toast(err.message));
      } else if (item && item.optout_url) openUrl(item.optout_url);
    } else if (event.key === "s") {
      const item = currentCase();
      if (item) {
        api(`/api/removals/${item.id}`, { method: "POST", body: { status: "submitted", method: walled(item) ? "email" : "web_form" } })
          .then(refresh)
          .then(() => toast("Logged. The deadline is running."))
          .catch((err) => toast(err.message));
      }
    }
  }
  if (event.key === "g") state.chord = true;
  else if (state.chord) {
    const map = { d: "desk", s: "sightings", p: "pull", w: "watch", b: "brokers", l: "letters" };
    if (map[event.key]) go(map[event.key]);
    state.chord = false;
  }
}

function route() {
  const name = (location.hash.replace(/^#\/?/, "").split("?")[0] || "");
  if (!state.profileId) state.view = "welcome";
  else state.view = name || "desk";
  if (state.view === "dossier" && profile()) state.draft = draftFrom(profile());
  render();
}

async function boot() {
  try {
    state.meta = await api("/api/meta");
    state.profiles = await api("/api/profiles");
    const saved = Number(localStorage.getItem("lma-profile"));
    if (saved && state.profiles.some((p) => p.id === saved)) await adopt(saved);
    window.addEventListener("hashchange", route);
    document.getElementById("app").addEventListener("click", onClick);
    document.getElementById("app").addEventListener("submit", onSubmit);
    document.getElementById("app").addEventListener("input", onInput);
    document.addEventListener("keydown", onKey);
    route();
  } catch (err) {
    $app().innerHTML = `<p class="boot">The desk didn't open.</p><p class="muted">${esc(err.message)}</p>`;
  }
}

boot();
