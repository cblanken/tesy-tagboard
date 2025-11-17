(function () { // Self invoking function to avoid variable clashing
  let tagAction = (action) => {
    return new CustomEvent("tagAction", {
      bubbles: true,
      detail: { action: action }
    });
  }

  document.querySelectorAll(".tag-form").forEach(form => {
    form.addEventListener("tagAction", e => {
      if (e.detail.action == "search") {
        form.submit();
      }
    });
    form.addEventListener("click", e => {
      e.preventDefault()
    });
  });

  document.querySelectorAll(".tag-form .tag-actions button").forEach(btn => {
    htmx.on(btn, "click", (e) => {
      action = btn.dataset["action"]
      btn.dispatchEvent(tagAction(action));
    });
  });
})();
