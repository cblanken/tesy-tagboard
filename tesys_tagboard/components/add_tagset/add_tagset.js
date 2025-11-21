(function () { // Self invoking function to avoid variable clashing
  const root = document.querySelector(".add-tagset-container");
  const search_input = root.querySelector("input[type='search']")

  const get_search_results = () => {
    return root.querySelector(".result-container ul");
  }


  const add_tag_to_set_handler = (e) => {
    let autocomplete_item = e.currentTarget;
    const tagset = htmx.find(".tagset");
    const tag_id = autocomplete_item.dataset['id'];
    const tag_name = autocomplete_item.dataset['name'];
    const tag_div = document.createElement("div");
    tag_div.classList.add("rounded-md", "bg-secondary", "text-secondary-content", "h-8", "px-2", "py-1");
    tag_div.textContent = tag_name;

    let tag_input = document.createElement("input");
    tag_input.setAttribute("id", `tag-${tag_id}`);
    tag_input.setAttribute("type", "hidden");
    tag_input.setAttribute("name", "tagset");
    tag_input.setAttribute("value", tag_id);

    tag_div.appendChild(tag_input);
    tagset.appendChild(tag_div);
  }

  htmx.on(root.querySelector(".result-container"), "htmx:afterSettle", (e) => {
    let search_results = get_search_results();
    if (search_results) {
      Array.from(search_results.children).forEach(autocomplete_item => {
        htmx.on(autocomplete_item, "mousedown", add_tag_to_set_handler);
        htmx.on(autocomplete_item, "keydown", (e) => {
          switch (e.code) {
            case "Enter":
              // e.preventDefault();
              add_tag_to_set_handler(e);
              break;
            case "Escape":
              e.preventDefault();
              search_input.focus();
            case "ArrowLeft":
              e.preventDefault();
              search_input.focus();
            case "ArrowRight":
              e.preventDefault();
              search_input.focus();
            default:
              // Do nothing
          }
        });
      });
    }
  });
})();
