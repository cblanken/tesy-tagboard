function show_thumbnail(container, img) {
  img.classList.add(`animate-pop-in-fast`);
  img.classList.add(`motion-reduce:animate-fade-in-fast`);
  img.classList.remove(`invisible`);
  container.classList.remove("skeleton")
}

document.querySelectorAll(`.post-thumbnail`).forEach((thumbnail) => {
  let img = thumbnail.querySelector(`img`);

  if (img.complete) {
    show_thumbnail(thumbnail, img);
  } else {
    img.onload = function() {
      show_thumbnail(thumbnail, img);
    }
  }

});
