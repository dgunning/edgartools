// Wrap parenthetical form codes in nav links with a dim <span>
// e.g. "Fund Portfolios (N-PORT)" → "Fund Portfolios <span>(N-PORT)</span>"
// Uses Material for MkDocs' document$ observable for correct timing
function dimFormCodes() {
  document.querySelectorAll(".md-sidebar .md-nav__link").forEach(function (link) {
    if (link.querySelector(".nav-form-code")) return; // already processed
    var nodes = link.childNodes;
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].nodeType === Node.TEXT_NODE) {
        var val = nodes[i].textContent;
        var match = val.match(/^(.+?)(\s*\([^)]+\))$/);
        if (match) {
          var name = document.createTextNode(match[1]);
          var code = document.createElement("span");
          code.className = "nav-form-code";
          code.textContent = match[2];
          var parent = nodes[i].parentNode;
          parent.insertBefore(name, nodes[i]);
          parent.insertBefore(code, nodes[i]);
          parent.removeChild(nodes[i]);
          break;
        }
      }
    }
  });
}

// Material for MkDocs emits document$ on each page load (including instant navigation)
if (typeof document$ !== "undefined") {
  document$.subscribe(function () { dimFormCodes(); });
} else {
  document.addEventListener("DOMContentLoaded", dimFormCodes);
}
