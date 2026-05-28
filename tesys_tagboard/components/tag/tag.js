(function () { // Self invoking function to avoid variable clashing

  const setup = (root) => {
    if (root === undefined || root === null) {
      console.warning(`Tags could not be initialized because an undefined root node was provided`);
      return;
    }
    let tagAction = (action, tag_id) => {
      return new CustomEvent("tagAction", {
        bubbles: true,
        detail: { action: action, tag_id: tag_id}
      });
    }

    const tag_containers = root.querySelectorAll(".tag-container");
    if (!tag_containers) {
      console.warning(`No tags found under ${root}`);
      return;
    }
    tag_containers.forEach(tag_container => {
      tag_container.addEventListener("tagAction", e => {
        if (e.detail.action == "remove") {
          tag_container.remove();
        }
      });

      tag_container.querySelectorAll(".tag-actions button").forEach(btn => {
        btn.addEventListener("click", (e) => {
          const action = btn.dataset?.action;
          const arg = btn.dataset?.arg;
          const tag_id = btn.dataset?.tag;
          const alias_id = btn.dataset?.alias;

          switch (action) {
            case "remove":
              let form = htmx.find('form').closest('form');
              form.dispatchEvent(new Event("confirmed-change"));
              break;
            case "search":
              window.location.replace(arg);
              break;
            case "update-tag":
              htmx.ajax("GET", `/tags/tag/update/${tag_id}/`, { target: "#modal_form_wrapper" });
              console.log(`Request to update the tag with id=${tag_id}.`)
              break;
            case "delete-tag":
              htmx.ajax("GET", `/tags/tag/delete/${tag_id}/`, { target: "#modal_form_wrapper" });
              console.log(`Request to delete the tag with id=${tag_id}.`)
              break;
            case "restore-tag":
              htmx.ajax("GET", `/tags/tag/restore/${tag_id}/`, { target: "#modal_form_wrapper" });
              console.log(`Request to restore the deleted tag with id=${tag_id}.`)
              break;
            case "update-alias":
              htmx.ajax("GET", `/tags/alias/update/${alias_id}/`, { target: "#modal_form_wrapper" });
              console.log(`Request to update the tag alias with id=${alias_id}.`)
              break;
            case "delete-alias":
              htmx.ajax("GET", `/tags/alias/delete/${alias_id}/`, { target: "#modal_form_wrapper" });
              console.log(`Request to delete the tag alias with id=${alias_id}.`)
              break;
            default:
              console.error(`The "${action}" action does not match a valid action.`);
          }

          btn.dispatchEvent(tagAction(action, tag_id));
        });
      });
    });
  };

  setup(document);

  // Re-initialize tags when reloaded into a search result container
  document.addEventListener("htmx:after:settle", (e) => {
    if (e.target.querySelector(".tag-container")) {
      setup(e.target)
    }
  });
})();
