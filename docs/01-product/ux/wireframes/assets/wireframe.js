/* ParkSmart AI — wireframe behaviour (vanilla JS, no dependencies).
 *
 * Declarative hooks used by the screens:
 *   body[data-role]                 Role label shown in the top bar.
 *   [data-states="k:Label,..."]     State group. Children [data-state="k"] (space-separated keys allowed)
 *                                   are shown when the group is in that state. A switcher bar is rendered.
 *   ?state=k                        URL param: puts every group that knows key k into that state.
 *   [data-set-state="a>b"]          Click: set nearest group (or data-target="#id") to a, then b after a delay.
 *   form[data-submit-state="a>b"]   Submit: validate, then behave like data-set-state.
 *   [data-open="#id"] / [data-close] Modal open / close.
 *   .tabs [data-tab="#panel"]       Tab switching; panels are [data-tab-panel] siblings.
 *   [data-toast="text"]             Show a toast.
 *   [data-enable-when="#checkbox"]  Button enabled only while the checkbox is checked.
 *   tr[data-href]                   Clickable table row.
 *   [data-confirm-reveal]           Reveals [data-plate-original] values and appends an audit row to #audit-log.
 */
(function () {
  "use strict";

  var NAV = [
    { group: "Tổng quan", items: [["index.html", "Danh mục màn hình"]] },
    { group: "Chung", items: [
      ["register.html", "Đăng ký & đồng ý dữ liệu"],
      ["notifications.html", "Thông báo"],
      ["dispute-report.html", "Báo tranh chấp"]
    ] },
    { group: "Chủ chỗ", items: [
      ["owner-home.html", "Chỗ của tôi"],
      ["owner-share-schedule.html", "Lập lịch chia sẻ"],
      ["owner-early-return.html", "Báo về sớm"]
    ] },
    { group: "Người cần chỗ", items: [
      ["request-parking.html", "Yêu cầu chỗ đỗ"],
      ["agreement.html", "Thỏa thuận điện tử"],
      ["payment.html", "Thanh toán (đã bỏ)"],
      ["renter-booking.html", "Lượt đỗ của tôi"],
      ["swap-proposal.html", "Đề xuất hoán đổi"]
    ] },
    { group: "Shophouse", items: [["shophouse-voucher.html", "Voucher lượt TH3"]] },
    { group: "BQL", items: [
      ["admin-dashboard.html", "Bảng điều khiển"],
      ["admin-approvals.html", "Duyệt giao dịch (HITL)"],
      ["admin-disputes.html", "Ticket tranh chấp"],
      ["admin-dispute-detail.html", "Chi tiết ticket"],
      ["admin-swaps.html", "Duyệt hoán đổi"],
      ["admin-lpr-review.html", "Log LPR & hàng chờ OCR"],
      ["admin-ledger.html", "Bằng chứng xác nhận"]
    ] }
  ];

  var DELAY = 900;

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function currentFile() {
    var f = location.pathname.split("/").pop();
    return f === "" ? "index.html" : f;
  }

  /* ---------- Shell: top bar + side navigation ---------- */
  function renderShell() {
    var role = document.body.getAttribute("data-role") || "";
    var top = document.createElement("header");
    top.className = "topbar";
    top.innerHTML =
      '<button class="menu-btn" type="button" aria-expanded="false" aria-controls="sidenav">Menu</button>' +
      '<a class="brand" href="index.html">ParkSmart AI</a><span class="tag">WIREFRAME</span>' +
      '<span class="spacer"></span>' +
      (role ? '<span class="role">Vai trò: ' + role + "</span>" : "");
    document.body.insertBefore(top, document.body.firstChild);

    var nav = $("#sidenav");
    if (!nav) return;
    var here = currentFile();
    var html = "";
    NAV.forEach(function (g) {
      html += '<div class="group">' + g.group + "</div>";
      g.items.forEach(function (it) {
        var active = it[0] === here ? ' class="active" aria-current="page"' : "";
        html += '<a href="' + it[0] + '"' + active + ">" + it[1] + "</a>";
      });
    });
    nav.innerHTML = html;

    var btn = $(".menu-btn", top);
    btn.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      btn.setAttribute("aria-expanded", String(open));
    });
  }

  /* ---------- State groups ---------- */
  var groups = [];

  function parseStates(spec) {
    return spec.split(",").map(function (s) {
      var p = s.split(":");
      return { key: p[0].trim(), label: (p[1] || p[0]).trim() };
    });
  }

  function setState(group, key) {
    if (!group.states.some(function (s) { return s.key === key; })) return;
    group.current = key;
    $all("[data-state]", group.el).forEach(function (child) {
      if (child.closest("[data-states]") !== group.el) return; // only own children
      var keys = child.getAttribute("data-state").split(/\s+/);
      child.hidden = keys.indexOf(key) === -1;
    });
    $all("button", group.bar).forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-key") === key));
    });
  }

  function runSequence(group, seq) {
    var steps = seq.split(">").map(function (s) { return s.trim(); });
    setState(group, steps[0]);
    steps.slice(1).forEach(function (k, i) {
      setTimeout(function () { setState(group, k); }, DELAY * (i + 1));
    });
  }

  function initStates() {
    $all("[data-states]").forEach(function (el) {
      var g = { el: el, states: parseStates(el.getAttribute("data-states")), current: null };
      var bar = document.createElement("div");
      bar.className = "statebar";
      bar.setAttribute("role", "group");
      bar.setAttribute("aria-label", "Trạng thái UI (chỉ dùng cho wireframe)");
      bar.innerHTML = '<span class="label">' + (el.getAttribute("data-states-label") || "Trạng thái UI") + ":</span>" +
        g.states.map(function (s) {
          return '<button type="button" data-key="' + s.key + '" aria-pressed="false">' + s.label + "</button>";
        }).join("");
      el.parentNode.insertBefore(bar, el);
      g.bar = bar;
      bar.addEventListener("click", function (e) {
        var b = e.target.closest("button[data-key]");
        if (b) setState(g, b.getAttribute("data-key"));
      });
      el._group = g;
      groups.push(g);
      setState(g, g.states[0].key);
    });

    var wanted = new URLSearchParams(location.search).get("state");
    if (wanted) groups.forEach(function (g) { setState(g, wanted); });
  }

  function groupFor(el) {
    var target = el.getAttribute("data-target");
    var host = target ? $(target) : el.closest("[data-states]");
    return host && host._group;
  }

  /* ---------- Modals ---------- */
  function openModal(sel) {
    var m = $(sel);
    if (!m) return;
    m.classList.add("open");
    var f = $("button, input, select, textarea", m);
    if (f) f.focus();
  }
  function closeModal(m) { if (m) m.classList.remove("open"); }

  /* ---------- Toast ---------- */
  function toast(text) {
    var t = document.createElement("div");
    t.className = "toast";
    t.setAttribute("role", "status");
    t.textContent = text;
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 2400);
  }

  /* ---------- Plate reveal (audited) ---------- */
  function revealPlates() {
    $all("[data-plate-original]").forEach(function (el) {
      el.textContent = el.getAttribute("data-plate-original");
    });
    var log = $("#audit-log");
    if (log) {
      var tr = document.createElement("tr");
      var now = new Date();
      var hh = String(now.getHours()).padStart(2, "0") + ":" + String(now.getMinutes()).padStart(2, "0");
      tr.innerHTML = "<td>" + hh + "</td><td>BQL · [tài khoản]</td><td>Xem biển số gốc</td><td>[lý do đã nhập]</td>";
      log.insertBefore(tr, log.firstChild);
      var empty = $("#audit-empty");
      if (empty) empty.hidden = true;
    }
    toast("Đã hiển thị biển số gốc — lượt xem đã được ghi log");
  }

  /* ---------- Event delegation ---------- */
  function bindEvents() {
    document.addEventListener("click", function (e) {
      var t = e.target;

      var setBtn = t.closest("[data-set-state]");
      if (setBtn) {
        var g = groupFor(setBtn);
        if (g) { e.preventDefault(); runSequence(g, setBtn.getAttribute("data-set-state")); }
      }

      var opener = t.closest("[data-open]");
      if (opener) { e.preventDefault(); openModal(opener.getAttribute("data-open")); }

      if (t.closest("[data-close]")) closeModal(t.closest(".modal-backdrop"));
      if (t.classList.contains("modal-backdrop")) closeModal(t);

      if (t.closest("[data-confirm-reveal]")) {
        var reason = $("#reveal-reason");
        if (reason && !reason.value.trim()) { reason.reportValidity(); return; }
        closeModal(t.closest(".modal-backdrop"));
        revealPlates();
      }

      var toaster = t.closest("[data-toast]");
      if (toaster) toast(toaster.getAttribute("data-toast"));

      var tab = t.closest(".tabs [data-tab]");
      if (tab) {
        var tabs = tab.closest(".tabs");
        $all("[data-tab]", tabs).forEach(function (b) {
          var on = b === tab;
          b.setAttribute("aria-selected", String(on));
          var p = $(b.getAttribute("data-tab"));
          if (p) p.hidden = !on;
        });
      }

      var row = t.closest("tr[data-href]");
      if (row && !t.closest("a, button")) location.href = row.getAttribute("data-href");
    });

    document.addEventListener("submit", function (e) {
      var form = e.target;
      var seq = form.getAttribute("data-submit-state");
      if (!seq) return;
      e.preventDefault();
      if (!form.reportValidity()) return;
      var g = groupFor(form);
      if (g) runSequence(g, seq);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") $all(".modal-backdrop.open").forEach(closeModal);
    });

    $all("[data-enable-when]").forEach(function (btn) {
      var box = $(btn.getAttribute("data-enable-when"));
      if (!box) return;
      var sync = function () { btn.disabled = !box.checked; };
      box.addEventListener("change", sync);
      sync();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderShell();
    initStates();
    bindEvents();
  });
})();
