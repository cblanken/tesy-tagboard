(function () { // Self invoking function to avoid variable clashing
  let root = document.querySelector(".search-container");
  let search_input = root.querySelector("input[type='search']")
  function get_search_results() {
    return root.querySelector(".result-container ul");
  }

  function remove_results() {
    let search_results = get_search_results();
    if (search_results) {
      htmx.remove(search_results)
    }
  }

  htmx.on(search_input, "blur", (e) => {
    // TODO: refactor to handle result selection with arrow keys or TAB
    if (!e.currentTarget.contains(e.relatedTarget)) {
      remove_results();
    }
  });



})();
