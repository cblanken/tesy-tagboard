/* Project specific Javascript goes here. */
document.querySelectorAll("button.btn").forEach(btn => {
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
  });
});
